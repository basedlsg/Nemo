"""Gemini-powered answer composer that replaces template-based generation."""

import asyncio
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

from .service import GeminiService
from .schemas import GeminiConfig

logger = logging.getLogger(__name__)


class GeminiAnswerComposer:
    """Answer composer that uses Gemini for intelligent answer generation."""

    def __init__(self, config: Optional[GeminiConfig] = None):
        """Initialize Gemini answer composer."""
        self.config = config or GeminiConfig()
        self.gemini_service = GeminiService(self.config)
        self.initialized = False

    def initialize_sync(self):
        """Initialize the composer synchronously for FastAPI compatibility."""
        if not self.initialized:
            # Create event loop for initialization
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            if loop.is_running():
                # If loop is running, schedule initialization
                import nest_asyncio
                nest_asyncio.apply()
                loop.run_until_complete(self.gemini_service.initialize())
            else:
                loop.run_until_complete(self.gemini_service.initialize())

            self.initialized = True
            logger.info("Gemini answer composer initialized")

    def compose_answer(
        self,
        search_results: List[Dict[str, Any]],
        query: Dict[str, Any],
        max_citations: int = 10
    ) -> Dict[str, Any]:
        """Compose answer using Gemini instead of templates."""
        # Ensure initialization
        if not self.initialized:
            self.initialize_sync()

        try:
            # Extract question and context
            question = query.get("question", "")
            query_context = {
                "province": query.get("province", ""),
                "asset": query.get("asset", ""),
                "doc_class": query.get("doc_class", ""),
                "lang": query.get("lang", "zh-CN"),
                "max_citations": max_citations
            }

            # Generate answer using Gemini
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            result = loop.run_until_complete(
                self.gemini_service.generate_answer(
                    question=question,
                    search_results=search_results,
                    query_context=query_context,
                    validate_answer=True
                )
            )

            # Format result to match existing composer interface
            formatted_result = self._format_gemini_result(result, query)

            logger.info(f"Gemini composer generated answer with {len(formatted_result.get('citations', []))} citations")
            return formatted_result

        except Exception as e:
            logger.error(f"Gemini composition failed: {e}")
            # Fallback to refusal response
            return self._create_refusal_response(f"Gemini生成失败: {str(e)}")

    def _format_gemini_result(self, gemini_result: Dict[str, Any], query: Dict[str, Any]) -> Dict[str, Any]:
        """Format Gemini result to match existing composer interface."""
        try:
            # Create citation metadata
            citations = []
            for citation in gemini_result.get("citations", []):
                citation_meta = {
                    "citation_id": citation.get("citation_id", f"gemini_{len(citations) + 1}"),
                    "title": citation.get("title", "Generated Citation"),
                    "url": citation.get("url", ""),
                    "effective_date": citation.get("effective_date", ""),
                    "score": citation.get("score", 0.8)
                }
                citations.append(citation_meta)

            # Format answer sections
            sections = []
            for section in gemini_result.get("sections", []):
                section_data = {
                    "title": section.get("title", "回答"),
                    "bullets": section.get("bullets", [])
                }
                sections.append(section_data)

            # Create final result
            return {
                "answer_zh": gemini_result.get("answer_zh", ""),
                "citations": citations,
                "sections": sections,
                "total_citations": len(citations),
                "composed_at": datetime.utcnow().isoformat(),
                "query_context": query,
                "confidence_score": gemini_result.get("confidence_score", 0.0),
                "grounding_score": gemini_result.get("grounding_score", 0.0),
                "processing_time_ms": gemini_result.get("processing_time_ms", 0),
                "validation": gemini_result.get("validation", {})
            }

        except Exception as e:
            logger.error(f"Failed to format Gemini result: {e}")
            return self._create_refusal_response("结果格式化失败")

    def _create_refusal_response(self, reason: str) -> Dict[str, Any]:
        """Create a refusal response when Gemini fails."""
        return {
            "answer_zh": f"无法生成有效答案: {reason}",
            "citations": [],
            "sections": [],
            "total_citations": 0,
            "composed_at": datetime.utcnow().isoformat(),
            "query_context": {},
            "refusal_reason": reason
        }

    def health_check(self) -> Dict[str, Any]:
        """Check composer health."""
        try:
            # Ensure initialization
            if not self.initialized:
                self.initialize_sync()

            # Check Gemini service health synchronously
            import asyncio
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            if loop.is_running():
                import nest_asyncio
                nest_asyncio.apply()
                service_health = loop.run_until_complete(self.gemini_service.health_check())
            else:
                service_health = loop.run_until_complete(self.gemini_service.health_check())

            return {
                "status": service_health["status"],
                "gemini_service": service_health,
                "composer_type": "gemini"
            }

        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "composer_type": "gemini"
            }

    def get_composer_stats(self) -> Dict[str, Any]:
        """Get composer statistics."""
        import asyncio
        try:
            # Ensure initialization
            if not self.initialized:
                self.initialize_sync()

            # Get Gemini service stats synchronously
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            if loop.is_running():
                import nest_asyncio
                nest_asyncio.apply()
                stats = loop.run_until_complete(self.gemini_service.get_service_stats())
            else:
                stats = loop.run_until_complete(self.gemini_service.get_service_stats())

            return stats
        except Exception as e:
            logger.error(f"Failed to get composer stats: {e}")
            return {"error": str(e)}
