"""Main Gemini service that orchestrates text parsing and answer generation."""

import logging
from typing import List, Dict, Any, Optional
import time

from .client import GeminiClient
from .parser import HierarchicalDocumentParser
from .validator import AnswerValidator
from .schemas import GeminiConfig, GeminiRequest, GeminiResponse, AnswerValidationResult

logger = logging.getLogger(__name__)


class GeminiService:
    """Main service for Gemini-powered text parsing and answer generation."""

    def __init__(self, config: Optional[GeminiConfig] = None):
        """Initialize Gemini service with all components."""
        self.config = config or GeminiConfig()

        # Initialize components
        self.client = GeminiClient(self.config)
        self.parser = HierarchicalDocumentParser()
        self.validator = AnswerValidator()

        # Performance tracking
        self.metrics = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "avg_generation_time_ms": 0.0,
            "avg_validation_time_ms": 0.0,
            "grounding_scores": []
        }

        logger.info("Initialized Gemini service")

    async def initialize(self) -> None:
        """Initialize service components."""
        try:
            # Test Gemini client health
            health = await self.client.health_check()
            if health["status"] != "healthy":
                logger.warning(f"Gemini client health check failed: {health}")

            logger.info("Gemini service initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize Gemini service: {e}")
            raise

    async def generate_answer(
        self,
        question: str,
        search_results: List[Dict[str, Any]],
        query_context: Dict[str, Any],
        validate_answer: bool = True
    ) -> Dict[str, Any]:
        """Generate answer from search results using Gemini."""
        start_time = time.time()
        self.metrics["total_requests"] += 1

        try:
            # Convert search results to document structure
            doc_structure = self._convert_search_results_to_structure(search_results)

            # Create Gemini request
            gemini_request = GeminiRequest(
                question=question,
                document_structure=doc_structure,
                query_context=query_context,
                max_citations=query_context.get("max_citations", 10)
            )

            # Generate answer with Gemini
            generation_start = time.time()
            gemini_response = await self.client.generate_answer(gemini_request)
            generation_time = int((time.time() - generation_start) * 1000)

            # Update metrics
            self._update_metrics("generation_time", generation_time)

            # Validate answer if requested
            validation_result = None
            if validate_answer:
                validation_start = time.time()
                validation_result = self.validator.validate_answer(
                    answer=gemini_response.answer_zh,
                    source_documents=search_results,
                    citations=gemini_response.citations
                )
                validation_time = int((time.time() - validation_start) * 1000)
                self._update_metrics("validation_time", validation_time)

                # Store grounding score for analysis
                self.metrics["grounding_scores"].append(validation_result.grounding.grounding_score)

            # Prepare final response
            total_time = int((time.time() - start_time) * 1000)

            result = {
                "answer_zh": gemini_response.answer_zh,
                "citations": gemini_response.citations,
                "sections": gemini_response.sections,
                "confidence_score": gemini_response.confidence_score,
                "grounding_score": gemini_response.grounding_score,
                "processing_time_ms": total_time,
                "generated_at": gemini_response.generated_at.isoformat(),
                "query_context": query_context
            }

            # Add validation results if available
            if validation_result:
                result["validation"] = {
                    "is_valid": validation_result.is_valid,
                    "overall_score": validation_result.overall_score,
                    "issues": validation_result.issues,
                    "recommendations": validation_result.recommendations,
                    "grounding": {
                        "is_grounded": validation_result.grounding.is_grounded,
                        "grounding_score": validation_result.grounding.grounding_score,
                        "grounded_phrases": validation_result.grounding.grounded_phrases,
                        "ungrounded_phrases": validation_result.grounding.ungrounded_phrases
                    }
                }

            self.metrics["successful_requests"] += 1
            logger.info(f"Gemini answer generated successfully in {total_time}ms")

            return result

        except Exception as e:
            self.metrics["failed_requests"] += 1
            logger.error(f"Gemini answer generation failed: {e}")
            raise

    def _convert_search_results_to_structure(self, search_results: List[Dict[str, Any]]) -> 'DocumentStructure':
        """Convert search results to document structure format."""
        from .schemas import DocumentStructure, DocumentSection

        if not search_results:
            return DocumentStructure(
                title="No documents found",
                url="",
                sections=[],
                tables=[],
                metadata={}
            )

        # Use the first (most relevant) search result as primary document
        primary_doc = search_results[0]

        # Extract chunks from all search results
        all_chunks = []
        for doc in search_results:
            # Convert document content to chunks
            chunks = self._extract_chunks_from_document(doc)
            all_chunks.extend(chunks)

        # Parse into hierarchical structure
        return self.parser.parse_document_structure(
            title=primary_doc.get('title', 'Unknown Document'),
            url=primary_doc.get('url', ''),
            chunks=all_chunks,
            metadata=primary_doc.get('metadata', {})
        )

    def _extract_chunks_from_document(self, document: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract chunks from a single document."""
        chunks = []

        # Add title as chunk
        if document.get('title'):
            chunks.append({
                'content': document['title'],
                'chunk_type': 'title',
                'position': 0,
                'confidence': 1.0,
                'metadata': {'field': 'title'}
            })

        # Add headings as chunks
        if document.get('headings'):
            chunks.append({
                'content': document['headings'],
                'chunk_type': 'headings',
                'position': 1,
                'confidence': 0.9,
                'metadata': {'field': 'headings'}
            })

        # Add body content as chunks
        if document.get('body'):
            # Split body into logical chunks
            body_chunks = self._split_text_into_chunks(document['body'])
            for i, chunk_content in enumerate(body_chunks):
                chunks.append({
                    'content': chunk_content,
                    'chunk_type': 'body',
                    'position': 2 + i,
                    'confidence': 0.8,
                    'metadata': {'field': 'body', 'chunk_index': i}
                })

        return chunks

    def _split_text_into_chunks(self, text: str, max_chunk_length: int = 1000) -> List[str]:
        """Split text into manageable chunks."""
        if len(text) <= max_chunk_length:
            return [text]

        chunks = []
        sentences = text.split('。')

        current_chunk = ""
        for sentence in sentences:
            if len(current_chunk + sentence) <= max_chunk_length:
                current_chunk += sentence + "。"
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = sentence + "。"

        if current_chunk:
            chunks.append(current_chunk.strip())

        return chunks

    def _update_metrics(self, metric_type: str, value: int) -> None:
        """Update performance metrics."""
        if metric_type == "generation_time":
            # Update average generation time
            current_avg = self.metrics["avg_generation_time_ms"]
            total_requests = self.metrics["total_requests"]
            self.metrics["avg_generation_time_ms"] = (current_avg * (total_requests - 1) + value) / total_requests

        elif metric_type == "validation_time":
            # Update average validation time
            current_avg = self.metrics["avg_validation_time_ms"]
            total_requests = self.metrics["total_requests"]
            self.metrics["avg_validation_time_ms"] = (current_avg * (total_requests - 1) + value) / total_requests

    async def get_service_stats(self) -> Dict[str, Any]:
        """Get service performance statistics."""
        return {
            "total_requests": self.metrics["total_requests"],
            "successful_requests": self.metrics["successful_requests"],
            "failed_requests": self.metrics["failed_requests"],
            "success_rate": (self.metrics["successful_requests"] / max(self.metrics["total_requests"], 1)) * 100,
            "avg_generation_time_ms": self.metrics["avg_generation_time_ms"],
            "avg_validation_time_ms": self.metrics["avg_validation_time_ms"],
            "avg_grounding_score": sum(self.metrics["grounding_scores"]) / max(len(self.metrics["grounding_scores"]), 1)
        }

    async def health_check(self) -> Dict[str, Any]:
        """Check overall service health."""
        try:
            # Check Gemini client health
            client_health = await self.client.health_check()

            # Overall service health
            is_healthy = client_health["status"] == "healthy"

            return {
                "status": "healthy" if is_healthy else "unhealthy",
                "components": {
                    "gemini_client": client_health,
                    "parser": {"status": "healthy"},
                    "validator": {"status": "healthy"}
                },
                "metrics": await self.get_service_stats()
            }

        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "components": {},
                "metrics": {}
            }



