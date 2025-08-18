"""Unit tests for database connection and CRUD operations."""

import pytest
import asyncio
from datetime import datetime, date, timedelta
from uuid import uuid4
from unittest.mock import AsyncMock, patch, MagicMock

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from services.database.connection import DatabaseManager, DatabaseSettings
from services.database.models import Citation, Pack, Source, CitationCreate, SourceCreate
from services.database.crud import CitationCRUD, PackCRUD, SourceCRUD


class TestDatabaseManager:
    """Test database manager functionality."""
    
    @pytest.fixture
    def db_settings(self):
        """Test database settings."""
        return DatabaseSettings(
            database_url="postgresql+asyncpg://test:test@localhost:5432/test_db",
            database_pool_size=5,
            database_echo=False
        )
    
    @pytest.fixture
    def db_manager(self, db_settings):
        """Test database manager instance."""
        return DatabaseManager(db_settings)
    
    @pytest.mark.asyncio
    async def test_database_manager_initialization(self, db_manager):
        """Test database manager initialization."""
        with patch('services.database.connection.create_async_engine') as mock_engine:
            mock_engine.return_value = AsyncMock()
            
            await db_manager.initialize()
            
            assert db_manager._initialized is True
            assert db_manager.engine is not None
            assert db_manager.session_factory is not None
            mock_engine.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_health_check_success(self, db_manager):
        """Test successful health check."""
        mock_engine = AsyncMock()
        mock_conn = AsyncMock()
        mock_engine.begin.return_value.__aenter__.return_value = mock_conn
        
        db_manager.engine = mock_engine
        db_manager._initialized = True
        
        result = await db_manager.health_check()
        
        assert result is True
        mock_conn.execute.assert_called_once_with("SELECT 1")
    
    @pytest.mark.asyncio
    async def test_health_check_failure(self, db_manager):
        """Test health check failure."""
        mock_engine = AsyncMock()
        mock_engine.begin.side_effect = Exception("Connection failed")
        
        db_manager.engine = mock_engine
        db_manager._initialized = True
        
        result = await db_manager.health_check()
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_get_session_context_manager(self, db_manager):
        """Test session context manager."""
        mock_session = AsyncMock()
        mock_session_factory = AsyncMock()
        mock_session_factory.return_value.__aenter__.return_value = mock_session
        
        db_manager.session_factory = mock_session_factory
        db_manager._initialized = True
        
        async with db_manager.get_session() as session:
            assert session == mock_session
        
        mock_session.close.assert_called_once()


class TestCitationCRUD:
    """Test citation CRUD operations."""
    
    @pytest.fixture
    def mock_session(self):
        """Mock database session."""
        return AsyncMock(spec=AsyncSession)
    
    @pytest.fixture
    def sample_citation_data(self):
        """Sample citation data for testing."""
        return CitationCreate(
            province="guangdong",
            doc_class="grid_connection",
            asset="solar",
            title="广东省分布式光伏并网管理办法",
            url="https://gzpec.cn/rules/solar-grid-connection",
            effective_date=date(2025, 3, 1),
            checksum="a" * 64,  # SHA256 length
            content="根据国家能源局相关规定，分布式光伏发电项目并网应满足以下条件...",
            embedding=[0.1] * 1536
        )
    
    @pytest.mark.asyncio
    async def test_create_citation(self, mock_session, sample_citation_data):
        """Test creating a new citation."""
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()
        
        result = await CitationCRUD.create(mock_session, sample_citation_data)
        
        assert isinstance(result, Citation)
        assert result.province == "guangdong"
        assert result.doc_class == "grid_connection"
        assert result.title == "广东省分布式光伏并网管理办法"
        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()
        mock_session.refresh.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_citation_by_id(self, mock_session):
        """Test getting citation by ID."""
        citation_id = uuid4()
        mock_citation = Citation(
            citation_id=citation_id,
            province="guangdong",
            doc_class="grid_connection",
            title="Test Citation",
            url="https://example.com",
            effective_date=date.today(),
            checksum="test_checksum",
            content="Test content"
        )
        
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = mock_citation
        mock_session.execute.return_value = mock_result
        
        result = await CitationCRUD.get_by_id(mock_session, citation_id)
        
        assert result == mock_citation
        mock_session.execute.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_citation_by_checksum(self, mock_session):
        """Test getting citation by checksum to avoid duplicates."""
        checksum = "test_checksum_123"
        mock_citation = Citation(
            citation_id=uuid4(),
            province="guangdong",
            doc_class="grid_connection",
            title="Test Citation",
            url="https://example.com",
            effective_date=date.today(),
            checksum=checksum,
            content="Test content"
        )
        
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = mock_citation
        mock_session.execute.return_value = mock_result
        
        result = await CitationCRUD.get_by_checksum(mock_session, checksum)
        
        assert result == mock_citation
        mock_session.execute.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_active_citations_by_province_and_class(self, mock_session):
        """Test getting active citations by province and document class."""
        mock_citations = [
            Citation(
                citation_id=uuid4(),
                province="guangdong",
                doc_class="grid_connection",
                title=f"Citation {i}",
                url=f"https://example.com/{i}",
                effective_date=date.today(),
                checksum=f"checksum_{i}",
                content=f"Content {i}"
            ) for i in range(3)
        ]
        
        mock_result = AsyncMock()
        mock_result.scalars.return_value.all.return_value = mock_citations
        mock_session.execute.return_value = mock_result
        
        result = await CitationCRUD.get_active_by_province_and_class(
            mock_session, "guangdong", "grid_connection"
        )
        
        assert len(result) == 3
        assert all(isinstance(citation, Citation) for citation in result)
        mock_session.execute.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_mark_superseded(self, mock_session):
        """Test marking a citation as superseded."""
        old_id = uuid4()
        new_id = uuid4()
        
        mock_result = AsyncMock()
        mock_result.rowcount = 1
        mock_session.execute.return_value = mock_result
        mock_session.commit = AsyncMock()
        
        result = await CitationCRUD.mark_superseded(mock_session, old_id, new_id)
        
        assert result is True
        mock_session.execute.assert_called_once()
        mock_session.commit.assert_called_once()


class TestPackCRUD:
    """Test pack CRUD operations."""
    
    @pytest.fixture
    def mock_session(self):
        """Mock database session."""
        return AsyncMock(spec=AsyncSession)
    
    @pytest.mark.asyncio
    async def test_create_pack(self, mock_session):
        """Test creating a new pack."""
        citation_ids = [uuid4(), uuid4()]
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()
        
        result = await PackCRUD.create(
            mock_session,
            province="guangdong",
            asset="solar",
            doc_class="grid_connection",
            query_fingerprint="test_fingerprint",
            citation_ids=citation_ids,
            answer_zh="测试答案"
        )
        
        assert isinstance(result, Pack)
        assert result.province == "guangdong"
        assert result.asset == "solar"
        assert result.doc_class == "grid_connection"
        assert result.citation_ids == citation_ids
        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()
        mock_session.refresh.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_pack_by_id(self, mock_session):
        """Test getting pack by ID."""
        pack_id = uuid4()
        mock_pack = Pack(
            pack_id=pack_id,
            province="guangdong",
            doc_class="grid_connection",
            query_fingerprint="test_fingerprint",
            citation_ids=[uuid4()]
        )
        
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = mock_pack
        mock_session.execute.return_value = mock_result
        
        result = await PackCRUD.get_by_id(mock_session, pack_id)
        
        assert result == mock_pack
        mock_session.execute.assert_called_once()


class TestSourceCRUD:
    """Test source CRUD operations."""
    
    @pytest.fixture
    def mock_session(self):
        """Mock database session."""
        return AsyncMock(spec=AsyncSession)
    
    @pytest.fixture
    def sample_source_data(self):
        """Sample source data for testing."""
        return SourceCreate(
            domain="gzpec.cn",
            province="guangdong",
            label="广东电力交易中心",
            cadence="P1D",  # Daily
            robots="allow",
            owner="CC",
            doc_classes=["market_rules", "grid_connection"],
            fetch_method="html",
            enabled=True
        )
    
    @pytest.mark.asyncio
    async def test_create_source(self, mock_session, sample_source_data):
        """Test creating a new source."""
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()
        
        result = await SourceCRUD.create(mock_session, sample_source_data)
        
        assert isinstance(result, Source)
        assert result.domain == "gzpec.cn"
        assert result.province == "guangdong"
        assert result.label == "广东电力交易中心"
        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()
        mock_session.refresh.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_source_by_domain(self, mock_session):
        """Test getting source by domain."""
        domain = "gzpec.cn"
        mock_source = Source(
            domain=domain,
            province="guangdong",
            label="广东电力交易中心",
            enabled=True
        )
        
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = mock_source
        mock_session.execute.return_value = mock_result
        
        result = await SourceCRUD.get_by_domain(mock_session, domain)
        
        assert result == mock_source
        mock_session.execute.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_enabled_sources_by_province(self, mock_session):
        """Test getting enabled sources for a province."""
        mock_sources = [
            Source(
                domain=f"source{i}.gov.cn",
                province="guangdong",
                enabled=True
            ) for i in range(2)
        ]
        
        mock_result = AsyncMock()
        mock_result.scalars.return_value.all.return_value = mock_sources
        mock_session.execute.return_value = mock_result
        
        result = await SourceCRUD.get_enabled_by_province(mock_session, "guangdong")
        
        assert len(result) == 2
        assert all(source.enabled for source in result)
        mock_session.execute.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_update_crawl_time(self, mock_session):
        """Test updating last crawled time."""
        domain = "gzpec.cn"
        
        mock_result = AsyncMock()
        mock_result.rowcount = 1
        mock_session.execute.return_value = mock_result
        mock_session.commit = AsyncMock()
        
        result = await SourceCRUD.update_crawl_time(mock_session, domain)
        
        assert result is True
        mock_session.execute.assert_called_once()
        mock_session.commit.assert_called_once()


class TestVectorOperations:
    """Test vector similarity operations."""
    
    @pytest.mark.asyncio
    async def test_vector_similarity_search(self):
        """Test vector similarity search functionality."""
        from services.database.connection import vector_similarity_search
        
        mock_session = AsyncMock()
        query_embedding = [0.1] * 1536
        
        mock_results = [
            {
                "citation_id": uuid4(),
                "title": "Test Citation 1",
                "url": "https://example.com/1",
                "effective_date": date.today(),
                "checksum": "checksum1",
                "content": "Test content 1",
                "similarity": 0.85
            },
            {
                "citation_id": uuid4(),
                "title": "Test Citation 2", 
                "url": "https://example.com/2",
                "effective_date": date.today(),
                "checksum": "checksum2",
                "content": "Test content 2",
                "similarity": 0.78
            }
        ]
        
        mock_result = AsyncMock()
        mock_result.fetchall.return_value = [
            MagicMock(**result) for result in mock_results
        ]
        mock_session.execute.return_value = mock_result
        
        results = await vector_similarity_search(
            mock_session,
            query_embedding,
            "guangdong",
            "grid_connection",
            limit=10,
            similarity_threshold=0.7
        )
        
        assert len(results) == 2
        assert results[0]["similarity"] == 0.85
        assert results[1]["similarity"] == 0.78
        mock_session.execute.assert_called_once()


@pytest.mark.asyncio
async def test_database_connection_pooling():
    """Test database connection pooling functionality."""
    from services.database.connection import ConnectionPool
    
    pool = ConnectionPool(
        "postgresql://test:test@localhost:5432/test_db",
        min_size=2,
        max_size=5
    )
    
    with patch('asyncpg.create_pool') as mock_create_pool:
        mock_pool = AsyncMock()
        mock_create_pool.return_value = mock_pool
        
        await pool.initialize()
        
        assert pool.pool == mock_pool
        mock_create_pool.assert_called_once_with(
            "postgresql://test:test@localhost:5432/test_db",
            min_size=2,
            max_size=5,
            command_timeout=60,
            server_settings={
                "application_name": "geo-energy-assistant-pool",
                "jit": "off",
            }
        )


if __name__ == "__main__":
    pytest.main([__file__])