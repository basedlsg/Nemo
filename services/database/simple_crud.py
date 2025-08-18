"""Simple CRUD operations using connection pool."""

import logging
from typing import Dict, Any, List, Optional
from uuid import UUID

from .pool import get_connection, upsert_citation_rows, get_citations_by_province, search_similar_citations

logger = logging.getLogger(__name__)


class SimpleCitationCRUD:
    """Simple CRUD operations for citations."""
    
    def upsert_citation(self, citation_data: Dict[str, Any]) -> bool:
        """Insert or update a citation."""
        try:
            # Convert single citation to list format
            rows = [citation_data]
            count = upsert_citation_rows(rows)
            return count > 0
        except Exception as e:
            logger.error(f"Failed to upsert citation: {e}")
            return False
    
    def get_citations_by_province(self, province: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get citations by province."""
        try:
            return get_citations_by_province(province, limit)
        except Exception as e:
            logger.error(f"Failed to get citations by province: {e}")
            return []
    
    def search_similar(
        self, 
        embedding: List[float], 
        province: Optional[str] = None,
        limit: int = 10,
        threshold: float = 0.7
    ) -> List[Dict[str, Any]]:
        """Search for similar citations."""
        try:
            return search_similar_citations(embedding, province, limit, threshold)
        except Exception as e:
            logger.error(f"Failed to search similar citations: {e}")
            return []
    
    def get_citation_by_id(self, citation_id: UUID) -> Optional[Dict[str, Any]]:
        """Get citation by ID."""
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT citation_id, province, doc_class, asset, title, url,
                               effective_date, checksum, content
                        FROM citations 
                        WHERE citation_id = %s
                    """, (citation_id,))
                    
                    row = cur.fetchone()
                    return dict(row) if row else None
                    
        except Exception as e:
            logger.error(f"Failed to get citation by ID: {e}")
            return None
    
    def health_check(self) -> bool:
        """Check if CRUD operations are working."""
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT COUNT(*) FROM citations LIMIT 1")
                    cur.fetchone()
                    return True
        except Exception as e:
            logger.error(f"CRUD health check failed: {e}")
            return False


class SimpleSourceCRUD:
    """Simple CRUD operations for sources."""
    
    def upsert_source(self, source_data: Dict[str, Any]) -> bool:
        """Insert or update a source."""
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO sources (
                            domain, province, label, cadence, robots, owner
                        ) VALUES (
                            %(domain)s, %(province)s, %(label)s, %(cadence)s, %(robots)s, %(owner)s
                        )
                        ON CONFLICT (domain) DO UPDATE SET
                            province = EXCLUDED.province,
                            label = EXCLUDED.label,
                            cadence = EXCLUDED.cadence,
                            robots = EXCLUDED.robots,
                            owner = EXCLUDED.owner
                    """, source_data)
                    
                    logger.info(f"Upserted source {source_data['domain']}")
                    return True
                    
        except Exception as e:
            logger.error(f"Failed to upsert source: {e}")
            return False
    
    def get_sources_by_province(self, province: str) -> List[Dict[str, Any]]:
        """Get sources by province."""
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT domain, province, label, cadence, robots, last_crawled_at, owner
                        FROM sources 
                        WHERE province = %s
                        ORDER BY domain
                    """, (province,))
                    
                    return cur.fetchall()
                    
        except Exception as e:
            logger.error(f"Failed to get sources by province: {e}")
            return []
    
    def get_all_sources(self) -> List[Dict[str, Any]]:
        """Get all sources."""
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT domain, province, label, cadence, robots, last_crawled_at, owner
                        FROM sources 
                        ORDER BY province, domain
                    """)
                    
                    return cur.fetchall()
                    
        except Exception as e:
            logger.error(f"Failed to get all sources: {e}")
            return []
    
    def update_crawl_time(self, domain: str) -> bool:
        """Update last crawled time for a source."""
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE sources 
                        SET last_crawled_at = NOW() 
                        WHERE domain = %s
                    """, (domain,))
                    
                    return cur.rowcount > 0
                    
        except Exception as e:
            logger.error(f"Failed to update crawl time: {e}")
            return False


class SimplePackCRUD:
    """Simple CRUD operations for packs."""
    
    def create_pack(self, pack_data: Dict[str, Any]) -> bool:
        """Create a new pack."""
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO packs (
                            pack_id, province, asset, doc_class, query_fingerprint, citation_ids
                        ) VALUES (
                            %(pack_id)s, %(province)s, %(asset)s, %(doc_class)s, 
                            %(query_fingerprint)s, %(citation_ids)s
                        )
                    """, pack_data)
                    
                    logger.info(f"Created pack {pack_data['pack_id']}")
                    return True
                    
        except Exception as e:
            logger.error(f"Failed to create pack: {e}")
            return False
    
    def get_pack_by_fingerprint(self, fingerprint: str) -> Optional[Dict[str, Any]]:
        """Get pack by query fingerprint."""
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT pack_id, created_at, province, asset, doc_class, 
                               query_fingerprint, citation_ids
                        FROM packs 
                        WHERE query_fingerprint = %s
                        ORDER BY created_at DESC
                        LIMIT 1
                    """, (fingerprint,))
                    
                    row = cur.fetchone()
                    return dict(row) if row else None
                    
        except Exception as e:
            logger.error(f"Failed to get pack by fingerprint: {e}")
            return None