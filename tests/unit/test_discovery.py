"""Unit tests for document discovery service."""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from services.discovery.models import (
    DocumentCandidate, DiscoveryQuery, DiscoveryResult, DiscoveryStatus,
    DiscoveryMetrics
)
from services.discovery.perplexity_client import (
    PerplexityClient, PerplexityConfig, RateLimiter, PerplexityMockClient
)
from services.discovery.discovery_service import (
    DiscoveryService, DiscoveryRequest, DiscoveryScheduler
)
from services.core.models import Province, DocumentClass, AssetType


class TestDocumentCandidate:
    """Test DocumentCandidate model."""
    
    @pytest.fixture
    def valid_candidate_data(self):
        """Valid candidate data for testing."""
        return {
            "url": "https://gzpec.cn/rules/solar-2025",
            "title": "广东省分布式光伏并网管理办法",
            "snippet": "根据国家能源局相关规定...",
            "domain": "gzpec.cn",
            "confidence_score": 0.85
        }
    
    def test_valid_candidate_creation(self, valid_candidate_data):
        """Test creating valid document candidate."""
        candidate = DocumentCandidate(**valid_candidate_data)
        
        assert candidate.url == "https://gzpec.cn/rules/solar-2025"
        assert candidate.title == "广东省分布式光伏并网管理办法"
        assert candidate.domain == "gzpec.cn"
        assert candidate.confidence_score == 0.85
        assert candidate.source == "perplexity"
    
    def test_url_validation(self, valid_candidate_data):
        """Test URL format validation."""
        # Valid URLs
        candidate = DocumentCandidate(**valid_candidate_data)
        assert candidate.url.startswith("https://")
        
        # Invalid URL
        with pytest.raises(ValueError, match="URL must start with"):
            invalid_data = valid_candidate_data.copy()
            invalid_data["url"] = "invalid-url"
            DocumentCandidate(**invalid_data)
    
    def test_domain_validation(self, valid_candidate_data):
        """Test domain format validation."""
        # Valid domain
        candidate = DocumentCandidate(**valid_candidate_data)
        assert "." in candidate.domain
        
        # Invalid domain
        with pytest.raises(ValueError, match="Domain must be valid"):
            invalid_data = valid_candidate_data.copy()
            invalid_data["domain"] = "invalid"
            DocumentCandidate(**invalid_data)
    
    def test_is_official_domain(self, valid_candidate_data):
        """Test official domain checking."""
        # Official domain
        candidate = DocumentCandidate(**valid_candidate_data)
        assert candidate.is_official_domain() is True
        
        # Non-official domain
        non_official_data = valid_candidate_data.copy()
        non_official_data["domain"] = "example.com"
        candidate = DocumentCandidate(**non_official_data)
        assert candidate.is_official_domain() is False
    
    def test_extract_potential_date(self, valid_candidate_data):
        """Test date extraction from URL/title."""
        # URL with date
        date_url_data = valid_candidate_data.copy()
        date_url_data["url"] = "https://gzpec.cn/rules/2025-03-01/solar"
        candidate = DocumentCandidate(**date_url_data)
        
        extracted_date = candidate.extract_potential_date()
        assert extracted_date == "2025-03-01"
        
        # Title with Chinese date
        chinese_date_data = valid_candidate_data.copy()
        chinese_date_data["title"] = "2025年3月1日发布的管理办法"
        candidate = DocumentCandidate(**chinese_date_data)
        
        extracted_date = candidate.extract_potential_date()
        assert "2025年3月1日" in extracted_date


class TestDiscoveryQuery:
    """Test DiscoveryQuery model."""
    
    @pytest.fixture
    def valid_query_data(self):
        """Valid query data for testing."""
        return {
            "province": Province.GUANGDONG,
            "doc_class": DocumentClass.GRID_CONNECTION,
            "asset": AssetType.SOLAR,
            "keywords": ["分布式", "光伏"],
            "max_results": 20
        }
    
    def test_valid_query_creation(self, valid_query_data):
        """Test creating valid discovery query."""
        query = DiscoveryQuery(**valid_query_data)
        
        assert query.province == Province.GUANGDONG
        assert query.doc_class == DocumentClass.GRID_CONNECTION
        assert query.asset == AssetType.SOLAR
        assert "分布式" in query.keywords
        assert query.max_results == 20
    
    def test_generate_search_query(self, valid_query_data):
        """Test search query generation."""
        query = DiscoveryQuery(**valid_query_data)
        search_query = query.generate_search_query()
        
        # Should contain province terms
        assert any(term in search_query for term in ["广东", "粤"])
        
        # Should contain doc class terms
        assert any(term in search_query for term in ["并网", "接入"])
        
        # Should contain asset terms
        assert any(term in search_query for term in ["光伏", "太阳能"])
        
        # Should contain custom keywords
        assert "分布式" in search_query
        
        # Should contain regulatory terms
        assert any(term in search_query for term in ["规定", "办法"])
    
    def test_get_domain_allowlist(self, valid_query_data):
        """Test domain allowlist generation."""
        query = DiscoveryQuery(**valid_query_data)
        allowlist = query.get_domain_allowlist()
        
        # Should contain base domains
        assert ".gov.cn" in allowlist
        
        # Should contain province-specific domains
        assert any("gzpec.cn" in domain or "gdpec.com.cn" in domain for domain in allowlist)
    
    def test_date_range_in_search_query(self, valid_query_data):
        """Test date range inclusion in search query."""
        query_data = valid_query_data.copy()
        query_data["date_range"] = {
            "start_date": "2025-01-01",
            "end_date": "2025-12-31"
        }
        
        query = DiscoveryQuery(**query_data)
        search_query = query.generate_search_query()
        
        assert "after:2025-01-01" in search_query
        assert "before:2025-12-31" in search_query


class TestDiscoveryResult:
    """Test DiscoveryResult model."""
    
    @pytest.fixture
    def sample_candidates(self):
        """Sample candidates for testing."""
        return [
            DocumentCandidate(
                url="https://gzpec.cn/rules/solar",
                title="Solar Rules",
                domain="gzpec.cn",
                confidence_score=0.9
            ),
            DocumentCandidate(
                url="https://example.com/test",
                title="Test Document",
                domain="example.com",
                confidence_score=0.6
            ),
            DocumentCandidate(
                url="https://shandong-electric.com.cn/wind",
                title="Wind Rules",
                domain="shandong-electric.com.cn",
                confidence_score=0.8
            )
        ]
    
    def test_get_official_candidates(self, sample_candidates):
        """Test filtering official candidates."""
        result = DiscoveryResult(
            query_id=uuid4(),
            status=DiscoveryStatus.COMPLETED,
            candidates=sample_candidates
        )
        
        official_candidates = result.get_official_candidates()
        
        # Should filter out example.com
        assert len(official_candidates) == 2
        assert all(c.is_official_domain() for c in official_candidates)
    
    def test_get_candidates_by_domain(self, sample_candidates):
        """Test filtering candidates by domain."""
        result = DiscoveryResult(
            query_id=uuid4(),
            status=DiscoveryStatus.COMPLETED,
            candidates=sample_candidates
        )
        
        gzpec_candidates = result.get_candidates_by_domain("gzpec.cn")
        assert len(gzpec_candidates) == 1
        assert gzpec_candidates[0].domain == "gzpec.cn"
    
    def test_get_high_confidence_candidates(self, sample_candidates):
        """Test filtering high confidence candidates."""
        result = DiscoveryResult(
            query_id=uuid4(),
            status=DiscoveryStatus.COMPLETED,
            candidates=sample_candidates
        )
        
        high_confidence = result.get_high_confidence_candidates(threshold=0.7)
        assert len(high_confidence) == 2  # 0.9 and 0.8 scores
        assert all(c.confidence_score >= 0.7 for c in high_confidence)
    
    def test_sort_by_confidence(self, sample_candidates):
        """Test sorting candidates by confidence."""
        result = DiscoveryResult(
            query_id=uuid4(),
            status=DiscoveryStatus.COMPLETED,
            candidates=sample_candidates
        )
        
        sorted_candidates = result.sort_by_confidence()
        
        # Should be sorted in descending order
        assert sorted_candidates[0].confidence_score == 0.9
        assert sorted_candidates[1].confidence_score == 0.8
        assert sorted_candidates[2].confidence_score == 0.6
    
    def test_get_summary(self, sample_candidates):
        """Test result summary generation."""
        result = DiscoveryResult(
            query_id=uuid4(),
            status=DiscoveryStatus.COMPLETED,
            candidates=sample_candidates,
            processing_time_ms=500
        )
        
        summary = result.get_summary()
        
        assert summary["total_candidates"] == 3
        assert summary["official_candidates"] == 2
        assert summary["processing_time_ms"] == 500
        assert len(summary["domains_found"]) == 3
        assert summary["avg_confidence"] > 0


class TestRateLimiter:
    """Test RateLimiter functionality."""
    
    @pytest.mark.asyncio
    async def test_rate_limiter_allows_requests(self):
        """Test rate limiter allows requests within limit."""
        limiter = RateLimiter(requests_per_minute=5)
        
        # Should allow first 5 requests
        for _ in range(5):
            assert await limiter.acquire() is True
        
        # Should deny 6th request
        assert await limiter.acquire() is False
    
    @pytest.mark.asyncio
    async def test_rate_limiter_resets(self):
        """Test rate limiter resets after time window."""
        limiter = RateLimiter(requests_per_minute=2)
        
        # Use up the limit
        assert await limiter.acquire() is True
        assert await limiter.acquire() is True
        assert await limiter.acquire() is False
        
        # Mock time passage
        import time
        with patch('time.time') as mock_time:
            mock_time.return_value = time.time() + 61  # 61 seconds later
            
            # Should allow requests again
            assert await limiter.acquire() is True
    
    def test_get_reset_time(self):
        """Test reset time calculation."""
        limiter = RateLimiter(requests_per_minute=5)
        
        # No requests yet
        assert limiter.get_reset_time() is None
        
        # Add a request
        import time
        limiter.requests.append(time.time())
        
        reset_time = limiter.get_reset_time()
        assert reset_time is not None
        assert isinstance(reset_time, datetime)


class TestPerplexityClient:
    """Test PerplexityClient functionality."""
    
    @pytest.fixture
    def mock_config(self):
        """Mock Perplexity configuration."""
        return PerplexityConfig(
            api_key="test_key",
            timeout=30,
            max_retries=2,
            rate_limit_requests_per_minute=10
        )
    
    @pytest.fixture
    def mock_client(self, mock_config):
        """Mock Perplexity client."""
        return PerplexityClient(mock_config)
    
    @pytest.mark.asyncio
    async def test_search_documents_success(self, mock_client):
        """Test successful document search."""
        mock_response = {
            "choices": [{
                "message": {
                    "content": "1. 广东省光伏管理办法: https://gzpec.cn/rules/solar\n2. 山东风电规定: https://shandong-electric.com.cn/wind"
                }
            }]
        }
        
        with patch.object(mock_client, '_make_request_with_retries', return_value=mock_response):
            result = await mock_client.search_documents(
                query="光伏并网规定",
                domain_filter=[".gov.cn", "gzpec.cn"],
                max_results=10
            )
        
        assert result.status == DiscoveryStatus.COMPLETED
        assert len(result.candidates) > 0
        assert result.processing_time_ms is not None
    
    @pytest.mark.asyncio
    async def test_search_documents_rate_limited(self, mock_client):
        """Test rate limited response."""
        # Mock rate limiter to deny requests
        with patch.object(mock_client.rate_limiter, 'acquire', return_value=False):
            result = await mock_client.search_documents(
                query="test query",
                domain_filter=[".gov.cn"],
                max_results=10
            )
        
        assert result.status == DiscoveryStatus.RATE_LIMITED
        assert result.rate_limit_reset_at is not None
    
    @pytest.mark.asyncio
    async def test_health_check(self, mock_client):
        """Test health check functionality."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status.return_value = None
        
        with patch.object(mock_client.client, 'post', return_value=mock_response):
            health = await mock_client.health_check()
        
        assert health["status"] == "healthy"
        assert "latency_ms" in health
        assert "rate_limit_remaining" in health
    
    def test_build_search_prompt(self, mock_client):
        """Test search prompt building."""
        prompt = mock_client._build_search_prompt(
            "光伏并网规定",
            [".gov.cn", "gzpec.cn"]
        )
        
        assert "光伏并网规定" in prompt
        assert "official" in prompt.lower()
        assert "gzpec.cn" in prompt
    
    def test_extract_domain(self, mock_client):
        """Test domain extraction from URL."""
        domain = mock_client._extract_domain("https://gzpec.cn/rules/solar")
        assert domain == "gzpec.cn"
        
        domain = mock_client._extract_domain("http://subdomain.example.com:8080/path")
        assert domain == "subdomain.example.com:8080"
    
    def test_is_domain_allowed(self, mock_client):
        """Test domain allowlist checking."""
        domain_filter = [".gov.cn", "gzpec.cn", "example.com"]
        
        # Exact match
        assert mock_client._is_domain_allowed("gzpec.cn", domain_filter) is True
        
        # Suffix match
        assert mock_client._is_domain_allowed("beijing.gov.cn", domain_filter) is True
        
        # Subdomain match
        assert mock_client._is_domain_allowed("sub.example.com", domain_filter) is True
        
        # No match
        assert mock_client._is_domain_allowed("notallowed.com", domain_filter) is False


class TestPerplexityMockClient:
    """Test PerplexityMockClient functionality."""
    
    @pytest.mark.asyncio
    async def test_mock_search_documents(self):
        """Test mock client search functionality."""
        mock_client = PerplexityMockClient()
        
        result = await mock_client.search_documents(
            query="test query",
            domain_filter=["gzpec.cn"],
            max_results=10
        )
        
        assert result.status == DiscoveryStatus.COMPLETED
        assert len(result.candidates) > 0
        assert result.processing_time_ms == 100
        
        # Should filter by domain
        gzpec_candidates = [c for c in result.candidates if "gzpec.cn" in c.domain]
        assert len(gzpec_candidates) > 0
    
    @pytest.mark.asyncio
    async def test_mock_health_check(self):
        """Test mock health check."""
        mock_client = PerplexityMockClient()
        
        health = await mock_client.health_check()
        
        assert health["status"] == "healthy"
        assert health["latency_ms"] == 50


class TestDiscoveryService:
    """Test DiscoveryService functionality."""
    
    @pytest.fixture
    def mock_perplexity_client(self):
        """Mock Perplexity client."""
        return PerplexityMockClient()
    
    @pytest.fixture
    def mock_registry_manager(self):
        """Mock registry manager."""
        manager = AsyncMock()
        manager.initialize = AsyncMock()
        manager.get_sources_for_province = AsyncMock(return_value=[])
        manager.get_priority_sources_for_asset = AsyncMock(return_value=[])
        manager.get_registry_health = AsyncMock(return_value={
            "overall_status": "healthy",
            "summary": {"total_sources": 5}
        })
        return manager
    
    @pytest.fixture
    def discovery_service(self, mock_perplexity_client, mock_registry_manager):
        """Discovery service with mocked dependencies."""
        return DiscoveryService(
            perplexity_client=mock_perplexity_client,
            registry_manager=mock_registry_manager
        )
    
    @pytest.mark.asyncio
    async def test_initialize(self, discovery_service):
        """Test discovery service initialization."""
        await discovery_service.initialize()
        
        # Should initialize registry manager
        discovery_service.registry_manager.initialize.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_discover_documents(self, discovery_service):
        """Test document discovery."""
        request = DiscoveryRequest(
            province=Province.GUANGDONG,
            doc_class=DocumentClass.GRID_CONNECTION,
            asset=AssetType.SOLAR,
            keywords=["光伏"],
            max_results=10
        )
        
        result = await discovery_service.discover_documents(request)
        
        assert result.status == DiscoveryStatus.COMPLETED
        assert result.query_id == request.request_id
        assert len(result.candidates) > 0
    
    @pytest.mark.asyncio
    async def test_discover_for_province_and_asset(self, discovery_service):
        """Test comprehensive discovery for province/asset."""
        results = await discovery_service.discover_for_province_and_asset(
            Province.GUANGDONG,
            AssetType.SOLAR
        )
        
        assert len(results) > 0
        assert all(isinstance(r, DiscoveryResult) for r in results)
    
    @pytest.mark.asyncio
    async def test_get_discovery_metrics(self, discovery_service):
        """Test discovery metrics retrieval."""
        # Perform a discovery to generate metrics
        request = DiscoveryRequest(
            province=Province.GUANGDONG,
            doc_class=DocumentClass.GRID_CONNECTION
        )
        await discovery_service.discover_documents(request)
        
        metrics = await discovery_service.get_discovery_metrics()
        
        assert metrics["total_queries"] == 1
        assert metrics["successful_queries"] == 1
        assert "success_rate" in metrics
        assert "avg_processing_time_ms" in metrics
    
    @pytest.mark.asyncio
    async def test_health_check(self, discovery_service):
        """Test discovery service health check."""
        health = await discovery_service.health_check()
        
        assert health["service"] == "discovery"
        assert health["status"] in ["healthy", "degraded", "unhealthy"]
        assert "components" in health
        assert "perplexity" in health["components"]
        assert "registry" in health["components"]
    
    @pytest.mark.asyncio
    async def test_get_discovery_status(self, discovery_service):
        """Test getting discovery status for active queries."""
        # No active queries initially
        status = await discovery_service.get_discovery_status(uuid4())
        assert status is None
        
        # Mock active query
        query_id = uuid4()
        mock_query = DiscoveryQuery(
            query_id=query_id,
            province=Province.GUANGDONG,
            doc_class=DocumentClass.GRID_CONNECTION
        )
        discovery_service._active_queries[query_id] = mock_query
        
        status = await discovery_service.get_discovery_status(query_id)
        assert status is not None
        assert status["query_id"] == str(query_id)
        assert status["status"] == "running"


class TestDiscoveryScheduler:
    """Test DiscoveryScheduler functionality."""
    
    @pytest.fixture
    def mock_discovery_service(self):
        """Mock discovery service."""
        service = AsyncMock()
        service.discover_for_province_and_asset = AsyncMock(return_value=[
            DiscoveryResult(
                query_id=uuid4(),
                status=DiscoveryStatus.COMPLETED,
                candidates=[]
            )
        ])
        return service
    
    @pytest.fixture
    def scheduler(self, mock_discovery_service):
        """Discovery scheduler with mocked service."""
        return DiscoveryScheduler(mock_discovery_service)
    
    @pytest.mark.asyncio
    async def test_start_scheduled_discovery(self, scheduler):
        """Test starting scheduled discovery."""
        # Mock Province.enabled_provinces to return limited set for testing
        with patch.object(Province, 'enabled_provinces', return_value=[Province.GUANGDONG]):
            await scheduler.start_scheduled_discovery()
        
        # Should have called discovery for each asset type
        assert scheduler.discovery_service.discover_for_province_and_asset.call_count == len(AssetType)
    
    @pytest.mark.asyncio
    async def test_stop_scheduled_discovery(self, scheduler):
        """Test stopping scheduled discovery."""
        # Start discovery in background
        discovery_task = asyncio.create_task(scheduler.start_scheduled_discovery())
        
        # Give it a moment to start
        await asyncio.sleep(0.1)
        
        # Stop discovery
        await scheduler.stop_scheduled_discovery()
        
        # Task should be cancelled
        assert discovery_task.cancelled() or discovery_task.done()


class TestDiscoveryMetrics:
    """Test DiscoveryMetrics functionality."""
    
    def test_update_with_successful_result(self):
        """Test updating metrics with successful result."""
        metrics = DiscoveryMetrics()
        
        result = DiscoveryResult(
            query_id=uuid4(),
            status=DiscoveryStatus.COMPLETED,
            candidates=[
                DocumentCandidate(
                    url="https://gzpec.cn/test",
                    domain="gzpec.cn",
                    confidence_score=0.8
                )
            ],
            processing_time_ms=500
        )
        
        metrics.update_with_result(result)
        
        assert metrics.total_queries == 1
        assert metrics.successful_queries == 1
        assert metrics.failed_queries == 0
        assert metrics.avg_processing_time_ms == 500
        assert metrics.total_candidates_found == 1
    
    def test_update_with_failed_result(self):
        """Test updating metrics with failed result."""
        metrics = DiscoveryMetrics()
        
        result = DiscoveryResult(
            query_id=uuid4(),
            status=DiscoveryStatus.FAILED,
            error_message="Test error"
        )
        
        metrics.update_with_result(result)
        
        assert metrics.total_queries == 1
        assert metrics.successful_queries == 0
        assert metrics.failed_queries == 1
    
    def test_get_success_rate(self):
        """Test success rate calculation."""
        metrics = DiscoveryMetrics()
        
        # No queries yet
        assert metrics.get_success_rate() == 0.0
        
        # Add successful and failed queries
        metrics.total_queries = 10
        metrics.successful_queries = 8
        
        assert metrics.get_success_rate() == 0.8
    
    def test_get_official_candidate_ratio(self):
        """Test official candidate ratio calculation."""
        metrics = DiscoveryMetrics()
        
        # No candidates yet
        assert metrics.get_official_candidate_ratio() == 0.0
        
        # Add candidates
        metrics.total_candidates_found = 10
        metrics.official_candidates_found = 7
        
        assert metrics.get_official_candidate_ratio() == 0.7


if __name__ == "__main__":
    pytest.main([__file__])