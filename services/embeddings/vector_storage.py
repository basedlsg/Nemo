"""Vector storage service for AlloyDB pgvector integration."""

import asyncio
import logging
import time
from typing import List, Dict, Any, Optional
from uuid import UUID

import asyncpg
from asyncpg import Connection, Pool

from .schemas import (
    EmbeddingVector, VectorStorageRequest, VectorStorageResult, 
    EmbeddingStatus, EmbeddingConfig
)

logger = logging.getLogger(__name__)


class VectorStorageService:
    """Service for storing embeddings in AlloyDB with pgvector."""
    
    def __init__(self, config: Optional[EmbeddingConfig] = None):
        """Initialize vector storage service."""
        self.config = config or EmbeddingConfig()
        self.pool: Optional[Pool] = None
        
        logger.info("Initialized vector storage service")
    
    async def initialize(self) -> None:
        """Initialize database connection pool."""
        try:
            logger.info("Initializing AlloyDB connection pool")
            
            self.pool = await asyncpg.create_pool(
                self.config.alloydb_connection_string,
                min_size=2,
                max_size=10,
                command_timeout=60
            )
            
            # Ensure pgvector extension is enabled
            await self._ensure_pgvector_extension()
            
            # Create tables if they don't exist
            await self._create_tables()
            
            logger.info("Vector storage service initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize vector storage: {e}")
            raise
    
    async def store_embeddings(self, request: VectorStorageRequest) -> VectorStorageResult:
        """Store embeddings in AlloyDB."""
        start_time = time.time()
        
        try:
            logger.info(f"Storing {len(request.embeddings)} embeddings in table {request.table_name}")
            
            if not self.pool:
                raise Exception("Vector storage not initialized")
            
            stored_count = 0
            updated_count = 0
            failed_count = 0
            failed_embeddings = []
            
            async with self.pool.acquire() as conn:
                # Process embeddings in batches
                batch_size = 100
                
                for i in range(0, len(request.embeddings), batch_size):
                    batch = request.embeddings[i:i + batch_size]
                    
                    try:
                        batch_stored, batch_updated = await self._store_batch(
                            conn, batch, request.table_name, request.upsert_mode
                        )
                        stored_count += batch_stored
                        updated_count += batch_updated
                        
                    except Exception as e:
                        logger.error(f"Batch storage failed: {e}")
                        failed_count += len(batch)
                        failed_embeddings.extend([emb.text[:50] + "..." for emb in batch])
                
                # Create vector index if requested
                index_created = False
                if request.create_index and stored_count > 0:
                    index_created = await self._create_vector_index(conn, request.table_name)
            
            # Create result
            storage_time = int((time.time() - start_time) * 1000)
            
            result = VectorStorageResult(
                storage_id=request.storage_id,
                status=EmbeddingStatus.SUCCESS if stored_count > 0 else EmbeddingStatus.FAILED,
                stored_count=stored_count,
                updated_count=updated_count,
                failed_count=failed_count,
                storage_time_ms=storage_time,
                table_name=request.table_name,
                index_created=index_created,
                failed_embeddings=failed_embeddings
            )
            
            logger.info(f"Stored {stored_count} embeddings, updated {updated_count} in {storage_time}ms")
            return result
            
        except Exception as e:
            storage_time = int((time.time() - start_time) * 1000)
            logger.error(f"Vector storage failed: {e}")
            
            return VectorStorageResult(
                storage_id=request.storage_id,
                status=EmbeddingStatus.FAILED,
                storage_time_ms=storage_time,
                table_name=request.table_name,
                error_message=str(e)
            )
    
    async def search_similar_vectors(
        self,
        query_embedding: List[float],
        table_name: str = "citation_embeddings",
        limit: int = 10,
        similarity_threshold: float = 0.7,
        province_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Search for similar vectors using cosine similarity."""
        try:
            if not self.pool:
                raise Exception("Vector storage not initialized")
            
            async with self.pool.acquire() as conn:
                # Build query with optional province filter
                where_clause = ""
                params = [query_embedding, similarity_threshold, limit]
                
                if province_filter:
                    where_clause = "AND province = $4"
                    params.append(province_filter)
                
                query = f"""
                    SELECT 
                        citation_id,
                        chunk_id,
                        text,
                        province,
                        doc_class,
                        1 - (embedding <=> $1::vector) as similarity,
                        created_at
                    FROM {table_name}
                    WHERE 1 - (embedding <=> $1::vector) >= $2
                    {where_clause}
                    ORDER BY embedding <=> $1::vector
                    LIMIT $3
                """
                
                rows = await conn.fetch(query, *params)
                
                results = []
                for row in rows:
                    results.append({
                        "citation_id": str(row["citation_id"]) if row["citation_id"] else None,
                        "chunk_id": row["chunk_id"],
                        "text": row["text"],
                        "province": row["province"],
                        "doc_class": row["doc_class"],
                        "similarity": float(row["similarity"]),
                        "created_at": row["created_at"].isoformat() if row["created_at"] else None
                    })
                
                logger.info(f"Found {len(results)} similar vectors")
                return results
                
        except Exception as e:
            logger.error(f"Vector search failed: {e}")
            return []
    
    async def get_embedding_by_id(
        self,
        citation_id: Optional[UUID] = None,
        chunk_id: Optional[str] = None,
        table_name: str = "citation_embeddings"
    ) -> Optional[Dict[str, Any]]:
        """Get embedding by citation ID or chunk ID."""
        try:
            if not self.pool:
                raise Exception("Vector storage not initialized")
            
            if not citation_id and not chunk_id:
                raise ValueError("Either citation_id or chunk_id must be provided")
            
            async with self.pool.acquire() as conn:
                if citation_id:
                    query = f"SELECT * FROM {table_name} WHERE citation_id = $1"
                    row = await conn.fetchrow(query, citation_id)
                else:
                    query = f"SELECT * FROM {table_name} WHERE chunk_id = $1"
                    row = await conn.fetchrow(query, chunk_id)
                
                if row:
                    return {
                        "citation_id": str(row["citation_id"]) if row["citation_id"] else None,
                        "chunk_id": row["chunk_id"],
                        "text": row["text"],
                        "embedding": list(row["embedding"]),
                        "dimension": row["dimension"],
                        "province": row["province"],
                        "doc_class": row["doc_class"],
                        "model": row["model"],
                        "created_at": row["created_at"].isoformat() if row["created_at"] else None
                    }
                
                return None
                
        except Exception as e:
            logger.error(f"Failed to get embedding: {e}")
            return None
    
    async def delete_embeddings(
        self,
        citation_ids: Optional[List[UUID]] = None,
        chunk_ids: Optional[List[str]] = None,
        province: Optional[str] = None,
        table_name: str = "citation_embeddings"
    ) -> int:
        """Delete embeddings by various criteria."""
        try:
            if not self.pool:
                raise Exception("Vector storage not initialized")
            
            async with self.pool.acquire() as conn:
                conditions = []
                params = []
                param_count = 0
                
                if citation_ids:
                    param_count += 1
                    conditions.append(f"citation_id = ANY(${param_count})")
                    params.append(citation_ids)
                
                if chunk_ids:
                    param_count += 1
                    conditions.append(f"chunk_id = ANY(${param_count})")
                    params.append(chunk_ids)
                
                if province:
                    param_count += 1
                    conditions.append(f"province = ${param_count}")
                    params.append(province)
                
                if not conditions:
                    raise ValueError("At least one deletion criteria must be provided")
                
                where_clause = " AND ".join(conditions)
                query = f"DELETE FROM {table_name} WHERE {where_clause}"
                
                result = await conn.execute(query, *params)
                deleted_count = int(result.split()[-1])
                
                logger.info(f"Deleted {deleted_count} embeddings")
                return deleted_count
                
        except Exception as e:
            logger.error(f"Failed to delete embeddings: {e}")
            return 0
    
    async def get_storage_stats(self, table_name: str = "citation_embeddings") -> Dict[str, Any]:
        """Get storage statistics."""
        try:
            if not self.pool:
                raise Exception("Vector storage not initialized")
            
            async with self.pool.acquire() as conn:
                # Get basic counts
                count_query = f"SELECT COUNT(*) as total_embeddings FROM {table_name}"
                count_row = await conn.fetchrow(count_query)
                
                # Get province distribution
                province_query = f"""
                    SELECT province, COUNT(*) as count 
                    FROM {table_name} 
                    GROUP BY province 
                    ORDER BY count DESC
                """
                province_rows = await conn.fetch(province_query)
                
                # Get model distribution
                model_query = f"""
                    SELECT model, COUNT(*) as count 
                    FROM {table_name} 
                    GROUP BY model 
                    ORDER BY count DESC
                """
                model_rows = await conn.fetch(model_query)
                
                # Get dimension info
                dim_query = f"SELECT DISTINCT dimension FROM {table_name}"
                dim_rows = await conn.fetch(dim_query)
                
                return {
                    "total_embeddings": count_row["total_embeddings"],
                    "province_distribution": {row["province"]: row["count"] for row in province_rows},
                    "model_distribution": {row["model"]: row["count"] for row in model_rows},
                    "dimensions": [row["dimension"] for row in dim_rows],
                    "table_name": table_name,
                    "timestamp": time.time()
                }
                
        except Exception as e:
            logger.error(f"Failed to get storage stats: {e}")
            return {"error": str(e)}
    
    async def health_check(self) -> Dict[str, Any]:
        """Check vector storage health."""
        try:
            if not self.pool:
                return {
                    "status": "unhealthy",
                    "error": "Connection pool not initialized"
                }
            
            start_time = time.time()
            
            async with self.pool.acquire() as conn:
                # Test basic connectivity
                await conn.fetchval("SELECT 1")
                
                # Test pgvector extension
                pgvector_version = await conn.fetchval(
                    "SELECT extversion FROM pg_extension WHERE extname = 'vector'"
                )
                
                latency_ms = int((time.time() - start_time) * 1000)
                
                return {
                    "status": "healthy",
                    "latency_ms": latency_ms,
                    "pgvector_version": pgvector_version,
                    "pool_size": self.pool.get_size(),
                    "pool_max_size": self.pool.get_max_size(),
                    "timestamp": time.time()
                }
                
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": time.time()
            }
    
    async def close(self) -> None:
        """Close database connection pool."""
        if self.pool:
            await self.pool.close()
            logger.info("Vector storage connection pool closed")
    
    async def _ensure_pgvector_extension(self) -> None:
        """Ensure pgvector extension is enabled."""
        async with self.pool.acquire() as conn:
            await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
            logger.info("Ensured pgvector extension is enabled")
    
    async def _create_tables(self) -> None:
        """Create embedding tables if they don't exist."""
        async with self.pool.acquire() as conn:
            # Create main embeddings table
            create_table_query = f"""
                CREATE TABLE IF NOT EXISTS {self.config.vector_table_name} (
                    id SERIAL PRIMARY KEY,
                    citation_id UUID,
                    chunk_id TEXT,
                    text TEXT NOT NULL,
                    embedding vector(768) NOT NULL,
                    dimension INTEGER NOT NULL DEFAULT 768,
                    province TEXT,
                    doc_class TEXT,
                    model TEXT NOT NULL,
                    norm FLOAT,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                );
            """
            
            await conn.execute(create_table_query)
            
            # Create indexes
            await conn.execute(f"""
                CREATE INDEX IF NOT EXISTS idx_{self.config.vector_table_name}_citation_id 
                ON {self.config.vector_table_name} (citation_id)
            """)
            
            await conn.execute(f"""
                CREATE INDEX IF NOT EXISTS idx_{self.config.vector_table_name}_chunk_id 
                ON {self.config.vector_table_name} (chunk_id)
            """)
            
            await conn.execute(f"""
                CREATE INDEX IF NOT EXISTS idx_{self.config.vector_table_name}_province 
                ON {self.config.vector_table_name} (province)
            """)
            
            logger.info(f"Created table {self.config.vector_table_name} with indexes")
    
    async def _store_batch(
        self,
        conn: Connection,
        embeddings: List[EmbeddingVector],
        table_name: str,
        upsert_mode: bool
    ) -> tuple[int, int]:
        """Store a batch of embeddings."""
        stored_count = 0
        updated_count = 0
        
        for embedding in embeddings:
            try:
                if upsert_mode:
                    # Use upsert (INSERT ... ON CONFLICT)
                    query = f"""
                        INSERT INTO {table_name} 
                        (citation_id, chunk_id, text, embedding, dimension, province, doc_class, model, norm)
                        VALUES ($1, $2, $3, $4::vector, $5, $6, $7, $8, $9)
                        ON CONFLICT (chunk_id) 
                        DO UPDATE SET
                            text = EXCLUDED.text,
                            embedding = EXCLUDED.embedding,
                            dimension = EXCLUDED.dimension,
                            model = EXCLUDED.model,
                            norm = EXCLUDED.norm,
                            updated_at = NOW()
                        RETURNING (xmax = 0) AS inserted
                    """
                    
                    result = await conn.fetchrow(
                        query,
                        embedding.citation_id,
                        embedding.chunk_id,
                        embedding.text,
                        embedding.embedding,
                        embedding.dimension,
                        None,  # province - will be set from citation context
                        None,  # doc_class - will be set from citation context
                        embedding.model.value,
                        embedding.norm
                    )
                    
                    if result["inserted"]:
                        stored_count += 1
                    else:
                        updated_count += 1
                
                else:
                    # Simple insert
                    query = f"""
                        INSERT INTO {table_name} 
                        (citation_id, chunk_id, text, embedding, dimension, province, doc_class, model, norm)
                        VALUES ($1, $2, $3, $4::vector, $5, $6, $7, $8, $9)
                    """
                    
                    await conn.execute(
                        query,
                        embedding.citation_id,
                        embedding.chunk_id,
                        embedding.text,
                        embedding.embedding,
                        embedding.dimension,
                        None,  # province
                        None,  # doc_class
                        embedding.model.value,
                        embedding.norm
                    )
                    
                    stored_count += 1
                    
            except Exception as e:
                logger.error(f"Failed to store embedding {embedding.chunk_id}: {e}")
                raise
        
        return stored_count, updated_count
    
    async def _create_vector_index(self, conn: Connection, table_name: str) -> bool:
        """Create vector similarity index."""
        try:
            index_name = f"idx_{table_name}_embedding_cosine"
            
            # Create HNSW index for cosine similarity
            query = f"""
                CREATE INDEX IF NOT EXISTS {index_name}
                ON {table_name} 
                USING hnsw (embedding vector_cosine_ops)
                WITH (m = 16, ef_construction = 64)
            """
            
            await conn.execute(query)
            logger.info(f"Created vector index {index_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create vector index: {e}")
            return False


class VectorStorageServiceMock:
    """Mock vector storage service for testing."""
    
    def __init__(self, config: Optional[EmbeddingConfig] = None):
        """Initialize mock storage service."""
        self.config = config or EmbeddingConfig()
        self._storage: Dict[str, Dict[str, Any]] = {}
        self.storage_count = 0
    
    async def initialize(self) -> None:
        """Mock initialization."""
        pass
    
    async def store_embeddings(self, request: VectorStorageRequest) -> VectorStorageResult:
        """Mock embedding storage."""
        self.storage_count += len(request.embeddings)
        
        # Simulate storage time
        await asyncio.sleep(0.05)
        
        stored_count = 0
        for embedding in request.embeddings:
            key = embedding.chunk_id or str(embedding.citation_id)
            self._storage[key] = {
                "citation_id": embedding.citation_id,
                "chunk_id": embedding.chunk_id,
                "text": embedding.text,
                "embedding": embedding.embedding,
                "dimension": embedding.dimension,
                "model": embedding.model.value
            }
            stored_count += 1
        
        return VectorStorageResult(
            storage_id=request.storage_id,
            status=EmbeddingStatus.SUCCESS,
            stored_count=stored_count,
            updated_count=0,
            failed_count=0,
            storage_time_ms=50,
            table_name=request.table_name,
            index_created=request.create_index
        )
    
    async def search_similar_vectors(
        self,
        query_embedding: List[float],
        table_name: str = "citation_embeddings",
        limit: int = 10,
        similarity_threshold: float = 0.7,
        province_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Mock vector search."""
        # Return mock results
        results = []
        for i, (key, data) in enumerate(self._storage.items()):
            if i >= limit:
                break
            
            # Mock similarity calculation
            similarity = 0.8 - (i * 0.05)  # Decreasing similarity
            
            if similarity >= similarity_threshold:
                results.append({
                    "citation_id": str(data["citation_id"]) if data["citation_id"] else None,
                    "chunk_id": data["chunk_id"],
                    "text": data["text"],
                    "similarity": similarity,
                    "province": "guangdong",  # Mock province
                    "doc_class": "grid_connection"  # Mock doc class
                })
        
        return results
    
    async def health_check(self) -> Dict[str, Any]:
        """Mock health check."""
        return {
            "status": "healthy",
            "latency_ms": 10,
            "pgvector_version": "0.5.0",
            "storage_count": self.storage_count,
            "timestamp": time.time()
        }
    
    async def close(self) -> None:
        """Mock close."""
        pass