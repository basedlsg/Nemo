"""Tests for gateway orchestrator (Task 14)."""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

from services.gateway.orchestrator import (
    QueryOrchestrator, GuardrailsRefusalException, ComposerRefusalException,
    get_orchestrator
)
from services.gateway.models import QueryRequest, Province, DocClass, Asset, Language


class TestQueryOrchestrator:
    """Test query orchestrator functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.orchestrator = QueryOrchestrator()
        
        self.sample_request = QueryRequest(
            question="广东省光伏电站并网需要什么资料？",
            province=Province.GUANGDONG,
            doc_class=DocClass.GRID_CONNECTION,
            asset=Asset.SOLAR,
            lang=Language.CHINESE,
            max_citations=10
        )
        
        self.mock_search_results = [
            {
                "citation_id": "cite-guangdong-1",
                "passage": "光伏项目在广东需要提交相关技术资料和安全评估报告。",
                "score": 0.92,
                "metadata": {
                    "title": "广东省光伏并网管理办法",
                    "effective_date": "2024-06-01",
                    "url": "https://example.com/guangdong/rules"
                }
            },
            {
                "citation_id": "cite-guangdong-2",
                "passage": "申请受理时限为15个工作日，审批时限为30个工作日。",
                "score": 0.87,
                "metadata": {
                    "title": "广东省电力接入管理规定",
                    "effective_date": "2024-05-15",
                    "url": "https://example.com/guangdong/access"
                }
            }
        ]
        
        self.mock_composed_answer = {
            "answer_zh": "**并网要点（广东 / 光伏）**\n- 相关规定：\n  • 光伏项目需要提交技术资料 〔《广东省光伏并网管理办法》，生效：2024-06-01〕",
            "citations": [
                {
                    "citation_id": "cite-guangdong-1",
                    "title": "广东省光伏并网管理办法",
                    "url": "https://example.com/guangdong/rules",
                    "effective_date": "2024-06-01",
                    "score": 0.92,
                    "passage": "光伏项目需要提交技术资料"
                }
            ],
            "sections": 1,
            "total_citations": 1,
            "composed_at": "2025-01-14T10:00:00Z",
            "query_context": {
                "province": "guangdong",
                "asset": "solar",
                "doc_class": "grid_connection"
            }
        }
    
    def test_orchestrator_initialization(self):
        """Test orchestrator initialization."""
        assert self.orchestrator.retriever_client is None
        assert self.orchestrator.guardrails_client is None
        assert self.orchestrator.composer_client is None
        
        assert self.orchestrator.stats["total_queries"] == 0
        assert self.orchestrator.stats["successful_queries"] == 0
        assert self.orchestrator.stats["refusal_queries"] == 0
        assert self.orchestrator.stats["avg_processing_time_ms"] == 0.0
    
    def test_set_service_clients(self):
        """Test setting service clients."""
        mock_retriever = Mock()
        mock_guardrails = Mock()
        mock_composer = Mock()
        
        self.orchestrator.set_service_clients(mock_retriever, mock_guardrails, mock_composer)
        
        assert self.orchestrator.retriever_client == mock_retriever
        assert self.orchestrator.guardrails_client == mock_guardrails
        assert self.orchestrator.composer_client == mock_composer
    
    @pytest.mark.asyncio
    async def test_process_query_success(self):
        """Test successful query processing."""
        trace_id = "test-trace-123"
        
        # Mock the internal methods
        with patch.object(self.orchestrator, '_call_retriever', new_callable=AsyncMock) as mock_retriever, \
             patch.object(self.orchestrator, '_call_guardrails', new_callable=AsyncMock) as mock_guardrails, \
             patch.object(self.orchestrator, '_call_composer', new_callable=AsyncMock) as mock_composer:
            
            mock_retriever.return_value = self.mock_search_results
            mock_guardrails.return_value = self.mock_search_results
            mock_composer.return_value = self.mock_composed_answer
            
            result = await self.orchestrator.process_query(self.sample_request, trace_id)
            
            # Verify service calls
            mock_retriever.assert_called_once_with(self.sample_request, trace_id)
            mock_guardrails.assert_called_once_with(self.mock_search_results, self.sample_request, trace_id)
            mock_composer.assert_called_once_with(self.mock_search_results, self.sample_request, trace_id)
            
            # Verify response structure
            assert "answer_zh" in result
            assert "citations" in result
            assert "processing_time_ms" in result
            assert "trace_id" in result
            assert result["trace_id"] == trace_id
            
            # Verify statistics updated
            assert self.orchestrator.stats["total_queries"] == 1
            assert self.orchestrator.stats["successful_queries"] == 1
            assert self.orchestrator.stats["province_distribution"]["guangdong"] == 1
            assert self.orchestrator.stats["doc_class_distribution"]["grid_connection"] == 1
            assert self.orchestrator.stats["asset_distribution"]["solar"] == 1
    
    @pytest.mark.asyncio
    async def test_process_query_no_search_results(self):
        """Test query processing when no search results found."""
        trace_id = "test-trace-123"
        
        with patch.object(self.orchestrator, '_call_retriever', new_callable=AsyncMock) as mock_retriever:
            mock_retriever.return_value = []
            
            result = await self.orchestrator.process_query(self.sample_request, trace_id)
            
            # Should return refusal response
            assert result["error"] == "query_refused"
            assert result["reason"] == "没有找到相关的官方资料"
            assert result["policy_violated"] == "no_citations_found"
            assert result["trace_id"] == trace_id
            
            # Verify statistics updated
            assert self.orchestrator.stats["total_queries"] == 1
            assert self.orchestrator.stats["refusal_queries"] == 1
    
    @pytest.mark.asyncio
    async def test_process_query_guardrails_refusal(self):
        """Test query processing when guardrails refuse the query."""
        trace_id = "test-trace-123"
        
        with patch.object(self.orchestrator, '_call_retriever', new_callable=AsyncMock) as mock_retriever, \
             patch.object(self.orchestrator, '_call_guardrails', new_callable=AsyncMock) as mock_guardrails:
            
            mock_retriever.return_value = self.mock_search_results
            mock_guardrails.side_effect = GuardrailsRefusalException(
                "unsafe_scope",
                "查询范围不安全",
                "请选择有效的省份和资产类型"
            )
            
            result = await self.orchestrator.process_query(self.sample_request, trace_id)
            
            # Should return refusal response
            assert result["error"] == "query_refused"
            assert result["reason"] == "查询范围不安全"
            assert result["policy_violated"] == "unsafe_scope"
            assert result["suggestion"] == "请选择有效的省份和资产类型"
            assert result["trace_id"] == trace_id
            
            # Verify statistics updated
            assert self.orchestrator.stats["refusal_queries"] == 1
    
    @pytest.mark.asyncio
    async def test_process_query_composer_refusal(self):
        """Test query processing when composer cannot generate answer."""
        trace_id = "test-trace-123"
        
        with patch.object(self.orchestrator, '_call_retriever', new_callable=AsyncMock) as mock_retriever, \
             patch.object(self.orchestrator, '_call_guardrails', new_callable=AsyncMock) as mock_guardrails, \
             patch.object(self.orchestrator, '_call_composer', new_callable=AsyncMock) as mock_composer:
            
            mock_retriever.return_value = self.mock_search_results
            mock_guardrails.return_value = self.mock_search_results
            mock_composer.side_effect = ComposerRefusalException("无法生成有效答案")
            
            result = await self.orchestrator.process_query(self.sample_request, trace_id)
            
            # Should return refusal response
            assert result["error"] == "query_refused"
            assert result["reason"] == "无法生成有效答案"
            assert result["policy_violated"] == "composition_failed"
            assert result["trace_id"] == trace_id
    
    @pytest.mark.asyncio
    async def test_process_query_internal_error(self):
        """Test query processing with internal error."""
        trace_id = "test-trace-123"
        
        with patch.object(self.orchestrator, '_call_retriever', new_callable=AsyncMock) as mock_retriever:
            mock_retriever.side_effect = Exception("Internal error")
            
            result = await self.orchestrator.process_query(self.sample_request, trace_id)
            
            # Should return internal error refusal
            assert result["error"] == "query_refused"
            assert result["reason"] == "系统处理过程中出现错误"
            assert result["policy_violated"] == "internal_error"
            assert result["trace_id"] == trace_id
    
    @pytest.mark.asyncio
    async def test_call_retriever_mock(self):
        """Test retriever call with mock results."""
        trace_id = "test-trace-123"
        
        results = await self.orchestrator._call_retriever(self.sample_request, trace_id)
        
        assert len(results) == 2
        assert results[0]["citation_id"] == "cite-guangdong-1"
        assert "光伏项目在广东需要提交" in results[0]["passage"]
        assert results[0]["metadata"]["title"] == "广东省光伏并网管理办法"
    
    @pytest.mark.asyncio
    async def test_call_guardrails_mock(self):
        """Test guardrails call with mock validation."""
        trace_id = "test-trace-123"
        
        validated_results = await self.orchestrator._call_guardrails(
            self.mock_search_results, self.sample_request, trace_id
        )
        
        # Mock implementation returns results unchanged
        assert validated_results == self.mock_search_results
    
    @pytest.mark.asyncio
    async def test_call_composer_mock(self):
        """Test composer call with mock answer generation."""
        trace_id = "test-trace-123"
        
        composed_answer = await self.orchestrator._call_composer(
            self.mock_search_results, self.sample_request, trace_id
        )
        
        assert "answer_zh" in composed_answer
        assert composed_answer["answer_zh"].startswith("**并网要点（广东 / 光伏）**")
        assert len(composed_answer["citations"]) == len(self.mock_search_results)
        assert composed_answer["query_context"]["province"] == "guangdong"
    
    def test_update_query_stats(self):
        """Test query statistics updating."""
        # Process multiple requests
        requests = [
            QueryRequest(question="Q1", province=Province.GUANGDONG, doc_class=DocClass.GRID_CONNECTION, asset=Asset.SOLAR),
            QueryRequest(question="Q2", province=Province.GUANGDONG, doc_class=DocClass.MARKET_RULES, asset=Asset.WIND),
            QueryRequest(question="Q3", province=Province.SHANDONG, doc_class=DocClass.GRID_CONNECTION, asset=None),
        ]
        
        for request in requests:
            self.orchestrator._update_query_stats(request)
        
        assert self.orchestrator.stats["total_queries"] == 3
        assert self.orchestrator.stats["province_distribution"]["guangdong"] == 2
        assert self.orchestrator.stats["province_distribution"]["shandong"] == 1
        assert self.orchestrator.stats["doc_class_distribution"]["grid_connection"] == 2
        assert self.orchestrator.stats["doc_class_distribution"]["market_rules"] == 1
        assert self.orchestrator.stats["asset_distribution"]["solar"] == 1
        assert self.orchestrator.stats["asset_distribution"]["wind"] == 1
        assert self.orchestrator.stats["asset_distribution"]["none"] == 1
    
    def test_update_success_stats(self):
        """Test success statistics updating."""
        # Simulate successful queries with different processing times
        processing_times = [100.0, 200.0, 300.0]
        
        for time_ms in processing_times:
            self.orchestrator._update_success_stats(time_ms)
        
        assert self.orchestrator.stats["successful_queries"] == 3
        assert self.orchestrator.stats["avg_processing_time_ms"] == 200.0  # Average of 100, 200, 300
    
    def test_get_stats(self):
        """Test statistics retrieval."""
        # Setup some statistics
        self.orchestrator.stats["total_queries"] = 100
        self.orchestrator.stats["successful_queries"] = 85
        self.orchestrator.stats["refusal_queries"] = 15
        self.orchestrator.stats["avg_processing_time_ms"] = 250.5
        self.orchestrator.stats["province_distribution"] = {"guangdong": 50, "shandong": 30, "inner_mongolia": 20}
        
        stats = self.orchestrator.get_stats()
        
        assert stats["total_queries"] == 100
        assert stats["successful_queries"] == 85
        assert stats["refusal_rate"] == 0.15  # 15/100
        assert stats["avg_processing_time_ms"] == 250.5
        assert stats["province_distribution"]["guangdong"] == 50
        assert "timestamp" in stats
    
    def test_create_refusal_response(self):
        """Test refusal response creation."""
        trace_id = "test-trace-123"
        
        refusal = self.orchestrator._create_refusal_response(
            "test_reason",
            "测试拒绝消息",
            "测试建议",
            trace_id
        )
        
        assert refusal["error"] == "query_refused"
        assert refusal["reason"] == "测试拒绝消息"
        assert refusal["policy_violated"] == "test_reason"
        assert refusal["suggestion"] == "测试建议"
        assert refusal["trace_id"] == trace_id
        assert "timestamp" in refusal
        
        # Verify refusal stats updated
        assert self.orchestrator.stats["refusal_queries"] == 1


class TestOrchestratorExceptions:
    """Test orchestrator exception classes."""
    
    def test_guardrails_refusal_exception(self):
        """Test GuardrailsRefusalException."""
        exception = GuardrailsRefusalException(
            "unsafe_scope",
            "查询范围不安全",
            "请选择有效的省份"
        )
        
        assert exception.reason_code == "unsafe_scope"
        assert exception.message == "查询范围不安全"
        assert exception.suggestion == "请选择有效的省份"
        assert str(exception) == "查询范围不安全"
    
    def test_composer_refusal_exception(self):
        """Test ComposerRefusalException."""
        exception = ComposerRefusalException("无法生成答案")
        
        assert exception.message == "无法生成答案"
        assert str(exception) == "无法生成答案"


class TestOrchestratorGlobal:
    """Test global orchestrator functions."""
    
    def test_get_orchestrator_singleton(self):
        """Test that get_orchestrator returns singleton instance."""
        # Clear any existing instance
        import services.gateway.orchestrator
        services.gateway.orchestrator._orchestrator = None
        
        orchestrator1 = get_orchestrator()
        orchestrator2 = get_orchestrator()
        
        assert orchestrator1 is orchestrator2
        assert isinstance(orchestrator1, QueryOrchestrator)


class TestOrchestratorIntegration:
    """Test orchestrator integration scenarios."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.orchestrator = QueryOrchestrator()
    
    @pytest.mark.asyncio
    async def test_guangdong_solar_grid_connection_query(self):
        """Test complete query processing for Guangdong solar grid connection."""
        request = QueryRequest(
            question="广东省光伏电站并网需要什么资料？",
            province=Province.GUANGDONG,
            doc_class=DocClass.GRID_CONNECTION,
            asset=Asset.SOLAR
        )
        
        trace_id = "test-guangdong-solar"
        
        with patch.object(self.orchestrator, '_call_retriever', new_callable=AsyncMock) as mock_retriever, \
             patch.object(self.orchestrator, '_call_guardrails', new_callable=AsyncMock) as mock_guardrails, \
             patch.object(self.orchestrator, '_call_composer', new_callable=AsyncMock) as mock_composer:
            
            # Mock realistic responses
            mock_search_results = [
                {
                    "citation_id": "cite-gd-solar-1",
                    "passage": "分布式光伏发电项目并网申请需要提交项目备案文件、设备清单和技术参数表。",
                    "score": 0.95,
                    "metadata": {
                        "title": "广东省分布式光伏并网管理办法",
                        "effective_date": "2025-01-01",
                        "url": "https://gzpec.cn/solar-grid-2025"
                    }
                }
            ]
            
            mock_composed_result = {
                "answer_zh": "**并网要点（广东 / 光伏）**\n- 资料清单：\n  • 分布式光伏发电项目并网申请需要提交项目备案文件、设备清单和技术参数表 〔《广东省分布式光伏并网管理办法》，生效：2025-01-01〕",
                "citations": [
                    {
                        "citation_id": "cite-gd-solar-1",
                        "title": "广东省分布式光伏并网管理办法",
                        "url": "https://gzpec.cn/solar-grid-2025",
                        "effective_date": "2025-01-01",
                        "score": 0.95,
                        "passage": "分布式光伏发电项目并网申请需要提交项目备案文件、设备清单和技术参数表。"
                    }
                ],
                "sections": 1,
                "total_citations": 1,
                "composed_at": "2025-01-14T10:00:00Z",
                "query_context": {
                    "province": "guangdong",
                    "asset": "solar",
                    "doc_class": "grid_connection"
                }
            }
            
            mock_retriever.return_value = mock_search_results
            mock_guardrails.return_value = mock_search_results
            mock_composer.return_value = mock_composed_result
            
            result = await self.orchestrator.process_query(request, trace_id)
            
            # Verify successful response
            assert "answer_zh" in result
            assert result["answer_zh"].startswith("**并网要点（广东 / 光伏）**")
            assert len(result["citations"]) == 1
            assert result["citations"][0]["title"] == "广东省分布式光伏并网管理办法"
            assert result["trace_id"] == trace_id
            
            # Verify statistics
            assert self.orchestrator.stats["total_queries"] == 1
            assert self.orchestrator.stats["successful_queries"] == 1
            assert self.orchestrator.stats["province_distribution"]["guangdong"] == 1
    
    @pytest.mark.asyncio
    async def test_shandong_wind_market_rules_query(self):
        """Test complete query processing for Shandong wind market rules."""
        request = QueryRequest(
            question="山东风电场参与电力市场交易需要满足什么条件？",
            province=Province.SHANDONG,
            doc_class=DocClass.MARKET_RULES,
            asset=Asset.WIND
        )
        
        trace_id = "test-shandong-wind"
        
        # Test with mock implementation (no patching needed)
        result = await self.orchestrator.process_query(request, trace_id)
        
        # Should get successful mock response
        assert "answer_zh" in result
        assert result["answer_zh"].startswith("**市场规则要点（山东 / 风电）**")
        assert result["query_context"]["province"] == "shandong"
        assert result["query_context"]["asset"] == "wind"
        assert result["query_context"]["doc_class"] == "market_rules"


if __name__ == "__main__":
    pytest.main([__file__])