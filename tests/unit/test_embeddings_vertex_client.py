"""Tests for Vertex AI embedding client."""

import pytest
import asyncio
from uuid import uuid4

from services.embeddings.vertex_client import VertexAIEmbeddingClientMock
from services.embeddings.schemas import EmbeddingRequest, EmbeddingModel, EmbeddingStatus


class TestVertexAIEmbeddingClient:
    """Test Vertex AI embedding client functionality."""
    
    @pytest.fixture
    def client(self):
        """Create mock Vertex AI client for testing."""
        return VertexAIEmbeddingClientMock()
    
    @pytest.fixture
    def sample_texts(self):
        """Sample Chinese energy regulation texts."""
        return [
            "第一条：风力发电项目应当符合技术要求，装机容量不少于50MW。",
            "第二条：电压等级应当为110KV或以上，功率因数不低于0.95。",
            "第三条：项目建设期间应当严格执行安全规程。"
        ]
    
    @pytest.mark.asyncio
    async def test_generate_embeddings_success(self, client, sample_texts):
        """Test successful embedding generation."""
        request = EmbeddingRequest(
            texts=sample_texts,
            model=EmbeddingModel.VERTEX_AI_MULTILINGUAL
        )
        
        result = await client.generate_embeddings(request)
        
        assert result.is_success()
        assert result.status == EmbeddingStatus.SUCCESS
        assert len(result.embeddings) == len(sample_texts)
        assert result.successful_embeddings == len(sample_texts)
        assert result.failed_embeddings == 0
        assert result.processing_time_ms > 0
        
        # Check embedding properties
        for i, embedding in enumerate(result.embeddings):
            assert embedding.text == sample_texts[i]
            assert len(embedding.embedding) == 768  # Standard dimension
            assert embedding.dimension == 768
            assert embedding.model == EmbeddingModel.VERTEX_AI_MULTILINGUAL
    
    @pytest.mark.asyncio
    async def test_generate_embeddings_with_metadata(self, client, sample_texts):
        """Test embedding generation with citation and chunk metadata."""
        citation_ids = [uuid4() for _ in sample_texts]
        chunk_ids = [f"chunk-{i}" for i in range(len(sample_texts))]
        
        request = EmbeddingRequest(
            texts=sample_texts,
            model=EmbeddingModel.VERTEX_AI_MULTILINGUAL,
            citation_ids=citation_ids,
            chunk_ids=chunk_ids,
            province="guangdong",
            doc_class="grid_connection"
        )
        
        result = await client.generate_embeddings(request)
        
        assert result.is_success()
        assert len(result.embeddings) == len(sample_texts)
        
        # Check metadata
        for i, embedding in enumerate(result.embeddings):
            assert embedding.citation_id == citation_ids[i]
            assert embedding.chunk_id == chunk_ids[i]
    
    @pytest.mark.asyncio
    async def test_generate_single_embedding(self, client):
        """Test single embedding generation."""
        text = "广东省电网接入管理办法第一条"
        
        embedding = await client.generate_single_embedding(text)
        
        assert embedding is not None
        assert embedding.text == text
        assert len(embedding.embedding) == 768
        assert embedding.dimension == 768
    
    @pytest.mark.asyncio
    async def test_embedding_normalization(self, client):
        """Test embedding normalization."""
        text = "测试文本"
        
        # Test with normalization
        embedding_normalized = await client.generate_single_embedding(text, normalize=True)
        
        # Test without normalization
        embedding_raw = await client.generate_single_embedding(text, normalize=False)
        
        assert embedding_normalized is not None
        assert embedding_raw is not None
        
        # Normalized embedding should have different values
        # (In mock, this might not be perfectly realistic, but tests the interface)
        assert embedding_normalized.embedding != embedding_raw.embedding
    
    @pytest.mark.asyncio
    async def test_different_models(self, client):
        """Test different embedding models."""
        text = "测试不同的模型"
        
        models = [
            EmbeddingModel.VERTEX_AI_MULTILINGUAL,
            EmbeddingModel.VERTEX_AI_ENGLISH,
            EmbeddingModel.VERTEX_AI_CHINESE
        ]
        
        for model in models:
            embedding = await client.generate_single_embedding(text, model=model)
            
            assert embedding is not None
            assert embedding.model == model
            assert len(embedding.embedding) == 768
    
    @pytest.mark.asyncio
    async def test_batch_processing(self, client):
        """Test batch processing with different batch sizes."""
        texts = [f"测试文本 {i}" for i in range(50)]
        
        request = EmbeddingRequest(
            texts=texts,
            batch_size=10  # Process in batches of 10
        )
        
        result = await client.generate_embeddings(request)
        
        assert result.is_success()
        assert len(result.embeddings) == len(texts)
        assert result.successful_embeddings == len(texts)
    
    @pytest.mark.asyncio
    async def test_empty_texts_validation(self, client):
        """Test validation of empty texts."""
        with pytest.raises(ValueError, match="Texts list cannot be empty"):
            EmbeddingRequest(texts=[])
        
        with pytest.raises(ValueError, match="Individual texts cannot be empty"):
            EmbeddingRequest(texts=["valid text", "", "another valid text"])
    
    @pytest.mark.asyncio
    async def test_batch_size_validation(self, client):
        """Test batch size validation."""
        texts = ["test text"]
        
        with pytest.raises(ValueError, match="Batch size must be between 1 and 1000"):
            EmbeddingRequest(texts=texts, batch_size=0)
        
        with pytest.raises(ValueError, match="Batch size must be between 1 and 1000"):
            EmbeddingRequest(texts=texts, batch_size=1001)
    
    @pytest.mark.asyncio
    async def test_health_check(self, client):
        """Test client health check."""
        health = await client.health_check()
        
        assert health["status"] == "healthy"
        assert "latency_ms" in health
        assert "test_embedding_dimension" in health
        assert health["test_embedding_dimension"] == 768
    
    def test_model_info(self, client):
        """Test getting model information."""
        model_info = client.get_model_info(EmbeddingModel.VERTEX_AI_MULTILINGUAL)
        
        assert "model_name" in model_info
        assert "dimension" in model_info
        assert "supports_chinese" in model_info
        assert "supports_batch" in model_info
        assert model_info["dimension"] == 768
        assert model_info["supports_chinese"] is True
        assert model_info["supports_batch"] is True
    
    @pytest.mark.asyncio
    async def test_deterministic_embeddings(self, client):
        """Test that same text produces same embedding (in mock)."""
        text = "相同的文本应该产生相同的嵌入"
        
        embedding1 = await client.generate_single_embedding(text)
        embedding2 = await client.generate_single_embedding(text)
        
        assert embedding1 is not None
        assert embedding2 is not None
        assert embedding1.embedding == embedding2.embedding
    
    @pytest.mark.asyncio
    async def test_chinese_text_handling(self, client):
        """Test handling of Chinese text specifically."""
        chinese_texts = [
            "广东省能源局关于电网接入的通知",
            "风力发电项目技术要求：装机容量≥50MW",
            "第一条：本办法适用于广东省内所有风电项目。",
            "（一）电压等级为110千伏及以上；",
            "（二）功率因数不低于0.95；"
        ]
        
        request = EmbeddingRequest(texts=chinese_texts)
        result = await client.generate_embeddings(request)
        
        assert result.is_success()
        assert len(result.embeddings) == len(chinese_texts)
        
        # All embeddings should have proper dimensions
        for embedding in result.embeddings:
            assert len(embedding.embedding) == 768
            assert all(isinstance(val, float) for val in embedding.embedding)
    
    @pytest.mark.asyncio
    async def test_mixed_language_text(self, client):
        """Test handling of mixed Chinese-English text."""
        mixed_texts = [
            "Guangdong Province 广东省 Grid Connection Requirements",
            "Wind Power 风力发电 Capacity: 50MW 装机容量：50兆瓦",
            "Technical Requirements 技术要求: Voltage Level 电压等级 110kV"
        ]
        
        request = EmbeddingRequest(texts=mixed_texts)
        result = await client.generate_embeddings(request)
        
        assert result.is_success()
        assert len(result.embeddings) == len(mixed_texts)
    
    @pytest.mark.asyncio
    async def test_long_text_handling(self, client):
        """Test handling of long texts."""
        # Create a long text (but within limits)
        long_text = "广东省电网接入管理办法。" * 100  # Repeat to make it long
        
        embedding = await client.generate_single_embedding(long_text)
        
        assert embedding is not None
        assert len(embedding.embedding) == 768
        # Text should be truncated if too long (handled in preprocessing)
    
    @pytest.mark.asyncio
    async def test_concurrent_requests(self, client):
        """Test concurrent embedding requests."""
        texts_batches = [
            [f"批次1文本{i}" for i in range(5)],
            [f"批次2文本{i}" for i in range(5)],
            [f"批次3文本{i}" for i in range(5)]
        ]
        
        # Create concurrent requests
        tasks = []
        for texts in texts_batches:
            request = EmbeddingRequest(texts=texts)
            task = client.generate_embeddings(request)
            tasks.append(task)
        
        # Execute concurrently
        results = await asyncio.gather(*tasks)
        
        # All should succeed
        assert all(result.is_success() for result in results)
        assert all(len(result.embeddings) == 5 for result in results)


class TestEmbeddingVector:
    """Test EmbeddingVector functionality."""
    
    def test_embedding_vector_creation(self):
        """Test creating embedding vector."""
        from services.embeddings.schemas import EmbeddingVector
        
        embedding = EmbeddingVector(
            text="测试文本",
            embedding=[0.1, 0.2, 0.3],
            dimension=3,
            model=EmbeddingModel.VERTEX_AI_MULTILINGUAL
        )
        
        assert embedding.text == "测试文本"
        assert embedding.embedding == [0.1, 0.2, 0.3]
        assert embedding.dimension == 3
        assert embedding.model == EmbeddingModel.VERTEX_AI_MULTILINGUAL
    
    def test_embedding_normalization(self):
        """Test embedding normalization."""
        from services.embeddings.schemas import EmbeddingVector
        
        embedding = EmbeddingVector(
            text="测试",
            embedding=[3.0, 4.0],  # Magnitude = 5.0
            dimension=2,
            model=EmbeddingModel.VERTEX_AI_MULTILINGUAL
        )
        
        normalized = embedding.get_normalized_embedding()
        
        # Should be [0.6, 0.8] (3/5, 4/5)
        assert abs(normalized[0] - 0.6) < 1e-6
        assert abs(normalized[1] - 0.8) < 1e-6
        
        # Check that norm is calculated
        assert embedding.norm == 5.0
    
    def test_embedding_dimension_validation(self):
        """Test embedding dimension validation."""
        from services.embeddings.schemas import EmbeddingVector
        
        with pytest.raises(ValueError, match="Embedding length .* does not match dimension"):
            EmbeddingVector(
                text="测试",
                embedding=[0.1, 0.2],  # Length 2
                dimension=3,  # But dimension is 3
                model=EmbeddingModel.VERTEX_AI_MULTILINGUAL
            )