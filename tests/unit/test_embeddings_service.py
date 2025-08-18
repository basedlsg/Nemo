"""Tests for embedding service integration."""

import pytest
import asyncio
from uuid import uuid4
from datetime import date

from services.embeddings.service import EmbeddingService, create_embedding_service
from services.embeddings.schemas import EmbeddingModel, EmbeddingRequest
from services.ocr.schemas import ChunkData, CitationRow


class TestEmbeddingService:
    """Test embedding service functionality."""
    
    @pytest.fixture
    def service(self):
        """Create embedding service with mocks for testing."""
        return create_embedding_service(use_mock=True)
    
    @pytest.fixture
    def sample_citation(self):
        """Create sample citation row."""
        return CitationRow(
            citation_id=uuid4(),
            province="guangdong",
            doc_class="grid_connection",
            asset="wind",
            title="广东省风电接入技术要求",
            url="https://gzpec.cn/wind-grid-connection",
            checksum="a" * 64,
            content="Combined content from chunks",
            effective_date=date(2025, 6, 1)
        )
    
    @pytest.fixture
    def sample_chunks(self):
        """Create sample text chunks."""
        return [
            ChunkData(
                chunk_id="chunk-1",
                content="第一条：风力发电项目应当符合技术要求，装机容量不少于50MW。",
                token_count=25,
                clause_type="article"
            ),
            ChunkData(
                chunk_id="chunk-2",
                content="第二条：电压等级应当为110KV或以上，功率因数不低于0.95。",
                token_count=22,
                clause_type="technical"
            ),
            ChunkData(
                chunk_id="chunk-3",
                content="第三条：项目建设期间应当严格执行安全规程。",
                token_count=18,
                clause_type="requirement"
            )
        ]
    
    @pytest.mark.asyncio
    async def test_service_initialization(self, service):
        """Test service initialization."""
        await service.initialize()
        
        # Service should be ready
        health = await service.health_check()
        assert health["status"] in ["healthy", "degraded"]
    
    @pytest.mark.asyncio
    async def test_process_citation_chunks(self, service, sample_citation, sample_chunks):
        """Test processing citation chunks end-to-end."""
        await service.initialize()
        
        result = await service.process_citation_chunks(
            sample_citation, 
            sample_chunks,
            EmbeddingModel.VERTEX_AI_MULTILINGUAL
        )
        
        assert result["success"] is True
        assert result["citation_id"] == str(sample_citation.citation_id)
        assert result["chunks_processed"] == len(sample_chunks)
        assert result["embeddings_generated"] == len(sample_chunks)
        assert result["embeddings_stored"] > 0
        assert result["processing_time_ms"] > 0
        
        # Check embedding result
        embedding_result = result["embedding_result"]
        assert embedding_result.is_success()
        assert len(embedding_result.embeddings) == len(sample_chunks)
        
        # Check storage result
        storage_result = result["storage_result"]
        assert storage_result.is_success()
        assert storage_result.stored_count == len(sample_chunks)
    
    @pytest.mark.asyncio
    async def test_generate_embeddings_direct(self, service):
        """Test direct embedding generation."""
        await service.initialize()
        
        texts = [
            "广东省电网接入管理办法",
            "风力发电项目技术要求",
            "电压等级110KV以上"
        ]
        
        request = EmbeddingRequest(texts=texts)
        result = await service.generate_embeddings(request)
        
        assert result.is_success()
        assert len(result.embeddings) == len(texts)
        assert result.successful_embeddings == len(texts)
        
        # Check embedding properties
        for i, embedding in enumerate(result.embeddings):
            assert embedding.text == texts[i]
            assert len(embedding.embedding) == 768
            assert embedding.dimension == 768
    
    @pytest.mark.asyncio
    async def test_search_similar_citations(self, service, sample_citation, sample_chunks):
        """Test semantic similarity search."""
        await service.initialize()
        
        # First, process and store some citations
        await service.process_citation_chunks(sample_citation, sample_chunks)
        
        # Now search for similar content
        query_text = "风力发电项目装机容量要求"
        
        results = await service.search_similar_citations(
            query_text,
            province="guangdong",
            limit=5,
            similarity_threshold=0.5
        )
        
        # Should find some results (mock will return mock data)
        assert isinstance(results, list)
        # In mock implementation, this might return mock results
    
    @pytest.mark.asyncio
    async def test_batch_process_citations(self, service):
        """Test batch processing of multiple citations."""
        await service.initialize()
        
        # Create multiple citation-chunk pairs
        citations_and_chunks = []
        
        for i in range(3):
            citation = CitationRow(
                citation_id=uuid4(),
                province="guangdong",
                doc_class="grid_connection",
                asset="wind",
                title=f"测试文档 {i+1}",
                url=f"https://example.com/doc-{i+1}",
                checksum=f"{i}" * 64,
                content=f"文档内容 {i+1}"
            )
            
            chunks = [
                ChunkData(
                    chunk_id=f"chunk-{i}-1",
                    content=f"第一条：文档{i+1}的第一条内容。",
                    token_count=15,
                    clause_type="article"
                ),
                ChunkData(
                    chunk_id=f"chunk-{i}-2",
                    content=f"第二条：文档{i+1}的第二条内容。",
                    token_count=15,
                    clause_type="article"
                )
            ]
            
            citations_and_chunks.append((citation, chunks))
        
        # Process batch
        results = await service.batch_process_citations(
            citations_and_chunks,
            max_concurrent=2
        )
        
        assert len(results) == 3
        assert all(result["success"] for result in results)
        assert all("citation_id" in result for result in results)
    
    @pytest.mark.asyncio
    async def test_delete_citation_embeddings(self, service, sample_citation, sample_chunks):
        """Test deleting citation embeddings."""
        await service.initialize()
        
        # First, process and store citation
        result = await service.process_citation_chunks(sample_citation, sample_chunks)
        assert result["success"]
        
        # Delete embeddings
        deleted = await service.delete_citation_embeddings(sample_citation.citation_id)
        
        # In mock implementation, this should work
        assert isinstance(deleted, bool)
    
    @pytest.mark.asyncio
    async def test_health_check(self, service):
        """Test service health check."""
        await service.initialize()
        
        health = await service.health_check()
        
        assert "status" in health
        assert health["status"] in ["healthy", "degraded", "unhealthy"]
        assert "vertex_ai" in health
        assert "vector_storage" in health
        assert "metrics" in health
        assert "timestamp" in health
    
    @pytest.mark.asyncio
    async def test_get_metrics(self, service, sample_citation, sample_chunks):
        """Test getting service metrics."""
        await service.initialize()
        
        # Process some data to generate metrics
        await service.process_citation_chunks(sample_citation, sample_chunks)
        
        metrics = await service.get_metrics()
        
        assert "total_requests" in metrics
        assert "successful_requests" in metrics
        assert "total_embeddings_generated" in metrics
        assert "success_rate" in metrics
        assert "embeddings_per_second" in metrics
        assert "storage_stats" in metrics
        
        # Should have processed at least one request
        assert metrics["total_requests"] >= 1
        assert metrics["total_embeddings_generated"] >= len(sample_chunks)
    
    @pytest.mark.asyncio
    async def test_different_models(self, service, sample_citation, sample_chunks):
        """Test processing with different embedding models."""
        await service.initialize()
        
        models = [
            EmbeddingModel.VERTEX_AI_MULTILINGUAL,
            EmbeddingModel.VERTEX_AI_CHINESE,
            EmbeddingModel.VERTEX_AI_ENGLISH
        ]
        
        for model in models:
            result = await service.process_citation_chunks(
                sample_citation, 
                sample_chunks[:1],  # Use just one chunk for speed
                model
            )
            
            assert result["success"] is True
            assert result["embedding_result"].model_used == model
    
    @pytest.mark.asyncio
    async def test_error_handling(self, service):
        """Test error handling in service."""
        await service.initialize()
        
        # Test with invalid citation (None)
        result = await service.process_citation_chunks(None, [])
        
        assert result["success"] is False
        assert "error" in result
    
    @pytest.mark.asyncio
    async def test_service_close(self, service):
        """Test service cleanup."""
        await service.initialize()
        
        # Should close without errors
        await service.close()


class TestEmbeddingServiceIntegration:
    """Test embedding service with realistic data."""
    
    @pytest.fixture
    def service(self):
        return create_embedding_service(use_mock=True)
    
    @pytest.fixture
    def guangdong_wind_citation(self):
        """Realistic Guangdong wind power citation."""
        return CitationRow(
            citation_id=uuid4(),
            province="guangdong",
            doc_class="grid_connection",
            asset="wind",
            title="广东省风力发电项目电网接入管理办法",
            url="https://gzpec.cn/wind-grid-connection-rules",
            checksum="wind123" + "0" * 57,
            content="广东省风力发电项目电网接入管理办法相关内容",
            effective_date=date(2025, 6, 1)
        )
    
    @pytest.fixture
    def guangdong_wind_chunks(self):
        """Realistic Guangdong wind power chunks."""
        return [
            ChunkData(
                chunk_id="gd-wind-1",
                content="第一条：风力发电项目接入电网应当符合以下技术要求：装机容量不少于50MW，电压等级为110KV或以上。",
                token_count=35,
                clause_type="article"
            ),
            ChunkData(
                chunk_id="gd-wind-2",
                content="第二条：风电场应当配备完善的功率预测系统，预测精度不低于85%，并与电网调度机构实现数据共享。",
                token_count=32,
                clause_type="technical"
            ),
            ChunkData(
                chunk_id="gd-wind-3",
                content="第三条：项目建设期间应当严格执行环境保护要求，确保生态环境安全，不得破坏当地生态平衡。",
                token_count=30,
                clause_type="environmental"
            ),
            ChunkData(
                chunk_id="gd-wind-4",
                content="第四条：风电项目应当建立完善的安全管理体系，配备专业技术人员，定期进行设备维护和安全检查。",
                token_count=31,
                clause_type="safety"
            )
        ]
    
    @pytest.mark.asyncio
    async def test_realistic_wind_power_processing(
        self, 
        service, 
        guangdong_wind_citation, 
        guangdong_wind_chunks
    ):
        """Test processing realistic wind power regulation content."""
        await service.initialize()
        
        result = await service.process_citation_chunks(
            guangdong_wind_citation,
            guangdong_wind_chunks,
            EmbeddingModel.VERTEX_AI_MULTILINGUAL
        )
        
        assert result["success"] is True
        assert result["chunks_processed"] == 4
        assert result["embeddings_generated"] == 4
        assert result["embeddings_stored"] == 4
        
        # Check that all chunks were processed
        embedding_result = result["embedding_result"]
        assert len(embedding_result.embeddings) == 4
        
        # Verify chunk metadata is preserved
        for i, embedding in enumerate(embedding_result.embeddings):
            expected_chunk = guangdong_wind_chunks[i]
            assert embedding.text == expected_chunk.content
            assert embedding.chunk_id == expected_chunk.chunk_id
            assert embedding.citation_id == guangdong_wind_citation.citation_id
    
    @pytest.mark.asyncio
    async def test_multi_province_processing(self, service):
        """Test processing citations from different provinces."""
        await service.initialize()
        
        # Create citations for different provinces
        provinces_data = [
            ("guangdong", "广东省风电接入规定", "风力发电项目应当符合广东省技术标准。"),
            ("shandong", "山东省电力调度规程", "电力调度应当遵循山东省统一调度原则。"),
            ("inner_mongolia", "内蒙古风电管理办法", "风电项目开发应当符合内蒙古自治区规划要求。")
        ]
        
        citations_and_chunks = []
        
        for province, title, content in provinces_data:
            citation = CitationRow(
                citation_id=uuid4(),
                province=province,
                doc_class="grid_connection",
                asset="wind",
                title=title,
                url=f"https://{province}.gov.cn/regulations",
                checksum=province + "0" * (64 - len(province)),
                content=content
            )
            
            chunks = [
                ChunkData(
                    chunk_id=f"{province}-chunk-1",
                    content=content,
                    token_count=len(content) // 4,
                    clause_type="article"
                )
            ]
            
            citations_and_chunks.append((citation, chunks))
        
        # Process all provinces
        results = await service.batch_process_citations(citations_and_chunks)
        
        assert len(results) == 3
        assert all(result["success"] for result in results)
        
        # Each province should be processed successfully
        for i, result in enumerate(results):
            province = provinces_data[i][0]
            assert result["chunks_processed"] == 1
            assert result["embeddings_generated"] == 1
    
    @pytest.mark.asyncio
    async def test_semantic_search_quality(self, service, guangdong_wind_citation, guangdong_wind_chunks):
        """Test semantic search quality with realistic queries."""
        await service.initialize()
        
        # Store the wind power citation
        await service.process_citation_chunks(guangdong_wind_citation, guangdong_wind_chunks)
        
        # Test various search queries
        search_queries = [
            "风力发电装机容量要求",
            "电网接入技术标准",
            "功率预测系统精度",
            "环境保护要求",
            "安全管理体系"
        ]
        
        for query in search_queries:
            results = await service.search_similar_citations(
                query,
                province="guangdong",
                limit=3,
                similarity_threshold=0.3
            )
            
            # Should return results (mock implementation)
            assert isinstance(results, list)
            # In a real implementation, we would check similarity scores and relevance
    
    @pytest.mark.asyncio
    async def test_large_batch_processing(self, service):
        """Test processing a large batch of citations."""
        await service.initialize()
        
        # Create a larger batch
        batch_size = 10
        citations_and_chunks = []
        
        for i in range(batch_size):
            citation = CitationRow(
                citation_id=uuid4(),
                province="guangdong",
                doc_class="grid_connection",
                asset="wind",
                title=f"测试文档 {i+1}",
                url=f"https://example.com/doc-{i+1}",
                checksum=f"{i:02d}" + "0" * 62,
                content=f"这是第{i+1}个测试文档的内容。"
            )
            
            # Create multiple chunks per citation
            chunks = []
            for j in range(3):
                chunk = ChunkData(
                    chunk_id=f"batch-{i}-chunk-{j}",
                    content=f"第{j+1}条：文档{i+1}的第{j+1}条内容，包含重要的技术要求和规定。",
                    token_count=20,
                    clause_type="article"
                )
                chunks.append(chunk)
            
            citations_and_chunks.append((citation, chunks))
        
        # Process with limited concurrency
        results = await service.batch_process_citations(
            citations_and_chunks,
            max_concurrent=3
        )
        
        assert len(results) == batch_size
        successful_results = [r for r in results if r["success"]]
        assert len(successful_results) == batch_size
        
        # Check total embeddings generated
        total_embeddings = sum(r["embeddings_generated"] for r in successful_results)
        expected_embeddings = batch_size * 3  # 3 chunks per citation
        assert total_embeddings == expected_embeddings
    
    @pytest.mark.asyncio
    async def test_metrics_accuracy(self, service, guangdong_wind_citation, guangdong_wind_chunks):
        """Test that metrics are accurately tracked."""
        await service.initialize()
        
        # Get initial metrics
        initial_metrics = await service.get_metrics()
        initial_requests = initial_metrics["total_requests"]
        initial_embeddings = initial_metrics["total_embeddings_generated"]
        
        # Process citation
        result = await service.process_citation_chunks(
            guangdong_wind_citation, 
            guangdong_wind_chunks
        )
        assert result["success"]
        
        # Get updated metrics
        updated_metrics = await service.get_metrics()
        
        # Verify metrics were updated
        assert updated_metrics["total_requests"] == initial_requests + 1
        assert updated_metrics["total_embeddings_generated"] == initial_embeddings + len(guangdong_wind_chunks)
        assert updated_metrics["success_rate"] > 0
        
        # Check that storage metrics are also updated
        if "storage_stats" in updated_metrics and "total_embeddings" in updated_metrics["storage_stats"]:
            assert updated_metrics["storage_stats"]["total_embeddings"] >= len(guangdong_wind_chunks)