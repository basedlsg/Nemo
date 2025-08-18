"""Tests for verification foundation components (Task 6)."""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime

from services.verification.simple_cse_client import SimpleCSEClient, verify_urls_with_cse
from services.verification.simple_verification_service import (
    SimpleVerificationService, FoundationPipeline
)


class TestSimpleCSEClient:
    """Test simplified Google CSE client functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.api_key = "test-api-key"
        self.cse_id = "test-cse-id"
        self.client = SimpleCSEClient(self.api_key, self.cse_id)
        self.foundation_allowlist = {"gzpec.cn", "sdpxc.cn", "impex.org.cn"}
    
    def test_init_with_keys(self):
        """Test client initialization with API keys."""
        client = SimpleCSEClient("test-key", "test-cse")
        assert client.api_key == "test-key"
        assert client.cse_id == "test-cse"
        assert client.daily_limit == 150
        assert client.request_count == 0
    
    def test_init_without_api_key_raises_error(self):
        """Test client initialization without API key raises error."""
        with patch.dict('os.environ', {}, clear=True):
            with pytest.raises(ValueError, match="GOOGLE_CSE_API_KEY"):
                SimpleCSEClient(None, "test-cse")
    
    def test_init_without_cse_id_raises_error(self):
        """Test client initialization without CSE ID raises error."""
        with patch.dict('os.environ', {}, clear=True):
            with pytest.raises(ValueError, match="GOOGLE_CSE_ENGINE_ID"):
                SimpleCSEClient("test-key", None)
    
    def test_check_rate_limit_within_limit(self):
        """Test rate limit check when within limit."""
        assert self.client._check_rate_limit() is True
        assert self.client.request_count == 0
    
    def test_check_rate_limit_at_limit(self):
        """Test rate limit check when at limit."""
        self.client.request_count = 150
        assert self.client._check_rate_limit() is False
    
    def test_check_rate_limit_resets_daily(self):
        """Test rate limit resets on new day."""
        from datetime import date, timedelta
        
        # Set to yesterday
        self.client.last_reset = date.today() - timedelta(days=1)
        self.client.request_count = 150
        
        # Should reset
        assert self.client._check_rate_limit() is True
        assert self.client.request_count == 0
        assert self.client.last_reset == date.today()
    
    def test_canonicalize_url_force_https(self):
        """Test URL canonicalization forces HTTPS."""
        url = "http://gzpec.cn/rules"
        canonical = self.client._canonicalize_url(url)
        assert canonical == "https://gzpec.cn/rules"
    
    def test_canonicalize_url_strip_tracking_params(self):
        """Test URL canonicalization strips tracking parameters."""
        url = "https://gzpec.cn/rules?utm_source=google&ref=search&id=123"
        canonical = self.client._canonicalize_url(url)
        assert canonical == "https://gzpec.cn/rules?id=123"
    
    def test_canonicalize_url_remove_fragment(self):
        """Test URL canonicalization removes fragment."""
        url = "https://gzpec.cn/rules#section1"
        canonical = self.client._canonicalize_url(url)
        assert canonical == "https://gzpec.cn/rules"
    
    def test_canonicalize_url_normalize_path(self):
        """Test URL canonicalization normalizes path."""
        url = "https://gzpec.cn/rules/"
        canonical = self.client._canonicalize_url(url)
        assert canonical == "https://gzpec.cn/rules"
        
        # Root path should keep trailing slash
        url = "https://gzpec.cn/"
        canonical = self.client._canonicalize_url(url)
        assert canonical == "https://gzpec.cn/"
    
    def test_canonicalize_url_handles_errors(self):
        """Test URL canonicalization handles malformed URLs."""
        malformed_url = "not-a-url"
        canonical = self.client._canonicalize_url(malformed_url)
        assert canonical == malformed_url  # Returns original on error
    
    def test_is_url_allowed_exact_match(self):
        """Test URL allowlist checking with exact match."""
        assert self.client._is_url_allowed("https://gzpec.cn/rules", {"gzpec.cn"}) is True
        assert self.client._is_url_allowed("https://example.com/rules", {"gzpec.cn"}) is False
    
    def test_is_url_allowed_subdomain_match(self):
        """Test URL allowlist checking with subdomain."""
        assert self.client._is_url_allowed("https://www.gzpec.cn/rules", {"gzpec.cn"}) is True
        assert self.client._is_url_allowed("https://api.gzpec.cn/data", {"gzpec.cn"}) is True
    
    def test_is_url_allowed_suffix_match(self):
        """Test URL allowlist checking with suffix pattern."""
        assert self.client._is_url_allowed("https://example.gov.cn/rules", {".gov.cn"}) is True
        assert self.client._is_url_allowed("https://test.gov.cn/data", {".gov.cn"}) is True
        assert self.client._is_url_allowed("https://example.com/rules", {".gov.cn"}) is False
    
    def test_extract_domain(self):
        """Test domain extraction from URLs."""
        assert self.client._extract_domain("https://gzpec.cn/rules") == "gzpec.cn"
        assert self.client._extract_domain("https://www.gzpec.cn/rules") == "www.gzpec.cn"
        assert self.client._extract_domain("invalid-url") == ""
    
    @patch('services.verification.simple_cse_client.httpx.AsyncClient.get')
    async def test_search_with_retries_success(self, mock_get):
        """Test successful CSE search."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "items": [
                {
                    "title": "广东电力规则",
                    "link": "https://gzpec.cn/rules",
                    "snippet": "电力市场交易规则",
                    "displayLink": "gzpec.cn"
                }
            ]
        }
        mock_get.return_value = mock_response
        
        results = await self.client._search_with_retries("test query")
        
        assert len(results) == 1
        assert results[0]["title"] == "广东电力规则"
        assert results[0]["link"] == "https://gzpec.cn/rules"
        mock_get.assert_called_once()
    
    @patch('services.verification.simple_cse_client.httpx.AsyncClient.get')
    async def test_search_with_retries_rate_limited(self, mock_get):
        """Test CSE search retry on rate limit (429)."""
        import httpx
        
        # First call returns 429, second succeeds
        mock_response_429 = Mock()
        mock_response_429.status_code = 429
        
        mock_response_success = Mock()
        mock_response_success.json.return_value = {"items": []}
        
        mock_get.side_effect = [
            httpx.HTTPStatusError("Rate limited", request=Mock(), response=mock_response_429),
            mock_response_success
        ]
        
        # Mock sleep to speed up test
        with patch('asyncio.sleep', new_callable=AsyncMock):
            results = await self.client._search_with_retries("test query")
        
        assert results == []
        assert mock_get.call_count == 2
    
    @patch('services.verification.simple_cse_client.httpx.AsyncClient.get')
    async def test_verify_urls_success(self, mock_get):
        """Test successful URL verification."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "items": [
                {"title": "Test Rule", "link": "https://gzpec.cn/rules"},
                {"title": "Blocked Rule", "link": "https://example.com/rules"}  # Not in allowlist
            ]
        }
        mock_get.return_value = mock_response
        
        results = await self.client.verify_urls("test query", self.foundation_allowlist)
        
        assert len(results) == 1
        assert results[0] == "https://gzpec.cn/rules"
        assert self.client.request_count == 1
    
    @patch('services.verification.simple_cse_client.httpx.AsyncClient.get')
    async def test_verify_urls_rate_limited(self, mock_get):
        """Test URL verification when rate limited."""
        self.client.request_count = 150  # At limit
        
        results = await self.client.verify_urls("test query", self.foundation_allowlist)
        
        assert results == []
        mock_get.assert_not_called()
    
    async def test_verify_candidate_urls(self):
        """Test candidate URL verification."""
        candidates = [
            {"url": "https://gzpec.cn/rules", "title": "广东规则"},
            {"url": "https://example.com/blocked", "title": "Blocked"},  # Not in allowlist
            {"url": "http://sdpxc.cn/grid", "title": "山东并网"}  # Will be canonicalized to HTTPS
        ]
        
        results = await self.client.verify_candidate_urls(candidates, self.foundation_allowlist)
        
        assert len(results) == 2  # One filtered out
        
        # Check first result
        assert results[0]["original_url"] == "https://gzpec.cn/rules"
        assert results[0]["canonical_url"] == "https://gzpec.cn/rules"
        assert results[0]["title"] == "广东规则"
        assert results[0]["domain"] == "gzpec.cn"
        
        # Check second result (canonicalized)
        assert results[1]["original_url"] == "http://sdpxc.cn/grid"
        assert results[1]["canonical_url"] == "https://sdpxc.cn/grid"
        assert results[1]["title"] == "山东并网"
        assert results[1]["domain"] == "sdpxc.cn"
    
    @patch('services.verification.simple_cse_client.httpx.AsyncClient.get')
    async def test_health_check_healthy(self, mock_get):
        """Test healthy CSE health check."""
        mock_response = Mock()
        mock_response.json.return_value = {"items": []}
        mock_get.return_value = mock_response
        
        health = await self.client.health_check()
        
        assert health["status"] == "healthy"
        assert "latency_ms" in health
        assert health["daily_requests_remaining"] == 150
    
    async def test_health_check_rate_limited(self):
        """Test health check when rate limited."""
        self.client.request_count = 150  # At limit
        
        health = await self.client.health_check()
        
        assert health["status"] == "rate_limited"
        assert health["daily_requests_remaining"] == 0
    
    @patch('services.verification.simple_cse_client.httpx.AsyncClient.get')
    async def test_health_check_unhealthy(self, mock_get):
        """Test unhealthy CSE health check."""
        mock_get.side_effect = Exception("Connection failed")
        
        health = await self.client.health_check()
        
        assert health["status"] == "unhealthy"
        assert "error" in health
    
    async def test_close(self):
        """Test client cleanup."""
        with patch.object(self.client.client, 'aclose', new_callable=AsyncMock) as mock_close:
            await self.client.close()
            mock_close.assert_called_once()


class TestSimpleVerificationService:
    """Test simplified verification service functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.service = SimpleVerificationService("test-api-key", "test-cse-id")
    
    @patch('services.verification.simple_verification_service.SimpleCSEClient')
    async def test_verify_discovery_candidates_success(self, mock_client_class):
        """Test successful candidate verification."""
        # Mock CSE client
        mock_client = Mock()
        mock_client.verify_candidate_urls = AsyncMock(return_value=[
            {
                "original_url": "https://gzpec.cn/rules",
                "canonical_url": "https://gzpec.cn/rules",
                "title": "广东规则",
                "domain": "gzpec.cn",
                "verification_method": "canonicalization"
            }
        ])
        mock_client_class.return_value = mock_client
        
        # Create service with mocked client
        service = SimpleVerificationService("test-key", "test-cse")
        
        candidates = [
            {"url": "https://gzpec.cn/rules", "title": "广东规则"},
            {"url": "https://example.com/blocked", "title": "Blocked"}
        ]
        
        result = await service.verify_discovery_candidates(candidates)
        
        assert result["status"] == "completed"
        assert result["input_candidates"] == 2
        assert result["verified_candidates"] == 1
        assert result["verification_rate"] == 0.5
        assert len(result["candidates"]) == 1
    
    @patch('services.verification.simple_verification_service.SimpleCSEClient')
    async def test_verify_discovery_candidates_failure(self, mock_client_class):
        """Test candidate verification failure."""
        mock_client = Mock()
        mock_client.verify_candidate_urls = AsyncMock(side_effect=Exception("CSE error"))
        mock_client_class.return_value = mock_client
        
        service = SimpleVerificationService("test-key", "test-cse")
        
        candidates = [{"url": "https://gzpec.cn/rules", "title": "Test"}]
        
        result = await service.verify_discovery_candidates(candidates)
        
        assert result["status"] == "failed"
        assert "error" in result
        assert result["verified_candidates"] == 0
    
    @patch('services.verification.simple_verification_service.SimpleCSEClient')
    async def test_search_and_verify_success(self, mock_client_class):
        """Test successful search and verify."""
        mock_client = Mock()
        mock_client.verify_urls = AsyncMock(return_value=[
            "https://gzpec.cn/rules",
            "https://sdpxc.cn/grid"
        ])
        mock_client._extract_domain = Mock(side_effect=lambda url: url.split("//")[1].split("/")[0])
        mock_client_class.return_value = mock_client
        
        service = SimpleVerificationService("test-key", "test-cse")
        
        result = await service.search_and_verify("test query")
        
        assert result["status"] == "completed"
        assert result["verified_urls"] == 2
        assert len(result["candidates"]) == 2
        assert result["candidates"][0]["url"] == "https://gzpec.cn/rules"
        assert result["candidates"][0]["verification_method"] == "google_cse"
    
    async def test_emit_verified_candidates_for_fetch(self):
        """Test fetch job emission."""
        candidates = [
            {
                "url": "https://gzpec.cn/rules",
                "canonical_url": "https://gzpec.cn/rules",
                "title": "广东规则",
                "domain": "gzpec.cn",
                "province": "guangdong"
            },
            {
                "url": "https://sdpxc.cn/grid",
                "canonical_url": "https://sdpxc.cn/grid",
                "title": "山东并网",
                "domain": "sdpxc.cn",
                "province": "shandong"
            }
        ]
        
        fetch_jobs = await self.service.emit_verified_candidates_for_fetch(candidates)
        
        assert len(fetch_jobs) == 2
        assert all(job["job_type"] == "fetch" for job in fetch_jobs)
        assert all("job_id" in job for job in fetch_jobs)
        assert fetch_jobs[0]["url"] == "https://gzpec.cn/rules"
        assert fetch_jobs[1]["url"] == "https://sdpxc.cn/grid"
    
    @patch('services.verification.simple_verification_service.SimpleCSEClient')
    async def test_get_verification_stats(self, mock_client_class):
        """Test verification statistics retrieval."""
        mock_client = Mock()
        mock_client.health_check = AsyncMock(return_value={"status": "healthy"})
        mock_client_class.return_value = mock_client
        
        service = SimpleVerificationService("test-key", "test-cse")
        
        stats = await service.get_verification_stats()
        
        assert stats["service"] == "verification"
        assert "stats" in stats
        assert "cse_health" in stats
        assert "foundation_allowlist" in stats
    
    @patch('services.verification.simple_verification_service.SimpleCSEClient')
    async def test_health_check_healthy(self, mock_client_class):
        """Test healthy service health check."""
        mock_client = Mock()
        mock_client.health_check = AsyncMock(return_value={"status": "healthy"})
        mock_client_class.return_value = mock_client
        
        service = SimpleVerificationService("test-key", "test-cse")
        
        health = await service.health_check()
        
        assert health["status"] == "healthy"
        assert health["components"]["google_cse"]["status"] == "healthy"
    
    @patch('services.verification.simple_verification_service.SimpleCSEClient')
    async def test_health_check_degraded(self, mock_client_class):
        """Test degraded service health check."""
        mock_client = Mock()
        mock_client.health_check = AsyncMock(return_value={"status": "rate_limited"})
        mock_client_class.return_value = mock_client
        
        service = SimpleVerificationService("test-key", "test-cse")
        
        health = await service.health_check()
        
        assert health["status"] == "degraded"
    
    async def test_close(self):
        """Test service cleanup."""
        with patch.object(self.service.cse_client, 'close', new_callable=AsyncMock) as mock_close:
            await self.service.close()
            mock_close.assert_called_once()


class TestFoundationPipeline:
    """Test foundation quartet pipeline functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.pipeline = FoundationPipeline()
    
    @patch('services.verification.simple_verification_service.SimpleDiscoveryService')
    @patch('services.verification.simple_verification_service.SimpleVerificationService')
    async def test_run_end_to_end_pipeline_success(self, mock_verification_class, mock_discovery_class):
        """Test successful end-to-end pipeline."""
        # Mock discovery service
        mock_discovery = Mock()
        mock_discovery.discover_for_province = AsyncMock(return_value={
            "status": "completed",
            "province": "guangdong",
            "total_found": 3,
            "candidates": [
                {"url": "https://gzpec.cn/rule1", "title": "Rule 1"},
                {"url": "https://gzpec.cn/rule2", "title": "Rule 2"}
            ],
            "processing_time_seconds": 2.5
        })
        mock_discovery_class.return_value = mock_discovery
        
        # Mock verification service
        mock_verification = Mock()
        mock_verification.verify_discovery_candidates = AsyncMock(return_value={
            "status": "completed",
            "verified_candidates": 2,
            "verification_rate": 1.0,
            "candidates": [
                {"url": "https://gzpec.cn/rule1", "title": "Rule 1"},
                {"url": "https://gzpec.cn/rule2", "title": "Rule 2"}
            ],
            "processing_time_seconds": 1.5
        })
        mock_verification.emit_verified_candidates_for_fetch = AsyncMock(return_value=[
            {"job_id": "job1", "job_type": "fetch"},
            {"job_id": "job2", "job_type": "fetch"}
        ])
        mock_verification_class.return_value = mock_verification
        
        # Create pipeline with mocked services
        pipeline = FoundationPipeline(mock_discovery, mock_verification)
        
        result = await pipeline.run_end_to_end_pipeline("guangdong")
        
        assert result["status"] == "completed"
        assert result["province"] == "guangdong"
        assert result["stages"]["discovery"]["candidates_found"] == 3
        assert result["stages"]["verification"]["candidates_verified"] == 2
        assert result["stages"]["fetch_emission"]["fetch_jobs_created"] == 2
        assert len(result["final_candidates"]) == 2
    
    @patch('services.verification.simple_verification_service.SimpleDiscoveryService')
    async def test_run_end_to_end_pipeline_discovery_failure(self, mock_discovery_class):
        """Test pipeline with discovery failure."""
        mock_discovery = Mock()
        mock_discovery.discover_for_province = AsyncMock(return_value={
            "status": "failed",
            "error": "Discovery failed"
        })
        mock_discovery_class.return_value = mock_discovery
        
        pipeline = FoundationPipeline(mock_discovery)
        
        result = await pipeline.run_end_to_end_pipeline("guangdong")
        
        assert result["status"] == "failed"
        assert result["stage"] == "discovery"
        assert "Discovery failed" in result["error"]
    
    @patch('services.verification.simple_verification_service.SimpleDiscoveryService')
    @patch('services.verification.simple_verification_service.SimpleVerificationService')
    async def test_run_walking_skeleton(self, mock_verification_class, mock_discovery_class):
        """Test walking skeleton execution."""
        # Mock successful pipeline runs
        mock_pipeline = Mock()
        mock_pipeline.run_end_to_end_pipeline = AsyncMock(return_value={
            "status": "completed",
            "province": "test",
            "final_candidates": [{"url": "test"}]
        })
        
        # Mock sleep to speed up test
        with patch('asyncio.sleep', new_callable=AsyncMock):
            with patch.object(FoundationPipeline, 'run_end_to_end_pipeline', mock_pipeline.run_end_to_end_pipeline):
                pipeline = FoundationPipeline()
                result = await pipeline.run_walking_skeleton()
        
        assert result["status"] == "completed"
        assert result["provinces_tested"] == 3
        assert result["successful_provinces"] == 3
        assert len(result["pipeline_stages_validated"]) == 3
        assert mock_pipeline.run_end_to_end_pipeline.call_count == 3
    
    async def test_close(self):
        """Test pipeline cleanup."""
        mock_verification = Mock()
        mock_verification.close = AsyncMock()
        
        mock_discovery = Mock()
        mock_discovery.close = AsyncMock()
        
        pipeline = FoundationPipeline(mock_discovery, mock_verification)
        
        await pipeline.close()
        
        mock_verification.close.assert_called_once()
        mock_discovery.close.assert_called_once()


class TestVerificationIntegration:
    """Test verification integration functions."""
    
    @patch('services.verification.simple_cse_client.SimpleCSEClient')
    def test_verify_urls_with_cse_sync(self, mock_client_class):
        """Test synchronous verification convenience function."""
        mock_client = Mock()
        mock_client.verify_urls = AsyncMock(return_value=["https://gzpec.cn/test"])
        mock_client.close = AsyncMock()
        mock_client_class.return_value = mock_client
        
        results = verify_urls_with_cse("test query", {"gzpec.cn"})
        
        assert len(results) == 1
        assert results[0] == "https://gzpec.cn/test"


if __name__ == "__main__":
    pytest.main([__file__])