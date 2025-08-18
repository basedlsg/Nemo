"""Research orchestrator service for coordinating discovery → verification → ingestion workflow."""
import asyncio
import logging
import json
from typing import Dict, Any, List, Optional, Union
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, asdict
import uuid

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class JobStatus(str, Enum):
    """Job status values."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"


class JobType(str, Enum):
    """Job types in the research pipeline."""
    DISCOVERY = "discovery"
    VERIFICATION = "verification"
    INGESTION = "ingestion"
    FULL_PIPELINE = "full_pipeline"


class JobPriority(str, Enum):
    """Job priority levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class JobResult:
    """Job execution result."""
    job_id: str
    status: str
    result_data: Optional[Dict[str, Any]]
    error_message: Optional[str]
    execution_time_ms: int
    retry_count: int
    created_at: str
    started_at: Optional[str]
    completed_at: Optional[str]


@dataclass
class PipelineJob:
    """Pipeline job definition."""
    job_id: str
    job_type: str
    priority: str
    status: str
    input_data: Dict[str, Any]
    result_data: Optional[Dict[str, Any]]
    error_message: Optional[str]
    retry_count: int
    max_retries: int
    created_at: str
    started_at: Optional[str]
    completed_at: Optional[str]
    next_job_id: Optional[str]
    parent_job_id: Optional[str]


class DiscoveryJobRequest(BaseModel):
    """Discovery job request model."""
    province: str = Field(..., min_length=1)
    asset_type: str = Field(..., min_length=1)
    doc_class: str = Field(..., min_length=1)
    keywords: Optional[str] = None
    priority: JobPriority = JobPriority.MEDIUM
    max_results: int = Field(10, ge=1, le=50)


class VerificationJobRequest(BaseModel):
    """Verification job request model."""
    candidate_urls: List[str] = Field(..., min_items=1)
    province: str = Field(..., min_length=1)
    priority: JobPriority = JobPriority.MEDIUM


class IngestionJobRequest(BaseModel):
    """Ingestion job request model."""
    verified_urls: List[str] = Field(..., min_items=1)
    province: str = Field(..., min_length=1)
    asset_type: str = Field(..., min_length=1)
    doc_class: str = Field(..., min_length=1)
    priority: JobPriority = JobPriority.MEDIUM


class ResearchOrchestrator:
    """Research orchestrator for managing discovery → verification → ingestion pipeline."""
    
    def __init__(self):
        """Initialize research orchestrator."""
        # In-memory job storage (would use Redis/database in production)
        self.jobs: Dict[str, PipelineJob] = {}
        self.job_queue: List[str] = []  # Job IDs in execution order
        self.running_jobs: Dict[str, asyncio.Task] = {}
        
        # Configuration
        self.max_concurrent_jobs = 5
        self.default_retry_delay = 30  # seconds
        self.max_retries = 3
        
        # Statistics
        self.stats = {
            "total_jobs": 0,
            "completed_jobs": 0,
            "failed_jobs": 0,
            "by_type": {job_type.value: 0 for job_type in JobType},
            "by_status": {status.value: 0 for status in JobStatus}
        }
        
        # Start job processor
        self._processor_task = None
        self._start_job_processor()
    
    def _start_job_processor(self):
        """Start the job processor task."""
        if self._processor_task is None or self._processor_task.done():
            self._processor_task = asyncio.create_task(self._process_job_queue())
    
    async def _process_job_queue(self):
        """Process jobs from the queue."""
        while True:
            try:
                # Check for pending jobs
                if len(self.running_jobs) < self.max_concurrent_jobs and self.job_queue:
                    job_id = self.job_queue.pop(0)
                    
                    if job_id in self.jobs:
                        job = self.jobs[job_id]
                        if job.status == JobStatus.PENDING.value:
                            # Start job execution
                            task = asyncio.create_task(self._execute_job(job_id))
                            self.running_jobs[job_id] = task
                
                # Clean up completed tasks
                completed_jobs = []
                for job_id, task in self.running_jobs.items():
                    if task.done():
                        completed_jobs.append(job_id)
                
                for job_id in completed_jobs:
                    del self.running_jobs[job_id]
                
                # Wait before next iteration
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f"Error in job processor: {e}")
                await asyncio.sleep(5)
    
    async def _execute_job(self, job_id: str):
        """Execute a specific job."""
        try:
            job = self.jobs[job_id]
            logger.info(f"Starting job execution: {job_id} ({job.job_type})")
            
            # Update job status
            job.status = JobStatus.RUNNING.value
            job.started_at = datetime.utcnow().isoformat()
            
            start_time = datetime.utcnow()
            
            # Execute based on job type
            if job.job_type == JobType.DISCOVERY.value:
                result = await self._execute_discovery_job(job)
            elif job.job_type == JobType.VERIFICATION.value:
                result = await self._execute_verification_job(job)
            elif job.job_type == JobType.INGESTION.value:
                result = await self._execute_ingestion_job(job)
            elif job.job_type == JobType.FULL_PIPELINE.value:
                result = await self._execute_full_pipeline_job(job)
            else:
                raise ValueError(f"Unknown job type: {job.job_type}")
            
            # Calculate execution time
            execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            # Update job with results
            job.status = JobStatus.COMPLETED.value
            job.result_data = result
            job.completed_at = datetime.utcnow().isoformat()
            
            # Update statistics
            self.stats["completed_jobs"] += 1
            self.stats["by_status"][JobStatus.COMPLETED.value] += 1
            
            logger.info(f"Job completed successfully: {job_id} ({execution_time:.0f}ms)")
            
            # Schedule next job if part of pipeline
            if job.next_job_id:
                await self._schedule_next_job(job)
            
        except Exception as e:
            logger.error(f"Job execution failed: {job_id} - {e}")
            await self._handle_job_failure(job_id, str(e))
    
    async def _execute_discovery_job(self, job: PipelineJob) -> Dict[str, Any]:
        """Execute discovery job."""
        try:
            # Mock discovery service call (would use actual service in production)
            input_data = job.input_data
            
            # Simulate discovery process
            await asyncio.sleep(2)  # Simulate API call delay
            
            # Mock discovered URLs
            discovered_urls = [
                f"https://drc.gd.gov.cn/mock/{input_data['province']}/{input_data['asset_type']}/doc1.html",
                f"https://nyj.{input_data['province']}.gov.cn/mock/{input_data['asset_type']}/doc2.html"
            ]
            
            return {
                "discovered_urls": discovered_urls,
                "total_found": len(discovered_urls),
                "province": input_data["province"],
                "asset_type": input_data["asset_type"],
                "doc_class": input_data["doc_class"]
            }
            
        except Exception as e:
            logger.error(f"Discovery job failed: {e}")
            raise
    
    async def _execute_verification_job(self, job: PipelineJob) -> Dict[str, Any]:
        """Execute verification job."""
        try:
            # Mock verification service call
            input_data = job.input_data
            candidate_urls = input_data.get("candidate_urls", [])
            
            # Simulate verification process
            await asyncio.sleep(1.5)  # Simulate API call delay
            
            # Mock verification results (assume 80% pass rate)
            verified_urls = []
            failed_urls = []
            
            for i, url in enumerate(candidate_urls):
                if i % 5 != 0:  # 80% pass rate
                    verified_urls.append(url)
                else:
                    failed_urls.append(url)
            
            return {
                "verified_urls": verified_urls,
                "failed_urls": failed_urls,
                "total_verified": len(verified_urls),
                "verification_rate": len(verified_urls) / len(candidate_urls) if candidate_urls else 0
            }
            
        except Exception as e:
            logger.error(f"Verification job failed: {e}")
            raise
    
    async def _execute_ingestion_job(self, job: PipelineJob) -> Dict[str, Any]:
        """Execute ingestion job."""
        try:
            # Mock ingestion service call
            input_data = job.input_data
            verified_urls = input_data.get("verified_urls", [])
            
            # Simulate ingestion process
            await asyncio.sleep(3)  # Simulate processing delay
            
            # Mock ingestion results
            ingested_documents = []
            failed_ingestions = []
            
            for i, url in enumerate(verified_urls):
                if i % 10 != 0:  # 90% success rate
                    doc_id = f"DOC-{datetime.utcnow().strftime('%Y%m%d')}-{i:03d}"
                    ingested_documents.append({
                        "document_id": doc_id,
                        "source_url": url,
                        "citations_extracted": 5 + (i % 10),
                        "processing_time_ms": 1000 + (i * 100)
                    })
                else:
                    failed_ingestions.append(url)
            
            return {
                "ingested_documents": ingested_documents,
                "failed_ingestions": failed_ingestions,
                "total_ingested": len(ingested_documents),
                "total_citations": sum(doc["citations_extracted"] for doc in ingested_documents),
                "ingestion_rate": len(ingested_documents) / len(verified_urls) if verified_urls else 0
            }
            
        except Exception as e:
            logger.error(f"Ingestion job failed: {e}")
            raise
    
    async def _execute_full_pipeline_job(self, job: PipelineJob) -> Dict[str, Any]:
        """Execute full pipeline job (discovery → verification → ingestion)."""
        try:
            input_data = job.input_data
            pipeline_results = {}
            
            # Step 1: Discovery
            logger.info(f"Pipeline {job.job_id}: Starting discovery phase")
            discovery_job = PipelineJob(
                job_id=f"{job.job_id}-discovery",
                job_type=JobType.DISCOVERY.value,
                priority=job.priority,
                status=JobStatus.RUNNING.value,
                input_data=input_data,
                result_data=None,
                error_message=None,
                retry_count=0,
                max_retries=self.max_retries,
                created_at=datetime.utcnow().isoformat(),
                started_at=datetime.utcnow().isoformat(),
                completed_at=None,
                next_job_id=None,
                parent_job_id=job.job_id
            )
            
            discovery_result = await self._execute_discovery_job(discovery_job)
            pipeline_results["discovery"] = discovery_result
            
            # Step 2: Verification
            logger.info(f"Pipeline {job.job_id}: Starting verification phase")
            verification_input = {
                "candidate_urls": discovery_result["discovered_urls"],
                "province": input_data["province"]
            }
            
            verification_job = PipelineJob(
                job_id=f"{job.job_id}-verification",
                job_type=JobType.VERIFICATION.value,
                priority=job.priority,
                status=JobStatus.RUNNING.value,
                input_data=verification_input,
                result_data=None,
                error_message=None,
                retry_count=0,
                max_retries=self.max_retries,
                created_at=datetime.utcnow().isoformat(),
                started_at=datetime.utcnow().isoformat(),
                completed_at=None,
                next_job_id=None,
                parent_job_id=job.job_id
            )
            
            verification_result = await self._execute_verification_job(verification_job)
            pipeline_results["verification"] = verification_result
            
            # Step 3: Ingestion
            logger.info(f"Pipeline {job.job_id}: Starting ingestion phase")
            ingestion_input = {
                "verified_urls": verification_result["verified_urls"],
                "province": input_data["province"],
                "asset_type": input_data["asset_type"],
                "doc_class": input_data["doc_class"]
            }
            
            ingestion_job = PipelineJob(
                job_id=f"{job.job_id}-ingestion",
                job_type=JobType.INGESTION.value,
                priority=job.priority,
                status=JobStatus.RUNNING.value,
                input_data=ingestion_input,
                result_data=None,
                error_message=None,
                retry_count=0,
                max_retries=self.max_retries,
                created_at=datetime.utcnow().isoformat(),
                started_at=datetime.utcnow().isoformat(),
                completed_at=None,
                next_job_id=None,
                parent_job_id=job.job_id
            )
            
            ingestion_result = await self._execute_ingestion_job(ingestion_job)
            pipeline_results["ingestion"] = ingestion_result
            
            # Pipeline summary
            pipeline_results["summary"] = {
                "total_discovered": discovery_result["total_found"],
                "total_verified": verification_result["total_verified"],
                "total_ingested": ingestion_result["total_ingested"],
                "total_citations": ingestion_result["total_citations"],
                "pipeline_success_rate": (
                    ingestion_result["total_ingested"] / discovery_result["total_found"]
                    if discovery_result["total_found"] > 0 else 0
                )
            }
            
            logger.info(f"Pipeline {job.job_id}: Completed successfully")
            return pipeline_results
            
        except Exception as e:
            logger.error(f"Full pipeline job failed: {e}")
            raise
    
    async def _handle_job_failure(self, job_id: str, error_message: str):
        """Handle job failure with retry logic."""
        try:
            job = self.jobs[job_id]
            job.error_message = error_message
            job.retry_count += 1
            
            if job.retry_count <= job.max_retries:
                # Schedule retry
                job.status = JobStatus.RETRYING.value
                logger.info(f"Scheduling retry for job {job_id} (attempt {job.retry_count}/{job.max_retries})")
                
                # Add delay before retry
                await asyncio.sleep(self.default_retry_delay)
                
                # Reset job for retry
                job.status = JobStatus.PENDING.value
                job.started_at = None
                job.completed_at = None
                
                # Re-queue job
                self.job_queue.append(job_id)
            else:
                # Max retries exceeded
                job.status = JobStatus.FAILED.value
                job.completed_at = datetime.utcnow().isoformat()
                
                # Update statistics
                self.stats["failed_jobs"] += 1
                self.stats["by_status"][JobStatus.FAILED.value] += 1
                
                logger.error(f"Job failed permanently: {job_id} after {job.retry_count} retries")
                
        except Exception as e:
            logger.error(f"Error handling job failure: {e}")
    
    async def _schedule_next_job(self, completed_job: PipelineJob):
        """Schedule the next job in a pipeline."""
        try:
            if completed_job.next_job_id and completed_job.next_job_id in self.jobs:
                next_job = self.jobs[completed_job.next_job_id]
                
                # Update next job input with results from completed job
                if completed_job.result_data:
                    next_job.input_data.update(completed_job.result_data)
                
                # Queue next job
                self.job_queue.append(completed_job.next_job_id)
                logger.info(f"Scheduled next job: {completed_job.next_job_id}")
                
        except Exception as e:
            logger.error(f"Error scheduling next job: {e}")
    
    async def submit_discovery_job(self, request: DiscoveryJobRequest) -> str:
        """Submit discovery job."""
        try:
            job_id = f"DISC-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{str(uuid.uuid4())[:8].upper()}"
            
            job = PipelineJob(
                job_id=job_id,
                job_type=JobType.DISCOVERY.value,
                priority=request.priority.value,
                status=JobStatus.PENDING.value,
                input_data=request.dict(),
                result_data=None,
                error_message=None,
                retry_count=0,
                max_retries=self.max_retries,
                created_at=datetime.utcnow().isoformat(),
                started_at=None,
                completed_at=None,
                next_job_id=None,
                parent_job_id=None
            )
            
            # Store job and queue for execution
            self.jobs[job_id] = job
            self.job_queue.append(job_id)
            
            # Update statistics
            self.stats["total_jobs"] += 1
            self.stats["by_type"][JobType.DISCOVERY.value] += 1
            self.stats["by_status"][JobStatus.PENDING.value] += 1
            
            logger.info(f"Discovery job submitted: {job_id}")
            return job_id
            
        except Exception as e:
            logger.error(f"Failed to submit discovery job: {e}")
            raise
    
    async def submit_verification_job(self, request: VerificationJobRequest) -> str:
        """Submit verification job."""
        try:
            job_id = f"VERIF-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{str(uuid.uuid4())[:8].upper()}"
            
            job = PipelineJob(
                job_id=job_id,
                job_type=JobType.VERIFICATION.value,
                priority=request.priority.value,
                status=JobStatus.PENDING.value,
                input_data=request.dict(),
                result_data=None,
                error_message=None,
                retry_count=0,
                max_retries=self.max_retries,
                created_at=datetime.utcnow().isoformat(),
                started_at=None,
                completed_at=None,
                next_job_id=None,
                parent_job_id=None
            )
            
            # Store job and queue for execution
            self.jobs[job_id] = job
            self.job_queue.append(job_id)
            
            # Update statistics
            self.stats["total_jobs"] += 1
            self.stats["by_type"][JobType.VERIFICATION.value] += 1
            self.stats["by_status"][JobStatus.PENDING.value] += 1
            
            logger.info(f"Verification job submitted: {job_id}")
            return job_id
            
        except Exception as e:
            logger.error(f"Failed to submit verification job: {e}")
            raise
    
    async def submit_ingestion_job(self, request: IngestionJobRequest) -> str:
        """Submit ingestion job."""
        try:
            job_id = f"INGEST-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{str(uuid.uuid4())[:8].upper()}"
            
            job = PipelineJob(
                job_id=job_id,
                job_type=JobType.INGESTION.value,
                priority=request.priority.value,
                status=JobStatus.PENDING.value,
                input_data=request.dict(),
                result_data=None,
                error_message=None,
                retry_count=0,
                max_retries=self.max_retries,
                created_at=datetime.utcnow().isoformat(),
                started_at=None,
                completed_at=None,
                next_job_id=None,
                parent_job_id=None
            )
            
            # Store job and queue for execution
            self.jobs[job_id] = job
            self.job_queue.append(job_id)
            
            # Update statistics
            self.stats["total_jobs"] += 1
            self.stats["by_type"][JobType.INGESTION.value] += 1
            self.stats["by_status"][JobStatus.PENDING.value] += 1
            
            logger.info(f"Ingestion job submitted: {job_id}")
            return job_id
            
        except Exception as e:
            logger.error(f"Failed to submit ingestion job: {e}")
            raise
    
    async def submit_full_pipeline_job(self, request: DiscoveryJobRequest) -> str:
        """Submit full pipeline job (discovery → verification → ingestion)."""
        try:
            job_id = f"PIPELINE-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{str(uuid.uuid4())[:8].upper()}"
            
            job = PipelineJob(
                job_id=job_id,
                job_type=JobType.FULL_PIPELINE.value,
                priority=request.priority.value,
                status=JobStatus.PENDING.value,
                input_data=request.dict(),
                result_data=None,
                error_message=None,
                retry_count=0,
                max_retries=self.max_retries,
                created_at=datetime.utcnow().isoformat(),
                started_at=None,
                completed_at=None,
                next_job_id=None,
                parent_job_id=None
            )
            
            # Store job and queue for execution
            self.jobs[job_id] = job
            self.job_queue.append(job_id)
            
            # Update statistics
            self.stats["total_jobs"] += 1
            self.stats["by_type"][JobType.FULL_PIPELINE.value] += 1
            self.stats["by_status"][JobStatus.PENDING.value] += 1
            
            logger.info(f"Full pipeline job submitted: {job_id}")
            return job_id
            
        except Exception as e:
            logger.error(f"Failed to submit full pipeline job: {e}")
            raise
    
    async def get_job_status(self, job_id: str) -> Optional[JobResult]:
        """Get job status and results."""
        try:
            if job_id not in self.jobs:
                return None
            
            job = self.jobs[job_id]
            
            # Calculate execution time if job is running or completed
            execution_time_ms = 0
            if job.started_at:
                end_time = datetime.fromisoformat(job.completed_at) if job.completed_at else datetime.utcnow()
                start_time = datetime.fromisoformat(job.started_at)
                execution_time_ms = int((end_time - start_time).total_seconds() * 1000)
            
            return JobResult(
                job_id=job.job_id,
                status=job.status,
                result_data=job.result_data,
                error_message=job.error_message,
                execution_time_ms=execution_time_ms,
                retry_count=job.retry_count,
                created_at=job.created_at,
                started_at=job.started_at,
                completed_at=job.completed_at
            )
            
        except Exception as e:
            logger.error(f"Failed to get job status: {e}")
            return None
    
    async def cancel_job(self, job_id: str) -> bool:
        """Cancel a pending or running job."""
        try:
            if job_id not in self.jobs:
                return False
            
            job = self.jobs[job_id]
            
            # Can only cancel pending or running jobs
            if job.status in [JobStatus.PENDING.value, JobStatus.RUNNING.value, JobStatus.RETRYING.value]:
                job.status = JobStatus.CANCELLED.value
                job.completed_at = datetime.utcnow().isoformat()
                
                # Remove from queue if pending
                if job_id in self.job_queue:
                    self.job_queue.remove(job_id)
                
                # Cancel running task if exists
                if job_id in self.running_jobs:
                    self.running_jobs[job_id].cancel()
                    del self.running_jobs[job_id]
                
                logger.info(f"Job cancelled: {job_id}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to cancel job: {e}")
            return False
    
    async def get_orchestrator_stats(self) -> Dict[str, Any]:
        """Get orchestrator statistics."""
        try:
            # Calculate real-time stats
            pending_jobs = len([j for j in self.jobs.values() if j.status == JobStatus.PENDING.value])
            running_jobs = len([j for j in self.jobs.values() if j.status == JobStatus.RUNNING.value])
            
            # Queue stats
            queue_length = len(self.job_queue)
            active_tasks = len(self.running_jobs)
            
            # Recent activity (last 24 hours)
            twenty_four_hours_ago = datetime.utcnow() - timedelta(hours=24)
            recent_jobs = [
                j for j in self.jobs.values()
                if datetime.fromisoformat(j.created_at) >= twenty_four_hours_ago
            ]
            
            return {
                "total_jobs": self.stats["total_jobs"],
                "completed_jobs": self.stats["completed_jobs"],
                "failed_jobs": self.stats["failed_jobs"],
                "pending_jobs": pending_jobs,
                "running_jobs": running_jobs,
                "queue_length": queue_length,
                "active_tasks": active_tasks,
                "max_concurrent_jobs": self.max_concurrent_jobs,
                "job_type_distribution": self.stats["by_type"],
                "job_status_distribution": self.stats["by_status"],
                "recent_activity": {
                    "count": len(recent_jobs),
                    "period": "last_24_hours"
                },
                "last_updated": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to get orchestrator stats: {e}")
            return {}
    
    async def cleanup(self):
        """Cleanup orchestrator resources."""
        try:
            # Cancel all running jobs
            for job_id, task in self.running_jobs.items():
                task.cancel()
            
            # Cancel processor task
            if self._processor_task and not self._processor_task.done():
                self._processor_task.cancel()
            
            logger.info("Research orchestrator cleaned up")
            
        except Exception as e:
            logger.error(f"Error during orchestrator cleanup: {e}")


# Global orchestrator instance
_research_orchestrator = None


async def get_research_orchestrator() -> ResearchOrchestrator:
    """Get or create global research orchestrator instance."""
    global _research_orchestrator
    
    if _research_orchestrator is None:
        _research_orchestrator = ResearchOrchestrator()
    
    return _research_orchestrator