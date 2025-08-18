"""Tests for discovery foundation components (Task 5)."""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime

from services.discovery.simple_perplexity_client import SimplePerplexityClient, discover_official_documents
from services.discovery.simple_discovery_service import SimpleDiscoveryService, run_foundation_discovery


class TestSimplePerplexityClient:
    """Test simplified Perplexity client functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.api_key = "test-api-key"
        self.client = SimplePerplexityClient(self.api_key)
        self.foundation_allowlist = ["gzpec.cn", "sdpxc.cn", "impex.org.cn"]
    
    def test_init_with_api_key(self):
        """Test client initialization with API key."""
        client = SimplePerplexityClient("test-key")
        assert client.api_key == "test-key"
        assert client.daily_limit == 150
        assert client.request_count == 0
    
    def test_init_without_api_key_raises_error(self):
        """Test client initialization without API key raises error."""
        with patch.dict('os.environ', {}, clear=True):
            with pytest.raises(ValueError, match="PERPLEXITY_API_KEY"):
                SimplePerplexityClient()
    
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
    
    def test_build_chinese_prompt_guangdong(self):
        """Test Chinese prompt building for Guangdong."""
        prompt = self.client._build_chinese_prompt("guangdong", self.foundation_allowlist)
        
        assert "广东省" in prompt
        assert "gzpec.cn" in prompt
        assert "sdpxc.cn" in prompt
        assert "impex.org.cn" in prompt
        assert "JSON" in prompt
        assert "电力交易规则" in prompt
    
    def test_build_chinese_prompt_shandong(self):
        """Test Chinese prompt building for Shandong."""
        prompt = self.client._build_chinese_prompt("shandong", self.foundation_allowlist)
        
        assert "山东省" in prompt
        assert "只返回以下域名" in prompt
        assert "不要返回非官方站点" in prompt
    
    def test_build_chinese_prompt_inner_mongolia(self):
        """Test Chinese prompt building for Inner Mongolia."""
        prompt = self.client._build_chinese_prompt("inner_mongolia", self.foundation_allowlist)
        
        assert "内蒙古自治区" in prompt
        assert "官方电力交易中心" in prompt
    
    def test_is_url_allowed_exact_match(self):
        """Test URL allowlist checking with exact match."""
        assert self.client._is_url_allowed("https://gzpec.cn/rules", ["gzpec.cn"]) is True
        assert self.client._is_url_allowed("https://example.com/rules", ["gzpec.cn"]) is False
    
    def test_is_url_allowed_subdomain_match(self):
        """Test URL allowlist checking with subdomain."""
        assert self.client._is_url_allowed("https://www.gzpec.cn/rules", ["gzpec.cn"]) is True
        assert self.client._is_url_allowed("https://api.gzpec.cn/data", ["gzpec.cn"]) is True
    
    def test_is_url_allowed_suffix_match(self):
        """Test URL allowlist checking with suffix pattern."""
        assert self.client._is_url_allowed("https://example.gov.cn/rules", [".gov.cn"]) is True
        assert self.client._is_url_allowed("https://test.gov.cn/data", [".gov.cn"]) is True
        assert self.client._is_url_allowed("https://example.com/rules", [".gov.cn"]) is False
    
    def test_extract_json_candidates(self):
        """Test JSON candidate extraction from response."""
        content = '''Here are the results:
        [
            {"title": "广东电力市场规则", "url": "https://gzpec.cn/rules/2025"},
            {"title": "山东并网管理办法", "url": "https://sdpxc.cn/grid/2025"}
        ]
        Additional text here.'''
        
        candidates = self.client._extract_json_candidates(content)
        
        assert len(candidates) == 2
        assert candidates[0]["title"] == "广东电力市场规则"
        assert candidates[0]["url"] == "https://gzpec.cn/rules/2025"
        assert candidates[1]["title"] == "山东并网管理办法"
        assert candidates[1]["url"] == "https://sdpxc.cn/grid/2025"
    
    def test_extract_text_candidates(self):
        """Test text candidate extraction from response."""
        content = '''
        1. 广东省电力交易规则: https://gzpec.cn/rules/market-2025
        2. 山东省并网管理办法：https://sdpxc.cn/grid/connection-2025
        
        Additional URLs:
        https://impex.org.cn/dispatch/rules
        '''
        
        candidates = self.client._extract_text_candidates(content, self.foundation_allowlist)
        
        assert len(candidates) >= 2
        
        # Check title-URL pairs
        title_candidates = [c for c in candidates if c["title"]]
        assert len(title_candidates) >= 2
        assert any("广东省电力交易规则" in c["title"] for c in title_candidates)
        assert any("山东省并网管理办法" in c["title"] for c in title_candidates)
    
    def test_deduplicate_candidates(self):
        """Test candidate deduplication."""
        candidates = [
            {"title": "Rule 1", "url": "https://gzpec.cn/rule1"},
            {"title": "Rule 2", "url": "https://sdpxc.cn/rule2"},
            {"title": "Rule 1 Duplicate", "url": "https://gzpec.cn/rule1"},  # Duplicate URL
            {"title": "Rule 3", "url": "https://impex.org.cn/rule3"}
        ]
        
        unique_candidates = self.client._deduplicate_candidates(candidates)
        
        assert len(unique_candidates) == 3
        urls = [c["url"] for c in unique_candidates]
        assert len(set(urls)) == 3  # All unique
    
    @patch('services.discovery.simple_perplexity_client.httpx.AsyncClient.post')
    async def test_make_api_request_success(self, mock_post):
        """Test successful API request."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": '[{"title": "Test Rule", "url": "https://gzpec.cn/test"}]'
                    }
                }
            ]
        }
        mock_post.return_value = mock_response
        
        result = await self.client._make_api_request("test prompt", self.foundation_allowlist)
        
        assert "choices" in result
        mock_post.assert_called_once()
    
    @patch('services.discovery.simple_perplexity_client.httpx.AsyncClient.post')
    async def test_make_api_request_retry_on_429(self, mock_post):
        """Test API request retry on rate limit (429)."""
        import httpx
        
        # First call returns 429, second succeeds
        mock_response_429 = Mock()
        mock_response_429.status_code = 429
        
        mock_response_success = Mock()
        mock_response_success.json.return_value = {"choices": []}
        
        mock_post.side_effect = [
            httpx.HTTPStatusError("Rate limited", request=Mock(), response=mock_response_429),
            mock_response_success
        ]
        
        # Mock sleep to speed up test
        with patch('asyncio.sleep', new_callable=AsyncMock):
            result = await self.client._make_api_request("test", self.foundation_allowlist)
        
        assert result == {"choices": []}
        assert mock_post.call_count == 2
    
    @patch('services.discovery.simple_perplexity_client.httpx.AsyncClient.post')
    async def test_discover_official_success(self, mock_post):
        """Test successful document discovery."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": '[{"title": "广东电力规则", "url": "https://gzpec.cn/rules"}]'
                    }
                }
            ]
        }
        mock_post.return_value = mock_response
        
        results = await self.client.discover_official("guangdong", self.foundation_allowlist)
        
        assert len(results) == 1
        assert results[0]["title"] == "广东电力规则"
        assert results[0]["url"] == "https://gzpec.cn/rules"
        assert self.client.request_count == 1
    
    @patch('services.discovery.simple_perplexity_client.httpx.AsyncClient.post')
    async def test_discover_official_rate_limited(self, mock_post):
        """Test discovery when rate limited."""
        self.client.request_count = 150  # At limit
        
        results = await self.client.discover_official("guangdong", self.foundation_allowlist)
        
        assert results == []
        mock_post.assert_not_called()
    
    @patch('services.discovery.simple_perplexity_client.httpx.AsyncClient.post')
    async def test_health_check_healthy(self, mock_post):
        """Test healthy API health check."""
        mock_response = Mock()
        mock_response.json.return_value = {"choices": []}
        mock_post.return_value = mock_response
        
        health = await self.client.health_check()
        
        assert health["status"] == "healthy"
        assert "latency_ms" in health
        assert health["daily_requests_remaining"] == 150
    
    @patch('services.discovery.simple_perplexity_client.httpx.AsyncClient.post')
    async def test_health_check_unhealthy(self, mock_post):
        """Test unhealthy API health check."""
        mock_post.side_effect = Exception("Connection failed")
        
        health = await self.client.health_check()
        
        assert health["status"] == "unhealthy"
        assert "error" in health
    
    async def test_close(self):
        """Test client cleanup."""
        with patch.object(self.client.client, 'aclose', new_callable=AsyncMock) as mock_close:
            await self.client.close()
            mock_close.assert_called_once()


class TestSimpleDiscoveryService:
    """Test simplified discovery service functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.service = SimpleDiscoveryService("test-api-key")
    
    @patch('services.discovery.simple_discovery_service.SimplePerplexityClient')
    @patch('services.discovery.simple_discovery_service.SimpleRegistryLoader')
    async def test_discover_for_province_success(self, mock_loader_class, mock_client_class):
        """Test successful province discovery."""
        # Mock registry loader
        mock_loader = Mock()
        mock_loader.get_sources_for_province.return_value = [
            {"domain": "gzpec.cn", "label": "广东电力交易中心"}
        ]
        mock_loader_class.return_value = mock_loader
        
        # Mock Perplexity client
        mock_client = Mock()
        mock_client.discover_official = AsyncMock(return_value=[
            {"title": "广东电力规则", "url": "https://gzpec.cn/rules", "source": "perplexity"}
        ])
        mock_client_class.return_value = mock_client
        
        # Create service with mocked dependencies
        service = SimpleDiscoveryService("test-key")
        
        result = await service.discover_for_province("guangdong")
        
        assert result["status"] == "completed"
        assert result["province"] == "guangdong"
        assert len(result["candidates"]) == 1
        assert result["candidates"][0]["title"] == "广东电力规则"
        assert "confidence_score" in result["candidates"][0]
    
    @patch('services.discovery.simple_discovery_service.SimplePerplexityClient')
    async def test_discover_for_province_failure(self, mock_client_class):
        """Test province discovery failure."""
        mock_client = Mock()
        mock_client.discover_official = AsyncMock(side_effect=Exception("API error"))
        mock_client_class.return_value = mock_client
        
        service = SimpleDiscoveryService("test-key")
        
        result = await service.discover_for_province("guangdong")
        
        assert result["status"] == "failed"
        assert "error" in result
        assert result["total_found"] == 0
    
    @patch('services.discovery.simple_discovery_service.SimpleDiscoveryService.discover_for_province')
    async def test_discover_all_provinces(self, mock_discover):
        """Test discovery for all provinces."""
        mock_discover.side_effect = [
            {"province": "guangdong", "status": "completed", "total_found": 5},
            {"province": "shandong", "status": "completed", "total_found": 3},
            {"province": "inner_mongolia", "status": "completed", "total_found": 2}
        ]
        
        # Mock sleep to speed up test
        with patch('asyncio.sleep', new_callable=AsyncMock):
            results = await self.service.discover_all_provinces()
        
        assert len(results) == 3
        assert all(r["status"] == "completed" for r in results)
        assert mock_discover.call_count == 3
    
    async def test_emit_candidates_for_verification(self):
        """Test verification job emission."""
        candidates = [
            {"url": "https://gzpec.cn/rule1", "title": "Rule 1", "domain": "gzpec.cn"},
            {"url": "https://sdpxc.cn/rule2", "title": "Rule 2", "domain": "sdpxc.cn"}
        ]
        
        verification_jobs = await self.service.emit_candidates_for_verification(
            candidates, "guangdong"
        )
        
        assert len(verification_jobs) == 2
        assert all(job["job_type"] == "verification" for job in verification_jobs)
        assert all(job["province"] == "guangdong" for job in verification_jobs)
        assert all("job_id" in job for job in verification_jobs)
    
    def test_calculate_confidence_score_with_title(self):
        """Test confidence score calculation with title."""
        candidate = {
            "title": "广东省电力市场交易规则管理办法",
            "url": "https://gzpec.cn/rules/market",
            "domain": "gzpec.cn"
        }
        
        score = self.service._calculate_confidence_score(candidate, "guangdong")
        
        assert 0.0 <= score <= 1.0
        assert score > 0.5  # Should be higher than base score
    
    def test_calculate_confidence_score_without_title(self):
        """Test confidence score calculation without title."""
        candidate = {
            "title": "",
            "url": "https://example.com/document",
            "domain": "example.com"
        }
        
        score = self.service._calculate_confidence_score(candidate, "guangdong")
        
        assert 0.0 <= score <= 1.0
        assert score <= 0.7  # Should be lower without title and official domain
    
    def test_calculate_confidence_score_official_domain(self):
        """Test confidence score bonus for official domains."""
        candidate = {
            "title": "Test Rule",
            "url": "https://gzpec.cn/test",
            "domain": "gzpec.cn"
        }
        
        score = self.service._calculate_confidence_score(candidate, "guangdong")
        
        # Should get bonus for official domain
        assert score >= 0.7
    
    @patch('services.discovery.simple_discovery_service.SimplePerplexityClient')
    async def test_get_discovery_stats(self, mock_client_class):
        """Test discovery statistics retrieval."""
        mock_client = Mock()
        mock_client.health_check = AsyncMock(return_value={"status": "healthy"})
        mock_client_class.return_value = mock_client
        
        service = SimpleDiscoveryService("test-key")
        
        stats = await service.get_discovery_stats()
        
        assert stats["service"] == "discovery"
        assert "stats" in stats
        assert "perplexity_health" in stats
        assert "foundation_allowlist" in stats
        assert "supported_provinces" in stats
    
    @patch('services.discovery.simple_discovery_service.SimplePerplexityClient')
    @patch('services.discovery.simple_discovery_service.SimpleRegistryLoader')
    async def test_health_check_healthy(self, mock_loader_class, mock_client_class):
        """Test healthy service health check."""
        # Mock Perplexity client
        mock_client = Mock()
        mock_client.health_check = AsyncMock(return_value={"status": "healthy"})
        mock_client_class.return_value = mock_client
        
        # Mock registry loader
        mock_loader = Mock()
        mock_loader.validate_registry_file.return_value = {
            "file_valid": True,
            "total_sources": 3,
            "enabled_sources": 3
        }
        mock_loader_class.return_value = mock_loader
        
        service = SimpleDiscoveryService("test-key")
        
        health = await service.health_check()
        
        assert health["status"] == "healthy"
        assert health["components"]["perplexity"]["status"] == "healthy"
        assert health["components"]["registry"]["status"] == "healthy"
    
    @patch('services.discovery.simple_discovery_service.SimplePerplexityClient')
    @patch('services.discovery.simple_discovery_service.SimpleRegistryLoader')
    async def test_health_check_degraded(self, mock_loader_class, mock_client_class):
        """Test degraded service health check."""
        # Mock unhealthy Perplexity client
        mock_client = Mock()
        mock_client.health_check = AsyncMock(return_value={"status": "unhealthy"})
        mock_client_class.return_value = mock_client
        
        # Mock healthy registry
        mock_loader = Mock()
        mock_loader.validate_registry_file.return_value = {"file_valid": True}
        mock_loader_class.return_value = mock_loader
        
        service = SimpleDiscoveryService("test-key")
        
        health = await service.health_check()
        
        assert health["status"] == "degraded"
    
    async def test_close(self):
        """Test service cleanup."""
        with patch.object(self.service.perplexity_client, 'close', new_callable=AsyncMock) as mock_close:
            await self.service.close()
            mock_close.assert_called_once()


class TestDiscoveryIntegration:
    """Test discovery integration functions."""
    
    @patch('services.discovery.simple_perplexity_client.SimplePerplexityClient')
    def test_discover_official_documents_sync(self, mock_client_class):
        """Test synchronous discovery convenience function."""
        mock_client = Mock()
        mock_client.discover_official = AsyncMock(return_value=[
            {"title": "Test Rule", "url": "https://gzpec.cn/test"}
        ])
        mock_client.close = AsyncMock()
        mock_client_class.return_value = mock_client
        
        results = discover_official_documents("guangdong", ["gzpec.cn"])
        
        assert len(results) == 1
        assert results[0]["title"] == "Test Rule"
    
    @patch('services.discovery.simple_discovery_service.SimpleDiscoveryService')
    async def test_run_foundation_discovery(self, mock_service_class):
        """Test foundation discovery runner."""
        mock_service = Mock()
        mock_service.discover_all_provinces = AsyncMock(return_value=[
            {"province": "guangdong", "status": "completed", "total_found": 5}
        ])
        mock_service.get_discovery_stats = AsyncMock(return_value={"stats": "test"})
        mock_service.close = AsyncMock()
        mock_service_class.return_value = mock_service
        
        result = await run_foundation_discovery()
        
        assert "discovery_results" in result
        assert "service_stats" in result
        assert "summary" in result
        assert result["summary"]["total_provinces"] == 1


if __name__ == "__main__":
    pytest.main([__file__])