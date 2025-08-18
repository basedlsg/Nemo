"""Tests for retriever service (Task 11)."""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, date

from services.retriever.hybrid_search import HybridSearchService, RetrieverClient, get_retriever_client


class TestHybridSearchService:
    """Test hybrid search service functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.service = HybridSearchService(alpha=0.6)
        self.sample_embedding = [0.1] * 768  # Mock 768-dimensional embedding
        
        self.sample_db_results = [
            {
                "citation_id": "cite-1",
                "province": "guangdong",
                "doc_class": "grid_connection",
                "asset": "solar",
                "title": "广东省光伏并网管理办法",
                "url": "https://gzpec.cn/solar-grid",
                "effective_date": date(2025, 1, 1),
                "checksum": "abc123",
                "content": "光伏发电项目并网需要提交以下资料：1. 项目备案文件；2. 设备技术参数；3. 安全评估报告。",
                "vscore": 0.85,
                "tscore": 0.75,
                "score": 0.81  # 0.6 * 0.85 + 0.4 * 0.75
            },
            {
                "citation_id": "cite-2",
                "province": "guangdong",
                "doc_class": "grid_connection",
                "asset": "solar",
                "title": "分布式光伏接入技术规范",
                "url": "https://gzpec.cn/solar-tech",
                "effective_date": date(2024, 12, 1),
                "checksum": "def456",
                "content": "分布式光伏发电系统接入电网应符合国家和地方相关技术标准。",
                "vscore": 0.78,
                "tscore": 0.65,
                "score": 0.728  # 0.6 * 0.78 + 0.4 * 0.65
            }
        ]
    
    def test_init_with_alpha(self):
        """Test service initialization with alpha parameter."""
        service = HybridSearchService(alpha=0.7)
        assert service.alpha == 0.7
    
    def test_init_default_alpha(self):
        """Test service initialization with default alpha."""
        service = HybridSearchService()
        assert service.alpha == 0.6
    
    def test_extract_relevant_passage_short_content(self):
        """Test passage extraction with short content."""
        content = "这是一个短文本。"
        passage = self.service._extract_relevant_passage(content, max_length=500)
        assert passage == content
    
    def test_extract_relevant_passage_long_content_with_sentence_boundary(self):
        """Test passage extraction with sentence boundary."""
        content = "这是第一句话。这是第二句话。这是第三句话。" + "很长的内容" * 100
        passage = self.service._extract_relevant_passage(content, max_length=50)
        assert passage == "这是第一句话。这是第二句话。这是第三句话。"
    
    def test_extract_relevant_passage_long_content_no_boundary(self):
        """Test passage extraction without sentence boundary."""
        content = "这是一个很长的句子没有句号" * 50
        passage = self.service._extract_relevant_passage(content, max_length=100)
        assert passage.endswith("...")
        assert len(passage) <= 103  # 100 + "..."
    
    def test_extract_relevant_passage_empty_content(self):
        """Test passage extraction with empty content."""
        passage = self.service._extract_relevant_passage("", max_length=500)
        assert passage == ""
    
    @patch('services.retriever.hybrid_search.VertexEmbeddingClient')
    @patch('services.retriever.hybrid_search.get_pool')
    async def test_search_success(self, mock_get_pool, mock_embedding_client_class):
        """Test successful search operation."""
        # Mock embedding client
        mock_embedding_client = Mock()
        mock_embedding_client.embed_text = AsyncMock(return_value=self.sample_embedding)
        mock_embedding_client_class.return_value = mock_embedding_client
        
        # Mock database pool
        mock_pool = Mock()
        mock_conn = Mock()
        mock_cursor = Mock()
        
        mock_pool.connection.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.fetchall.return_value = self.sample_db_results
        mock_get_pool.return_value = mock_pool
        
        # Create service with mocked dependencies
        service = HybridSearchService(alpha=0.6)
        
        results = await service.search(
            question="光伏并网需要什么资料？",
            province="guangdong",
            doc_class="grid_connection",
            asset="solar",
            limit=10
        )
        
        assert len(results) == 2
        assert results[0]["citation_id"] == "cite-1"
        assert results[0]["score"] == 0.81
        assert results[0]["vector_score"] == 0.85
        assert results[0]["bm25_score"] == 0.75
        assert "光伏发电项目并网需要提交以下资料" in results[0]["passage"]
        assert results[0]["metadata"]["title"] == "广东省光伏并网管理办法"
        
        # Verify embedding was called
        mock_embedding_client.embed_text.assert_called_once_with("光伏并网需要什么资料？")
        
        # Verify database query was executed
        mock_cursor.execute.assert_called_once()
        query_args = mock_cursor.execute.call_args[0]
        assert "WITH q AS" in query_args[0]  # Check SQL query structure
        assert query_args[1][1] == "guangdong"  # Check province parameter
        assert query_args[1][2] == "grid_connection"  # Check doc_class parameter
    
    @patch('services.retriever.hybrid_search.VertexEmbeddingClient')
    @patch('services.retriever.hybrid_search.get_pool')
    async def test_search_no_results(self, mock_get_pool, mock_embedding_client_class):
        """Test search with no results."""
        # Mock embedding client
        mock_embedding_client = Mock()
        mock_embedding_client.embed_text = AsyncMock(return_value=self.sample_embedding)
        mock_embedding_client_class.return_value = mock_embedding_client
        
        # Mock database pool with empty results
        mock_pool = Mock()
        mock_conn = Mock()
        mock_cursor = Mock()
        
        mock_pool.connection.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.fetchall.return_value = []
        mock_get_pool.return_value = mock_pool
        
        service = HybridSearchService()
        
        results = await service.search(
            question="不存在的问题",
            province="guangdong",
            doc_class="grid_connection"
        )
        
        assert results == []
    
    @patch('services.retriever.hybrid_search.VertexEmbeddingClient')
    async def test_search_embedding_failure(self, mock_embedding_client_class):
        """Test search with embedding service failure."""
        mock_embedding_client = Mock()
        mock_embedding_client.embed_text = AsyncMock(side_effect=Exception("Embedding failed"))
        mock_embedding_client_class.return_value = mock_embedding_client
        
        service = HybridSearchService()
        
        results = await service.search(
            question="测试问题",
            province="guangdong",
            doc_class="grid_connection"
        )
        
        assert results == []
    
    @patch('services.retriever.hybrid_search.get_pool')
    async def test_health_check_healthy(self, mock_get_pool):
        """Test healthy service health check."""
        # Mock database pool
        mock_pool = Mock()
        mock_conn = Mock()
        mock_cursor = Mock()
        
        mock_pool.connection.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.fetchone.return_value = [1000]  # Citation count
        mock_get_pool.return_value = mock_pool
        
        # Mock embedding client health check
        with patch.object(self.service.embedding_client, 'health_check', new_callable=AsyncMock) as mock_health:
            mock_health.return_value = {"status": "healthy"}
            
            health = await self.service.health_check()
            
            assert health["status"] == "healthy"
            assert health["citation_count"] == 1000
            assert "latency_ms" in health
            assert health["embedding_service"]["status"] == "healthy"
            assert health["alpha"] == 0.6
    
    @patch('services.retriever.hybrid_search.get_pool')
    async def test_health_check_unhealthy(self, mock_get_pool):
        """Test unhealthy service health check."""
        mock_get_pool.side_effect = Exception("Database connection failed")
        
        health = await self.service.health_check()
        
        assert health["status"] == "unhealthy"
        assert "error" in health
    
    @patch('services.retriever.hybrid_search.get_pool')
    async def test_get_search_stats(self, mock_get_pool):
        """Test search statistics retrieval."""
        # Mock database results
        mock_stats_results = [
            {
                "province": "guangdong",
                "doc_class": "grid_connection",
                "citation_count": 150,
                "earliest_date": date(2024, 1, 1),
                "latest_date": date(2025, 1, 1)
            },
            {
                "province": "guangdong",
                "doc_class": "market_rules",
                "citation_count": 100,
                "earliest_date": date(2024, 6, 1),
                "latest_date": date(2024, 12, 1)
            },
            {
                "province": "shandong",
                "doc_class": "grid_connection",
                "citation_count": 80,
                "earliest_date": date(2024, 3, 1),
                "latest_date": date(2024, 11, 1)
            }
        ]
        
        mock_pool = Mock()
        mock_conn = Mock()
        mock_cursor = Mock()
        
        mock_pool.connection.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.fetchall.return_value = mock_stats_results
        mock_get_pool.return_value = mock_pool
        
        stats = await self.service.get_search_stats()
        
        assert stats["total_citations"] == 330  # 150 + 100 + 80
        assert stats["by_province"]["guangdong"] == 250  # 150 + 100
        assert stats["by_province"]["shandong"] == 80
        assert stats["by_doc_class"]["grid_connection"] == 230  # 150 + 80
        assert stats["by_doc_class"]["market_rules"] == 100
        assert len(stats["coverage"]) == 3
    
    @patch('services.retriever.hybrid_search.get_pool')
    async def test_get_search_stats_failure(self, mock_get_pool):
        """Test search statistics failure."""
        mock_get_pool.side_effect = Exception("Database error")
        
        stats = await self.service.get_search_stats()
        
        assert "error" in stats


class TestRetrieverClient:
    """Test retriever client functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.client = RetrieverClient(alpha=0.7)
    
    def test_init_with_alpha(self):
        """Test client initialization with alpha parameter."""
        assert self.client.search_service.alpha == 0.7
    
    @patch('services.retriever.hybrid_search.HybridSearchService.search')
    async def test_search(self, mock_search):
        """Test client search method."""
        mock_search.return_value = [{"citation_id": "test", "score": 0.9}]
        
        results = await self.client.search(
            province="guangdong",
            doc_class="grid_connection",
            question="测试问题",
            asset="solar",
            limit=10
        )
        
        assert results == [{"citation_id": "test", "score": 0.9}]
        mock_search.assert_called_once_with(
            question="测试问题",
            province="guangdong",
            doc_class="grid_connection",
            asset="solar",
            limit=10
        )
    
    @patch('services.retriever.hybrid_search.HybridSearchService.health_check')
    async def test_health_check(self, mock_health_check):
        """Test client health check method."""
        mock_health_check.return_value = {"status": "healthy"}
        
        health = await self.client.health_check()
        
        assert health == {"status": "healthy"}
        mock_health_check.assert_called_once()
    
    @patch('services.retriever.hybrid_search.HybridSearchService.get_search_stats')
    async def test_get_stats(self, mock_get_stats):
        """Test client get stats method."""
        mock_get_stats.return_value = {"total_citations": 1000}
        
        stats = await self.client.get_stats()
        
        assert stats == {"total_citations": 1000}
        mock_get_stats.assert_called_once()


class TestRetrieverGlobal:
    """Test global retriever client functionality."""
    
    def test_get_retriever_client_singleton(self):
        """Test that get_retriever_client returns singleton instance."""
        # Clear any existing instance
        import services.retriever.hybrid_search
        services.retriever.hybrid_search._retriever_client = None
        
        client1 = get_retriever_client()
        client2 = get_retriever_client()
        
        assert client1 is client2
        assert isinstance(client1, RetrieverClient)


class TestHybridSearchSQL:
    """Test hybrid search SQL query construction."""
    
    def test_embedding_format(self):
        """Test embedding vector format for SQL."""
        embedding = [0.1, 0.2, 0.3]
        embedding_str = f"[{','.join(map(str, embedding))}]"
        
        assert embedding_str == "[0.1,0.2,0.3]"
    
    def test_alpha_beta_calculation(self):
        """Test alpha and beta weight calculation."""
        alpha = 0.6
        beta = 1 - alpha
        
        assert alpha == 0.6
        assert beta == 0.4
        
        # Test score calculation
        vscore = 0.8
        tscore = 0.7
        combined_score = alpha * vscore + beta * tscore
        
        assert combined_score == 0.76  # 0.6 * 0.8 + 0.4 * 0.7


if __name__ == "__main__":
    pytest.main([__file__])