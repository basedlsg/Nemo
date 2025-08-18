"""OCR worker for processing document snapshots into citations."""

import logging
import time
from datetime import datetime
from typing import Dict, Any, Optional, List
from uuid import uuid4

from .schemas import OcrJob, OcrResult, OcrStatus, NormalizedContent, CitationRow, ChunkData
from .docai_client import DocAIClient, DocAIClientMock
from .normalize import doc_to_normalized_content, extract_document_metadata
from .effective_date import extract_effective_date, validate_effective_date
from .chunker import chunk_document_content, analyze_chunking_quality
from .storage import GCSStorageClient, GCSStorageClientMock, generate_parsed_path, generate_normalized_path
from .metrics import OcrMetricsCollector
from services.database.crud import CitationCRUD
from services.ontology.integration import OntologyIntegrationService, create_enriched_citation_from_chunks
from services.ontology.schemas import Jurisdiction
from services.embeddings.service import EmbeddingService

logger = logging.getLogger(__name__)


class OcrWorker:
    """Worker for processing OCR jobs and creating citations."""
    
    def __init__(
        self,
        docai_client: Optional[DocAIClient] = None,
        storage_client: Optional[GCSStorageClient] = None,
        citation_crud: Optional[CitationCRUD] = None,
        metrics_collector: Optional[OcrMetricsCollector] = None,
        ontology_service: Optional[OntologyIntegrationService] = None,
        embedding_service: Optional[EmbeddingService] = None,
        use_mock: bool = False
    ):
        """Initialize OCR worker."""
        if use_mock:
            self.docai_client = DocAIClientMock()
            self.storage_client = GCSStorageClientMock()
            self.embedding_service = EmbeddingService(use_mock=True)
        else:
            self.docai_client = docai_client or DocAIClient()
            self.storage_client = storage_client or GCSStorageClient()
            self.embedding_service = embedding_service or EmbeddingService()
        
        self.citation_crud = citation_crud
        self.metrics_collector = metrics_collector or OcrMetricsCollector()
        self.ontology_service = ontology_service or OntologyIntegrationService()
        
        logger.info("Initialized OCR worker with ontology and embedding integration")
    
    def process_job(self, job: OcrJob) -> OcrResult:
        """
        Process a single OCR job end-to-end.
        
        Args:
            job: OCR job specification
            
        Returns:
            OCR result with processing status and outputs
        """
        start_time = time.time()
        
        try:
            logger.info(f"Processing OCR job {job.job_id} for {job.gcs_uri}")
            
            # Step 1: Process document with Document AI
            doc_result = self._process_with_docai(job)
            if not doc_result:
                return self._create_error_result(job, "Document AI processing failed")
            
            # Step 2: Normalize content
            normalized_content = self._normalize_content(doc_result, job)
            if not normalized_content:
                return self._create_error_result(job, "Content normalization failed")
            
            # Step 3: Extract effective date
            effective_date = self._extract_effective_date(normalized_content, job)
            normalized_content.effective_date = effective_date
            
            # Step 4: Create chunks
            chunks = self._create_chunks(normalized_content)
            if not chunks:
                return self._create_error_result(job, "Text chunking failed")
            
            # Step 5: Store processed artifacts
            storage_paths = self._store_artifacts(job, doc_result, normalized_content)
            
            # Step 6: Create citation row
            citation_row = self._create_citation_row(job, normalized_content, chunks)
            
            # Step 7: Generate and store embeddings
            embedding_result = await self._process_embeddings(citation_row, chunks)
            
            # Step 8: Store in database
            if self.citation_crud:
                success = self._store_citation(citation_row)
                if not success:
                    logger.warning(f"Failed to store citation for job {job.job_id}")
            
            # Create successful result
            processing_time = int((time.time() - start_time) * 1000)
            
            result = OcrResult(
                job_id=job.job_id,
                status=OcrStatus.SUCCESS,
                citation_id=citation_row.citation_id,
                normalized_content=normalized_content,
                chunks=chunks,
                processing_time_ms=processing_time,
                pages_processed=normalized_content.page_count,
                tables_extracted=len(normalized_content.tables),
                effective_date_found=effective_date is not None,
                parsed_gcs_path=storage_paths.get("parsed"),
                normalized_gcs_path=storage_paths.get("normalized")
            )
            
            # Update metrics
            self.metrics_collector.record_job_result(result)
            
            logger.info(f"Successfully processed OCR job {job.job_id} in {processing_time}ms")
            return result
            
        except Exception as e:
            processing_time = int((time.time() - start_time) * 1000)
            logger.error(f"Error processing OCR job {job.job_id}: {e}")
            
            result = self._create_error_result(
                job, 
                str(e), 
                processing_time_ms=processing_time
            )
            
            self.metrics_collector.record_job_result(result)
            return result
    
    def process_batch(self, jobs: List[OcrJob]) -> List[OcrResult]:
        """Process multiple OCR jobs."""
        results = []
        
        logger.info(f"Processing batch of {len(jobs)} OCR jobs")
        
        for job in jobs:
            result = self.process_job(job)
            results.append(result)
            
            # Add small delay between jobs to avoid overwhelming services
            time.sleep(0.1)
        
        successful = sum(1 for r in results if r.is_success())
        logger.info(f"Batch processing complete: {successful}/{len(jobs)} successful")
        
        return results
    
    def _process_with_docai(self, job: OcrJob) -> Optional[Dict[str, Any]]:
        """Process document with Document AI."""
        try:
            logger.info(f"Processing {job.gcs_uri} with Document AI")
            
            # Process document
            doc_result = self.docai_client.process_gcs_document(job.gcs_uri)
            
            # Extract basic info
            doc_info = self.docai_client.extract_document_info(doc_result)
            logger.info(f"Document processed: {doc_info['page_count']} pages, "
                       f"{doc_info['table_count']} tables, "
                       f"avg confidence: {doc_info['avg_confidence']:.2f}")
            
            return doc_result
            
        except Exception as e:
            logger.error(f"Document AI processing failed for {job.gcs_uri}: {e}")
            return None
    
    def _normalize_content(self, doc_result: Dict[str, Any], job: OcrJob) -> Optional[NormalizedContent]:
        """Normalize document content."""
        try:
            logger.info("Normalizing document content")
            
            normalized = doc_to_normalized_content(doc_result)
            
            logger.info(f"Normalized content: {len(normalized.paragraphs)} paragraphs, "
                       f"{len(normalized.tables)} tables, "
                       f"language: {normalized.language}")
            
            return normalized
            
        except Exception as e:
            logger.error(f"Content normalization failed: {e}")
            return None
    
    def _extract_effective_date(self, normalized_content: NormalizedContent, job: OcrJob) -> Optional[date]:
        """Extract effective date from normalized content."""
        try:
            logger.info("Extracting effective date")
            
            # Combine all text for date extraction
            full_text = '\n'.join(normalized_content.paragraphs)
            
            # Add table content for date extraction
            for table in normalized_content.tables:
                full_text += '\n' + table.markdown
            
            effective_date = extract_effective_date(full_text, job.source_url)
            
            if effective_date:
                logger.info(f"Found effective date: {effective_date}")
                
                # Validate the date
                validation = validate_effective_date(effective_date, full_text)
                if not validation["is_valid"]:
                    logger.warning(f"Effective date validation failed: {validation['validation_notes']}")
                    return None
                
                return effective_date
            else:
                logger.warning("No effective date found")
                return None
                
        except Exception as e:
            logger.error(f"Effective date extraction failed: {e}")
            return None
    
    def _create_chunks(self, normalized_content: NormalizedContent) -> List[ChunkData]:
        """Create text chunks from normalized content."""
        try:
            logger.info("Creating text chunks")
            
            chunks = chunk_document_content(normalized_content.paragraphs)
            
            # Analyze chunking quality
            quality = analyze_chunking_quality(chunks)
            logger.info(f"Created {quality['total_chunks']} chunks, "
                       f"avg tokens: {quality['avg_tokens_per_chunk']:.1f}")
            
            return chunks
            
        except Exception as e:
            logger.error(f"Text chunking failed: {e}")
            return []
    
    def _store_artifacts(
        self, 
        job: OcrJob, 
        doc_result: Dict[str, Any], 
        normalized_content: NormalizedContent
    ) -> Dict[str, str]:
        """Store processed artifacts to GCS."""
        storage_paths = {}
        
        try:
            # Store parsed Document AI result
            parsed_path = generate_parsed_path(job.gcs_uri)
            if self.storage_client.write_gcs_json(parsed_path, doc_result):
                storage_paths["parsed"] = parsed_path
                logger.info(f"Stored parsed result to {parsed_path}")
            
            # Store normalized content
            normalized_path = generate_normalized_path(job.gcs_uri)
            normalized_data = {
                "paragraphs": normalized_content.paragraphs,
                "tables": [table.dict() for table in normalized_content.tables],
                "effective_date": normalized_content.effective_date.isoformat() if normalized_content.effective_date else None,
                "language": normalized_content.language,
                "page_count": normalized_content.page_count,
                "job_id": str(job.job_id),
                "processed_at": datetime.utcnow().isoformat()
            }
            
            if self.storage_client.write_gcs_jsonl(normalized_path, [normalized_data]):
                storage_paths["normalized"] = normalized_path
                logger.info(f"Stored normalized content to {normalized_path}")
            
        except Exception as e:
            logger.error(f"Error storing artifacts: {e}")
        
        return storage_paths
    
    def _create_citation_row(
        self, 
        job: OcrJob, 
        normalized_content: NormalizedContent, 
        chunks: List[ChunkData]
    ) -> CitationRow:
        """Create citation row for database storage with ontology enrichment."""
        
        # Create enriched citation using ontology integration
        try:
            jurisdiction = Jurisdiction(job.province)
        except ValueError:
            jurisdiction = None
        
        citation_row = create_enriched_citation_from_chunks(
            chunks=chunks,
            citation_id=uuid4(),
            province=job.province,
            doc_class=job.doc_class,
            title=job.title or "未命名文档",
            url=job.source_url,
            checksum=job.checksum,
            effective_date=normalized_content.effective_date,
            integration_service=self.ontology_service
        )
        
        return citation_row
    
    async def _process_embeddings(self, citation_row: CitationRow, chunks: List[ChunkData]) -> Optional[Dict[str, Any]]:
        """Process embeddings for citation chunks."""
        try:
            logger.info(f"Processing embeddings for citation {citation_row.citation_id}")
            
            # Initialize embedding service if needed
            if not hasattr(self.embedding_service, '_initialized'):
                await self.embedding_service.initialize()
                self.embedding_service._initialized = True
            
            # Process citation chunks to generate and store embeddings
            embedding_result = await self.embedding_service.process_citation_chunks(
                citation_row, chunks
            )
            
            if embedding_result["success"]:
                logger.info(f"Successfully processed embeddings for citation {citation_row.citation_id}")
                return embedding_result
            else:
                logger.error(f"Embedding processing failed: {embedding_result.get('error')}")
                return None
                
        except Exception as e:
            logger.error(f"Error processing embeddings: {e}")
            return None
    
    def _store_citation(self, citation_row: CitationRow) -> bool:
        """Store citation in database."""
        try:
            # Convert to database format
            citation_data = {
                "citation_id": citation_row.citation_id,
                "province": citation_row.province,
                "doc_class": citation_row.doc_class,
                "asset": citation_row.asset,
                "title": citation_row.title,
                "url": citation_row.url,
                "effective_date": citation_row.effective_date,
                "checksum": citation_row.checksum,
                "content": citation_row.content
            }
            
            # Use CRUD to insert/update
            result = self.citation_crud.upsert_citation(citation_data)
            
            if result:
                logger.info(f"Stored citation {citation_row.citation_id}")
                return True
            else:
                logger.error(f"Failed to store citation {citation_row.citation_id}")
                return False
                
        except Exception as e:
            logger.error(f"Error storing citation: {e}")
            return False
    
    def _create_error_result(
        self, 
        job: OcrJob, 
        error_message: str, 
        processing_time_ms: Optional[int] = None
    ) -> OcrResult:
        """Create error result for failed job."""
        return OcrResult(
            job_id=job.job_id,
            status=OcrStatus.FAILED,
            error_message=error_message,
            processing_time_ms=processing_time_ms or 0
        )
    
    def health_check(self) -> Dict[str, Any]:
        """Check worker health and dependencies."""
        health = {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "dependencies": {}
        }
        
        try:
            # Check Document AI
            docai_health = self.docai_client.health_check()
            health["dependencies"]["document_ai"] = docai_health
            
            # Check storage (simple test)
            test_uri = "gs://test-bucket/health-check.json"
            storage_healthy = True
            try:
                self.storage_client.write_gcs_json(test_uri, {"test": "health_check"})
            except Exception:
                storage_healthy = False
            
            health["dependencies"]["storage"] = {
                "status": "healthy" if storage_healthy else "unhealthy"
            }
            
            # Check database if available
            if self.citation_crud:
                try:
                    db_healthy = self.citation_crud.health_check()
                    health["dependencies"]["database"] = {
                        "status": "healthy" if db_healthy else "unhealthy"
                    }
                except Exception as e:
                    health["dependencies"]["database"] = {
                        "status": "unhealthy",
                        "error": str(e)
                    }
            
            # Overall status
            all_healthy = all(
                dep.get("status") == "healthy" 
                for dep in health["dependencies"].values()
            )
            
            if not all_healthy:
                health["status"] = "degraded"
            
        except Exception as e:
            health["status"] = "unhealthy"
            health["error"] = str(e)
        
        return health
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get worker metrics."""
        return self.metrics_collector.get_metrics()


def create_ocr_job_from_message(message_data: Dict[str, Any]) -> OcrJob:
    """Create OCR job from Pub/Sub message or API request."""
    return OcrJob(
        gcs_uri=message_data["gcs_uri"],
        province=message_data["province"],
        doc_class=message_data["doc_class"],
        source_url=message_data["source_url"],
        checksum=message_data["checksum"],
        title=message_data.get("title"),
        source_domain=message_data.get("source_domain"),
        trace_id=message_data.get("trace_id")
    )