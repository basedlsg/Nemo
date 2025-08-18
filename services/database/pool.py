"""Simple database connection pool for AlloyDB with psycopg."""

import logging
import os
from typing import Optional, Dict, Any

import psycopg
from psycopg_pool import ConnectionPool
from psycopg.rows import dict_row

logger = logging.getLogger(__name__)

# Global connection pool
POOL: Optional[ConnectionPool] = None


def initialize_pool(dsn: Optional[str] = None) -> None:
    """Initialize global connection pool."""
    global POOL
    
    if POOL is not None:
        return
    
    connection_string = dsn or os.environ.get("DATABASE_URL") or os.environ.get("ALLOYDB_DSN")
    if not connection_string:
        raise ValueError("DATABASE_URL or ALLOYDB_DSN environment variable is required")
    
    try:
        POOL = ConnectionPool(
            conninfo=connection_string,
            min_size=1,
            max_size=10,
            kwargs={
                "row_factory": dict_row,
                "autocommit": True
            }
        )
        
        # Test connection
        with POOL.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                result = cur.fetchone()
                if result[0] != 1:
                    raise Exception("Database connection test failed")
        
        logger.info("Database connection pool initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize database pool: {e}")
        raise


def get_connection():
    """Get database connection from pool."""
    if POOL is None:
        initialize_pool()
    
    return POOL.connection()


def db_health_ok() -> bool:
    """Simple health check function."""
    try:
        if POOL is None:
            initialize_pool()
        
        with POOL.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                return cur.fetchone()[0] == 1
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return False


def get_health_info() -> Dict[str, Any]:
    """Get detailed health information."""
    try:
        if POOL is None:
            return {
                "status": "unhealthy",
                "error": "Connection pool not initialized"
            }
        
        with POOL.connection() as conn:
            with conn.cursor() as cur:
                # Test basic connectivity
                cur.execute("SELECT 1")
                result = cur.fetchone()
                
                # Check pgvector extension
                cur.execute(
                    "SELECT extversion FROM pg_extension WHERE extname = 'vector'"
                )
                pgvector_row = cur.fetchone()
                pgvector_version = pgvector_row[0] if pgvector_row else None
                
                # Get pool stats
                pool_stats = {
                    "size": POOL.get_stats().pool_size,
                    "max_size": POOL.get_stats().pool_max,
                    "available": POOL.get_stats().pool_available
                }
                
                return {
                    "status": "healthy",
                    "database_test": result[0] == 1,
                    "pgvector_version": pgvector_version,
                    "pool_stats": pool_stats
                }
            
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e)
        }


def close_pool() -> None:
    """Close global connection pool."""
    global POOL
    
    if POOL:
        POOL.close()
        POOL = None
        logger.info("Database connection pool closed")


def upsert_citation_rows(rows: list[dict]) -> int:
    """Upsert citation rows to database."""
    if not rows:
        return 0
    
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                inserted_count = 0
                
                for row in rows:
                    cur.execute("""
                        INSERT INTO citations (
                            citation_id, province, doc_class, asset, title, url, 
                            effective_date, checksum, content, embedding
                        ) VALUES (
                            %(citation_id)s, %(province)s, %(doc_class)s, %(asset)s, 
                            %(title)s, %(url)s, %(effective_date)s, %(checksum)s, 
                            %(content)s, %(embedding)s
                        )
                        ON CONFLICT (citation_id) DO UPDATE SET
                            title = EXCLUDED.title,
                            effective_date = EXCLUDED.effective_date,
                            content = EXCLUDED.content,
                            embedding = EXCLUDED.embedding
                    """, row)
                    
                    inserted_count += 1
                
                logger.info(f"Upserted {inserted_count} citation rows")
                return inserted_count
                
    except Exception as e:
        logger.error(f"Failed to upsert citation rows: {e}")
        raise


def get_citations_by_province(province: str, limit: int = 100) -> list[dict]:
    """Get citations by province."""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT citation_id, province, doc_class, asset, title, url, 
                           effective_date, checksum, content
                    FROM citations 
                    WHERE province = %s 
                    ORDER BY effective_date DESC 
                    LIMIT %s
                """, (province, limit))
                
                return cur.fetchall()
                
    except Exception as e:
        logger.error(f"Failed to get citations by province: {e}")
        return []


def search_similar_citations(
    embedding: list[float], 
    province: Optional[str] = None,
    limit: int = 10,
    threshold: float = 0.7
) -> list[dict]:
    """Search for similar citations using vector similarity."""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                # Build query with optional province filter
                where_clause = ""
                params = [embedding, threshold, limit]
                
                if province:
                    where_clause = "AND province = %s"
                    params.insert(-1, province)  # Insert before limit
                
                query = f"""
                    SELECT 
                        citation_id, province, doc_class, asset, title, url,
                        effective_date, content,
                        1 - (embedding <=> %s::vector) as similarity
                    FROM citations
                    WHERE 1 - (embedding <=> %s::vector) >= %s
                    {where_clause}
                    ORDER BY embedding <=> %s::vector
                    LIMIT %s
                """
                
                # Adjust params for the query structure
                query_params = [embedding, embedding, threshold]
                if province:
                    query_params.append(province)
                query_params.extend([embedding, limit])
                
                cur.execute(query, query_params)
                return cur.fetchall()
                
    except Exception as e:
        logger.error(f"Vector similarity search failed: {e}")
        return []