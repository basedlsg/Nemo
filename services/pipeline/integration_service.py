"""Integration service that wires together all RAG components for end-to-end processing."""

import logging
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime

from services.pipeline.query_processor import QueryProcessor, ProcessingResult
from services.gateway.models import QueryRequest, QueryResponse, CitationMetadata
from services.core.models import QueryContext

logger = logging.getLogger(__name__)


class RAGIntegrationService:
    """
    Integration service that provides a unified interface for the complete RAG system.
    
    This service acts as the main entry point for query processing, handling:
    - Request validation and preprocessing
    - Query processing through the complete pipeline
    - Response formatting and post-processing
    - Error handling and logging
    - Performance monitoring and metrics collection
    """
    
    def __init__(self):
        """Initialize integration service."""
        self.query_processor = None
        self.initialized = False
        
        # Service metrics
        self.metrics = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "avg_response_time_ms": 0.0,
            "error_distribution": {}
        }
    
    async def initialize(self):
        """Initialize all service dependencies."""
        try:
            logger.info("Initializing RAG Integration Service...")
            
            # Initialize query processor
            self.query_processor = QueryProcessor()
            await self.query_processor.initialize()
            
            self.initialized = True
            logger.info("RAG Integration Service initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize RAG Integration Service: {e}")
            raise
    
    async def process_query_request(
        self,
        request: QueryRequest,
        trace_id: str
    ) -> QueryResponse:
        """
        Process a complete query request through the RAG pipeline.
        
        Args:
            request: Validated query request
            trace_id: Unique trace identifier
            
        Returns:
            Complete query response with answer and metadata
        """
        if not self.initialized:
            raise RuntimeError("Integration service not initialized")
        
        start_time = datetime.utcnow()
        
        try:
            logger.info(f"[{trace_id}] Processing query request: {request.question[:50]}...")
            
            # Update request metrics
            self.metrics["total_requests"] += 1
            
            # Process query through pipeline
            result = await self.query_processor.process_query(
                question=request.question,
                province=request.province.value,
                doc_class=request.doc_class.value,
                asset=request.asset.value if request.asset else None,
                lang=request.lang.value,
                max_citations=request.max_citations,
                trace_id=trace_id
            )
            
            # Format response
            response = self._format_query_response(request, result, trace_id, start_time)
            
            # Update success metrics
            self._update_success_metrics(result.processing_metrics.total_time_ms)
            
            logger.info(f"[{trace_id}] Query request processed successfully")
            
            return response
            
        except Exception as e:
            # Update error metrics
            self._update_error_metrics(str(e))
            
            logger.error(f"[{trace_id}] Query request processing failed: {e}")
            raise
    
    def _format_query_response(
        self,
        request: QueryRequest,
        result: ProcessingResult,
        trace_id: str,
        start_time: datetime
    ) -> QueryResponse:
        """Format processing result into query response."""
        try:
            # Convert citations to response format
            citations = [
                CitationMetadata(
                    citation_id=citation["citation_id"],
                    title=citation["title"],
                    url=citation["url"],
                    effective_date=citation["effective_date"],
                    score=citation["score"],
                    passage=citation.get("passage", "")
                )
                for citation in result.citations
            ]
            
            # Calculate total processing time
            end_time = datetime.utcnow()
            total_processing_time = int((end_time - start_time).total_seconds() * 1000)
            
            # Create query context
            query_context = {
                "province": request.province.value,
                "doc_class": request.doc_class.value,
                "asset": request.asset.value if request.asset else None,
                "lang": request.lang.value,
                "max_citations": request.max_citations,
                "question_length": len(request.question),
                "fingerprint": result.query_fingerprint.fingerprint_hash,
                "pack_id": result.pack_id,
                "cached": result.cached
            }
            
            response = QueryResponse(
                answer_zh=result.answer_zh,
                citations=citations,
                sections=result.sections,
                total_citations=result.total_citations,
                processing_time_ms=total_processing_time,
                composed_at=datetime.utcnow().isoformat(),
                query_context=query_context,
                trace_id=trace_id
            )
            
            return response
            
        except Exception as e:
            logger.error(f"[{trace_id}] Response formatting failed: {e}")
            raise
    
    def _update_success_metrics(self, processing_time_ms: float):
        """Update success metrics."""
        self.metrics["successful_requests"] += 1
        
        # Update average response time
        total_successful = self.metrics["successful_requests"]
        current_avg = self.metrics["avg_response_time_ms"]
        self.metrics["avg_response_time_ms"] = ((current_avg * (total_successful - 1)) + processing_time_ms) / total_successful
    
    def _update_error_metrics(self, error_message: str):
        """Update error metrics."""
        self.metrics["failed_requests"] += 1
        
        # Categorize error
        error_category = "unknown"
        if "no_citations" in error_message.lower():
            error_category = "no_citations"
        elif "policy" in error_message.lower() or "guardrails" in error_message.lower():
            error_category = "policy_violation"
        elif "composition" in error_message.lower():
            error_category = "composition_failed"
        elif "retrieval" in error_message.lower():
            error_category = "retrieval_failed"
        elif "internal" in error_message.lower():
            error_category = "internal_error"
        
        self.metrics["error_distribution"][error_category] = self.metrics["error_distribution"].get(error_category, 0) + 1
    
    async def get_service_health(self) -> Dict[str, Any]:
        """Get comprehensive service health status."""
        try:
            health_status = {
                "status": "healthy",
                "initialized": self.initialized,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            if self.initialized and self.query_processor:
                # Get query processor health
                processor_health = await self.query_processor.health_check()
                health_status["query_processor"] = processor_health
                
                # Determine overall status
                if processor_health.get("status") != "healthy":
                    health_status["status"] = "degraded"
            else:
                health_status["status"] = "not_initialized"
            
            return health_status
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def get_service_metrics(self) -> Dict[str, Any]:
        """Get comprehensive service metrics."""
        try:
            total_requests = self.metrics["total_requests"]
            success_rate = self.metrics["successful_requests"] / max(total_requests, 1)
            failure_rate = self.metrics["failed_requests"] / max(total_requests, 1)
            
            service_metrics = {
                "total_requests": total_requests,
                "successful_requests": self.metrics["successful_requests"],
                "failed_requests": self.metrics["failed_requests"],
                "success_rate": success_rate,
                "failure_rate": failure_rate,
                "avg_response_time_ms": self.metrics["avg_response_time_ms"],
                "error_distribution": self.metrics["error_distribution"],
                "timestamp": datetime.utcnow().isoformat()
            }
            
            # Add query processor metrics if available
            if self.initialized and self.query_processor:
                processor_metrics = self.query_processor.get_metrics()
                service_metrics["query_processor"] = processor_metrics
            
            return service_metrics
            
        except Exception as e:
            logger.error(f"Failed to get service metrics: {e}")
            return {
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    async def validate_system_integration(self) -> Dict[str, Any]:
        """Validate complete system integration with test queries."""
        try:
            logger.info("Starting system integration validation...")
            
            validation_results = {
                "status": "success",
                "tests_run": 0,
                "tests_passed": 0,
                "tests_failed": 0,
                "test_results": [],
                "timestamp": datetime.utcnow().isoformat()
            }
            
            # Test queries for each province and doc_class combination
            test_queries = [
                {
                    "question": "广东省光伏电站并网需要什么资料？",
                    "province": "guangdong",
                    "doc_class": "grid_connection",
                    "asset": "solar",
                    "expected_keywords": ["资料", "并网", "光伏"]
                },
                {
                    "question": "山东风电场参与市场交易的条件是什么？",
                    "province": "shandong",
                    "doc_class": "market_rules",
                    "asset": "wind",
                    "expected_keywords": ["条件", "市场", "风电"]
                },
                {
                    "question": "内蒙古储能电站调度运行有什么要求？",
                    "province": "inner_mongolia",
                    "doc_class": "dispatch_ops",
                    "asset": "bess",
                    "expected_keywords": ["要求", "调度", "储能"]
                }
            ]
            
            for i, test_query in enumerate(test_queries):
                validation_results["tests_run"] += 1
                test_trace_id = f"validation-test-{i+1}"
                
                try:
                    # Create test request
                    from services.gateway.models import Province, DocClass, Asset, Language
                    
                    request = QueryRequest(
                        question=test_query["question"],
                        province=Province(test_query["province"]),
                        doc_class=DocClass(test_query["doc_class"]),
                        asset=Asset(test_query["asset"]) if test_query["asset"] else None,
                        lang=Language.CHINESE,
                        max_citations=5
                    )
                    
                    # Process test query
                    response = await self.process_query_request(request, test_trace_id)
                    
                    # Validate response
                    test_result = {
                        "test_id": i + 1,
                        "query": test_query["question"],
                        "status": "passed",
                        "response_length": len(response.answer_zh),
                        "citations_count": len(response.citations),
                        "processing_time_ms": response.processing_time_ms,
                        "keywords_found": []
                    }
                    
                    # Check for expected keywords
                    answer_lower = response.answer_zh.lower()
                    for keyword in test_query["expected_keywords"]:
                        if keyword in answer_lower:
                            test_result["keywords_found"].append(keyword)
                    
                    # Validate minimum requirements
                    if len(response.citations) == 0:
                        test_result["status"] = "failed"
                        test_result["error"] = "No citations returned"
                    elif len(response.answer_zh) < 50:
                        test_result["status"] = "failed"
                        test_result["error"] = "Answer too short"
                    elif not any(keyword in answer_lower for keyword in test_query["expected_keywords"]):
                        test_result["status"] = "failed"
                        test_result["error"] = "No expected keywords found"
                    
                    if test_result["status"] == "passed":
                        validation_results["tests_passed"] += 1
                    else:
                        validation_results["tests_failed"] += 1
                    
                    validation_results["test_results"].append(test_result)
                    
                    logger.info(f"Validation test {i+1}: {test_result['status']}")
                    
                except Exception as e:
                    validation_results["tests_failed"] += 1
                    validation_results["test_results"].append({
                        "test_id": i + 1,
                        "query": test_query["question"],
                        "status": "failed",
                        "error": str(e)
                    })
                    
                    logger.error(f"Validation test {i+1} failed: {e}")
            
            # Determine overall validation status
            if validation_results["tests_failed"] > 0:
                validation_results["status"] = "partial_failure"
                if validation_results["tests_passed"] == 0:
                    validation_results["status"] = "failure"
            
            logger.info(f"System integration validation completed: {validation_results['status']}")
            
            return validation_results
            
        except Exception as e:
            logger.error(f"System integration validation failed: {e}")
            return {
                "status": "error",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }


# Global integration service instance
_integration_service: Optional[RAGIntegrationService] = None


async def get_integration_service() -> RAGIntegrationService:
    """Get global integration service instance."""
    global _integration_service
    if _integration_service is None:
        _integration_service = RAGIntegrationService()
        await _integration_service.initialize()
    return _integration_service


async def process_query_request(request: QueryRequest, trace_id: str) -> QueryResponse:
    """
    Convenience function for processing query requests.
    
    Args:
        request: Validated query request
        trace_id: Unique trace identifier
        
    Returns:
        Complete query response
    """
    service = await get_integration_service()
    return await service.process_query_request(request, trace_id)


if __name__ == "__main__":
    # Quick test of integration service
    import asyncio
    from services.gateway.models import QueryRequest, Province, DocClass, Asset, Language
    
    async def test_integration():
        print("=== RAG Integration Service Test ===")
        
        try:
            # Test query request
            request = QueryRequest(
                question="广东省光伏电站并网需要什么资料？",
                province=Province.GUANGDONG,
                doc_class=DocClass.GRID_CONNECTION,
                asset=Asset.SOLAR,
                lang=Language.CHINESE,
                max_citations=5
            )
            
            response = await process_query_request(request, "test-integration-1")
            
            print(f"Answer: {response.answer_zh[:100]}...")
            print(f"Citations: {len(response.citations)}")
            print(f"Processing time: {response.processing_time_ms}ms")
            print(f"Trace ID: {response.trace_id}")
            
            # Test system validation
            print("\n=== System Validation Test ===")
            service = await get_integration_service()
            validation_results = await service.validate_system_integration()
            
            print(f"Validation status: {validation_results['status']}")
            print(f"Tests run: {validation_results['tests_run']}")
            print(f"Tests passed: {validation_results['tests_passed']}")
            print(f"Tests failed: {validation_results['tests_failed']}")
            
        except Exception as e:
            print(f"Test failed: {e}")
    
    asyncio.run(test_integration())