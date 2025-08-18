"""Main embedding service that orchestrates generation and storage."""

import asyncio
import logging
import time
from typing import List, Dict, Any, Optional
from uuid import UUID

from .schemas import (
    EmbeddingRequest, EmbeddingResult, VectorStorageRequest, VectorStorageResult,
    EmbeddingVector, EmbeddingModel, EmbeddingMetrics, EmbeddingConfig
)
from .vertex_client import VertexAIEmbeddingClient, VertexAIEmbeddingClientMock
from .vector_storage import VectorStorageService, VectorStorageServiceMock
from services.ocr.schemas import ChunkData, CitationRow

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Main service for generating and storing embeddings."""
    
    def __init__(
        self,
        config: Optional[EmbeddingConfig] = None,
        vertex_client: Optional[VertexAIEmbeddingClient] = None,
        storage_service: Optional[VectorStorageService] = None,
        use_mock: bool = False
    ):
        """Initialize embedding service."""
        self.config = config or EmbeddingConfig()
        
        if use_mock:
            self.vertex_client = VertexAIEmbeddingClientMock(self.config)
            self.storage_service = VectorStorageServiceMock(self.config)
        else:
            self.vertex_client = vertex_client or VertexAIEmbeddingClient(self.config)
            self.storage_service = storage_service or VectorStorageService(self.config)
        
        self.metrics = EmbeddingMetrics()
        
        logger.info("Initialized embedding service")
    
    async def initialize(self) -> None:
        """Initialize service components."""
        try:
            await self.storage_service.initialize()
            logger.info("Embedding service initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize embedding service: {e}")
            raise
    
    async def process_citation_chunks(
        self,
        citation_row: CitationRow,
        chunks: List[ChunkData],
        model: EmbeddingModel = EmbeddingModel.VERTEX_AI_MULTILINGUAL
    ) -> Dict[str, Any]:
        """
        Process citation chunks to generate and store embeddings.
        
        Args:
            citation_row: Citation metadata
            chunks: Text chunks to embed
            model: Embedding model to use
            
        Returns:
            Processing result with embedding and storage information
        """
        start_time = time.time()
        
        try:
            logger.info(f"Processing {len(chunks)} chunks for citation {citation_row.citation_id}")
            
            # Step 1: Generate embeddings
            embedding_result = await self._generate_chunk_embeddings(
                chunks, citation_row, model
            )
            
            if not embedding_result.is_success():
                return {
                    "success": False,
                    "error": "Embedding generation failed",
                    "embedding_result": embedding_result
                }
            
            # Step 2: Store embeddings
            storage_result = await self._store_chunk_embeddings(
                embedding_result.embeddings, citation_row
            )
            
            # Step 3: Update metrics
            self.metrics.update_with_result(embedding_result)
            self.metrics.update_with_storage_result(storage_result)
            
            processing_time = int((time.time() - start_time) * 1000)
            
            result = {
                "success": True,
                "processing_time_ms": processing_time,
                "citation_id": str(citation_row.citation_id),
                "chunks_processed": len(chunks),
                "embeddings_generated": len(embedding_result.embeddings),
                "embeddings_stored": storage_result.stored_count,
                "embedding_result": embedding_result,
                "storage_result": storage_result
            }
            
            logger.info(f"Successfully processed citation {citation_row.citation_id} in {processing_time}ms")
            return result
            
        except Exception as e:
            processing_time = int((time.time() - start_time) * 1000)
            logger.error(f"Error processing citation chunks: {e}")
            
            return {
                "success": False,
                "error": str(e),
                "processing_time_ms": processing_time,
                "citation_id": str(citation_row.citation_id) if citation_row else None
            }
    
    async def generate_embeddings(self, request: EmbeddingRequest) -> EmbeddingResult:
        """Generate embeddings for text list."""
        try:
            result = await self.vertex_client.generate_embeddings(request)
            self.metrics.update_with_result(result)
            return result
        except Exception as e:
            logger.error(f"Embedding generation failed: {e}")
            raise
    
    async def store_embeddings(self, request: VectorStorageRequest) -> VectorStorageResult:
        """Store embeddings in vector database."""
        try:
            result = await self.storage_service.store_embeddings(request)
            self.metrics.update_with_storage_result(result)
            return result
        except Exception as e:
            logger.error(f"Embedding storage failed: {e}")
            raise
    
    async def search_similar_citations(
        self,
        query_text: str,
        province: Optional[str] = None,
        limit: int = 10,
        similarity_threshold: float = 0.7,
        model: EmbeddingModel = EmbeddingModel.VERTEX_AI_MULTILINGUAL
    ) -> List[Dict[str, Any]]:
        """
        Search for similar citations using semantic similarity.
        
        Args:
            query_text: Query text to search for
            province: Optional province filter
            limit: Maximum number of results
            similarity_threshold: Minimum similarity score
            model: Embedding model to use for query
            
        Returns:
            List of similar citations with similarity scores
        """
        try:
            logger.info(f"Searching for similar citations: '{query_text[:50]}...'")
            
            # Generate query embedding
            query_embedding = await self.vertex_client.generate_single_embedding(
                query_text, model
            )
            
            if not query_embedding:
                logger.error("Failed to generate query embedding")
                return []
            
            # Search similar vectors
            results = await self.storage_service.search_similar_vectors(
                query_embedding.embedding,
                limit=limit,
                similarity_threshold=similarity_threshold,
                province_filter=province
            )
            
            logger.info(f"Found {len(results)} similar citations")
            return results
            
        except Exception as e:
            logger.error(f"Similarity search failed: {e}")
            return []
    
    async def get_citation_embeddings(self, citation_id: UUID) -> List[Dict[str, Any]]:
        """Get all embeddings for a specific citation."""
        try:
            # This would require a method to get embeddings by citation_id
            # For now, return empty list
            logger.info(f"Getting embeddings for citation {citation_id}")
            return []
        except Exception as e:
            logger.error(f"Failed to get citation embeddings: {e}")
            return []
    
    async def delete_citation_embeddings(self, citation_id: UUID) -> bool:
        """Delete all embeddings for a specific citation."""
        try:
            deleted_count = await self.storage_service.delete_embeddings(
                citation_ids=[citation_id]
            )
            logger.info(f"Deleted {deleted_count} embeddings for citation {citation_id}")
            return deleted_count > 0
        except Exception as e:
            logger.error(f"Failed to delete citation embeddings: {e}")
            return False
    
    async def batch_process_citations(
        self,
        citations_and_chunks: List[tuple[CitationRow, List[ChunkData]]],
        model: EmbeddingModel = EmbeddingModel.VERTEX_AI_MULTILINGUAL,
        max_concurrent: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Process multiple citations in parallel.
        
        Args:
            citations_and_chunks: List of (citation, chunks) tuples
            model: Embedding model to use
            max_concurrent: Maximum concurrent processing
            
        Returns:
            List of processing results
        """
        logger.info(f"Batch processing {len(citations_and_chunks)} citations")
        
        # Create semaphore for concurrency control
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def process_single(citation_chunks):
            async with semaphore:
                citation, chunks = citation_chunks
                return await self.process_citation_chunks(citation, chunks, model)
        
        # Process all citations
        tasks = [process_single(cc) for cc in citations_and_chunks]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Handle exceptions
        final_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                citation, _ = citations_and_chunks[i]
                final_results.append({
                    "success": False,
                    "error": str(result),
                    "citation_id": str(citation.citation_id)
                })
            else:
                final_results.append(result)
        
        successful = sum(1 for r in final_results if r.get("success", False))
        logger.info(f"Batch processing complete: {successful}/{len(final_results)} successful")
        
        return final_results
    
    async def health_check(self) -> Dict[str, Any]:
        """Check service health."""
        try:
            # Check Vertex AI client
            vertex_health = await self.vertex_client.health_check()
            
            # Check storage service
            storage_health = await self.storage_service.health_check()
            
            # Overall health
            overall_status = "healthy"
            if vertex_health.get("status") != "healthy" or storage_health.get("status") != "healthy":
                overall_status = "degraded"
            
            return {
                "status": overall_status,
                "vertex_ai": vertex_health,
                "vector_storage": storage_health,
                "metrics": {
                    "total_requests": self.metrics.total_requests,
                    "success_rate": self.metrics.get_success_rate(),
                    "embeddings_generated": self.metrics.total_embeddings_generated,
                    "embeddings_stored": self.metrics.total_embeddings_stored
                },
                "timestamp": time.time()
            }
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": time.time()
            }
    
    async def get_metrics(self) -> Dict[str, Any]:
        """Get service metrics."""
        metrics_dict = self.metrics.dict()
        
        # Add computed metrics
        metrics_dict["success_rate"] = self.metrics.get_success_rate()
        metrics_dict["embeddings_per_second"] = self.metrics.get_embeddings_per_second()
        
        # Add storage stats
        try:
            storage_stats = await self.storage_service.get_storage_stats()
            metrics_dict["storage_stats"] = storage_stats
        except Exception as e:
            logger.error(f"Failed to get storage stats: {e}")
            metrics_dict["storage_stats"] = {"error": str(e)}
        
        return metrics_dict
    
    async def close(self) -> None:
        """Close service and cleanup resources."""
        try:
            await self.storage_service.close()
            logger.info("Embedding service closed")
        except Exception as e:
            logger.error(f"Error closing embedding service: {e}")
    
    async def _generate_chunk_embeddings(
        self,
        chunks: List[ChunkData],
        citation_row: CitationRow,
        model: EmbeddingModel
    ) -> EmbeddingResult:
        """Generate embeddings for chunks."""
        # Prepare texts and metadata
        texts = [chunk.content for chunk in chunks]
        chunk_ids = [chunk.chunk_id for chunk in chunks]
        citation_ids = [citation_row.citation_id] * len(chunks)
        
        # Create embedding request
        request = EmbeddingRequest(
            texts=texts,
            model=model,
            citation_ids=citation_ids,
            chunk_ids=chunk_ids,
            province=citation_row.province,
            doc_class=citation_row.doc_class,
            batch_size=self.config.default_batch_size,
            normalize_embeddings=self.config.normalize_embeddings
        )
        
        # Generate embeddings
        return await self.vertex_client.generate_embeddings(request)
    
    async def _store_chunk_embeddings(
        self,
        embeddings: List[EmbeddingVector],
        citation_row: CitationRow
    ) -> VectorStorageResult:
        """Store chunk embeddings in vector database."""
        # Create storage request
        request = VectorStorageRequest(
            embeddings=embeddings,
            table_name=self.config.vector_table_name,
            upsert_mode=True,
            create_index=self.config.enable_vector_index,
            province=citation_row.province
        )
        
        # Store embeddings
        return await self.storage_service.store_embeddings(request)


def create_embedding_service(
    config: Optional[EmbeddingConfig] = None,
    use_mock: bool = False
) -> EmbeddingService:
    """Factory function to create embedding service."""
    return EmbeddingService(config=config, use_mock=use_mock)