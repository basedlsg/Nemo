"""Tests for database foundation components (Task 2)."""

import pytest
import uuid
from datetime import datetime, date
from unittest.mock import Mock, patch, MagicMock

from services.database.pool import get_pool, db_health_ok
from services.database.simple_health import check_database_health, check_pgvector_extension, check_tables_exist
from services.database.simple_crud import CitationCRUD, SourceCRUD, PackCRUD


class TestDatabasePool:
    """Test database connection pool functionality."""
    
    @patch('services.database.pool.ConnectionPool')
    def test_get_pool_creates_pool(self, mock_pool_class):
        """Test that get_pool creates a connection pool."""
        mock_pool = Mock()
        mock_pool_class.return_value = mock_pool
        
        # Clear any existing pool
        import services.database.pool
        services.database.pool.POOL = None
        
        pool = get_pool()
        
        assert pool == mock_pool
        mock_pool_class.assert_called_once()
    
    @patch('services.database.pool.get_pool')
    def test_db_health_ok_success(self, mock_get_pool):
        """Test successful health check."""
        mock_pool = Mock()
        mock_conn = Mock()
        mock_cursor = Mock()
        
        mock_pool.connection.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.fetchone.return_value = [1]
        mock_get_pool.return_value = mock_pool
        
        result = db_health_ok()
        
        assert result is True
        mock_cursor.execute.assert_called_once_with("SELECT 1")
    
    @patch('services.database.pool.get_pool')
    def test_db_health_ok_failure(self, mock_get_pool):
        """Test health check failure."""
        mock_get_pool.side_effect = Exception("Connection failed")
        
        result = db_health_ok()
        
        assert result is False


class TestDatabaseHealth:
    """Test database health check functions."""
    
    @patch('services.database.simple_health.get_database_connection')
    def test_check_database_health_success(self, mock_get_db):
        """Test successful database health check."""
        mock_db = Mock()
        mock_db.health_check.return_value = {"status": "healthy", "pool_size": 5}
        mock_get_db.return_value = mock_db
        
        result = check_database_health()
        
        assert result["database"]["status"] == "healthy"
        assert "timestamp" in result
    
    @patch('services.database.simple_health.get_database_connection')
    def test_check_pgvector_extension_available(self, mock_get_db):
        """Test pgvector extension check when available."""
        mock_db = Mock()
        mock_conn = Mock()
        mock_cursor = Mock()
        
        mock_db.get_connection.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.fetchone.return_value = {"extname": "vector", "extversion": "0.5.0"}
        mock_get_db.return_value = mock_db
        
        result = check_pgvector_extension()
        
        assert result["pgvector"]["status"] == "available"
        assert result["pgvector"]["version"] == "0.5.0"
    
    @patch('services.database.simple_health.get_database_connection')
    def test_check_tables_exist_complete(self, mock_get_db):
        """Test table existence check when all tables exist."""
        mock_db = Mock()
        mock_conn = Mock()
        mock_cursor = Mock()
        
        mock_db.get_connection.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.fetchall.return_value = [
            {"table_name": "citations"},
            {"table_name": "sources"},
            {"table_name": "packs"}
        ]
        mock_get_db.return_value = mock_db
        
        result = check_tables_exist()
        
        assert result["tables"]["status"] == "complete"
        assert len(result["tables"]["missing"]) == 0


class TestCitationCRUD:
    """Test citation CRUD operations."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_db = Mock()
        self.crud = CitationCRUD(self.mock_db)
        self.sample_citation = {
            "citation_id": str(uuid.uuid4()),
            "province": "guangdong",
            "doc_class": "market_rules",
            "asset": "generation",
            "title": "Test Citation",
            "url": "https://example.com/doc.pdf",
            "effective_date": date.today(),
            "checksum": "abc123",
            "content": "Test content",
            "embedding": [0.1] * 768
        }
    
    def test_create_citation_success(self):
        """Test successful citation creation."""
        mock_conn = Mock()
        mock_cursor = Mock()
        
        self.mock_db.get_connection.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.fetchone.return_value = {"citation_id": self.sample_citation["citation_id"]}
        
        result = self.crud.create_citation(self.sample_citation)
        
        assert result == self.sample_citation["citation_id"]
        mock_cursor.execute.assert_called_once()
    
    def test_get_citation_success(self):
        """Test successful citation retrieval."""
        mock_conn = Mock()
        mock_cursor = Mock()
        citation_id = uuid.uuid4()
        
        self.mock_db.get_connection.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.fetchone.return_value = self.sample_citation
        
        result = self.crud.get_citation(citation_id)
        
        assert result == self.sample_citation
        mock_cursor.execute.assert_called_once_with(
            "SELECT * FROM citations WHERE citation_id = %s", 
            (citation_id,)
        )
    
    def test_search_citations_with_filters(self):
        """Test citation search with filters."""
        mock_conn = Mock()
        mock_cursor = Mock()
        
        self.mock_db.get_connection.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.fetchall.return_value = [self.sample_citation]
        
        result = self.crud.search_citations(
            province="guangdong",
            doc_class="market_rules",
            limit=10
        )
        
        assert len(result) == 1
        assert result[0] == self.sample_citation
        mock_cursor.execute.assert_called_once()


class TestSourceCRUD:
    """Test source CRUD operations."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_db = Mock()
        self.crud = SourceCRUD(self.mock_db)
        self.sample_source = {
            "domain": "gzpec.cn",
            "province": "guangdong",
            "label": "广东电力交易中心",
            "cadence": "R/2025-01-01T00:00:00Z/P1D",
            "robots": "respect",
            "owner": "CC"
        }
    
    def test_create_source_success(self):
        """Test successful source creation."""
        mock_conn = Mock()
        mock_cursor = Mock()
        
        self.mock_db.get_connection.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        
        result = self.crud.create_source(self.sample_source)
        
        assert result is True
        mock_cursor.execute.assert_called_once()
    
    def test_get_all_sources(self):
        """Test retrieving all sources."""
        mock_conn = Mock()
        mock_cursor = Mock()
        
        self.mock_db.get_connection.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.fetchall.return_value = [self.sample_source]
        
        result = self.crud.get_all_sources()
        
        assert len(result) == 1
        assert result[0] == self.sample_source


class TestPackCRUD:
    """Test pack CRUD operations."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_db = Mock()
        self.crud = PackCRUD(self.mock_db)
        self.sample_pack = {
            "pack_id": str(uuid.uuid4()),
            "province": "guangdong",
            "asset": "generation",
            "doc_class": "market_rules",
            "query_fingerprint": "hash123",
            "citation_ids": [str(uuid.uuid4()), str(uuid.uuid4())]
        }
    
    def test_create_pack_success(self):
        """Test successful pack creation."""
        mock_conn = Mock()
        mock_cursor = Mock()
        
        self.mock_db.get_connection.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.fetchone.return_value = {"pack_id": self.sample_pack["pack_id"]}
        
        result = self.crud.create_pack(self.sample_pack)
        
        assert result == self.sample_pack["pack_id"]
        mock_cursor.execute.assert_called_once()
    
    def test_find_pack_by_fingerprint(self):
        """Test finding pack by query fingerprint."""
        mock_conn = Mock()
        mock_cursor = Mock()
        
        self.mock_db.get_connection.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.fetchone.return_value = self.sample_pack
        
        result = self.crud.find_pack_by_fingerprint("hash123")
        
        assert result == self.sample_pack
        mock_cursor.execute.assert_called_once_with(
            "SELECT * FROM packs WHERE query_fingerprint = %s",
            ("hash123",)
        )


if __name__ == "__main__":
    pytest.main([__file__])