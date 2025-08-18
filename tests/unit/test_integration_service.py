"""Tests for RAG integration service (Task 15)."""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

from services.pipeline.integration_service import (
    RAGIntegrationService, get_integration_service, process_query_request
)
from services.pipeline.query_processor import ProcessingResult, QueryFingerprint
from services.gateway.models import QueryRequest, QueryResponse, Province, DocClass, Asset, Language
from services.core.models import ProcessingMetrics


class TestRAGIntegrationService:
    """Test RAG integration service functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.service = RAGIntegrationService()
        
        self.sample_request = QueryRequest(
            question="广东省光伏电站并网需要什么资料？",
            province=Province.GUANGDONG,
            doc_class=DocClass.GRID_CONNECTION,
            asset=Asset.SOLAR,
            lang=Language.CHINESE,
            max_citations=10
        )
        
        self.sample_processing_result = ProcessingResult(
            answer_zh="**并网要点（广东 / 光伏）**\n- 相关规定：\n  • 光伏项目需要提交技术资料 〔《广东省光伏并网管理办法》，生效：2024-06-01〕",
            citations=[
                {
                    "citation_id": "cite-guangdong-1",
                    "title": "广东省光伏并网管理办法",
                    "url": "https://example.com/guangdong/rules",
                    "effective_date": "2024-06-01",
                    "score": 0.92,
                    "passage": "光伏项目需要提交技术资料"
                }
            ],
            sections=1,
            total_citations=1,
            processing_metrics=ProcessingMetrics(
                start_time=datetime.utcnow().timestamp(),
                trace_id="test-trace-123",
                total_time_ms=150.0,
                retrieval_time_ms=80.0,
                composition_time_ms=40.0
            ),
            query_fingerprint=QueryFingerprint(
                fingerprint_hash="test123",
                province="guangdong",
                doc_class="grid_connection",
                asset="solar",
                question_hash="abc123",
                created_at=datetime.utcnow()
            ),
            pack_id="pack-test-123",
            cached=False
        )
    
    def test_service_initialization(self):
        """Test service initialization."""
        assert self.service.query_processor is None
        assert self.service.initialized is False
        
        assert self.service.metrics["total_requests"] == 0
        assert self.service.metrics["successful_requests"] == 0
        assert self.service.metrics["failed_requests"] == 0
        assert self.service.metrics["avg_response_time_ms"] == 0.0
        assert self.service.metrics["error_distribution"] == {}
    
    @pytest.mark.asyncio
    async def test_initialize_success(self):
        """Test successful service initialization."""
        with patch('services.pipeline.integration_service.QueryProcessor') as mock_processor_class:
            mock_processor = Mock()
            mock_processor.initialize = AsyncMock()
            mock_processor_class.return_value = mock_processor
            
            await self.service.initialize()
            
            assert self.service.query_processor is not None
            assert self.service.initialized is True
            mock_processor.initialize.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_initialize_failure(self):
        """Test service initialization failure."""
        with patch('services.pipeline.integration_service.QueryProcessor') as mock_processor_class:
            mock_processor_class.side_effect = Exception("Initialization failed")
            
            with pytest.raises(Exception, match="Initialization failed"):
                await self.service.initialize()
            
            assert self.service.initialized is False
    
    @pytest.mark.asyncio
    async def test_process_query_request_success(self):
        """Test successful query request processing."""
        trace_id = "test-trace-123"
        
        # Mock query processor
        mock_processor = Mock()
        mock_processor.process_query = AsyncMock(return_value=self.sample_processing_result)
        self.service.query_processor = mock_processor
        self.service.initialized = True
        
        response = await self.service.process_query_request(self.sample_request, trace_id)
        
        # Verify response structure
        assert isinstance(response, QueryResponse)
        assert response.answer_zh.startswith("**并网要点（广东 / 光伏）**")
        assert len(response.citations) == 1
        assert response.total_citations == 1
        assert response.sections == 1
        assert response.trace_id == trace_id
        assert response.processing_time_ms > 0
        
        # Verify citation structure
        citation = response.citations[0]
        assert citation.citation_id == "cite-guangdong-1"
        assert citation.title == "广东省光伏并网管理办法"
        assert citation.url == "https://example.com/guangdong/rules"
        assert citation.effective_date == "2024-06-01"
        assert citation.score == 0.92
        
        # Verify query context
        assert response.query_context["province"] == "guangdong"
        assert response.query_context["doc_class"] == "grid_connection"
        assert response.query_context["asset"] == "solar"
        assert response.query_context["lang"] == "zh-CN"
        assert response.query_context["fingerprint"] == "test123"
        assert response.query_context["pack_id"] == "pack-test-123"
        assert response.query_context["cached"] is False
        
        # Verify processor was called correctly
        mock_processor.process_query.assert_called_once_with(
            question=self.sample_request.question,
            province=self.sample_request.province.value,
            doc_class=self.sample_request.doc_class.value,
            asset=self.sample_request.asset.value,
            lang=self.sample_request.lang.value,
            max_citations=self.sample_request.max_citations,
            trace_id=trace_id
        )
        
        # Verify metrics updated
        assert self.service.metrics["total_requests"] == 1
        assert self.service.metrics["successful_requests"] == 1
    
    @pytest.mark.asyncio
    async def test_process_query_request_not_initialized(self):
        """Test query request processing when service not initialized."""
        trace_id = "test-trace-123"
        
        with pytest.raises(RuntimeError, match="Integration service not initialized"):
            await self.service.process_query_request(self.sample_request, trace_id)
    
    @pytest.mark.asyncio
    async def test_process_query_request_failure(self):
        """Test query request processing failure."""
        trace_id = "test-trace-123"
        
        # Mock query processor that fails
        mock_processor = Mock()
        mock_processor.process_query = AsyncMock(side_effect=Exception("Processing failed"))
        self.service.query_processor = mock_processor
        self.service.initialized = True
        
        with pytest.raises(Exception, match="Processing failed"):
            await self.service.process_query_request(self.sample_request, trace_id)
        
        # Verify error metrics updated
        assert self.service.metrics["total_requests"] == 1
        assert self.service.metrics["failed_requests"] == 1
        assert self.service.metrics["error_distribution"]["unknown"] == 1
    
    def test_format_query_response(self):
        """Test query response formatting."""
        trace_id = "test-trace-123"
        start_time = datetime.utcnow()
        
        response = self.service._format_query_response(
            self.sample_request, self.sample_processing_result, trace_id, start_time
        )
        
        assert isinstance(response, QueryResponse)
        assert response.answer_zh == self.sample_processing_result.answer_zh
        assert len(response.citations) == len(self.sample_processing_result.citations)
        assert response.sections == self.sample_processing_result.sections
        assert response.total_citations == self.sample_processing_result.total_citations
        assert response.trace_id == trace_id
        assert response.processing_time_ms > 0
        assert "composed_at" in response.composed_at
        
        # Verify query context
        assert response.query_context["province"] == "guangdong"
        assert response.query_context["doc_class"] == "grid_connection"
        assert response.query_context["asset"] == "solar"
        assert response.query_context["lang"] == "zh-CN"
        assert response.query_context["max_citations"] == 10
        assert response.query_context["question_length"] == len(self.sample_request.question)
    
    def test_update_success_metrics(self):
        """Test success metrics updating."""
        # Process multiple successful requests
        processing_times = [100.0, 200.0, 300.0]
        
        for i, time_ms in enumerate(processing_times):
            self.service._update_success_metrics(time_ms)
            
            assert self.service.metrics["successful_requests"] == i + 1
        
        # Check average response time
        assert self.service.metrics["avg_response_time_ms"] == 200.0  # Average of 100, 200, 300
    
    def test_update_error_metrics(self):
        """Test error metrics updating."""
        # Test different error categories
        error_messages = [
            "No citations found",
            "Policy violation detected",
            "Composition failed to generate answer",
            "Retrieval service unavailable",
            "Internal server error",
            "Unknown error occurred"
        ]
        
        for error_msg in error_messages:
            self.service._update_error_metrics(error_msg)
        
        assert self.service.metrics["failed_requests"] == len(error_messages)
        
        # Verify error categorization
        assert self.service.metrics["error_distribution"]["no_citations"] == 1
        assert self.service.metrics["error_distribution"]["policy_violation"] == 1
        assert self.service.metrics["error_distribution"]["composition_failed"] == 1
        assert self.service.metrics["error_distribution"]["retrieval_failed"] == 1
        assert self.service.metrics["error_distribution"]["internal_error"] == 1
        assert self.service.metrics["error_distribution"]["unknown"] == 1
    
    @pytest.mark.asyncio
    async def test_get_service_health_healthy(self):
        """Test service health check when healthy."""
        # Mock healthy query processor
        mock_processor = Mock()
        mock_processor.health_check = AsyncMock(return_value={"status": "healthy"})
        self.service.query_processor = mock_processor
        self.service.initialized = True
        
        health = await self.service.get_service_health()
        
        assert health["status"] == "healthy"
        assert health["initialized"] is True
        assert health["query_processor"]["status"] == "healthy"
        assert "timestamp" in health
    
    @pytest.mark.asyncio
    async def test_get_service_health_degraded(self):
        """Test service health check when degraded."""
        # Mock unhealthy query processor
        mock_processor = Mock()
        mock_processor.health_check = AsyncMock(return_value={"status": "unhealthy"})
        self.service.query_processor = mock_processor
        self.service.initialized = True
        
        health = await self.service.get_service_health()
        
        assert health["status"] == "degraded"
        assert health["query_processor"]["status"] == "unhealthy"
    
    @pytest.mark.asyncio
    async def test_get_service_health_not_initialized(self):
        """Test service health check when not initialized."""
        health = await self.service.get_service_health()
        
        assert health["status"] == "not_initialized"
        assert health["initialized"] is False
    
    def test_get_service_metrics(self):
        """Test service metrics retrieval."""
        # Setup some metrics
        self.service.metrics["total_requests"] = 100
        self.service.metrics["successful_requests"] = 85
        self.service.metrics["failed_requests"] = 15
        self.service.metrics["avg_response_time_ms"] = 250.5
        self.service.metrics["error_distribution"] = {"no_citations": 5, "policy_violation": 10}
        
        # Mock query processor metrics
        mock_processor = Mock()
        mock_processor.get_metrics = Mock(return_value={"cache_hit_rate": 0.2})
        self.service.query_processor = mock_processor
        self.service.initialized = True
        
        metrics = self.service.get_service_metrics()
        
        assert metrics["total_requests"] == 100
        assert metrics["successful_requests"] == 85
        assert metrics["failed_requests"] == 15
        assert metrics["success_rate"] == 0.85  # 85/100
        assert metrics["failure_rate"] == 0.15  # 15/100
        assert metrics["avg_response_time_ms"] == 250.5
        assert metrics["error_distribution"]["no_citations"] == 5
        assert metrics["query_processor"]["cache_hit_rate"] == 0.2
        assert "timestamp" in metrics
    
    @pytest.mark.asyncio
    async def test_validate_system_integration_success(self):
        """Test successful system integration validation."""
        # Mock successful query processing
        mock_processor = Mock()
        mock_processor.process_query = AsyncMock(return_value=self.sample_processing_result)
        self.service.query_processor = mock_processor
        self.service.initialized = True
        
        validation_results = await self.service.validate_system_integration()
        
        assert validation_results["status"] == "success"
        assert validation_results["tests_run"] == 3
        assert validation_results["tests_passed"] == 3
        assert validation_results["tests_failed"] == 0
        assert len(validation_results["test_results"]) == 3
        
        # Check individual test results
        for test_result in validation_results["test_results"]:
            assert test_result["status"] == "passed"
            assert test_result["citations_count"] == 1
            assert test_result["response_length"] > 0
            assert len(test_result["keywords_found"]) > 0
    
    @pytest.mark.asyncio
    async def test_validate_system_integration_partial_failure(self):
        """Test system integration validation with partial failures."""
        # Mock query processor that fails for some queries
        mock_processor = Mock()
        
        def mock_process_query(*args, **kwargs):
            question = kwargs.get("question", "")
            if "山东" in question:
                raise Exception("Processing failed")
            return self.sample_processing_result
        
        mock_processor.process_query = AsyncMock(side_effect=mock_process_query)
        self.service.query_processor = mock_processor
        self.service.initialized = True
        
        validation_results = await self.service.validate_system_integration()
        
        assert validation_results["status"] == "partial_failure"
        assert validation_results["tests_run"] == 3
        assert validation_results["tests_passed"] == 2
        assert validation_results["tests_failed"] == 1
        
        # Check that failed test has error information
        failed_tests = [t for t in validation_results["test_results"] if t["status"] == "failed"]
        assert len(failed_tests) == 1
        assert "error" in failed_tests[0]
    
    @pytest.mark.asyncio
    async def test_validate_system_integration_no_citations(self):
        """Test system integration validation when no citations returned."""
        # Mock processing result with no citations
        no_citations_result = ProcessingResult(
            answer_zh="短答案",
            citations=[],
            sections=0,
            total_citations=0,
            processing_metrics=self.sample_processing_result.processing_metrics,
            query_fingerprint=self.sample_processing_result.query_fingerprint,
            pack_id=None,
            cached=False
        )
        
        mock_processor = Mock()
        mock_processor.process_query = AsyncMock(return_value=no_citations_result)
        self.service.query_processor = mock_processor
        self.service.initialized = True
        
        validation_results = await self.service.validate_system_integration()
        
        assert validation_results["status"] == "failure"
        assert validation_results["tests_passed"] == 0
        assert validation_results["tests_failed"] == 3
        
        # Check that all tests failed due to no citations
        for test_result in validation_results["test_results"]:
            assert test_result["status"] == "failed"
            assert test_result["error"] == "No citations returned"


class TestIntegrationServiceGlobal:
    """Test global integration service functions."""
    
    @pytest.mark.asyncio
    async def test_get_integration_service_singleton(self):
        """Test that get_integration_service returns singleton instance."""
        # Clear any existing instance
        import services.pipeline.integration_service
        services.pipeline.integration_service._integration_service = None
        
        with patch('services.pipeline.integration_service.RAGIntegrationService') as mock_service_class:
            mock_service = Mock()
            mock_service.initialize = AsyncMock()
            mock_service_class.return_value = mock_service
            
            service1 = await get_integration_service()
            service2 = await get_integration_service()
            
            assert service1 is service2
            mock_service.initialize.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_process_query_request_convenience_function(self):
        """Test convenience function for processing query requests."""
        with patch('services.pipeline.integration_service.get_integration_service') as mock_get_service:
            mock_service = Mock()
            mock_service.process_query_request = AsyncMock(return_value=Mock(spec=QueryResponse))
            mock_get_service.return_value = mock_service
            
            request = QueryRequest(
                question="测试问题",
                province=Province.GUANGDONG,
                doc_class=DocClass.GRID_CONNECTION
            )
            
            result = await process_query_request(request, "test-trace-123")
            
            assert result is not None
            mock_service.process_query_request.assert_called_once_with(request, "test-trace-123")


class TestIntegrationServiceScenarios:
    """Test integration service with realistic scenarios."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.service = RAGIntegrationService()
        self.service.initialized = True
    
    @pytest.mark.asyncio
    async def test_guangdong_solar_grid_connection_scenario(self):
        """Test complete Guangdong solar grid connection scenario."""
        request = QueryRequest(
            question="广东省光伏电站并网验收需要提交哪些资料？",
            province=Province.GUANGDONG,
            doc_class=DocClass.GRID_CONNECTION,
            asset=Asset.SOLAR,
            lang=Language.CHINESE,
            max_citations=10
        )
        
        # Mock realistic processing result
        processing_result = ProcessingResult(
            answer_zh="**并网要点（广东 / 光伏）**\n- 资料清单：\n  • 提交竣工验收报告、电网接入协议以及安全评估意见书 〔《广东省电网企业并网管理细则（2024版）》，生效：2024-05-01〕\n  • 并网申请表需加盖项目法人单位公章 〔《广东省电网企业并网管理细则（2024版）》，生效：2024-05-01〕",
            citations=[
                {
                    "citation_id": "cite-gd-grid-1",
                    "title": "广东省电网企业并网管理细则（2024版）",
                    "url": "https://www.gzpec.cn/rules/grid2024",
                    "effective_date": "2024-05-01",
                    "score": 0.95,
                    "passage": "提交竣工验收报告、电网接入协议以及安全评估意见书。"
                },
                {
                    "citation_id": "cite-gd-grid-2",
                    "title": "广东省电网企业并网管理细则（2024版）",
                    "url": "https://www.gzpec.cn/rules/grid2024",
                    "effective_date": "2024-05-01",
                    "score": 0.88,
                    "passage": "并网申请表需加盖项目法人单位公章。"
                }
            ],
            sections=1,
            total_citations=2,
            processing_metrics=ProcessingMetrics(
                start_time=datetime.utcnow().timestamp(),
                trace_id="gd-solar-test",
                total_time_ms=180.0,
                retrieval_time_ms=90.0,
                composition_time_ms=50.0
            ),
            query_fingerprint=QueryFingerprint(
                fingerprint_hash="gd-solar-123",
                province="guangdong",
                doc_class="grid_connection",
                asset="solar",
                question_hash="gd123",
                created_at=datetime.utcnow()
            ),
            pack_id="pack-gd-solar-123",
            cached=False
        )
        
        # Mock query processor
        mock_processor = Mock()
        mock_processor.process_query = AsyncMock(return_value=processing_result)
        self.service.query_processor = mock_processor
        
        response = await self.service.process_query_request(request, "gd-solar-test")
        
        # Verify response structure
        assert response.answer_zh.startswith("**并网要点（广东 / 光伏）**")
        assert "资料清单" in response.answer_zh
        assert len(response.citations) == 2
        assert response.total_citations == 2
        assert response.sections == 1
        
        # Verify citations
        for citation in response.citations:
            assert citation.title == "广东省电网企业并网管理细则（2024版）"
            assert citation.effective_date == "2024-05-01"
            assert citation.url == "https://www.gzpec.cn/rules/grid2024"
            assert citation.score > 0.8
        
        # Verify query context
        assert response.query_context["province"] == "guangdong"
        assert response.query_context["asset"] == "solar"
        assert response.query_context["doc_class"] == "grid_connection"
        assert response.query_context["pack_id"] == "pack-gd-solar-123"
    
    @pytest.mark.asyncio
    async def test_shandong_wind_market_rules_scenario(self):
        """Test complete Shandong wind market rules scenario."""
        request = QueryRequest(
            question="山东光伏电站参与现货市场交易需要满足哪些资格条件？",
            province=Province.SHANDONG,
            doc_class=DocClass.MARKET_RULES,
            asset=Asset.SOLAR,
            lang=Language.CHINESE,
            max_citations=5
        )
        
        # Mock realistic processing result
        processing_result = ProcessingResult(
            answer_zh="**市场规则要点（山东 / 光伏）**\n- 市场准入：\n  • 装机容量不低于10MW，具备独立计量和通信系统 〔《山东省电力现货市场交易实施细则（2025年）》，生效：2025-01-20〕",
            citations=[
                {
                    "citation_id": "cite-sd-market-1",
                    "title": "山东省电力现货市场交易实施细则（2025年）",
                    "url": "https://www.sdpxc.cn/rules/market2025",
                    "effective_date": "2025-01-20",
                    "score": 0.92,
                    "passage": "装机容量不低于10MW，具备独立计量和通信系统。"
                }
            ],
            sections=1,
            total_citations=1,
            processing_metrics=ProcessingMetrics(
                start_time=datetime.utcnow().timestamp(),
                trace_id="sd-solar-test",
                total_time_ms=160.0,
                retrieval_time_ms=85.0,
                composition_time_ms=45.0
            ),
            query_fingerprint=QueryFingerprint(
                fingerprint_hash="sd-solar-456",
                province="shandong",
                doc_class="market_rules",
                asset="solar",
                question_hash="sd456",
                created_at=datetime.utcnow()
            ),
            pack_id="pack-sd-solar-456",
            cached=False
        )
        
        # Mock query processor
        mock_processor = Mock()
        mock_processor.process_query = AsyncMock(return_value=processing_result)
        self.service.query_processor = mock_processor
        
        response = await self.service.process_query_request(request, "sd-solar-test")
        
        # Verify response structure
        assert response.answer_zh.startswith("**市场规则要点（山东 / 光伏）**")
        assert "市场准入" in response.answer_zh
        assert len(response.citations) == 1
        assert response.total_citations == 1
        
        # Verify citation
        citation = response.citations[0]
        assert citation.title == "山东省电力现货市场交易实施细则（2025年）"
        assert citation.effective_date == "2025-01-20"
        assert "装机容量不低于10MW" in citation.passage
        
        # Verify query context
        assert response.query_context["province"] == "shandong"
        assert response.query_context["asset"] == "solar"
        assert response.query_context["doc_class"] == "market_rules"


if __name__ == "__main__":
    pytest.main([__file__])