"""Hybrid search service combining vector similarity and BM25 for Task 11."""

import logging
import time
import os
from typing import List, Dict, Any, Optional
from datetime import datetime

from services.database import pool
from services.embeddings.vertex_client import VertexAIEmbeddingClient
from services.normalize.sectioner import rank_sections, score_text  # PR3: Section-level re-ranking

logger = logging.getLogger(__name__)


class HybridSearchService:
    """
    Hybrid search service that combines vector similarity and BM25 scoring.
    
    Implements: score = α * vector_cosine + (1-α) * BM25 (α default 0.6)
    Target: p95 < 600ms retriever performance
    """
    
    def __init__(self, alpha: float = 0.6):
        """
        Initialize hybrid search service.
        
        Args:
            alpha: Weight for vector similarity (0.6 = 60% vector, 40% BM25)
        """
        self.alpha = alpha
        self.embedding_client = VertexAIEmbeddingClient()
        dsn = os.getenv("DATABASE_URL") or os.getenv("ALLOYDB_DSN")
        logging.info("Retriever DB DSN: %s", "SET" if dsn else "MISSING")
        self.pool = pool
    
    async def search(
        self,
        question: str,
        province: str,
        doc_class: str,
        asset: Optional[str] = None,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Perform hybrid search over citations.
        
        Args:
            question: User question to search for
            province: Province filter (guangdong, shandong, inner_mongolia)
            doc_class: Document class filter (market_rules, grid_connection, dispatch_ops)
            asset: Optional asset filter (wind, solar, bess, coal_flex)
            limit: Maximum results to return
            
        Returns:
            List of search results with citation_id, passage, score, metadata
        """
        start_time = time.time()
        
        try:
            # Generate embedding for the question
            question_embedding = await self.embedding_client.embed_text(question)
            
            # Perform hybrid search query
            results = await self._hybrid_search_query(
                question_embedding, question, province, doc_class, asset, limit
            )
            
            # PR3: Add section-level re-ranking for better passage extraction
            section_ranked_results = await self._section_level_rerank(results, question, limit)

            # Add passage slicing and metadata
            enriched_results = await self._enrich_search_results(section_ranked_results)

            processing_time_ms = int((time.time() - start_time) * 1000)

            logger.info(f"Hybrid search completed: {len(enriched_results)} results in {processing_time_ms}ms")

            return enriched_results
            
        except Exception as e:
            logger.error(f"Hybrid search failed: {e}")
            return []

    async def _section_level_rerank(
        self,
        results: List[Dict[str, Any]],
        question: str,
        limit: int
    ) -> List[Dict[str, Any]]:
        """
        PR3: Perform section-level re-ranking on search results.

        This improves passage extraction by finding the most relevant sections
        within each document rather than using document-level relevance.
        """
        try:
            reranked_results = []

            for result in results:
                doc_text = result.get("content", "")
                if not doc_text:
                    # Keep original result if no content
                    reranked_results.append(result)
                    continue

                # Split document into sections and rank them
                top_sections = rank_sections(question, doc_text, top_k=3)

                if top_sections:
                    # Use the best section as the passage
                    best_section = top_sections[0]

                    # Update the result with section-specific information
                    section_result = result.copy()
                    section_result["content"] = best_section["text"]
                    section_result["section_id"] = best_section["section_id"]
                    section_result["section_heading"] = best_section["heading"]
                    section_result["section_score"] = score_text(question, best_section["text"])

                    # Boost score for documents with highly relevant sections
                    original_score = result.get("score", 0)
                    section_boost = best_section["section_score"] * 0.1  # Small boost
                    section_result["score"] = original_score + section_boost

                    reranked_results.append(section_result)
                else:
                    # No sections found, keep original
                    reranked_results.append(result)

            # Re-sort by the updated scores
            reranked_results.sort(key=lambda x: x.get("score", 0), reverse=True)

            # Return top results
            return reranked_results[:limit]

        except Exception as e:
            logger.warning(f"Section-level reranking failed: {e}")
            # Fall back to original results
            return results

    async def _hybrid_search_query(
        self,
        question_embedding: List[float],
        question_text: str,
        province: str,
        doc_class: str,
        asset: Optional[str],
        limit: int
    ) -> List[Dict[str, Any]]:
        """Execute the hybrid search SQL query."""
        
        # Convert embedding to pgvector format
        embedding_str = f"[{','.join(map(str, question_embedding))}]"
        
        # Build the hybrid search query based on the provided SQL sketch
        query = """
        WITH q AS (
            SELECT $1::vector AS qv
        ),
        vec AS (
            SELECT citation_id, province, doc_class, asset, title, url, 
                   effective_date, checksum, content,
                   (1 - (citations.embedding <=> (SELECT qv FROM q))) AS vscore
            FROM citations
            WHERE province = $2 AND doc_class = $3
            ORDER BY citations.embedding <=> (SELECT qv FROM q)
            LIMIT 200
        ),
        txt AS (
            SELECT citation_id,
                   ts_rank_cd(to_tsvector('simple', content), plainto_tsquery('simple', $4)) AS tscore
            FROM citations
            WHERE province = $2 AND doc_class = $3
        )
        SELECT v.citation_id, v.province, v.doc_class, v.asset, v.title, v.url, 
               v.effective_date, v.checksum, v.content,
               v.vscore, COALESCE(t.tscore, 0) AS tscore,
               ($5 * v.vscore + $6 * COALESCE(t.tscore, 0)) AS score
        FROM vec v
        LEFT JOIN txt t USING (citation_id)
        ORDER BY score DESC
        LIMIT $7
        """
        
        params = [
            embedding_str,      # $1: question embedding
            province,           # $2: province filter
            doc_class,          # $3: doc_class filter
            question_text,      # $4: question text for BM25
            self.alpha,         # $5: vector weight (α)
            1 - self.alpha,     # $6: BM25 weight (1-α)
            limit               # $7: result limit
        ]
        
        with self.pool.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                results = cur.fetchall()
                
                return [dict(row) for row in results]
    
    async def _enrich_search_results(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Enrich search results with passage slicing and metadata."""
        enriched_results = []
        
        for result in results:
            try:
                # Extract relevant passage (simplified - could be improved with better chunking)
                content = result.get("content", "")
                passage = self._extract_relevant_passage(content, max_length=500)
                
                enriched_result = {
                    "citation_id": result["citation_id"],
                    "passage": passage,
                    "score": float(result["score"]),
                    "vector_score": float(result["vscore"]),
                    "bm25_score": float(result["tscore"]),
                    "metadata": {
                        "title": result["title"],
                        "url": result["url"],
                        "effective_date": result["effective_date"].isoformat() if result["effective_date"] else None,
                        "checksum": result["checksum"],
                        "province": result["province"],
                        "doc_class": result["doc_class"],
                        "asset": result["asset"]
                    }
                }
                
                enriched_results.append(enriched_result)
                
            except Exception as e:
                logger.error(f"Failed to enrich result for citation {result.get('citation_id')}: {e}")
        
        return enriched_results
    
    def _extract_relevant_passage(self, content: str, max_length: int = 500) -> str:
        """
        Extract relevant passage from content.
        
        This is a simplified implementation. In production, you'd want:
        - Better sentence boundary detection
        - Keyword highlighting
        - Chunk boundary awareness
        """
        if not content:
            return ""
        
        # Simple approach: take first max_length characters with sentence boundary
        if len(content) <= max_length:
            return content
        
        # Find last sentence boundary within max_length
        truncated = content[:max_length]
        last_period = truncated.rfind('。')  # Chinese period
        last_exclamation = truncated.rfind('！')
        last_question = truncated.rfind('？')
        
        # Find the latest sentence boundary
        boundaries = [pos for pos in [last_period, last_exclamation, last_question] if pos > 0]
        
        if boundaries:
            end_pos = max(boundaries) + 1
            return content[:end_pos]
        else:
            # No sentence boundary found, just truncate
            return truncated + "..."
    
    async def health_check(self) -> Dict[str, Any]:
        """Check retriever service health."""
        try:
            start_time = time.time()
            
            # Test database connectivity
            with self.pool.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT COUNT(*) FROM citations")
                    citation_count = cur.fetchone()[0]
            
            # Test embedding service
            embedding_health = await self.embedding_client.health_check()
            
            latency_ms = int((time.time() - start_time) * 1000)
            
            return {
                "status": "healthy",
                "latency_ms": latency_ms,
                "citation_count": citation_count,
                "embedding_service": embedding_health,
                "alpha": self.alpha,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    async def get_search_stats(self) -> Dict[str, Any]:
        """Get search statistics by province and doc_class."""
        try:
            query = """
            SELECT province, doc_class, COUNT(*) as citation_count,
                   MIN(effective_date) as earliest_date,
                   MAX(effective_date) as latest_date
            FROM citations
            WHERE embedding IS NOT NULL
            GROUP BY province, doc_class
            ORDER BY province, doc_class
            """
            
            with self.pool.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query)
                    results = cur.fetchall()
                    
                    stats = {
                        "total_citations": 0,
                        "by_province": {},
                        "by_doc_class": {},
                        "coverage": []
                    }
                    
                    for row in results:
                        province = row["province"]
                        doc_class = row["doc_class"]
                        count = row["citation_count"]
                        
                        stats["total_citations"] += count
                        
                        if province not in stats["by_province"]:
                            stats["by_province"][province] = 0
                        stats["by_province"][province] += count
                        
                        if doc_class not in stats["by_doc_class"]:
                            stats["by_doc_class"][doc_class] = 0
                        stats["by_doc_class"][doc_class] += count
                        
                        stats["coverage"].append({
                            "province": province,
                            "doc_class": doc_class,
                            "citation_count": count,
                            "earliest_date": row["earliest_date"].isoformat() if row["earliest_date"] else None,
                            "latest_date": row["latest_date"].isoformat() if row["latest_date"] else None
                        })
                    
                    return stats
            
        except Exception as e:
            logger.error(f"Failed to get search stats: {e}")
            return {"error": str(e)}


class RetrieverClient:
    """Client interface for the retriever service."""
    
    def __init__(self, alpha: float = 0.6):
        """Initialize retriever client."""
        self.search_service = HybridSearchService(alpha)
    
    async def search(
        self,
        province: str,
        doc_class: str,
        question: str,
        asset: Optional[str] = None,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Search for relevant citations.
        
        Args:
            province: Province to search in
            doc_class: Document class to search
            question: User question
            asset: Optional asset filter
            limit: Maximum results
            
        Returns:
            List of search results with citation_id, passage, score
        """
        return await self.search_service.search(
            question=question,
            province=province,
            doc_class=doc_class,
            asset=asset,
            limit=limit
        )
    
    async def health_check(self) -> Dict[str, Any]:
        """Check retriever health."""
        return await self.search_service.health_check()
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get retriever statistics."""
        return await self.search_service.get_search_stats()


# Global retriever client instance
_retriever_client: Optional[RetrieverClient] = None


def get_retriever_client() -> RetrieverClient:
    """Get global retriever client instance."""
    global _retriever_client
    if _retriever_client is None:
        _retriever_client = RetrieverClient()
    return _retriever_client


if __name__ == "__main__":
    # Quick test of retriever service
    import asyncio
    import json
    
    async def test_retriever():
        print("=== Hybrid Retriever Test ===")
        
        client = RetrieverClient()
        
        try:
            # Test health check
            print("\n--- Health Check ---")
            health = await client.health_check()
            print(f"Status: {health['status']}")
            if health['status'] == 'healthy':
                print(f"Citation count: {health['citation_count']}")
                print(f"Latency: {health['latency_ms']}ms")
            
            # Test search
            print("\n--- Search Test ---")
            results = await client.search(
                province="guangdong",
                doc_class="grid_connection",
                question="光伏并网需要什么资料？",
                limit=5
            )
            
            print(f"Found {len(results)} results:")
            for i, result in enumerate(results[:3], 1):
                print(f"\n{i}. Score: {result['score']:.3f}")
                print(f"   Title: {result['metadata']['title']}")
                print(f"   Passage: {result['passage'][:100]}...")
                print(f"   Vector: {result['vector_score']:.3f}, BM25: {result['bm25_score']:.3f}")
            
            # Test stats
            print("\n--- Statistics ---")
            stats = await client.get_stats()
            print(f"Total citations: {stats.get('total_citations', 0)}")
            print("By province:", stats.get('by_province', {}))
            
        except Exception as e:
            print(f"Test failed: {e}")
    
    asyncio.run(test_retriever())
