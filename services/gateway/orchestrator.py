"""Query orchestrator that coordinates the RAG pipeline."""

import logging
import asyncio
import time
from typing import Dict, Any, List, Optional
from datetime import datetime
import os
from services.refusal.refusal_handler import create_refusal

from .models import QueryRequest, QueryResponse, RefusalResponse, CitationMetadata

logger = logging.getLogger(__name__)


class QueryOrchestrator:
    """
    Orchestrates the complete RAG pipeline: Retriever → Guardrails → Composer.
    
    Pipeline flow:
    1. Query → Retriever (hybrid search)
    2. Search results → Guardrails (policy validation)
    3. Validated results → Composer (answer generation)
    4. Composed answer → Response formatting
    """
    
    PLACEHOLDER = {"example.com", "gzpec.cn", "sdpxc.cn", "impex.org.cn"}  # remove when fully live
    
    def __init__(self):
        """Initialize orchestrator with service clients."""
        # Service clients will be injected via dependency injection
        self.retriever_client = None
        self.guardrails_client = None
        self.composer_client = None
        
        # Performance tracking
        self.stats = {
            "total_queries": 0,
            "successful_queries": 0,
            "refusal_queries": 0,
            "avg_processing_time_ms": 0.0,
            "province_distribution": {},
            "doc_class_distribution": {},
            "asset_distribution": {}
        }
    
    def set_service_clients(self, retriever_client, guardrails_client, composer_client):
        """Set service clients for dependency injection."""
        self.retriever_client = retriever_client
        self.guardrails_client = guardrails_client
        self.composer_client = composer_client

    def _has_placeholder(self, citations: List[Dict[str, Any]]) -> bool:
        """Check if any citation contains a placeholder URL."""
        for c in citations:
            u = (c.get("url") or "").lower()
            if any(ph in u for ph in self.PLACEHOLDER):
                return True
        return False
    
    async def process_query(self, request: QueryRequest, trace_id: str) -> Dict[str, Any]:
        """
        Process query through the complete RAG pipeline.
        
        Args:
            request: Query request with question and parameters
            trace_id: Unique trace identifier for logging
            
        Returns:
            Query response or refusal response
        """
        start_time = time.time()
        
        try:
            # Update statistics
            self._update_query_stats(request)
            
            logger.info(f"[{trace_id}] Starting query processing: {request.question[:50]}...")
            
            # Step 1: Retriever - Hybrid search for relevant citations
            retriever_start = time.time()
            search_results = await self._call_retriever(request, trace_id)
            retriever_time = (time.time() - retriever_start) * 1000
            
            logger.info(f"[{trace_id}] Retriever completed: {len(search_results)} results in {retriever_time:.1f}ms")
            
            if not search_results:
                return self._create_refusal_response(
                    "no_citations_found",
                    "没有找到相关的官方资料",
                    "尝试使用更具体的关键词或选择不同的省份/资产类型",
                    trace_id
                )
            
            # Step 2: Guardrails - Policy validation (temporarily disabled)
            validated_results = search_results
            
            # Step 3: Composer - Answer generation (temporarily disabled)
            composed_answer = {
                "answer_zh": "Temporarily disabled",
                "citations": validated_results
            }
            
            # Step 4: Format successful response
            total_time = (time.time() - start_time) * 1000
            
            # Guardrail: check for placeholder URLs before returning success
            if self._has_placeholder(composed_answer["citations"]):
                logger.warning(f"[{trace_id}] Placeholder URL detected in response, refusing.")
                raise create_refusal(
                    "stale_citation",
                    {"reason": "placeholder_url_detected"},
                    trace_id=trace_id
                )

            response = QueryResponse(
                answer_zh=composed_answer["answer_zh"],
                citations=[
                    CitationMetadata(
                        citation_id=citation["citation_id"],
                        title=citation["title"],
                        url=citation["url"],
                        effective_date=citation["effective_date"],
                        score=citation["score"],
                        passage=citation.get("passage", "")
                    )
                    for citation in composed_answer["citations"]
                ],
                sections=composed_answer.get("sections", 0),
                total_citations=composed_answer.get("total_citations", 0),
                processing_time_ms=int(total_time),
                composed_at=composed_answer["composed_at"],
                query_context=composed_answer.get("query_context", {}),
                trace_id=trace_id
            )
            
            # Update success statistics
            self._update_success_stats(total_time)
            
            logger.info(f"[{trace_id}] Query processing completed successfully in {total_time:.1f}ms")
            
            return response.dict()
            
        except Exception as e:
            logger.error(f"[{trace_id}] Query processing failed: {e}")
            return self._create_refusal_response(
                "internal_error",
                "系统处理过程中出现错误",
                "请稍后重试或联系技术支持",
                trace_id
            )
    
    async def _call_retriever(self, request: QueryRequest, trace_id: str) -> List[Dict[str, Any]]:
        """Call retriever service for hybrid search."""
        from services.retriever.hybrid_search import get_retriever_client
        retriever = get_retriever_client()

        ALLOW_MOCK = os.getenv("ALLOW_MOCK_FALLBACK", "false").lower() == "true"
        REAL = os.getenv("ENABLE_REAL_APIS", "false").lower() == "true"

        if not REAL:
            logger.warning(f"[{trace_id}] Real APIs disabled. Set ENABLE_REAL_APIS=true to enable.")
            raise create_refusal(
                "system_overload",
                {"detail": "real_apis_disabled", "hint": "Set ENABLE_REAL_APIS=true"},
                trace_id=trace_id
            )

        health = await retriever.health_check()
        if health.get("status") != "healthy":
            if ALLOW_MOCK:
                logger.warning(f"[{trace_id}] Retriever unhealthy, USING MOCK due to ALLOW_MOCK_FALLBACK. health={health}")
                return self._mock_retriever_results(request)
            logger.error(f"[{trace_id}] Retriever unhealthy, refusing (no mock). health={health}")
            raise create_refusal(
                "system_overload",
                {"detail": "retriever_unhealthy_no_mock", "health": health},
                trace_id=trace_id
            )

        results = await retriever.search(
            province=request.province.value,
            doc_class=request.doc_class.value,
            question=request.question,
            asset=request.asset.value if request.asset else None,
            limit=request.max_citations
        )
        
        logger.info(f"[{trace_id}] Retrieved {len(results)} real results from database")
        return results
    
    async def _call_guardrails(self, search_results: List[Dict[str, Any]], request: QueryRequest, trace_id: str) -> List[Dict[str, Any]]:
        """Call guardrails service for policy validation."""
        try:
            # Try to use local guardrails service directly
            from services.guardrails.policy_engine import get_guardrails_engine, RefusalException
            
            guardrails_engine = get_guardrails_engine()
            
            # Test if guardrails is working
            health = guardrails_engine.health_check()
            if health.get("status") != "healthy":
                logger.warning(f"[{trace_id}] Guardrails unhealthy, skipping validation: {health}")
                return search_results
            
            # Create query context for guardrails
            query_context = {
                "province": request.province.value,
                "doc_class": request.doc_class.value,
                "asset": request.asset.value if request.asset else None,
                "lang": request.lang.value,
                "question": request.question
            }
            
            # Extract citations from search results for guardrails check
            citations = []
            for result in search_results:
                metadata = result.get("metadata", {})
                citations.append({
                    "citation_id": result.get("citation_id"),
                    "url": metadata.get("url", ""),
                    "title": metadata.get("title", ""),
                    "effective_date": metadata.get("effective_date"),
                    "checksum": metadata.get("checksum"),
                    "superseded_by": metadata.get("superseded_by")
                })
            
            # Check guardrails policies (we'll check with empty answer for now, real answer comes later)
            try:
                guardrails_engine.check_all_policies("", citations, query_context)
                logger.info(f"[{trace_id}] Guardrails validation passed")
            except RefusalException as e:
                raise GuardrailsRefusalException(
                    e.reason.value,
                    e.message,
                    "请修改查询内容或联系相关部门"
                )
            
            return search_results
            
        except GuardrailsRefusalException:
            raise
        except Exception as e:
            logger.error(f"[{trace_id}] Guardrails call failed: {e}")
            # If guardrails fails, allow the query to proceed (fail-open)
            logger.warning(f"[{trace_id}] Guardrails service unavailable, proceeding without validation")
            return search_results
    
    async def _call_composer(self, validated_results: List[Dict[str, Any]], request: QueryRequest, trace_id: str) -> Dict[str, Any]:
        """Call composer service for answer generation."""
        try:
            # Try to use local composer service directly
            from services.composer.answer_composer import get_answer_composer
            
            composer = get_answer_composer()
            
            # Test if composer is working
            # health = composer.health_check()
            # if health.get("status") != "healthy":
            #     logger.warning(f"[{trace_id}] Composer unhealthy, using mock composition: {health}")
            #     return self._mock_composer_result(validated_results, request)
            
            # Create composer query
            composer_query = {
                "province": request.province.value,
                "doc_class": request.doc_class.value,
                "asset": request.asset.value if request.asset else None,
                "lang": request.lang.value,
                "question": request.question
            }
            
            # Compose answer
            result = composer.compose_answer(
                search_results=validated_results,
                query=composer_query,
                max_citations=request.max_citations
            )
            
            # Check if composer refused to generate answer
            if result.get("refusal_reason"):
                raise ComposerRefusalException(result.get("answer_zh", "无法生成有效答案"))
            
            logger.info(f"[{trace_id}] Answer composed with {result.get('total_citations', 0)} citations")
            return result
            
        except ComposerRefusalException:
            raise
        except Exception as e:
            logger.error(f"[{trace_id}] Composer call failed: {e}")
            raise ComposerRefusalException("答案生成过程中出现错误")
    
    def _mock_retriever_results(self, request: QueryRequest) -> List[Dict[str, Any]]:
        """Mock retriever results for testing."""
        province_labels = {
            "guangdong": "广东",
            "shandong": "山东",
            "inner_mongolia": "内蒙古"
        }
        
        asset_labels = {
            "wind": "风电",
            "solar": "光伏",
            "bess": "储能",
            "coal_flex": "煤电"
        }
        
        province_label = province_labels.get(request.province.value, request.province.value)
        asset_label = asset_labels.get(request.asset.value if request.asset else "solar", "光伏")
        
        return [
            {
                "citation_id": f"cite-{request.province.value}-1",
                "passage": f"{asset_label}项目在{province_label}需要提交相关技术资料和安全评估报告。",
                "score": 0.92,
                "metadata": {
                    "title": f"{province_label}省{asset_label}并网管理办法",
                    "effective_date": "2024-06-01",
                    "url": f"https://example.com/{request.province.value}/rules"
                }
            },
            {
                "citation_id": f"cite-{request.province.value}-2",
                "passage": f"申请受理时限为15个工作日，审批时限为30个工作日。",
                "score": 0.87,
                "metadata": {
                    "title": f"{province_label}省电力接入管理规定",
                    "effective_date": "2024-05-15",
                    "url": f"https://example.com/{request.province.value}/access"
                }
            }
        ]
    
    def _mock_composer_result(self, validated_results: List[Dict[str, Any]], request: QueryRequest) -> Dict[str, Any]:
        """Mock composer result for testing."""
        province_labels = {
            "guangdong": "广东",
            "shandong": "山东", 
            "inner_mongolia": "内蒙古"
        }
        
        asset_labels = {
            "wind": "风电",
            "solar": "光伏",
            "bess": "储能",
            "coal_flex": "煤电"
        }
        
        doc_class_labels = {
            "market_rules": "市场规则",
            "grid_connection": "并网",
            "dispatch_ops": "调度"
        }
        
        province_label = province_labels.get(request.province.value, request.province.value)
        asset_label = asset_labels.get(request.asset.value if request.asset else "solar", "光伏")
        doc_class_label = doc_class_labels.get(request.doc_class.value, request.doc_class.value)
        
        answer_title = f"**{doc_class_label}要点（{province_label} / {asset_label}）**"
        
        bullets = []
        citations = []
        
        for i, result in enumerate(validated_results):
            metadata = result["metadata"]
            bullet = f"  • {result['passage']} 〔《{metadata['title']}》，生效：{metadata['effective_date']}〕"
            bullets.append(bullet)
            
            citations.append({
                "citation_id": result["citation_id"],
                "title": metadata["title"],
                "url": metadata["url"],
                "effective_date": metadata["effective_date"],
                "score": result["score"],
                "passage": result["passage"]
            })
        
        answer_text = answer_title + "\n- 相关规定：\n" + "\n".join(bullets)
        
        return {
            "answer_zh": answer_text,
            "citations": citations,
            "sections": 1,
            "total_citations": len(citations),
            "composed_at": datetime.utcnow().isoformat(),
            "query_context": {
                "province": request.province.value,
                "asset": request.asset.value if request.asset else None,
                "doc_class": request.doc_class.value
            }
        }
    
    def _create_refusal_response(self, reason_code: str, message: str, suggestion: str, trace_id: str) -> Dict[str, Any]:
        """Create structured refusal response."""
        self.stats["refusal_queries"] += 1
        
        return RefusalResponse(
            error="query_refused",
            reason=message,
            policy_violated=reason_code,
            suggestion=suggestion,
            trace_id=trace_id,
            timestamp=datetime.utcnow().isoformat()
        ).dict()
    
    def _update_query_stats(self, request: QueryRequest):
        """Update query statistics."""
        self.stats["total_queries"] += 1
        
        # Province distribution
        province = request.province.value
        self.stats["province_distribution"][province] = self.stats["province_distribution"].get(province, 0) + 1
        
        # Doc class distribution
        doc_class = request.doc_class.value
        self.stats["doc_class_distribution"][doc_class] = self.stats["doc_class_distribution"].get(doc_class, 0) + 1
        
        # Asset distribution
        asset = request.asset.value if request.asset else "none"
        self.stats["asset_distribution"][asset] = self.stats["asset_distribution"].get(asset, 0) + 1
    
    def _update_success_stats(self, processing_time_ms: float):
        """Update success statistics."""
        self.stats["successful_queries"] += 1
        
        # Update average processing time
        total_successful = self.stats["successful_queries"]
        current_avg = self.stats["avg_processing_time_ms"]
        self.stats["avg_processing_time_ms"] = ((current_avg * (total_successful - 1)) + processing_time_ms) / total_successful
    
    def get_stats(self) -> Dict[str, Any]:
        """Get current orchestrator statistics."""
        total_queries = self.stats["total_queries"]
        refusal_rate = self.stats["refusal_queries"] / total_queries if total_queries > 0 else 0.0
        
        return {
            "total_queries": total_queries,
            "successful_queries": self.stats["successful_queries"],
            "refusal_rate": refusal_rate,
            "avg_processing_time_ms": self.stats["avg_processing_time_ms"],
            "province_distribution": self.stats["province_distribution"],
            "doc_class_distribution": self.stats["doc_class_distribution"],
            "asset_distribution": self.stats["asset_distribution"],
            "timestamp": datetime.utcnow().isoformat()
        }


class GuardrailsRefusalException(Exception):
    """Exception raised when guardrails refuse a query."""
    
    def __init__(self, reason_code: str, message: str, suggestion: str):
        self.reason_code = reason_code
        self.message = message
        self.suggestion = suggestion
        super().__init__(message)


class ComposerRefusalException(Exception):
    """Exception raised when composer cannot generate an answer."""
    
    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


# Global orchestrator instance
_orchestrator: Optional[QueryOrchestrator] = None


def get_orchestrator() -> QueryOrchestrator:
    """Get global orchestrator instance."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = QueryOrchestrator()
    return _orchestrator
