"""Unit tests for document verification service."""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from services.verification.models import (
    VerificationCandidate, VerificationResult, VerificationStatus,
    VerificationMethod, VerificationMetrics, CSESearchResult
)
from services.verification.google_cse_client import (
    GoogleCSEClient, GoogleCSEConfig, CSERateLimiter, GoogleCSEMockClient
)
from services.verification.verification_service import (
    VerificationService, VerificationRequest, VerificationPipeline
)
from services.discovery.models import DocumentCandidate
from services.core.models import Province, DocumentClass, AssetType


class TestVerificationCandidate:
    """Test VerificationCandidate model."""
    
    @pytest.fixture
    def valid_candidate_data(self):
        """Valid candidate data for testing."""
        return {
            "original_url": "https://gzpec.cn/rules/solar-2025",
            "title": "广东省分布式光伏并网管理办法",
            "domain": "gzpec.cn",
            "discovery_confidence": 0.8,
            "verification_status": VerificationStatus.VERIFIED,
            "verification_method": VerificationMethod.GOOGLE_CSE,
            "canonical_url": "https://gzpec.cn/rules/solar-2025-final",
            "verified_title": "广东省分布式光伏并网管理办法（最新版）",
            "verification_confidence": 0.9,
            "http_status_code": 200
        }
    
    def test_valid_candidate_creation(self, valid_candidate_data):
        """Test creating valid verification candidate."""
        candidate = VerificationCandidate(**valid_candidate_data)
        
        assert candidate.original_url == "https://gzpec.cn/rules/solar-2025"
        assert candidate.verification_status == VerificationStatus.VERIFIED
        assert candidate.verification_method == VerificationMethod.GOOGLE_CSE
        assert candidate.verification_confidence == 0.9
    
    def test_is_verified(self, valid_candidate_data):
        """Test verification status checking."""
        # Verified candidate
        candidate = VerificationCandidate(**valid_candidate_data)
        assert candidate.is_verified() is True
        
        # Not verified candidate
        not_verified_data = valid_candidate_data.copy()
        not_verified_data["verification_status"] = VerificationStatus.NOT_FOUND
        candidate = VerificationCandidate(**not_verified_data)
        assert candidate.is_verified() is False
    
    def test_is_accessible(self, valid_candidate_data):
        """Test accessibility checking."""
        # Accessible candidate (HTTP 200)
        candidate = VerificationCandidate(**valid_candidate_data)
        assert candidate.is_accessible() is True
        
        # Not accessible candidate
        not_accessible_data = valid_candidate_data.copy()
        not_accessible_data["http_status_code"] = 404
        candidate = VerificationCandidate(**not_accessible_data)
        assert candidate.is_accessible() is False
    
    def test_get_final_url(self, valid_candidate_data):
        """Test final URL retrieval."""
        # With canonical URL
        candidate = VerificationCandidate(**valid_candidate_data)
        assert candidate.get_final_url() == "https://gzpec.cn/rules/solar-2025-final"
        
        # Without canonical URL
        no_canonical_data = valid_candidate_data.copy()
        no_canonical_data["canonical_url"] = None
        candidate = VerificationCandidate(**no_canonical_data)
        assert candidate.get_final_url() == "https://gzpec.cn/rules/solar-2025"
    
    def test_get_combined_confidence(self, valid_candidate_data):
        """Test combined confidence calculation."""
        candidate = VerificationCandidate(**valid_candidate_data)
        
        # Should weight verification confidence more heavily (70%)
        expected = (0.8 * 0.3) + (0.9 * 0.7)  # 0.24 + 0.63 = 0.87
        assert abs(candidate.get_combined_confidence() - expected) < 0.01
        
        # Not verified should return 0
        not_verified_data = valid_candidate_data.copy()
        not_verified_data["verification_status"] = VerificationStatus.FAILED
        candidate = VerificationCandidate(**not_verified_data)
        assert candidate.get_combined_confidence() == 0.0
class T
estCSESearchResult:
    """Test CSESearchResult model."""
    
    @pytest.fixture
    def sample_search_result(self):
        """Sample CSE search result."""
        return CSESearchResult(
            title="广东省光伏并网管理办法",
            link="https://gzpec.cn/rules/solar-grid",
            snippet="根据国家能源局相关规定，制定本办法...",
            display_link="gzpec.cn"
        )
    
    def test_extract_domain(self, sample_search_result):
        """Test domain extraction from link."""
        domain = sample_search_result.extract_domain()
        assert domain == "gzpec.cn"
    
    def test_calculate_relevance_score_exact_match(self, sample_search_result):
        """Test relevance score for exact URL match."""
        score = sample_search_result.calculate_relevance_score(
            "https://gzpec.cn/rules/solar-grid",
            "广东省光伏并网管理办法"
        )
        
        # Should get high score for exact URL match + title match
        assert score > 0.7
    
    def test_calculate_relevance_score_domain_match(self, sample_search_result):
        """Test relevance score for domain match."""
        score = sample_search_result.calculate_relevance_score(
            "https://gzpec.cn/different/path",
            "Different Title"
        )
        
        # Should get moderate score for domain match
        assert 0.1 < score < 0.5
    
    def test_calculate_relevance_score_no_match(self, sample_search_result):
        """Test relevance score for no match."""
        score = sample_search_result.calculate_relevance_score(
            "https://different-domain.com/path",
            "Completely Different Title"
        )
        
        # Should get low score but not zero (due to snippet energy terms)
        assert 0.0 <= score < 0.3


class TestCSERateLimiter:
    """Test CSERateLimiter functionality."""
    
    @pytest.mark.asyncio
    async def test_rate_limiter_allows_requests(self):
        """Test rate limiter allows requests within limits."""
        limiter = CSERateLimiter(requests_per_day=10, requests_per_100_seconds=5)
        
        # Should allow first 5 requests (100-second limit)
        for _ in range(5):
            assert await limiter.acquire() is True
        
        # Should deny 6th request (100-second limit exceeded)
        assert await limiter.acquire() is False
    
    @pytest.mark.asyncio
    async def test_rate_limiter_daily_limit(self):
        """Test daily rate limit."""
        limiter = CSERateLimiter(requests_per_day=2, requests_per_100_seconds=10)
        
        # Should allow first 2 requests
        assert await limiter.acquire() is True
        assert await limiter.acquire() is True
        
        # Should deny 3rd request (daily limit exceeded)
        assert await limiter.acquire() is False
    
    def test_get_remaining_quota(self):
        """Test quota tracking."""
        limiter = CSERateLimiter(requests_per_day=10, requests_per_100_seconds=5)
        
        # Add some requests
        import time
        now = time.time()
        limiter.daily_requests = [now, now - 100]
        limiter.recent_requests = [now, now - 50]
        
        quota = limiter.get_remaining_quota()
        
        assert quota["daily_remaining"] == 8  # 10 - 2
        assert quota["recent_remaining"] == 3  # 5 - 2


class TestGoogleCSEClient:
    """Test GoogleCSEClient functionality."""
    
    @pytest.fixture
    def mock_config(self):
        """Mock Google CSE configuration."""
        return GoogleCSEConfig(
            api_key="test_key",
            cse_id="test_cse_id",
            timeout=30,
            max_retries=2,
            requests_per_day=100,
            requests_per_100_seconds=10
        )
    
    @pytest.fixture
    def mock_client(self, mock_config):
        """Mock Google CSE client."""
        return GoogleCSEClient(mock_config)
    
    @pytest.mark.asyncio
    async def test_verify_document_success(self, mock_client):
        """Test successful document verification."""
        mock_search_results = [
            CSESearchResult(
                title="Test Document",
                link="https://gzpec.cn/test-doc",
                snippet="Test snippet",
                display_link="gzpec.cn"
            )
        ]
        
        with patch.object(mock_client, '_search_with_retries', return_value=mock_search_results):
            result = await mock_client.verify_document(
                "https://gzpec.cn/test-doc",
                [".gov.cn", "gzpec.cn"],
                "Test Document"
            )
        
        assert result.verification_status == VerificationStatus.VERIFIED
        assert result.canonical_url == "https://gzpec.cn/test-doc"
        assert result.verification_method == VerificationMethod.GOOGLE_CSE
    
    @pytest.mark.asyncio
    async def test_verify_document_not_found(self, mock_client):
        """Test document not found in verification."""
        # Mock empty search results
        with patch.object(mock_client, '_search_with_retries', return_value=[]):
            result = await mock_client.verify_document(
                "https://gzpec.cn/nonexistent",
                [".gov.cn", "gzpec.cn"]
            )
        
        assert result.verification_status == VerificationStatus.NOT_FOUND
        assert result.verification_method == VerificationMethod.GOOGLE_CSE
    
    @pytest.mark.asyncio
    async def test_verify_document_rate_limited(self, mock_client):
        """Test rate limited verification."""
        # Mock rate limiter to deny requests
        with patch.object(mock_client.rate_limiter, 'acquire', return_value=False):
            result = await mock_client.verify_document(
                "https://gzpec.cn/test",
                [".gov.cn", "gzpec.cn"]
            )
        
        assert result.verification_status == VerificationStatus.RATE_LIMITED
    
    @pytest.mark.asyncio
    async def test_verify_documents_batch(self, mock_client):
        """Test batch document verification."""
        candidates = [
            {"url": "https://gzpec.cn/doc1", "title": "Doc 1", "confidence_score": 0.8},
            {"url": "https://gzpec.cn/doc2", "title": "Doc 2", "confidence_score": 0.7}
        ]
        
        # Mock individual verification
        mock_result = VerificationCandidate(
            original_url="https://gzpec.cn/doc1",
            domain="gzpec.cn",
            verification_status=VerificationStatus.VERIFIED
        )
        
        with patch.object(mock_client, 'verify_document', return_value=mock_result):
            results = await mock_client.verify_documents_batch(
                candidates, [".gov.cn", "gzpec.cn"], batch_delay=0.1
            )
        
        assert len(results) == 2
        assert all(isinstance(r, VerificationCandidate) for r in results)
    
    def test_build_verification_query(self, mock_client):
        """Test verification query building."""
        query = mock_client._build_verification_query(
            "https://gzpec.cn/rules/solar/2025/management",
            "广东省光伏管理办法"
        )
        
        # Should include site restriction
        assert "site:gzpec.cn" in query
        
        # Should include path components
        assert any(part in query for part in ["rules", "solar", "2025", "management"])
        
        # Should include title words
        assert any(word in query for word in ["广东省", "光伏", "管理办法"])
    
    def test_extract_domain(self, mock_client):
        """Test domain extraction."""
        domain = mock_client._extract_domain("https://gzpec.cn/path/to/doc")
        assert domain == "gzpec.cn"
        
        domain = mock_client._extract_domain("http://subdomain.example.com:8080/path")
        assert domain == "subdomain.example.com:8080"
    
    def test_is_domain_allowed(self, mock_client):
        """Test domain allowlist checking."""
        allowlist = [".gov.cn", "gzpec.cn", "example.com"]
        
        # Exact match
        assert mock_client._is_domain_allowed("gzpec.cn", allowlist) is True
        
        # Suffix match
        assert mock_client._is_domain_allowed("beijing.gov.cn", allowlist) is True
        
        # Subdomain match
        assert mock_client._is_domain_allowed("sub.example.com", allowlist) is True
        
        # No match
        assert mock_client._is_domain_allowed("notallowed.com", allowlist) is False


class TestGoogleCSEMockClient:
    """Test GoogleCSEMockClient functionality."""
    
    @pytest.mark.asyncio
    async def test_mock_verify_document_official_domain(self):
        """Test mock verification for official domains."""
        mock_client = GoogleCSEMockClient()
        
        result = await mock_client.verify_document(
            "https://gzpec.cn/test-doc",
            [".gov.cn", "gzpec.cn"],
            "Test Document"
        )
        
        assert result.verification_status == VerificationStatus.VERIFIED
        assert result.verification_method == VerificationMethod.GOOGLE_CSE
        assert result.canonical_url == "https://gzpec.cn/test-doc"
        assert result.verification_confidence == 0.85
    
    @pytest.mark.asyncio
    async def test_mock_verify_document_non_official_domain(self):
        """Test mock verification for non-official domains."""
        mock_client = GoogleCSEMockClient()
        
        result = await mock_client.verify_document(
            "https://example.com/test-doc",
            [".gov.cn", "gzpec.cn"]
        )
        
        assert result.verification_status == VerificationStatus.NOT_FOUND
        assert "not found in mock search" in result.error_message
    
    @pytest.mark.asyncio
    async def test_mock_search_documents(self):
        """Test mock document search."""
        mock_client = GoogleCSEMockClient()
        
        results = await mock_client.search_documents(
            "energy regulations",
            ["gzpec.cn"],
            max_results=5
        )
        
        assert len(results) > 0
        assert all(isinstance(r, CSESearchResult) for r in results)
        assert all("gzpec.cn" in r.link for r in results)


class TestVerificationService:
    """Test VerificationService functionality."""
    
    @pytest.fixture
    def mock_cse_client(self):
        """Mock Google CSE client."""
        return GoogleCSEMockClient()
    
    @pytest.fixture
    def mock_registry_manager(self):
        """Mock registry manager."""
        manager = AsyncMock()
        manager.initialize = AsyncMock()
        manager.get_sources_for_province = AsyncMock(return_value=[])
        manager.get_registry_health = AsyncMock(return_value={
            "overall_status": "healthy",
            "summary": {"total_sources": 5}
        })
        return manager
    
    @pytest.fixture
    def verification_service(self, mock_cse_client, mock_registry_manager):
        """Verification service with mocked dependencies."""
        return VerificationService(
            google_cse_client=mock_cse_client,
            registry_manager=mock_registry_manager
        )
    
    @pytest.mark.asyncio
    async def test_initialize(self, verification_service):
        """Test verification service initialization."""
        await verification_service.initialize()
        
        # Should initialize registry manager
        verification_service.registry_manager.initialize.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_verify_documents(self, verification_service):
        """Test document verification."""
        # Create test candidates
        candidates = [
            DocumentCandidate(
                url="https://gzpec.cn/rules/solar",
                title="Solar Rules",
                domain="gzpec.cn",
                confidence_score=0.8
            ),
            DocumentCandidate(
                url="https://shandong-electric.com.cn/wind",
                title="Wind Rules", 
                domain="shandong-electric.com.cn",
                confidence_score=0.7
            )
        ]
        
        request = VerificationRequest(
            candidates=candidates,
            province=Province.GUANGDONG,
            doc_class=DocumentClass.GRID_CONNECTION,
            domain_allowlist=[".gov.cn", "gzpec.cn", "shandong-electric.com.cn"]
        )
        
        result = await verification_service.verify_documents(request)
        
        assert result.status == VerificationStatus.VERIFIED
        assert result.request_id == request.request_id
        assert result.total_candidates == 2
        assert result.verified_candidates > 0
    
    @pytest.mark.asyncio
    async def test_verify_single_document(self, verification_service):
        """Test single document verification."""
        result = await verification_service.verify_single_document(
            "https://gzpec.cn/test-doc",
            "Test Document",
            [".gov.cn", "gzpec.cn"]
        )
        
        assert isinstance(result, VerificationCandidate)
        assert result.original_url == "https://gzpec.cn/test-doc"
    
    @pytest.mark.asyncio
    async def test_search_and_verify(self, verification_service):
        """Test search and verify functionality."""
        results = await verification_service.search_and_verify(
            "energy regulations guangdong",
            [".gov.cn", "gzpec.cn"],
            max_results=5
        )
        
        assert isinstance(results, list)
        assert all(isinstance(r, VerificationCandidate) for r in results)
        assert all(r.verification_status == VerificationStatus.VERIFIED for r in results)
    
    @pytest.mark.asyncio
    async def test_get_verification_metrics(self, verification_service):
        """Test verification metrics retrieval."""
        # Perform a verification to generate metrics
        candidates = [
            DocumentCandidate(
                url="https://gzpec.cn/test",
                domain="gzpec.cn",
                confidence_score=0.8
            )
        ]
        
        request = VerificationRequest(candidates=candidates)
        await verification_service.verify_documents(request)
        
        metrics = await verification_service.get_verification_metrics()
        
        assert metrics["total_requests"] == 1
        assert "success_rate" in metrics
        assert "overall_verification_rate" in metrics
        assert "method_distribution" in metrics
    
    @pytest.mark.asyncio
    async def test_health_check(self, verification_service):
        """Test verification service health check."""
        health = await verification_service.health_check()
        
        assert health["service"] == "verification"
        assert health["status"] in ["healthy", "degraded", "unhealthy"]
        assert "components" in health
        assert "google_cse" in health["components"]
        assert "registry" in health["components"]


class TestVerificationResult:
    """Test VerificationResult model."""
    
    @pytest.fixture
    def sample_candidates(self):
        """Sample verification candidates."""
        return [
            VerificationCandidate(
                original_url="https://gzpec.cn/doc1",
                domain="gzpec.cn",
                verification_status=VerificationStatus.VERIFIED,
                discovery_confidence=0.8,
                verification_confidence=0.9
            ),
            VerificationCandidate(
                original_url="https://example.com/doc2",
                domain="example.com",
                verification_status=VerificationStatus.NOT_FOUND,
                discovery_confidence=0.6,
                verification_confidence=0.0
            ),
            VerificationCandidate(
                original_url="https://gzpec.cn/doc3",
                domain="gzpec.cn",
                verification_status=VerificationStatus.VERIFIED,
                discovery_confidence=0.7,
                verification_confidence=0.8
            )
        ]
    
    def test_get_verified_candidates(self, sample_candidates):
        """Test filtering verified candidates."""
        result = VerificationResult(
            request_id=uuid4(),
            status=VerificationStatus.VERIFIED,
            candidates=sample_candidates
        )
        
        verified = result.get_verified_candidates()
        assert len(verified) == 2  # Only verified candidates
        assert all(c.is_verified() for c in verified)
    
    def test_get_high_confidence_candidates(self, sample_candidates):
        """Test filtering high confidence candidates."""
        result = VerificationResult(
            request_id=uuid4(),
            status=VerificationStatus.VERIFIED,
            candidates=sample_candidates
        )
        
        high_confidence = result.get_high_confidence_candidates(threshold=0.8)
        
        # Should include candidates with combined confidence >= 0.8
        assert len(high_confidence) >= 1
        assert all(c.get_combined_confidence() >= 0.8 for c in high_confidence)
    
    def test_sort_by_confidence(self, sample_candidates):
        """Test sorting candidates by confidence."""
        result = VerificationResult(
            request_id=uuid4(),
            status=VerificationStatus.VERIFIED,
            candidates=sample_candidates
        )
        
        sorted_candidates = result.sort_by_confidence()
        
        # Should be sorted in descending order of combined confidence
        for i in range(len(sorted_candidates) - 1):
            assert sorted_candidates[i].get_combined_confidence() >= sorted_candidates[i + 1].get_combined_confidence()
    
    def test_get_verification_rate(self, sample_candidates):
        """Test verification rate calculation."""
        result = VerificationResult(
            request_id=uuid4(),
            status=VerificationStatus.VERIFIED,
            candidates=sample_candidates,
            total_candidates=3,
            verified_candidates=2
        )
        
        rate = result.get_verification_rate()
        assert rate == 2/3  # 2 verified out of 3 total


class TestVerificationMetrics:
    """Test VerificationMetrics functionality."""
    
    def test_update_with_successful_result(self):
        """Test updating metrics with successful result."""
        metrics = VerificationMetrics()
        
        result = VerificationResult(
            request_id=uuid4(),
            status=VerificationStatus.VERIFIED,
            total_candidates=5,
            verified_candidates=4,
            not_found_candidates=1,
            failed_candidates=0,
            processing_time_ms=1000
        )
        
        metrics.update_with_result(result)
        
        assert metrics.total_requests == 1
        assert metrics.successful_requests == 1
        assert metrics.total_candidates_processed == 5
        assert metrics.verified_candidates == 4
        assert metrics.avg_processing_time_ms == 1000
    
    def test_get_success_rate(self):
        """Test success rate calculation."""
        metrics = VerificationMetrics()
        
        # No requests yet
        assert metrics.get_success_rate() == 0.0
        
        # Add some requests
        metrics.total_requests = 10
        metrics.successful_requests = 8
        
        assert metrics.get_success_rate() == 0.8
    
    def test_get_overall_verification_rate(self):
        """Test overall verification rate calculation."""
        metrics = VerificationMetrics()
        
        # No candidates yet
        assert metrics.get_overall_verification_rate() == 0.0
        
        # Add candidates
        metrics.total_candidates_processed = 20
        metrics.verified_candidates = 15
        
        assert metrics.get_overall_verification_rate() == 0.75


if __name__ == "__main__":
    pytest.main([__file__])