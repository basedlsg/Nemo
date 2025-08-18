"""Database initialization module."""
import asyncio
import logging
import os
from typing import Optional
import asyncpg

logger = logging.getLogger(__name__)

# Database schema SQL
SCHEMA_SQL = """
-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Sources table for regulatory documents
CREATE TABLE IF NOT EXISTS sources (
    id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    url TEXT NOT NULL UNIQUE,
    province VARCHAR(50) NOT NULL,
    doc_class VARCHAR(100) NOT NULL,
    asset_type VARCHAR(50) NOT NULL,
    content TEXT,
    effective_date DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Citations table for document chunks with embeddings
CREATE TABLE IF NOT EXISTS citations (
    id SERIAL PRIMARY KEY,
    source_id INTEGER REFERENCES sources(id) ON DELETE CASCADE,
    citation_id VARCHAR(100) NOT NULL UNIQUE,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    page_number INTEGER,
    chunk_index INTEGER,
    embedding vector(768),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_sources_province ON sources(province);
CREATE INDEX IF NOT EXISTS idx_sources_doc_class ON sources(doc_class);
CREATE INDEX IF NOT EXISTS idx_sources_asset_type ON sources(asset_type);
CREATE INDEX IF NOT EXISTS idx_citations_source_id ON citations(source_id);
CREATE INDEX IF NOT EXISTS idx_citations_citation_id ON citations(citation_id);

-- Create vector similarity search index
CREATE INDEX IF NOT EXISTS idx_citations_embedding ON citations USING ivfflat (embedding vector_cosine_ops);
"""

async def init_database(database_url: str) -> bool:
    """
    Initialize database with required tables and extensions.
    
    Args:
        database_url: PostgreSQL connection string
        
    Returns:
        True if initialization successful, False otherwise
    """
    try:
        logger.info("Initializing database...")
        
        # Connect to database
        conn = await asyncpg.connect(database_url, timeout=30)
        
        try:
            # Execute schema creation
            await conn.execute(SCHEMA_SQL)
            logger.info("Database schema created successfully")
            
            # Check if tables exist and are accessible
            tables_result = await conn.fetch("""
                SELECT table_name FROM information_schema.tables 
                WHERE table_schema = 'public' AND table_name IN ('sources', 'citations')
            """)
            table_names = [row['table_name'] for row in tables_result]
            logger.info(f"Available tables: {table_names}")
            
            if 'sources' in table_names and 'citations' in table_names:
                logger.info("Database initialization completed successfully")
                return True
            else:
                logger.error(f"Missing required tables. Found: {table_names}")
                return False
                
        finally:
            await conn.close()
            
    except Exception as e:
        logger.error(f"Database initialization failed: {type(e).__name__}: {str(e)}")
        return False

async def check_database_health(database_url: str) -> dict:
    """
    Check database health and return status information.
    
    Args:
        database_url: PostgreSQL connection string
        
    Returns:
        Dictionary with health status information
    """
    try:
        conn = await asyncpg.connect(database_url, timeout=10)
        
        try:
            # Test basic connectivity
            test_result = await conn.fetchval("SELECT 1")
            
            # Check tables
            tables = await conn.fetch("""
                SELECT table_name FROM information_schema.tables 
                WHERE table_schema = 'public'
            """)
            table_names = [row['table_name'] for row in tables]
            
            # Check record counts
            sources_count = 0
            citations_count = 0
            
            if 'sources' in table_names:
                sources_count = await conn.fetchval("SELECT COUNT(*) FROM sources")
            if 'citations' in table_names:
                citations_count = await conn.fetchval("SELECT COUNT(*) FROM citations")
            
            return {
                "status": "healthy",
                "test_query": test_result,
                "tables": table_names,
                "sources_count": sources_count,
                "citations_count": citations_count
            }
            
        finally:
            await conn.close()
            
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": f"{type(e).__name__}: {str(e)}"
        }

if __name__ == "__main__":
    # Allow running this module directly for database setup
    import sys
    
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("ERROR: DATABASE_URL environment variable not set")
        sys.exit(1)
    
    async def main():
        success = await init_database(database_url)
        if success:
            print("Database initialization completed successfully")
            health = await check_database_health(database_url)
            print(f"Database health: {health}")
        else:
            print("Database initialization failed")
            sys.exit(1)
    
    asyncio.run(main())