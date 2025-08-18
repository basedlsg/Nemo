"""Tests for research orchestrator service."""
import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from fastapi.testclient import TestClient
from datetime import datetime

from services.orchestrator.api import app
from services.orchestrator.research_orchestrator import (
    ResearchOrchestrator,
    DiscoveryJobRequest,
    VerificationJobRequest,
    IngestionJobRequest,
    JobType,
    JobStatus,
    JobPriority
)


class TestResearchOrchestratorAPI:
    """Test Research Orchestrator API endpoints."""
    
    @pytest.fixture
    def client(self):
        """Test client fixture."""
        return TestClient(app)
    
    @pytest.fixture
    def sample_discovery_request(self):
        """Sample discovery request for testing."""
        return {
            "province": "guangdong",
            "asset_type": "solar",
            "doc_class": "grid_connection",
            "keywords": "分布式光伏并网",
            "priority": "medium",
            "max_results": 10
        }
    
    @pytest.fixture
    def sample_verification_request(self):
        """Sample verification request for testing."""
        return {
            "candidate_urls": [
                "https://drc.gd.gov.cn/test1.html",
                "https://drc.gd.gov.cn/test2.html"
            ],
            "province": "guangdong",
            "priority": "medium"
        }
    
    @pytest.fixture
    def sample_ingestion_request(self):
        """Sample ingestion request for testing."""
        return {
            "verified_urls": [
                "https://drc.gd.gov.cn/verified1.html",
                "https://drc.gd.gov.cn/verified2.html"
            ],
            "province": "guangdong",
            "asset_type": "solar",
            "doc_class": "grid_connection",
            "priority": "medium"
        }
    
    def test_submit_discovery_job(self, client, sample_discovery_request):
        """Test submitting discovery job."""
        with patch('services.orchestrator.api.get_research_orchestrator') as mock_get_orchestrator:
            mock_orchestrator = AsyncMock()
            mock_orchestrator.submit_discovery_job.return_value = "DISC-20240116-001"
            mock_get_orchestrator.return_value = mock_orchestrator
            
            response = client.post("/jobs/discovery", json=sample_discovery_request)
            assert response.status_code == 200
            
            data = response.json()
            assert data["job_id"] == "DISC-20240116-001"
            assert data["job_type"] == "discovery"
            assert data["status"] == "pending"
            assert "submitted_at" in data
    
    def test_submit_verification_job(self, client, sample_verification_request):
        """Test submitting verification job."""
        with patch('services.orchestrator.api.get_research_orchestrator') as mock_get_orchestrator:
            mock_orchestrator = AsyncMock()
            mock_orchestrator.submit_verification_job.return_value = "VERIF-20240116-001"
            mock_get_orchestrator.return_value = mock_orchestrator
            
            response = client.post("/jobs/verification", json=sample_verification_request)
            assert response.status_code == 200
            
            data = response.json()
            assert data["job_id"] == "VERIF-20240116-001"
            assert data["job_type"] == "verification"
            assert data["status"] == "pending"
    
    def test_submit_ingestion_job(self, client, sample_ingestion_request):
        """Test submitting ingestion job."""
        with patch('services.orchestrator.api.get_research_orchestrator') as mock_get_orchestrator:
            mock_orchestrator = AsyncMock()
            mock_orchestrator.submit_ingestion_job.return_value = "INGEST-20240116-001"
            mock_get_orchestrator.return_value = mock_orchestrator
            
            response = client.post("/jobs/ingestion", json=sample_ingestion_request)
            assert response.status_code == 200
            
            data = response.json()
            assert data["job_id"] == "INGEST-20240116-001"
            assert data["job_type"] == "ingestion"
            assert data["status"] == "pending"
    
    def test_submit_full_pipeline_job(self, client, sample_discovery_request):
        """Test submitting full pipeline job."""
        with patch('services.orchestrator.api.get_research_orchestrator') as mock_get_orchestrator:
            mock_orchestrator = AsyncMock()
            mock_orchestrator.submit_full_pipeline_job.return_value = "PIPELINE-20240116-001"
            mock_get_orchestrator.return_value = mock_orchestrator
            
            response = client.post("/jobs/pipeline", json=sample_discovery_request)
            assert response.status_code == 200
            
            data = response.json()
            assert data["job_id"] == "PIPELINE-20240116-001"
            assert data["job_type"] == "full_pipeline"
            assert data["status"] == "pending"
            assert "pipeline_stages" in data
            assert len(data["pipeline_stages"]) == 3
    
    def test_get_job_status(self, client):
        """Test getting job status."""
        with patch('services.orchestrator.api.get_research_orchestrator') as mock_get_orchestrator:
            mock_orchestrator = AsyncMock()
            mock_job_result = Mock()
            mock_job_result.__dict__ = {
                "job_id": "DISC-20240116-001",
                "status": "completed",
                "result_data": {"discovered_urls": ["https://test.com"]},
                "error_message": None,
                "execution_time_ms": 2500,
                "retry_count": 0,
                "created_at": "2024-01-16T10:00:00",
                "started_at": "2024-01-16T10:00:01",
                "completed_at": "2024-01-16T10:00:03"
            }
            mock_orchestrator.get_job_status.return_value = mock_job_result
            mock_get_orchestrator.return_value = mock_orchestrator
            
            response = client.get("/jobs/DISC-20240116-001")
            assert response.status_code == 200
            
            data = response.json()
            assert data["job"]["job_id"] == "DISC-20240116-001"
            assert data["job"]["status"] == "completed"
            assert data["job"]["execution_time_ms"] == 2500
    
    def test_get_job_status_not_found(self, client):
        """Test getting status for non-existent job."""
        with patch('services.orchestrator.api.get_research_orchestrator') as mock_get_orchestrator:
            mock_orchestrator = AsyncMock()
            mock_orchestrator.get_job_status.return_value = None
            mock_get_orchestrator.return_value = mock_orchestrator
            
            response = client.get("/jobs/nonexistent")
            assert response.status_code == 404
            assert "Job not found" in response.json()["detail"]
    
    def test_cancel_job(self, client):
        """Test cancelling a job."""
        with patch('services.orchestrator.api.get_research_orchestrator') as mock_get_orchestrator:
            mock_orchestrator = AsyncMock()
            mock_orchestrator.cancel_job.return_value = True
            mock_get_orchestrator.return_value = mock_orchestrator
            
            response = client.delete("/jobs/DISC-20240116-001")
            assert response.status_code == 200
            
            data = response.json()
            assert data["job_id"] == "DISC-20240116-001"
            assert data["status"] == "cancelled"
            assert "cancelled_at" in data
    
    def test_cancel_job_failure(self, client):
        """Test cancelling a job that cannot be cancelled."""
        with patch('services.orchestrator.api.get_research_orchestrator') as mock_get_orchestrator:
            mock_orchestrator = AsyncMock()
            mock_orchestrator.cancel_job.return_value = False
            mock_get_orchestrator.return_value = mock_orchestrator
            
            response = client.delete("/jobs/DISC-20240116-001")
            assert response.status_code == 400
            assert "cannot be cancelled" in response.json()["detail"]
    
    def test_get_orchestrator_stats(self, client):
        """Test getting orchestrator statistics."""
        with patch('services.orchestrator.api.get_research_orchestrator') as mock_get_orchestrator:
            mock_orchestrator = AsyncMock()
            mock_orchestrator.get_orchestrator_stats.return_value = {
                "total_jobs": 10,
                "completed_jobs": 7,
                "failed_jobs": 1,
                "pending_jobs": 1,
                "running_jobs": 1,
                "queue_length": 2,
                "active_tasks": 1,
                "job_type_distribution": {
                    "discovery": 4,
                    "verification": 3,
                    "ingestion": 2,
                    "full_pipeline": 1
                }
            }
            mock_get_orchestrator.return_value = mock_orchestrator
            
            response = client.get("/stats")
            assert response.status_code == 200
            
            data = response.json()
            assert data["total_jobs"] == 10
            assert data["completed_jobs"] == 7
            assert data["queue_length"] == 2
            assert "job_type_distribution" in data
    
    def test_get_enums(self, client):
        """Test getting enum values."""
        response = client.get("/enums")
        assert response.status_code == 200
        
        data = response.json()
        assert "job_types" in data
        assert "job_statuses" in data
        assert "job_priorities" in data
        
        # Check specific enum values
        assert "discovery" in data["job_types"]
        assert "pending" in data["job_statuses"]
        assert "medium" in data["job_priorities"]
        
        # Check bilingual labels
        assert data["job_types"]["discovery"]["label_zh"] == "发现"
        assert data["job_statuses"]["pending"]["label_zh"] == "等待中"
    
    def test_test_pipeline(self, client):
        """Test the test pipeline endpoint."""
        with patch('services.orchestrator.api.get_research_orchestrator') as mock_get_orchestrator:
            mock_orchestrator = AsyncMock()
            mock_orchestrator.submit_full_pipeline_job.return_value = "PIPELINE-TEST-001"
            mock_get_orchestrator.return_value = mock_orchestrator
            
            response = client.post("/test/pipeline?province=guangdong&asset_type=solar")
            assert response.status_code == 200
            
            data = response.json()
            assert data["test_job_id"] == "PIPELINE-TEST-001"
            assert data["test_parameters"]["province"] == "guangdong"
            assert data["test_parameters"]["asset_type"] == "solar"
            assert "This is a test job" in data["note"]
    
    def test_health_check(self, client):
        """Test health check endpoint."""
        with patch('services.orchestrator.api.get_research_orchestrator') as mock_get_orchestrator:
            mock_orchestrator = AsyncMock()
            mock_orchestrator.get_orchestrator_stats.return_value = {
                "total_jobs": 5,
                "pending_jobs": 1,
                "running_jobs": 2,
                "queue_length": 3,
                "active_tasks": 2
            }
            mock_get_orchestrator.return_value = mock_orchestrator
            
            response = client.get("/health")
            assert response.status_code == 200
            
            data = response.json()
            assert data["status"] == "healthy"
            assert data["service"] == "research_orchestrator"
            assert "stats_summary" in data
            assert data["stats_summary"]["total_jobs"] == 5
    
    def test_health_check_failure(self, client):
        """Test health check failure."""
        with patch('services.orchestrator.api.get_research_orchestrator', side_effect=Exception("Service error")):
            response = client.get("/health")
            assert response.status_code == 503
            
            data = response.json()
            assert data["status"] == "unhealthy"
            assert "Service error" in data["error"]


class TestResearchOrchestrator:
    """Test ResearchOrchestrator functionality."""
    
    @pytest.fixture
    def orchestrator(self):
        """Orchestrator fixture."""
        return ResearchOrchestrator()
    
    @pytest.fixture
    def sample_discovery_request(self):
        """Sample discovery request fixture."""
        return DiscoveryJobRequest(
            province="guangdong",
            asset_type="solar",
            doc_class="grid_connection",
            keywords="分布式光伏",
            priority=JobPriority.MEDIUM,
            max_results=5
        )
    
    @pytest.fixture
    def sample_verification_request(self):
        """Sample verification request fixture."""
        return VerificationJobRequest(
            candidate_urls=["https://test1.com", "https://test2.com"],
            province="guangdong",
            priority=JobPriority.MEDIUM
        )
    
    @pytest.fixture
    def sample_ingestion_request(self):
        """Sample ingestion request fixture."""
        return IngestionJobRequest(
            verified_urls=["https://verified1.com", "https://verified2.com"],
            province="guangdong",
            asset_type="solar",
            doc_class="grid_connection",
            priority=JobPriority.MEDIUM
        )
    
    @pytest.mark.asyncio
    async def test_submit_discovery_job(self, orchestrator, sample_discovery_request):
        """Test submitting discovery job."""
        job_id = await orchestrator.submit_discovery_job(sample_discovery_request)
        
        assert job_id.startswith("DISC-")
        assert job_id in orchestrator.jobs
        
        job = orchestrator.jobs[job_id]
        assert job.job_type == JobType.DISCOVERY.value
        assert job.status == JobStatus.PENDING.value
        assert job.input_data["province"] == "guangdong"
        assert job.input_data["asset_type"] == "solar"
    
    @pytest.mark.asyncio
    async def test_submit_verification_job(self, orchestrator, sample_verification_request):
        """Test submitting verification job."""
        job_id = await orchestrator.submit_verification_job(sample_verification_request)
        
        assert job_id.startswith("VERIF-")
        assert job_id in orchestrator.jobs
        
        job = orchestrator.jobs[job_id]
        assert job.job_type == JobType.VERIFICATION.value
        assert job.status == JobStatus.PENDING.value
        assert len(job.input_data["candidate_urls"]) == 2
    
    @pytest.mark.asyncio
    async def test_submit_ingestion_job(self, orchestrator, sample_ingestion_request):
        """Test submitting ingestion job."""
        job_id = await orchestrator.submit_ingestion_job(sample_ingestion_request)
        
        assert job_id.startswith("INGEST-")
        assert job_id in orchestrator.jobs
        
        job = orchestrator.jobs[job_id]
        assert job.job_type == JobType.INGESTION.value
        assert job.status == JobStatus.PENDING.value
        assert len(job.input_data["verified_urls"]) == 2
    
    @pytest.mark.asyncio
    async def test_submit_full_pipeline_job(self, orchestrator, sample_discovery_request):
        """Test submitting full pipeline job."""
        job_id = await orchestrator.submit_full_pipeline_job(sample_discovery_request)
        
        assert job_id.startswith("PIPELINE-")
        assert job_id in orchestrator.jobs
        
        job = orchestrator.jobs[job_id]
        assert job.job_type == JobType.FULL_PIPELINE.value
        assert job.status == JobStatus.PENDING.value
    
    @pytest.mark.asyncio
    async def test_get_job_status(self, orchestrator, sample_discovery_request):
        """Test getting job status."""
        job_id = await orchestrator.submit_discovery_job(sample_discovery_request)
        
        job_result = await orchestrator.get_job_status(job_id)
        
        assert job_result is not None
        assert job_result.job_id == job_id
        assert job_result.status == JobStatus.PENDING.value
        assert job_result.retry_count == 0
    
    @pytest.mark.asyncio
    async def test_get_job_status_nonexistent(self, orchestrator):
        """Test getting status for non-existent job."""
        job_result = await orchestrator.get_job_status("nonexistent")
        assert job_result is None
    
    @pytest.mark.asyncio
    async def test_cancel_job(self, orchestrator, sample_discovery_request):
        """Test cancelling a job."""
        job_id = await orchestrator.submit_discovery_job(sample_discovery_request)
        
        # Job should be pending
        job = orchestrator.jobs[job_id]
        assert job.status == JobStatus.PENDING.value
        
        # Cancel job
        success = await orchestrator.cancel_job(job_id)
        assert success is True
        
        # Job should be cancelled
        assert job.status == JobStatus.CANCELLED.value
        assert job.completed_at is not None
    
    @pytest.mark.asyncio
    async def test_cancel_nonexistent_job(self, orchestrator):
        """Test cancelling non-existent job."""
        success = await orchestrator.cancel_job("nonexistent")
        assert success is False
    
    @pytest.mark.asyncio
    async def test_execute_discovery_job(self, orchestrator):
        """Test discovery job execution."""
        # Create a mock job
        from services.orchestrator.research_orchestrator import PipelineJob
        
        job = PipelineJob(
            job_id="test-discovery",
            job_type=JobType.DISCOVERY.value,
            priority=JobPriority.MEDIUM.value,
            status=JobStatus.PENDING.value,
            input_data={
                "province": "guangdong",
                "asset_type": "solar",
                "doc_class": "grid_connection"
            },
            result_data=None,
            error_message=None,
            retry_count=0,
            max_retries=3,
            created_at=datetime.utcnow().isoformat(),
            started_at=None,
            completed_at=None,
            next_job_id=None,
            parent_job_id=None
        )
        
        result = await orchestrator._execute_discovery_job(job)
        
        assert "discovered_urls" in result
        assert "total_found" in result
        assert result["province"] == "guangdong"
        assert result["asset_type"] == "solar"
        assert len(result["discovered_urls"]) > 0
    
    @pytest.mark.asyncio
    async def test_execute_verification_job(self, orchestrator):
        """Test verification job execution."""
        from services.orchestrator.research_orchestrator import PipelineJob
        
        job = PipelineJob(
            job_id="test-verification",
            job_type=JobType.VERIFICATION.value,
            priority=JobPriority.MEDIUM.value,
            status=JobStatus.PENDING.value,
            input_data={
                "candidate_urls": [
                    "https://test1.com",
                    "https://test2.com",
                    "https://test3.com",
                    "https://test4.com",
                    "https://test5.com"
                ],
                "province": "guangdong"
            },
            result_data=None,
            error_message=None,
            retry_count=0,
            max_retries=3,
            created_at=datetime.utcnow().isoformat(),
            started_at=None,
            completed_at=None,
            next_job_id=None,
            parent_job_id=None
        )
        
        result = await orchestrator._execute_verification_job(job)
        
        assert "verified_urls" in result
        assert "failed_urls" in result
        assert "total_verified" in result
        assert "verification_rate" in result
        assert result["total_verified"] + len(result["failed_urls"]) == 5
    
    @pytest.mark.asyncio
    async def test_execute_ingestion_job(self, orchestrator):
        """Test ingestion job execution."""
        from services.orchestrator.research_orchestrator import PipelineJob
        
        job = PipelineJob(
            job_id="test-ingestion",
            job_type=JobType.INGESTION.value,
            priority=JobPriority.MEDIUM.value,
            status=JobStatus.PENDING.value,
            input_data={
                "verified_urls": [
                    "https://verified1.com",
                    "https://verified2.com"
                ],
                "province": "guangdong",
                "asset_type": "solar",
                "doc_class": "grid_connection"
            },
            result_data=None,
            error_message=None,
            retry_count=0,
            max_retries=3,
            created_at=datetime.utcnow().isoformat(),
            started_at=None,
            completed_at=None,
            next_job_id=None,
            parent_job_id=None
        )
        
        result = await orchestrator._execute_ingestion_job(job)
        
        assert "ingested_documents" in result
        assert "failed_ingestions" in result
        assert "total_ingested" in result
        assert "total_citations" in result
        assert "ingestion_rate" in result
        assert result["total_ingested"] >= 0
        assert result["total_citations"] >= 0
    
    @pytest.mark.asyncio
    async def test_execute_full_pipeline_job(self, orchestrator):
        """Test full pipeline job execution."""
        from services.orchestrator.research_orchestrator import PipelineJob
        
        job = PipelineJob(
            job_id="test-pipeline",
            job_type=JobType.FULL_PIPELINE.value,
            priority=JobPriority.MEDIUM.value,
            status=JobStatus.PENDING.value,
            input_data={
                "province": "guangdong",
                "asset_type": "solar",
                "doc_class": "grid_connection",
                "keywords": "分布式光伏",
                "max_results": 5
            },
            result_data=None,
            error_message=None,
            retry_count=0,
            max_retries=3,
            created_at=datetime.utcnow().isoformat(),
            started_at=None,
            completed_at=None,
            next_job_id=None,
            parent_job_id=None
        )
        
        result = await orchestrator._execute_full_pipeline_job(job)
        
        assert "discovery" in result
        assert "verification" in result
        assert "ingestion" in result
        assert "summary" in result
        
        # Check pipeline summary
        summary = result["summary"]
        assert "total_discovered" in summary
        assert "total_verified" in summary
        assert "total_ingested" in summary
        assert "pipeline_success_rate" in summary
    
    @pytest.mark.asyncio
    async def test_get_orchestrator_stats(self, orchestrator):
        """Test getting orchestrator statistics."""
        # Submit some jobs to generate stats
        discovery_request = DiscoveryJobRequest(
            province="guangdong",
            asset_type="solar",
            doc_class="grid_connection"
        )
        
        await orchestrator.submit_discovery_job(discovery_request)
        await orchestrator.submit_discovery_job(discovery_request)
        
        stats = await orchestrator.get_orchestrator_stats()
        
        assert "total_jobs" in stats
        assert "completed_jobs" in stats
        assert "failed_jobs" in stats
        assert "pending_jobs" in stats
        assert "running_jobs" in stats
        assert "queue_length" in stats
        assert "job_type_distribution" in stats
        assert "job_status_distribution" in stats
        assert "recent_activity" in stats
        
        assert stats["total_jobs"] >= 2
        assert stats["pending_jobs"] >= 2
    
    @pytest.mark.asyncio
    async def test_cleanup(self, orchestrator):
        """Test orchestrator cleanup."""
        # Submit a job
        discovery_request = DiscoveryJobRequest(
            province="guangdong",
            asset_type="solar",
            doc_class="grid_connection"
        )
        
        await orchestrator.submit_discovery_job(discovery_request)
        
        # Cleanup should not raise errors
        await orchestrator.cleanup()


class TestJobRequestModels:
    """Test job request model validation."""
    
    def test_discovery_job_request_valid(self):
        """Test valid discovery job request."""
        request = DiscoveryJobRequest(
            province="guangdong",
            asset_type="solar",
            doc_class="grid_connection",
            keywords="分布式光伏",
            priority=JobPriority.HIGH,
            max_results=20
        )
        
        assert request.province == "guangdong"
        assert request.asset_type == "solar"
        assert request.priority == JobPriority.HIGH
        assert request.max_results == 20
    
    def test_discovery_job_request_defaults(self):
        """Test discovery job request with defaults."""
        request = DiscoveryJobRequest(
            province="shandong",
            asset_type="wind",
            doc_class="market_rules"
        )
        
        assert request.priority == JobPriority.MEDIUM  # Default
        assert request.max_results == 10  # Default
        assert request.keywords is None  # Default
    
    def test_discovery_job_request_validation(self):
        """Test discovery job request validation."""
        from pydantic import ValidationError
        
        # Test invalid max_results
        with pytest.raises(ValidationError):
            DiscoveryJobRequest(
                province="guangdong",
                asset_type="solar",
                doc_class="grid_connection",
                max_results=100  # Too high
            )
        
        # Test empty province
        with pytest.raises(ValidationError):
            DiscoveryJobRequest(
                province="",
                asset_type="solar",
                doc_class="grid_connection"
            )
    
    def test_verification_job_request_valid(self):
        """Test valid verification job request."""
        request = VerificationJobRequest(
            candidate_urls=["https://test1.com", "https://test2.com"],
            province="guangdong",
            priority=JobPriority.HIGH
        )
        
        assert len(request.candidate_urls) == 2
        assert request.province == "guangdong"
        assert request.priority == JobPriority.HIGH
    
    def test_verification_job_request_validation(self):
        """Test verification job request validation."""
        from pydantic import ValidationError
        
        # Test empty candidate_urls
        with pytest.raises(ValidationError):
            VerificationJobRequest(
                candidate_urls=[],
                province="guangdong"
            )
    
    def test_ingestion_job_request_valid(self):
        """Test valid ingestion job request."""
        request = IngestionJobRequest(
            verified_urls=["https://verified1.com", "https://verified2.com"],
            province="guangdong",
            asset_type="solar",
            doc_class="grid_connection",
            priority=JobPriority.CRITICAL
        )
        
        assert len(request.verified_urls) == 2
        assert request.province == "guangdong"
        assert request.asset_type == "solar"
        assert request.priority == JobPriority.CRITICAL
    
    def test_ingestion_job_request_validation(self):
        """Test ingestion job request validation."""
        from pydantic import ValidationError
        
        # Test empty verified_urls
        with pytest.raises(ValidationError):
            IngestionJobRequest(
                verified_urls=[],
                province="guangdong",
                asset_type="solar",
                doc_class="grid_connection"
            )