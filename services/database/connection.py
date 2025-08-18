"""Database connection management for AlloyDB with pgvector support."""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

import asyncpg
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool
from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)


class DatabaseSettings(BaseSettings):
    """Database configuration settings."""
    
    database_url: str
    database_pool_size: int = 10
    database_max_overflow: int = 20
    database_pool_timeout: int = 30
    database_pool_recycle: int = 3600
    database_echo: bool = False
    
    class Config:
        env_file = ".env"


class DatabaseManager:
    """Manages database connections and health checks."""
    
    def __init__(self, settings: Optional[DatabaseSettings] = None):
        self.settings = settings or DatabaseSettings()
        self.engine = None
        self.session_factory = None
        self._initialized = False
    
    async def initialize(self) -> None:
        """Initialize database engine and session factory."""
        if self._initialized:
            return
            
        try:
            # Create async engine with connection pooling
            self.engine = create_async_engine(
                self.settings.database_url,
                poolclass=NullPool if "test" in self.settings.database_url else None,
                pool_size=self.settings.database_pool_size,
                max_overflow=self.settings.database_max_overflow,
                pool_timeout=self.settings.database_pool_timeout,
                pool_recycle=self.settings.database_pool_recycle,
                echo=self.settings.database_echo,
                # AlloyDB specific settings
                connect_args={
                    "server_settings": {
                        "application_name": "geo-energy-assistant",
                        "jit": "off",  # Disable JIT for better cold start performance
                    }
                }
            )
            
            # Create session factory
            self.session_factory = async_sessionmaker(
                self.engine,
                class_=AsyncSession,
                expire_on_commit=False
            )
            
            # Test connection and ensure pgvector extension
            await self._ensure_extensions()
            
            self._initialized = True
            logger.info("Database connection initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise
    
    async def _ensure_extensions(self) -> None:
        """Ensure required PostgreSQL extensions are available."""
        try:
            async with self.engine.begin() as conn:
                # Check for pgvector extension
                result = await conn.execute(
                    "SELECT 1 FROM pg_extension WHERE extname = 'vector'"
                )
                if not result.fetchone():
                    logger.warning("pgvector extension not found - vector operations may fail")
                
                # Check for uuid-ossp extension
                result = await conn.execute(
                    "SELECT 1 FROM pg_extension WHERE extname = 'uuid-ossp'"
                )
                if not result.fetchone():
                    logger.warning("uuid-ossp extension not found - UUID generation may fail")
                    
        except Exception as e:
            logger.error(f"Failed to check database extensions: {e}")
            raise
    
    async def health_check(self) -> bool:
        """Perform database health check."""
        if not self._initialized:
            return False
            
        try:
            async with self.engine.begin() as conn:
                await conn.execute("SELECT 1")
            return True
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False
    
    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get database session with automatic cleanup."""
        if not self._initialized:
            await self.initialize()
            
        async with self.session_factory() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()
    
    async def close(self) -> None:
        """Close database connections."""
        if self.engine:
            await self.engine.dispose()
            self._initialized = False
            logger.info("Database connections closed")


# Global database manager instance
_db_manager: Optional[DatabaseManager] = None


async def get_database() -> DatabaseManager:
    """Get or create global database manager instance."""
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager()
        await _db_manager.initialize()
    return _db_manager


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for getting database session in FastAPI."""
    db_manager = await get_database()
    async with db_manager.get_session() as session:
        yield session


class ConnectionPool:
    """Raw asyncpg connection pool for high-performance operations."""
    
    def __init__(self, database_url: str, min_size: int = 5, max_size: int = 20):
        self.database_url = database_url
        self.min_size = min_size
        self.max_size = max_size
        self.pool: Optional[asyncpg.Pool] = None
    
    async def initialize(self) -> None:
        """Initialize connection pool."""
        try:
            self.pool = await asyncpg.create_pool(
                self.database_url,
                min_size=self.min_size,
                max_size=self.max_size,
                command_timeout=60,
                server_settings={
                    "application_name": "geo-energy-assistant-pool",
                    "jit": "off",
                }
            )
            logger.info(f"Connection pool initialized with {self.min_size}-{self.max_size} connections")
        except Exception as e:
            logger.error(f"Failed to initialize connection pool: {e}")
            raise
    
    @asynccontextmanager
    async def acquire(self) -> AsyncGenerator[asyncpg.Connection, None]:
        """Acquire connection from pool."""
        if not self.pool:
            await self.initialize()
            
        async with self.pool.acquire() as connection:
            yield connection
    
    async def close(self) -> None:
        """Close connection pool."""
        if self.pool:
            await self.pool.close()
            logger.info("Connection pool closed")


# Utility functions for vector operations
async def insert_embeddings_batch(
    session: AsyncSession,
    citations_data: list[dict],
    batch_size: int = 100
) -> None:
    """Efficiently insert citations with embeddings in batches."""
    try:
        for i in range(0, len(citations_data), batch_size):
            batch = citations_data[i:i + batch_size]
            
            # Use raw SQL for efficient batch insert with pgvector
            values = []
            params = {}
            
            for j, citation in enumerate(batch):
                param_base = f"p{i}_{j}"
                values.append(f"""(
                    :{param_base}_id, :{param_base}_province, :{param_base}_doc_class,
                    :{param_base}_asset, :{param_base}_title, :{param_base}_url,
                    :{param_base}_effective_date, :{param_base}_checksum, 
                    :{param_base}_content, :{param_base}_embedding::vector
                )""")
                
                params.update({
                    f"{param_base}_id": citation["citation_id"],
                    f"{param_base}_province": citation["province"],
                    f"{param_base}_doc_class": citation["doc_class"],
                    f"{param_base}_asset": citation.get("asset"),
                    f"{param_base}_title": citation["title"],
                    f"{param_base}_url": citation["url"],
                    f"{param_base}_effective_date": citation["effective_date"],
                    f"{param_base}_checksum": citation["checksum"],
                    f"{param_base}_content": citation["content"],
                    f"{param_base}_embedding": str(citation["embedding"]),
                })
            
            query = f"""
                INSERT INTO citations (
                    citation_id, province, doc_class, asset, title, url,
                    effective_date, checksum, content, embedding
                ) VALUES {', '.join(values)}
            """
            
            await session.execute(query, params)
            
        await session.commit()
        logger.info(f"Inserted {len(citations_data)} citations with embeddings")
        
    except Exception as e:
        await session.rollback()
        logger.error(f"Failed to insert embeddings batch: {e}")
        raise


async def vector_similarity_search(
    session: AsyncSession,
    query_embedding: list[float],
    province: str,
    doc_class: str,
    limit: int = 10,
    similarity_threshold: float = 0.7
) -> list[dict]:
    """Perform vector similarity search with filters."""
    try:
        # Convert embedding to pgvector format
        embedding_str = "[" + ",".join(map(str, query_embedding)) + "]"
        
        query = """
            SELECT 
                citation_id,
                title,
                url,
                effective_date,
                checksum,
                content,
                1 - (embedding <=> :embedding::vector) as similarity
            FROM citations 
            WHERE province = :province 
                AND doc_class = :doc_class
                AND superseded_by IS NULL
                AND 1 - (embedding <=> :embedding::vector) > :threshold
            ORDER BY embedding <=> :embedding::vector
            LIMIT :limit
        """
        
        result = await session.execute(query, {
            "embedding": embedding_str,
            "province": province,
            "doc_class": doc_class,
            "threshold": similarity_threshold,
            "limit": limit
        })
        
        return [dict(row) for row in result.fetchall()]
        
    except Exception as e:
        logger.error(f"Vector similarity search failed: {e}")
        raise