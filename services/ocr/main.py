"""FastAPI application for OCR service."""

import logging
import os
from typing import Dict, Any, List, Optional

from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from .schemas import OcrJob, OcrResult, OcrConfig
from .worker import OcrWorker, create_ocr_job_from_message
from .metrics import OcrMetricsCollector, StructuredLogger
from .docai_client import DocAIClient
from .storage import GCSStorageClient
from services.database.crud import CitationCRUD
from services.database.connection import get_database_connection

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="OCR Service",
    description="Chinese document OCR and text extraction service",
    version="1.0.0"
)

# Global components
config = OcrConfig()
metrics_collector = OcrMetricsCollector()
structured_logger = StructuredLogger("ocr")

# Initialize worker (will be done on startup)
worker: Optional[OcrWorker] = None


class OcrTrigger(BaseModel):
    """API request model for triggering OCR processing."""
    gcs_uri: str
    province: str
    doc_class: str
    source_url: str
    checksum: str
    title: Optional[str] = None
    source_domain: Optional[str] = None
    trace_id: Optional[str] = None


class BatchOcrTrigger(BaseModel):
    """API request model for batch OCR processing."""
    jobs: List[OcrTrigger]


@app.on_event("startup")
async def startup_event():
    """Initialize service components on startup."""
    global worker
    
    try:
        logger.info("Starting OCR service...")
        
        # Initialize Document AI client
        docai_client = DocAIClient(config)
        
        # Initialize storage client
        storage_client = GCSStorageClient(config.project_id)
        
        # Initialize database connection
        try:
            db_connection = get_database_connection()
            citation_crud = CitationCRUD(db_connection)
        except Exception as e:
            logger.warning(f"Database connection failed, running without DB: {e}")
            citation_crud = None
        
        # Initialize worker
        worker = OcrWorker(
            docai_client=docai_client,
            storage_client=storage_client,
            citation_crud=citation_crud,
            metrics_collector=metrics_collector
        )
        
        logger.info("OCR service started successfully")
        
    except Exception as e:
        logger.error(f"Failed to start OCR service: {e}")
        raise


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on service shutdown."""
    logger.info("Shutting down OCR service...")


@app.get("/health")
async def health_check() -> Dict[str, Any]:
    """Health check endpoint."""
    if not worker:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    return worker.health_check()


@app.get("/metrics")
async def get_metrics() -> Dict[str, Any]:
    """Get service metrics."""
    if not worker:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    return worker.get_metrics()


@app.get("/metrics/prometheus", response_class=PlainTextResponse)
async def get_prometheus_metrics() -> str:
    """Get metrics in Prometheus format."""
    return metrics_collector.export_prometheus_metrics()


@app.get("/metrics/slo")
async def get_slo_metrics() -> Dict[str, Any]:
    """Get SLO-specific metrics."""
    return metrics_collector.get_slo_metrics()


@app.post("/api/v1/ocr")
async def process_document(
    request: OcrTrigger,
    background_tasks: BackgroundTasks
) -> Dict[str, Any]:
    """
    Process a single document with OCR.
    
    Can be run synchronously or asynchronously based on configuration.
    """
    if not worker:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    try:
        # Create OCR job
        job = OcrJob(
            gcs_uri=request.gcs_uri,
            province=request.province,
            doc_class=request.doc_class,
            source_url=request.source_url,
            checksum=request.checksum,
            title=request.title,
            source_domain=request.source_domain,
            trace_id=request.trace_id
        )
        
        # Log job start
        structured_logger.log_job_start(
            str(job.job_id),
            job.gcs_uri,
            job.province,
            job.doc_class
        )
        
        # Process synchronously for now (can be made async with background tasks)
        result = worker.process_job(job)
        
        # Log completion
        structured_logger.log_job_complete(
            str(job.job_id),
            result.status.value,
            result.processing_time_ms or 0,
            str(result.citation_id) if result.citation_id else None,
            result.error_message
        )
        
        # Return result
        return {
            "job_id": str(result.job_id),
            "status": result.status.value,
            "citation_id": str(result.citation_id) if result.citation_id else None,
            "processing_time_ms": result.processing_time_ms,
            "pages_processed": result.pages_processed,
            "tables_extracted": result.tables_extracted,
            "effective_date_found": result.effective_date_found,
            "error_message": result.error_message
        }
        
    except Exception as e:
        logger.error(f"Error processing OCR request: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/ocr/batch")
async def process_documents_batch(
    request: BatchOcrTrigger,
    background_tasks: BackgroundTasks
) -> Dict[str, Any]:
    """Process multiple documents in batch."""
    if not worker:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    try:
        # Create OCR jobs
        jobs = []
        for trigger in request.jobs:
            job = OcrJob(
                gcs_uri=trigger.gcs_uri,
                province=trigger.province,
                doc_class=trigger.doc_class,
                source_url=trigger.source_url,
                checksum=trigger.checksum,
                title=trigger.title,
                source_domain=trigger.source_domain,
                trace_id=trigger.trace_id
            )
            jobs.append(job)
        
        # Process batch
        results = worker.process_batch(jobs)
        
        # Summarize results
        successful = sum(1 for r in results if r.is_success())
        failed = len(results) - successful
        
        return {
            "batch_size": len(results),
            "successful": successful,
            "failed": failed,
            "results": [
                {
                    "job_id": str(r.job_id),
                    "status": r.status.value,
                    "citation_id": str(r.citation_id) if r.citation_id else None,
                    "error_message": r.error_message
                }
                for r in results
            ]
        }
        
    except Exception as e:
        logger.error(f"Error processing batch OCR request: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/ocr/pubsub")
async def process_pubsub_message(message_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process OCR job from Pub/Sub message.
    
    Expected message format:
    {
        "gcs_uri": "gs://bucket/path",
        "province": "guangdong",
        "doc_class": "grid_connection",
        "source_url": "https://...",
        "checksum": "abc123...",
        "title": "Document Title",
        "source_domain": "example.com",
        "trace_id": "trace-123"
    }
    """
    if not worker:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    try:
        # Create job from message
        job = create_ocr_job_from_message(message_data)
        
        # Process job
        result = worker.process_job(job)
        
        return {
            "job_id": str(result.job_id),
            "status": result.status.value,
            "processed": result.is_success()
        }
        
    except Exception as e:
        logger.error(f"Error processing Pub/Sub message: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/config")
async def get_config() -> Dict[str, Any]:
    """Get service configuration (non-sensitive parts)."""
    return {
        "processor_location": config.processor_location,
        "max_pages_per_job": config.max_pages_per_job,
        "timeout_seconds": config.timeout_seconds,
        "max_tokens_per_chunk": config.max_tokens_per_chunk,
        "chunk_overlap_tokens": config.chunk_overlap_tokens,
        "min_confidence_threshold": config.min_confidence_threshold,
        "effective_date_hit_rate_target": config.effective_date_hit_rate_target
    }


@app.post("/api/v1/test")
async def test_processing() -> Dict[str, Any]:
    """Test endpoint with mock data."""
    if not worker:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    # Create test job
    test_job = OcrJob(
        gcs_uri="gs://test-bucket/test-document.pdf",
        province="guangdong",
        doc_class="grid_connection",
        source_url="https://example.com/test-doc",
        checksum="a" * 64,  # Valid SHA256 format
        title="测试文档",
        source_domain="example.com",
        trace_id="test-trace-123"
    )
    
    # Use mock worker for testing
    from .worker import OcrWorker
    test_worker = OcrWorker(use_mock=True)
    
    result = test_worker.process_job(test_job)
    
    return {
        "test_result": "success",
        "job_id": str(result.job_id),
        "status": result.status.value,
        "processing_time_ms": result.processing_time_ms,
        "citation_created": result.citation_id is not None
    }


if __name__ == "__main__":
    import uvicorn
    
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)