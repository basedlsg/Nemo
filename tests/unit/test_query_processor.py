"""Tests for query processor (Task 15)."""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta

from services.pipeline.query_processor import (
    QueryProcessor, QueryProcessingException, QueryFingerprint, ProcessingResult,
    get_query_processor, process_query
)
from services.core.models import ProcessingMetrics


class TestQueryProcessor:
    """Test query processor functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.processor = QueryProcessor()
        
        self.sample_search_results = [
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
        
        self.sample_composed_answer = {
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
            "composed_at": "2025-01-14T10:00:00Z"
        }
    
    def test_processor_initialization(self):
        """Test processor initialization."""
        assert self.processor.db_client is None
        assert self.processor.retriever is None
        assert self.processor.guardrails is None
        assert self.processor.composer is None
        
        assert self.processor.metrics["total_queries"] == 0
        assert self.processor.metrics["successful_queries"] == 0
        assert self.processor.metrics["failed_queries"] == 0
        assert self.processor.cache_ttl_hours == 24
        assert self.processor.enable_caching is True
    
    @pytest.mark.asyncio
    async def test_initialize_success(self):
        """Test successful processor initialization."""
        with patch('services.pipeline.query_processor.get_database_client') as mock_db, \
             patch('services.pipeline.query_processor.HybridSearchService') as mock_retriever, \
             patch('services.pipeline.query_processor.PolicyEngine') as mock_guardrails, \
             patch('services.pipeline.query_processor.ChineseAnswerComposer') as mock_composer:
            
            mock_retriever_instance = Mock()
            mock_retriever_instance.initialize = AsyncMock()
            mock_retriever.return_value = mock_retriever_instance
            
            await self.processor.initialize()
            
            assert self.processor.db_client is not None
            assert self.processor.retriever is not None
            assert self.processor.guardrails is not None
            assert self.processor.composer is not None
            
            mock_retriever_instance.initialize.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_process_query_success(self):
        """Test successful query processing."""
        trace_id = "test-trace-123"
        
        # Mock all internal methods
        with patch.object(self.processor, '_execute_retrieval', new_callable=AsyncMock) as mock_retrieval, \
             patch.object(self.processor, '_execute_guardrails', new_callable=AsyncMock) as mock_guardrails, \
             patch.object(self.processor, '_enrich_citation_metadata', new_callable=AsyncMock) as mock_enrichment, \
             patch.object(self.processor, '_execute_composition', new_callable=AsyncMock) as mock_composition, \
             patch.object(self.processor, '_generate_pack', new_callable=AsyncMock) as mock_pack, \
             patch.object(self.processor, '_cache_result', new_callable=AsyncMock) as mock_cache:
            
            mock_retrieval.return_value = self.sample_search_results
            mock_guardrails.return_value = self.sample_search_results
            mock_enrichment.return_value = self.sample_search_results
            mock_composition.return_value = self.sample_composed_answer
            mock_pack.return_value = "pack-test-123"
            
            result = await self.processor.process_query(
                question="广东省光伏电站并网需要什么资料？",
                province="guangdong",
                doc_class="grid_connection",
                asset="solar",
                trace_id=trace_id
            )
            
            # Verify result structure
            assert isinstance(result, ProcessingResult)
            assert result.answer_zh.startswith("**并网要点（广东 / 光伏）**")
            assert len(result.citations) == 1
            assert result.total_citations == 1
            assert result.sections == 1
            assert result.pack_id == "pack-test-123"
            assert result.cached is False
            
            # Verify processing metrics
            assert result.processing_metrics.total_time_ms > 0
            assert result.processing_metrics.retrieval_time_ms > 0
            assert result.processing_metrics.composition_time_ms > 0
            assert result.processing_metrics.trace_id == trace_id
            
            # Verify query fingerprint
            assert result.query_fingerprint.province == "guangdong"
            assert result.query_fingerprint.doc_class == "grid_connection"
            assert result.query_fingerprint.asset == "solar"
            assert len(result.query_fingerprint.fingerprint_hash) == 16
            
            # Verify all pipeline steps were called
            mock_retrieval.assert_called_once()
            mock_guardrails.assert_called_once()
            mock_enrichment.assert_called_once()
            mock_composition.assert_called_once()
            mock_pack.assert_called_once()
            mock_cache.assert_called_once()
            
            # Verify metrics updated
            assert self.processor.metrics["total_queries"] == 1
            assert self.processor.metrics["successful_queries"] == 1
    
    @pytest.mark.asyncio
    async def test_process_query_no_search_results(self):
        """Test query processing when no search results found."""
        trace_id = "test-trace-123"
        
        with patch.object(self.processor, '_execute_retrieval', new_callable=AsyncMock) as mock_retrieval:
            mock_retrieval.return_value = []
            
            with pytest.raises(QueryProcessingException) as exc_info:
                await self.processor.process_query(
                    question="测试问题",
                    province="guangdong",
                    doc_class="grid_connection",
                    trace_id=trace_id
                )
            
            assert exc_info.value.error_code == "no_citations"
            assert "No relevant citations found" in str(exc_info.value)
            
            # Verify metrics updated
            assert self.processor.metrics["failed_queries"] == 1
    
    @pytest.mark.asyncio
    async def test_process_query_guardrails_failure(self):
        """Test query processing when guardrails fail."""
        trace_id = "test-trace-123"
        
        with patch.object(self.processor, '_execute_retrieval', new_callable=AsyncMock) as mock_retrieval, \
             patch.object(self.processor, '_execute_guardrails', new_callable=AsyncMock) as mock_guardrails:
            
            mock_retrieval.return_value = self.sample_search_results
            mock_guardrails.side_effect = QueryProcessingException("Guardrails failed", "guardrails_failed")
            
            with pytest.raises(QueryProcessingException) as exc_info:
                await self.processor.process_query(
                    question="测试问题",
                    province="guangdong",
                    doc_class="grid_connection",
                    trace_id=trace_id
                )
            
            assert exc_info.value.error_code == "guardrails_failed"
    
    @pytest.mark.asyncio
    async def test_process_query_composition_failure(self):
        """Test query processing when composition fails."""
        trace_id = "test-trace-123"
        
        with patch.object(self.processor, '_execute_retrieval', new_callable=AsyncMock) as mock_retrieval, \
             patch.object(self.processor, '_execute_guardrails', new_callable=AsyncMock) as mock_guardrails, \
             patch.object(self.processor, '_enrich_citation_metadata', new_callable=AsyncMock) as mock_enrichment, \
             patch.object(self.processor, '_execute_composition', new_callable=AsyncMock) as mock_composition:
            
            mock_retrieval.return_value = self.sample_search_results
            mock_guardrails.return_value = self.sample_search_results
            mock_enrichment.return_value = self.sample_search_results
            mock_composition.side_effect = QueryProcessingException("Composition failed", "composition_failed")
            
            with pytest.raises(QueryProcessingException) as exc_info:
                await self.processor.process_query(
                    question="测试问题",
                    province="guangdong",
                    doc_class="grid_connection",
                    trace_id=trace_id
                )
            
            assert exc_info.value.error_code == "composition_failed"
    
    @pytest.mark.asyncio
    async def test_execute_retrieval_success(self):
        """Test successful retrieval execution."""
        trace_id = "test-trace-123"
        
        # Mock retriever
        mock_retriever = Mock()
        mock_retriever.search = AsyncMock(return_value={"results": self.sample_search_results})
        self.processor.retriever = mock_retriever
        
        results = await self.processor._execute_retrieval(
            question="测试问题",
            province="guangdong",
            doc_class="grid_connection",
            asset="solar",
            max_citations=10,
            trace_id=trace_id
        )
        
        assert results == self.sample_search_results
        mock_retriever.search.assert_called_once_with(
            query="测试问题",
            province="guangdong",
            doc_class="grid_connection",
            asset="solar",
            limit=10
        )
    
    @pytest.mark.asyncio
    async def test_execute_retrieval_failure(self):
        """Test retrieval execution failure."""
        trace_id = "test-trace-123"
        
        # Mock retriever that fails
        mock_retriever = Mock()
        mock_retriever.search = AsyncMock(side_effect=Exception("Retrieval error"))
        self.processor.retriever = mock_retriever
        
        with pytest.raises(QueryProcessingException) as exc_info:
            await self.processor._execute_retrieval(
                question="测试问题",
                province="guangdong",
                doc_class="grid_connection",
                asset="solar",
                max_citations=10,
                trace_id=trace_id
            )
        
        assert exc_info.value.error_code == "retrieval_failed"
        assert "Retrieval error" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_execute_guardrails_success(self):
        """Test successful guardrails execution."""
        trace_id = "test-trace-123"
        
        # Mock guardrails
        mock_guardrails = Mock()
        mock_guardrails.check_citations_required = Mock()
        mock_guardrails.check_unsafe_scope = Mock()
        mock_guardrails.check_zh_first = Mock()
        self.processor.guardrails = mock_guardrails
        
        results = await self.processor._execute_guardrails(
            search_results=self.sample_search_results,
            province="guangdong",
            doc_class="grid_connection",
            asset="solar",
            lang="zh-CN",
            trace_id=trace_id
        )
        
        assert len(results) == len(self.sample_search_results)
        
        # Verify all policy checks were called
        assert mock_guardrails.check_citations_required.call_count == len(self.sample_search_results)
        assert mock_guardrails.check_unsafe_scope.call_count == len(self.sample_search_results)
        assert mock_guardrails.check_zh_first.call_count == len(self.sample_search_results)
    
    @pytest.mark.asyncio
    async def test_execute_guardrails_policy_violation(self):
        """Test guardrails execution with policy violations."""
        trace_id = "test-trace-123"
        
        # Mock guardrails that reject all citations
        mock_guardrails = Mock()
        mock_guardrails.check_citations_required = Mock(side_effect=Exception("Policy violation"))
        mock_guardrails.check_unsafe_scope = Mock()
        mock_guardrails.check_zh_first = Mock()
        self.processor.guardrails = mock_guardrails
        
        with pytest.raises(QueryProcessingException) as exc_info:
            await self.processor._execute_guardrails(
                search_results=self.sample_search_results,
                province="guangdong",
                doc_class="grid_connection",
                asset="solar",
                lang="zh-CN",
                trace_id=trace_id
            )
        
        assert exc_info.value.error_code == "policy_violation"
        assert "All citations failed policy validation" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_enrich_citation_metadata(self):
        """Test citation metadata enrichment."""
        trace_id = "test-trace-123"
        
        enriched_results = await self.processor._enrich_citation_metadata(
            self.sample_search_results, trace_id
        )
        
        assert len(enriched_results) == len(self.sample_search_results)
        
        for result in enriched_results:
            assert "enriched_at" in result
            assert result["validation_passed"] is True
            assert "metadata" in result
            
            metadata = result["metadata"]
            assert "effective_date" in metadata
            assert "title" in metadata
            assert "url" in metadata
    
    @pytest.mark.asyncio
    async def test_enrich_citation_metadata_missing_fields(self):
        """Test citation metadata enrichment with missing fields."""
        trace_id = "test-trace-123"
        
        # Create search results with missing metadata
        incomplete_results = [
            {
                "citation_id": "cite-1",
                "passage": "测试内容",
                "score": 0.8,
                "metadata": {}  # Empty metadata
            }
        ]
        
        enriched_results = await self.processor._enrich_citation_metadata(
            incomplete_results, trace_id
        )
        
        assert len(enriched_results) == 1
        
        metadata = enriched_results[0]["metadata"]
        assert metadata["effective_date"] == "未知"
        assert metadata["title"] == "未知文档"
        assert metadata["url"] == ""
    
    @pytest.mark.asyncio
    async def test_execute_composition_success(self):
        """Test successful composition execution."""
        trace_id = "test-trace-123"
        
        # Mock composer
        mock_composer = Mock()
        mock_composer.compose_answer = Mock(return_value=self.sample_composed_answer)
        self.processor.composer = mock_composer
        
        result = await self.processor._execute_composition(
            enriched_results=self.sample_search_results,
            question="测试问题",
            province="guangdong",
            doc_class="grid_connection",
            asset="solar",
            lang="zh-CN",
            max_citations=10,
            trace_id=trace_id
        )
        
        assert result == self.sample_composed_answer
        
        # Verify composer was called with correct parameters
        mock_composer.compose_answer.assert_called_once()
        call_args = mock_composer.compose_answer.call_args
        assert call_args[1]["search_results"] == self.sample_search_results
        assert call_args[1]["query"]["province"] == "guangdong"
        assert call_args[1]["query"]["question"] == "测试问题"
        assert call_args[1]["max_citations"] == 10
    
    @pytest.mark.asyncio
    async def test_execute_composition_no_answer(self):
        """Test composition execution when no answer is generated."""
        trace_id = "test-trace-123"
        
        # Mock composer that returns empty answer
        mock_composer = Mock()
        mock_composer.compose_answer = Mock(return_value={"answer_zh": ""})
        self.processor.composer = mock_composer
        
        with pytest.raises(QueryProcessingException) as exc_info:
            await self.processor._execute_composition(
                enriched_results=self.sample_search_results,
                question="测试问题",
                province="guangdong",
                doc_class="grid_connection",
                asset="solar",
                lang="zh-CN",
                max_citations=10,
                trace_id=trace_id
            )
        
        assert exc_info.value.error_code == "composition_failed"
        assert "Failed to compose valid answer" in str(exc_info.value)
    
    def test_generate_query_fingerprint(self):
        """Test query fingerprint generation."""
        fingerprint = self.processor._generate_query_fingerprint(
            question="广东省光伏电站并网需要什么资料？",
            province="guangdong",
            doc_class="grid_connection",
            asset="solar"
        )
        
        assert isinstance(fingerprint, QueryFingerprint)
        assert len(fingerprint.fingerprint_hash) == 16
        assert len(fingerprint.question_hash) == 8
        assert fingerprint.province == "guangdong"
        assert fingerprint.doc_class == "grid_connection"
        assert fingerprint.asset == "solar"
        assert isinstance(fingerprint.created_at, datetime)
        
        # Test that same query generates same fingerprint
        fingerprint2 = self.processor._generate_query_fingerprint(
            question="广东省光伏电站并网需要什么资料？",
            province="guangdong",
            doc_class="grid_connection",
            asset="solar"
        )
        
        assert fingerprint.fingerprint_hash == fingerprint2.fingerprint_hash
        assert fingerprint.question_hash == fingerprint2.question_hash
    
    def test_generate_query_fingerprint_different_queries(self):
        """Test that different queries generate different fingerprints."""
        fingerprint1 = self.processor._generate_query_fingerprint(
            question="广东省光伏电站并网需要什么资料？",
            province="guangdong",
            doc_class="grid_connection",
            asset="solar"
        )
        
        fingerprint2 = self.processor._generate_query_fingerprint(
            question="山东省风电场参与市场交易的条件是什么？",
            province="shandong",
            doc_class="market_rules",
            asset="wind"
        )
        
        assert fingerprint1.fingerprint_hash != fingerprint2.fingerprint_hash
        assert fingerprint1.question_hash != fingerprint2.question_hash
    
    @pytest.mark.asyncio
    async def test_check_cache_no_client(self):
        """Test cache check when no database client."""
        fingerprint = QueryFingerprint(
            fingerprint_hash="test123",
            province="guangdong",
            doc_class="grid_connection",
            asset="solar",
            question_hash="abc123",
            created_at=datetime.utcnow()
        )
        
        result = await self.processor._check_cache(fingerprint, "test-trace")
        assert result is None
    
    @pytest.mark.asyncio
    async def test_generate_pack(self):
        """Test pack generation."""
        fingerprint = QueryFingerprint(
            fingerprint_hash="test123",
            province="guangdong",
            doc_class="grid_connection",
            asset="solar",
            question_hash="abc123",
            created_at=datetime.utcnow()
        )
        
        pack_id = await self.processor._generate_pack(
            fingerprint, self.sample_composed_answer, "test-trace"
        )
        
        assert pack_id is not None
        assert pack_id.startswith("pack-test123-")
    
    def test_update_success_metrics(self):
        """Test success metrics updating."""
        # Process multiple successful queries
        processing_times = [100.0, 200.0, 300.0]
        retrieval_times = [50.0, 75.0, 100.0]
        composition_times = [30.0, 40.0, 50.0]
        
        for i, (total, retrieval, composition) in enumerate(zip(processing_times, retrieval_times, composition_times)):
            self.processor._update_success_metrics(total, retrieval, composition)
            
            assert self.processor.metrics["successful_queries"] == i + 1
        
        # Check averages
        assert self.processor.metrics["avg_processing_time_ms"] == 200.0  # Average of 100, 200, 300
        assert self.processor.metrics["avg_retrieval_time_ms"] == 75.0    # Average of 50, 75, 100
        assert self.processor.metrics["avg_composition_time_ms"] == 40.0  # Average of 30, 40, 50
    
    def test_get_metrics(self):
        """Test metrics retrieval."""
        # Setup some metrics
        self.processor.metrics["total_queries"] = 100
        self.processor.metrics["cached_responses"] = 20
        self.processor.metrics["successful_queries"] = 85
        self.processor.metrics["failed_queries"] = 15
        self.processor.metrics["avg_processing_time_ms"] = 250.5
        
        metrics = self.processor.get_metrics()
        
        assert metrics["total_queries"] == 100
        assert metrics["cached_responses"] == 20
        assert metrics["successful_queries"] == 85
        assert metrics["failed_queries"] == 15
        assert metrics["cache_hit_rate"] == 0.2  # 20/100
        assert metrics["success_rate"] == 0.85   # 85/100
        assert "timestamp" in metrics
    
    @pytest.mark.asyncio
    async def test_health_check_healthy(self):
        """Test health check when all services are healthy."""
        # Mock healthy services
        mock_retriever = Mock()
        mock_retriever.health_check = AsyncMock(return_value={"status": "healthy"})
        self.processor.retriever = mock_retriever
        
        mock_guardrails = Mock()
        mock_guardrails.health_check = Mock(return_value={"status": "healthy"})
        self.processor.guardrails = mock_guardrails
        
        mock_composer = Mock()
        mock_composer.health_check = Mock(return_value={"status": "healthy"})
        self.processor.composer = mock_composer
        
        health = await self.processor.health_check()
        
        assert health["status"] == "healthy"
        assert health["services"]["retriever"] == "healthy"
        assert health["services"]["guardrails"] == "healthy"
        assert health["services"]["composer"] == "healthy"
        assert "metrics" in health
        assert "timestamp" in health
    
    @pytest.mark.asyncio
    async def test_health_check_degraded(self):
        """Test health check when some services are unhealthy."""
        # Mock services with mixed health
        mock_retriever = Mock()
        mock_retriever.health_check = AsyncMock(return_value={"status": "unhealthy"})
        self.processor.retriever = mock_retriever
        
        mock_guardrails = Mock()
        mock_guardrails.health_check = Mock(return_value={"status": "healthy"})
        self.processor.guardrails = mock_guardrails
        
        mock_composer = Mock()
        mock_composer.health_check = Mock(return_value={"status": "healthy"})
        self.processor.composer = mock_composer
        
        health = await self.processor.health_check()
        
        assert health["status"] == "degraded"
        assert health["services"]["retriever"] == "unhealthy"
        assert "unhealthy_services" in health
        assert "retriever" in health["unhealthy_services"]


class TestQueryProcessingException:
    """Test query processing exception."""
    
    def test_exception_creation(self):
        """Test exception creation."""
        exception = QueryProcessingException("Test error", "test_code")
        
        assert exception.message == "Test error"
        assert exception.error_code == "test_code"
        assert str(exception) == "Test error"


class TestQueryProcessorGlobal:
    """Test global query processor functions."""
    
    @pytest.mark.asyncio
    async def test_get_query_processor_singleton(self):
        """Test that get_query_processor returns singleton instance."""
        # Clear any existing instance
        import services.pipeline.query_processor
        services.pipeline.query_processor._query_processor = None
        
        with patch('services.pipeline.query_processor.QueryProcessor') as mock_processor_class:
            mock_processor = Mock()
            mock_processor.initialize = AsyncMock()
            mock_processor_class.return_value = mock_processor
            
            processor1 = await get_query_processor()
            processor2 = await get_query_processor()
            
            assert processor1 is processor2
            mock_processor.initialize.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_process_query_convenience_function(self):
        """Test convenience function for query processing."""
        with patch('services.pipeline.query_processor.get_query_processor') as mock_get_processor:
            mock_processor = Mock()
            mock_processor.process_query = AsyncMock(return_value=Mock(spec=ProcessingResult))
            mock_get_processor.return_value = mock_processor
            
            result = await process_query(
                question="测试问题",
                province="guangdong",
                doc_class="grid_connection",
                asset="solar",
                trace_id="test-123"
            )
            
            assert result is not None
            mock_processor.process_query.assert_called_once_with(
                question="测试问题",
                province="guangdong",
                doc_class="grid_connection",
                asset="solar",
                lang="zh-CN",
                max_citations=10,
                trace_id="test-123"
            )


if __name__ == "__main__":
    pytest.main([__file__])