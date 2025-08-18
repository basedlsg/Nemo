"""Research orchestrator API service."""
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from services.orchestrator.research_orchestrator import (
    ResearchOrchestrator,
    DiscoveryJobRequest,
    VerificationJobRequest,
    IngestionJobRequest,
    JobType,
    JobStatus,
    JobPriority,
    get_research_orchestrator
)

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Research Orchestrator Service",
    description="Orchestrate discovery → verification → ingestion research pipeline",
    version="1.0.0"
)


@app.post("/jobs/discovery")
async def submit_discovery_job(request: DiscoveryJobRequest):
    """Submit discovery job."""
    try:
        orchestrator = await get_research_orchestrator()
        job_id = await orchestrator.submit_discovery_job(request)
        
        return {
            "job_id": job_id,
            "job_type": "discovery",
            "status": "pending",
            "message": "Discovery job submitted successfully",
            "submitted_at": datetime.utcnow().isoformat()
        }
        
    except ValidationError as e:
        logger.error(f"Validation error in discovery job: {e}")
        raise HTTPException(
            status_code=422,
            detail={
                "error": "Validation failed",
                "details": e.errors()
            }
        )
    except Exception as e:
        logger.error(f"Failed to submit discovery job: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Discovery job submission failed: {str(e)}"
        )


@app.post("/jobs/verification")
async def submit_verification_job(request: VerificationJobRequest):
    """Submit verification job."""
    try:
        orchestrator = await get_research_orchestrator()
        job_id = await orchestrator.submit_verification_job(request)
        
        return {
            "job_id": job_id,
            "job_type": "verification",
            "status": "pending",
            "message": "Verification job submitted successfully",
            "submitted_at": datetime.utcnow().isoformat()
        }
        
    except ValidationError as e:
        logger.error(f"Validation error in verification job: {e}")
        raise HTTPException(
            status_code=422,
            detail={
                "error": "Validation failed",
                "details": e.errors()
            }
        )
    except Exception as e:
        logger.error(f"Failed to submit verification job: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Verification job submission failed: {str(e)}"
        )


@app.post("/jobs/ingestion")
async def submit_ingestion_job(request: IngestionJobRequest):
    """Submit ingestion job."""
    try:
        orchestrator = await get_research_orchestrator()
        job_id = await orchestrator.submit_ingestion_job(request)
        
        return {
            "job_id": job_id,
            "job_type": "ingestion",
            "status": "pending",
            "message": "Ingestion job submitted successfully",
            "submitted_at": datetime.utcnow().isoformat()
        }
        
    except ValidationError as e:
        logger.error(f"Validation error in ingestion job: {e}")
        raise HTTPException(
            status_code=422,
            detail={
                "error": "Validation failed",
                "details": e.errors()
            }
        )
    except Exception as e:
        logger.error(f"Failed to submit ingestion job: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Ingestion job submission failed: {str(e)}"
        )


@app.post("/jobs/pipeline")
async def submit_full_pipeline_job(request: DiscoveryJobRequest):
    """Submit full pipeline job (discovery → verification → ingestion)."""
    try:
        orchestrator = await get_research_orchestrator()
        job_id = await orchestrator.submit_full_pipeline_job(request)
        
        return {
            "job_id": job_id,
            "job_type": "full_pipeline",
            "status": "pending",
            "message": "Full pipeline job submitted successfully",
            "submitted_at": datetime.utcnow().isoformat(),
            "pipeline_stages": ["discovery", "verification", "ingestion"]
        }
        
    except ValidationError as e:
        logger.error(f"Validation error in pipeline job: {e}")
        raise HTTPException(
            status_code=422,
            detail={
                "error": "Validation failed",
                "details": e.errors()
            }
        )
    except Exception as e:
        logger.error(f"Failed to submit pipeline job: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Pipeline job submission failed: {str(e)}"
        )


@app.get("/jobs/{job_id}")
async def get_job_status(job_id: str):
    """Get job status and results."""
    try:
        orchestrator = await get_research_orchestrator()
        job_result = await orchestrator.get_job_status(job_id)
        
        if not job_result:
            raise HTTPException(
                status_code=404,
                detail=f"Job not found: {job_id}"
            )
        
        return {
            "job": job_result.__dict__,
            "retrieved_at": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get job status: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Job status retrieval failed: {str(e)}"
        )


@app.delete("/jobs/{job_id}")
async def cancel_job(job_id: str):
    """Cancel a pending or running job."""
    try:
        orchestrator = await get_research_orchestrator()
        success = await orchestrator.cancel_job(job_id)
        
        if not success:
            raise HTTPException(
                status_code=400,
                detail=f"Job cannot be cancelled: {job_id} (may not exist or already completed)"
            )
        
        return {
            "job_id": job_id,
            "status": "cancelled",
            "message": "Job cancelled successfully",
            "cancelled_at": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to cancel job: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Job cancellation failed: {str(e)}"
        )


@app.get("/stats")
async def get_orchestrator_stats():
    """Get orchestrator statistics."""
    try:
        orchestrator = await get_research_orchestrator()
        stats = await orchestrator.get_orchestrator_stats()
        return stats
        
    except Exception as e:
        logger.error(f"Failed to get orchestrator stats: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Stats retrieval failed: {str(e)}"
        )


@app.get("/enums")
async def get_enums():
    """Get available enum values."""
    try:
        return {
            "job_types": {
                "discovery": {"value": "discovery", "label": "Discovery", "label_zh": "发现"},
                "verification": {"value": "verification", "label": "Verification", "label_zh": "验证"},
                "ingestion": {"value": "ingestion", "label": "Ingestion", "label_zh": "摄取"},
                "full_pipeline": {"value": "full_pipeline", "label": "Full Pipeline", "label_zh": "完整流水线"}
            },
            "job_statuses": {
                "pending": {"value": "pending", "label": "Pending", "label_zh": "等待中"},
                "running": {"value": "running", "label": "Running", "label_zh": "运行中"},
                "completed": {"value": "completed", "label": "Completed", "label_zh": "已完成"},
                "failed": {"value": "failed", "label": "Failed", "label_zh": "失败"},
                "cancelled": {"value": "cancelled", "label": "Cancelled", "label_zh": "已取消"},
                "retrying": {"value": "retrying", "label": "Retrying", "label_zh": "重试中"}
            },
            "job_priorities": {
                "low": {"value": "low", "label": "Low", "label_zh": "低"},
                "medium": {"value": "medium", "label": "Medium", "label_zh": "中"},
                "high": {"value": "high", "label": "High", "label_zh": "高"},
                "critical": {"value": "critical", "label": "Critical", "label_zh": "紧急"}
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to get enums: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Enum retrieval failed: {str(e)}"
        )


@app.post("/test/pipeline")
async def test_pipeline(
    province: str = "guangdong",
    asset_type: str = "solar",
    doc_class: str = "grid_connection",
    priority: str = "medium"
):
    """Test the full pipeline with sample data."""
    try:
        # Validate priority
        try:
            job_priority = JobPriority(priority)
        except ValueError:
            job_priority = JobPriority.MEDIUM
        
        # Create test request
        test_request = DiscoveryJobRequest(
            province=province,
            asset_type=asset_type,
            doc_class=doc_class,
            keywords=f"{asset_type} {doc_class}",
            priority=job_priority,
            max_results=5
        )
        
        # Submit pipeline job
        orchestrator = await get_research_orchestrator()
        job_id = await orchestrator.submit_full_pipeline_job(test_request)
        
        return {
            "test_job_id": job_id,
            "test_parameters": {
                "province": province,
                "asset_type": asset_type,
                "doc_class": doc_class,
                "priority": priority
            },
            "message": "Test pipeline job submitted successfully",
            "note": "This is a test job with mock data for demonstration purposes",
            "submitted_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to submit test pipeline: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Test pipeline submission failed: {str(e)}"
        )


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    try:
        orchestrator = await get_research_orchestrator()
        stats = await orchestrator.get_orchestrator_stats()
        
        return {
            "status": "healthy",
            "service": "research_orchestrator",
            "version": "1.0.0",
            "timestamp": datetime.utcnow().isoformat(),
            "stats_summary": {
                "total_jobs": stats.get("total_jobs", 0),
                "pending_jobs": stats.get("pending_jobs", 0),
                "running_jobs": stats.get("running_jobs", 0),
                "queue_length": stats.get("queue_length", 0),
                "active_tasks": stats.get("active_tasks", 0)
            }
        }
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
        )


@app.on_event("startup")
async def startup_event():
    """Initialize service on startup."""
    logger.info("Research Orchestrator Service starting up...")
    
    try:
        # Initialize orchestrator
        orchestrator = await get_research_orchestrator()
        logger.info("Research orchestrator initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize research orchestrator: {e}")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    logger.info("Research Orchestrator Service shutting down...")
    
    try:
        # Cleanup orchestrator
        orchestrator = await get_research_orchestrator()
        await orchestrator.cleanup()
        logger.info("Research orchestrator cleaned up successfully")
        
    except Exception as e:
        logger.error(f"Failed to cleanup research orchestrator: {e}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)