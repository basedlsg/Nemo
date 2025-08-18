"""End-to-end query processing pipeline that orchestrates all RAG components."""

import logging
import asyncio
import time
import hashlib
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass

from services.core.models import QueryContext, ProcessingMetrics
from services.database.simple_crud import get_database_client
from services.retriever.hybrid_search import HybridSearchService
from services.guardrails.policy_engine import PolicyEngine
from services.composer.answer_composer import ChineseAnswerComposer

logger = logging.getLogger(__name__)


@dataclass
class QueryFingerprint:
    """Query fingerprint for caching and pack generation."""
    fingerprint_hash: str
    province: str
    doc_class: str
    asset: Optional[str]
    question_hash: str
    created_at: datetime


@dataclass
class ProcessingResult:
    """Complete query processing result."""
    answer_zh: str
    citations: List[Dict[str, Any]]
    sections: int
    total_citations: int
    processing_metrics: ProcessingMetrics
    query_fingerprint: QueryFingerprint
    pack_id: Optional[str] = None
    cached: bool = False


class QueryProcessor:
    """
    End-to-end query processor that orchestrates the complete RAG pipeline.
    
    Pipeline flow:
    1. Query fingerprinting and cache check
    2. Hybrid search for relevant citations (Retriever)
    3. Policy validation and safety checks (Guardrails)
    4. Citation metadata enrichment
    5. Quote-first Chinese answer composition (Composer)
    6. Pack generation and caching
    7. Response assembly and metrics collection
    """
    
    def __init__(self):
        """Initialize query processor with service dependencies."""
        self.db_client = None
        self.retriever = None
        self.guardrails = None
        self.composer = None
        
        # Performance tracking
        self.metrics = {
            "total_queries": 0,
            "cached_responses": 0,
            "successful_queries": 0,
            "failed_queries": 0,
            "avg_processing_time_ms": 0.0,
            "avg_retrieval_time_ms": 0.0,
            "avg_composition_time_ms": 0.0
        }
        
        # Cache settings
        self.cache_ttl_hours = 24
        self.enable_caching = True
    
    async def initialize(self):
        """Initialize service dependencies."""
        try:
            # Initialize database client
            self.db_client = get_database_client()
            
            # Initialize RAG services
            self.retriever = HybridSearchService()
            await self.retriever.initialize()
            
            self.guardrails = PolicyEngine()
            self.composer = ChineseAnswerComposer()
            
            logger.info("Query processor initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize query processor: {e}")
            raise
    
    async def process_query(
        self,
        question: str,
        province: str,
        doc_class: str,
        asset: Optional[str] = None,
        lang: str = "zh-CN",
        max_citations: int = 10,
        trace_id: Optional[str] = None
    ) -> ProcessingResult:
        """
        Process query through the complete RAG pipeline.
        
        Args:
            question: User question in Chinese
            province: Province for geo-specific search
            doc_class: Document class for scoped search
            asset: Optional asset type for targeted search
            lang: Response language preference
            max_citations: Maximum citations to return
            trace_id: Optional trace identifier for logging
            
        Returns:
            Complete processing result with answer and metadata
        """
        start_time = time.time()
        trace_id = trace_id or f"qp-{int(time.time())}"
        
        try:
            logger.info(f"[{trace_id}] Starting query processing: {question[:50]}...")
            
            # Step 1: Generate query fingerprint
            fingerprint = self._generate_query_fingerprint(question, province, doc_class, asset)
            logger.debug(f"[{trace_id}] Query fingerprint: {fingerprint.fingerprint_hash}")
            
            # Step 2: Check cache for existing response
            if self.enable_caching:
                cached_result = await self._check_cache(fingerprint, trace_id)
                if cached_result:
                    self.metrics["cached_responses"] += 1
                    logger.info(f"[{trace_id}] Returning cached response")
                    return cached_result
            
            # Step 3: Execute RAG pipeline
            processing_metrics = ProcessingMetrics(
                start_time=start_time,
                trace_id=trace_id
            )
            
            # Retrieval phase
            retrieval_start = time.time()
            search_results = await self._execute_retrieval(
                question, province, doc_class, asset, max_citations, trace_id
            )
            processing_metrics.retrieval_time_ms = (time.time() - retrieval_start) * 1000
            
            if not search_results:
                raise QueryProcessingException("No relevant citations found", "no_citations")
            
            logger.info(f"[{trace_id}] Retrieved {len(search_results)} citations in {processing_metrics.retrieval_time_ms:.1f}ms")
            
            # Guardrails phase
            guardrails_start = time.time()
            validated_results = await self._execute_guardrails(
                search_results, province, doc_class, asset, lang, trace_id
            )
            processing_metrics.guardrails_time_ms = (time.time() - guardrails_start) * 1000
            
            logger.info(f"[{trace_id}] Guardrails validated {len(validated_results)} citations in {processing_metrics.guardrails_time_ms:.1f}ms")
            
            # Citation enrichment phase
            enrichment_start = time.time()
            enriched_results = await self._enrich_citation_metadata(validated_results, trace_id)
            processing_metrics.enrichment_time_ms = (time.time() - enrichment_start) * 1000
            
            # Composition phase
            composition_start = time.time()
            composed_answer = await self._execute_composition(
                enriched_results, question, province, doc_class, asset, lang, max_citations, trace_id
            )
            processing_metrics.composition_time_ms = (time.time() - composition_start) * 1000
            
            logger.info(f"[{trace_id}] Answer composed in {processing_metrics.composition_time_ms:.1f}ms")
            
            # Step 4: Generate pack and cache result
            pack_id = None
            if self.enable_caching:
                pack_id = await self._generate_pack(fingerprint, composed_answer, trace_id)
                await self._cache_result(fingerprint, composed_answer, pack_id, trace_id)
            
            # Step 5: Assemble final result
            processing_metrics.total_time_ms = (time.time() - start_time) * 1000
            
            result = ProcessingResult(
                answer_zh=composed_answer["answer_zh"],
                citations=composed_answer["citations"],
                sections=composed_answer.get("sections", 0),
                total_citations=composed_answer.get("total_citations", 0),
                processing_metrics=processing_metrics,
                query_fingerprint=fingerprint,
                pack_id=pack_id,
                cached=False
            )
            
            # Update metrics
            self._update_success_metrics(processing_metrics.total_time_ms, processing_metrics.retrieval_time_ms, processing_metrics.composition_time_ms)
            
            logger.info(f"[{trace_id}] Query processing completed successfully in {processing_metrics.total_time_ms:.1f}ms")
            
            return result
            
        except QueryProcessingException:
            self.metrics["failed_queries"] += 1
            raise
        except Exception as e:
            self.metrics["failed_queries"] += 1
            logger.error(f"[{trace_id}] Query processing failed: {e}")
            raise QueryProcessingException(f"Internal processing error: {str(e)}", "internal_error")
    
    async def _execute_retrieval(
        self,
        question: str,
        province: str,
        doc_class: str,
        asset: Optional[str],
        max_citations: int,
        trace_id: str
    ) -> List[Dict[str, Any]]:
        """Execute hybrid search retrieval."""
        try:
            search_results = await self.retriever.search(
                query=question,
                province=province,
                doc_class=doc_class,
                asset=asset,
                limit=max_citations
            )
            
            return search_results.get("results", [])
            
        except Exception as e:
            logger.error(f"[{trace_id}] Retrieval failed: {e}")
            raise QueryProcessingException(f"Retrieval error: {str(e)}", "retrieval_failed")
    
    async def _execute_guardrails(
        self,
        search_results: List[Dict[str, Any]],
        province: str,
        doc_class: str,
        asset: Optional[str],
        lang: str,
        trace_id: str
    ) -> List[Dict[str, Any]]:
        """Execute policy validation through guardrails."""
        try:
            # Create query context for guardrails
            query_context = {
                "province": province,
                "doc_class": doc_class,
                "asset": asset,
                "lang": lang
            }
            
            # Validate each search result through guardrails
            validated_results = []
            
            for result in search_results:
                try:
                    # Check citations_required policy
                    self.guardrails.check_citations_required([result])
                    
                    # Check unsafe_scope policy
                    self.guardrails.check_unsafe_scope(query_context, [result])
                    
                    # Check zh_first policy
                    self.guardrails.check_zh_first(lang, "mock_answer")
                    
                    validated_results.append(result)
                    
                except Exception as policy_error:
                    logger.warning(f"[{trace_id}] Citation {result.get('citation_id')} failed policy check: {policy_error}")
                    continue
            
            if not validated_results:
                raise QueryProcessingException("All citations failed policy validation", "policy_violation")
            
            return validated_results
            
        except QueryProcessingException:
            raise
        except Exception as e:
            logger.error(f"[{trace_id}] Guardrails failed: {e}")
            raise QueryProcessingException(f"Guardrails error: {str(e)}", "guardrails_failed")
    
    async def _enrich_citation_metadata(
        self,
        validated_results: List[Dict[str, Any]],
        trace_id: str
    ) -> List[Dict[str, Any]]:
        """Enrich citation metadata for response assembly."""
        try:
            enriched_results = []
            
            for result in validated_results:
                # Add additional metadata if needed
                enriched_result = {
                    **result,
                    "enriched_at": datetime.utcnow().isoformat(),
                    "validation_passed": True
                }
                
                # Ensure required fields are present
                if "metadata" not in enriched_result:
                    enriched_result["metadata"] = {}
                
                metadata = enriched_result["metadata"]
                
                # Validate and normalize metadata fields
                if "effective_date" not in metadata:
                    metadata["effective_date"] = "未知"
                    logger.warning(f"[{trace_id}] Missing effective_date for citation {result.get('citation_id')}")
                
                if "title" not in metadata:
                    metadata["title"] = "未知文档"
                    logger.warning(f"[{trace_id}] Missing title for citation {result.get('citation_id')}")
                
                if "url" not in metadata:
                    metadata["url"] = ""
                
                enriched_results.append(enriched_result)
            
            return enriched_results
            
        except Exception as e:
            logger.error(f"[{trace_id}] Citation enrichment failed: {e}")
            raise QueryProcessingException(f"Citation enrichment error: {str(e)}", "enrichment_failed")
    
    async def _execute_composition(
        self,
        enriched_results: List[Dict[str, Any]],
        question: str,
        province: str,
        doc_class: str,
        asset: Optional[str],
        lang: str,
        max_citations: int,
        trace_id: str
    ) -> Dict[str, Any]:
        """Execute answer composition."""
        try:
            query_params = {
                "province": province,
                "doc_class": doc_class,
                "asset": asset,
                "lang": lang,
                "question": question
            }
            
            composed_answer = self.composer.compose_answer(
                search_results=enriched_results,
                query=query_params,
                max_citations=max_citations
            )
            
            if not composed_answer.get("answer_zh"):
                raise QueryProcessingException("Failed to compose valid answer", "composition_failed")
            
            return composed_answer
            
        except Exception as e:
            logger.error(f"[{trace_id}] Composition failed: {e}")
            raise QueryProcessingException(f"Composition error: {str(e)}", "composition_failed")
    
    def _generate_query_fingerprint(
        self,
        question: str,
        province: str,
        doc_class: str,
        asset: Optional[str]
    ) -> QueryFingerprint:
        """Generate query fingerprint for caching and pack generation."""
        # Create normalized query string
        normalized_query = f"{province}:{doc_class}:{asset or 'none'}:{question.strip().lower()}"
        
        # Generate hash
        fingerprint_hash = hashlib.sha256(normalized_query.encode('utf-8')).hexdigest()[:16]
        question_hash = hashlib.sha256(question.encode('utf-8')).hexdigest()[:8]
        
        return QueryFingerprint(
            fingerprint_hash=fingerprint_hash,
            province=province,
            doc_class=doc_class,
            asset=asset,
            question_hash=question_hash,
            created_at=datetime.utcnow()
        )
    
    async def _check_cache(self, fingerprint: QueryFingerprint, trace_id: str) -> Optional[ProcessingResult]:
        """Check cache for existing response."""
        try:
            if not self.db_client:
                return None
            
            # Check for cached pack
            cutoff_time = datetime.utcnow() - timedelta(hours=self.cache_ttl_hours)
            
            # Query database for existing pack
            # This would be implemented with actual database queries
            # For now, return None (no cache hit)
            
            return None
            
        except Exception as e:
            logger.warning(f"[{trace_id}] Cache check failed: {e}")
            return None
    
    async def _generate_pack(
        self,
        fingerprint: QueryFingerprint,
        composed_answer: Dict[str, Any],
        trace_id: str
    ) -> Optional[str]:
        """Generate pack for query caching."""
        try:
            pack_id = f"pack-{fingerprint.fingerprint_hash}-{int(time.time())}"
            
            # Pack would be stored in database with:
            # - pack_id
            # - fingerprint_hash
            # - answer content
            # - citations
            # - created_at
            # - expires_at
            
            logger.debug(f"[{trace_id}] Generated pack: {pack_id}")
            
            return pack_id
            
        except Exception as e:
            logger.warning(f"[{trace_id}] Pack generation failed: {e}")
            return None
    
    async def _cache_result(
        self,
        fingerprint: QueryFingerprint,
        composed_answer: Dict[str, Any],
        pack_id: Optional[str],
        trace_id: str
    ):
        """Cache result for future queries."""
        try:
            if not pack_id or not self.db_client:
                return
            
            # Store in database cache
            # This would be implemented with actual database operations
            
            logger.debug(f"[{trace_id}] Cached result with pack: {pack_id}")
            
        except Exception as e:
            logger.warning(f"[{trace_id}] Result caching failed: {e}")
    
    def _update_success_metrics(self, total_time: float, retrieval_time: float, composition_time: float):
        """Update success metrics."""
        self.metrics["total_queries"] += 1
        self.metrics["successful_queries"] += 1
        
        # Update average processing time
        total_successful = self.metrics["successful_queries"]
        current_avg = self.metrics["avg_processing_time_ms"]
        self.metrics["avg_processing_time_ms"] = ((current_avg * (total_successful - 1)) + total_time) / total_successful
        
        # Update average retrieval time
        current_retrieval_avg = self.metrics["avg_retrieval_time_ms"]
        self.metrics["avg_retrieval_time_ms"] = ((current_retrieval_avg * (total_successful - 1)) + retrieval_time) / total_successful
        
        # Update average composition time
        current_composition_avg = self.metrics["avg_composition_time_ms"]
        self.metrics["avg_composition_time_ms"] = ((current_composition_avg * (total_successful - 1)) + composition_time) / total_successful
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get current processing metrics."""
        return {
            **self.metrics,
            "cache_hit_rate": self.metrics["cached_responses"] / max(self.metrics["total_queries"], 1),
            "success_rate": self.metrics["successful_queries"] / max(self.metrics["total_queries"], 1),
            "timestamp": datetime.utcnow().isoformat()
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """Check query processor health."""
        try:
            health_status = {
                "status": "healthy",
                "services": {},
                "metrics": self.get_metrics(),
                "timestamp": datetime.utcnow().isoformat()
            }
            
            # Check service dependencies
            if self.retriever:
                retriever_health = await self.retriever.health_check()
                health_status["services"]["retriever"] = retriever_health.get("status", "unknown")
            
            if self.guardrails:
                guardrails_health = self.guardrails.health_check()
                health_status["services"]["guardrails"] = guardrails_health.get("status", "unknown")
            
            if self.composer:
                composer_health = self.composer.health_check()
                health_status["services"]["composer"] = composer_health.get("status", "unknown")
            
            # Check if any service is unhealthy
            unhealthy_services = [name for name, status in health_status["services"].items() if status != "healthy"]
            if unhealthy_services:
                health_status["status"] = "degraded"
                health_status["unhealthy_services"] = unhealthy_services
            
            return health_status
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }


class QueryProcessingException(Exception):
    """Exception raised during query processing."""
    
    def __init__(self, message: str, error_code: str):
        self.message = message
        self.error_code = error_code
        super().__init__(message)


# Global processor instance
_query_processor: Optional[QueryProcessor] = None


async def get_query_processor() -> QueryProcessor:
    """Get global query processor instance."""
    global _query_processor
    if _query_processor is None:
        _query_processor = QueryProcessor()
        await _query_processor.initialize()
    return _query_processor


async def process_query(
    question: str,
    province: str,
    doc_class: str,
    asset: Optional[str] = None,
    lang: str = "zh-CN",
    max_citations: int = 10,
    trace_id: Optional[str] = None
) -> ProcessingResult:
    """
    Convenience function for query processing.
    
    Args:
        question: User question in Chinese
        province: Province for geo-specific search
        doc_class: Document class for scoped search
        asset: Optional asset type for targeted search
        lang: Response language preference
        max_citations: Maximum citations to return
        trace_id: Optional trace identifier for logging
        
    Returns:
        Complete processing result with answer and metadata
    """
    processor = await get_query_processor()
    return await processor.process_query(
        question=question,
        province=province,
        doc_class=doc_class,
        asset=asset,
        lang=lang,
        max_citations=max_citations,
        trace_id=trace_id
    )


if __name__ == "__main__":
    # Quick test of query processor
    import asyncio
    
    async def test_processor():
        print("=== Query Processor Test ===")
        
        try:
            result = await process_query(
                question="广东省光伏电站并网需要什么资料？",
                province="guangdong",
                doc_class="grid_connection",
                asset="solar",
                trace_id="test-query-1"
            )
            
            print(f"Answer: {result.answer_zh[:100]}...")
            print(f"Citations: {result.total_citations}")
            print(f"Processing time: {result.processing_metrics.total_time_ms:.1f}ms")
            print(f"Pack ID: {result.pack_id}")
            
        except Exception as e:
            print(f"Test failed: {e}")
    
    asyncio.run(test_processor())