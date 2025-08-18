"""Google Cloud Vertex AI client for embedding generation."""

import asyncio
import logging
import time
from typing import List, Dict, Any, Optional

import vertexai
from google.cloud import aiplatform
from vertexai.language_models import TextEmbeddingModel
from google.api_core import exceptions as gcp_exceptions

from .schemas import EmbeddingModel, EmbeddingVector, EmbeddingRequest, EmbeddingResult, EmbeddingStatus, EmbeddingConfig

logger = logging.getLogger(__name__)


class VertexAIEmbeddingClient:
    """Google Cloud Vertex AI client for generating text embeddings."""
    
    def __init__(self, config: Optional[EmbeddingConfig] = None):
        """Initialize Vertex AI embedding client."""
        self.config = config or EmbeddingConfig()
        
        # Initialize Vertex AI
        aiplatform.init(
            project=self.config.project_id,
            location=self.config.location
        )
        
        # Model cache
        self._models: Dict[EmbeddingModel, TextEmbeddingModel] = {}
        
        logger.info(f"Initialized Vertex AI embedding client for project {self.config.project_id}")
    
    async def generate_embeddings(self, request: EmbeddingRequest) -> EmbeddingResult:
        """Generate embeddings for text list."""
        start_time = time.time()
        
        try:
            logger.info(f"Generating embeddings for {len(request.texts)} texts using {request.model.value}")
            
            # Get model
            model = self._get_model(request.model)
            
            # Process in batches
            all_embeddings = []
            failed_texts = []
            
            for i in range(0, len(request.texts), request.batch_size):
                batch_texts = request.texts[i:i + request.batch_size]
                batch_citation_ids = request.citation_ids[i:i + request.batch_size] if request.citation_ids else None
                batch_chunk_ids = request.chunk_ids[i:i + request.batch_size] if request.chunk_ids else None
                
                try:
                    batch_embeddings = await self._process_batch(
                        model, batch_texts, request.model, 
                        batch_citation_ids, batch_chunk_ids, request.normalize_embeddings
                    )
                    all_embeddings.extend(batch_embeddings)
                    
                except Exception as e:
                    logger.error(f"Batch processing failed: {e}")
                    failed_texts.extend(batch_texts)
            
            # Create result
            processing_time = int((time.time() - start_time) * 1000)
            
            result = EmbeddingResult(
                request_id=request.request_id,
                status=EmbeddingStatus.SUCCESS if all_embeddings else EmbeddingStatus.FAILED,
                embeddings=all_embeddings,
                processing_time_ms=processing_time,
                total_texts=len(request.texts),
                successful_embeddings=len(all_embeddings),
                failed_embeddings=len(failed_texts),
                model_used=request.model,
                embedding_dimension=self._get_model_dimension(request.model),
                failed_texts=failed_texts
            )
            
            logger.info(f"Generated {len(all_embeddings)} embeddings in {processing_time}ms")
            return result
            
        except Exception as e:
            processing_time = int((time.time() - start_time) * 1000)
            logger.error(f"Embedding generation failed: {e}")
            
            return EmbeddingResult(
                request_id=request.request_id,
                status=EmbeddingStatus.FAILED,
                processing_time_ms=processing_time,
                total_texts=len(request.texts),
                model_used=request.model,
                embedding_dimension=self._get_model_dimension(request.model),
                error_message=str(e)
            )
    
    async def generate_single_embedding(
        self, 
        text: str, 
        model: EmbeddingModel = EmbeddingModel.VERTEX_AI_MULTILINGUAL,
        normalize: bool = True
    ) -> Optional[EmbeddingVector]:
        """Generate embedding for single text."""
        request = EmbeddingRequest(
            texts=[text],
            model=model,
            normalize_embeddings=normalize
        )
        
        result = await self.generate_embeddings(request)
        
        if result.is_success() and result.embeddings:
            return result.embeddings[0]
        
        return None
    
    def _get_model(self, model_type: EmbeddingModel) -> TextEmbeddingModel:
        """Get or create model instance."""
        if model_type not in self._models:
            try:
                self._models[model_type] = TextEmbeddingModel.from_pretrained(model_type.value)
                logger.info(f"Loaded model: {model_type.value}")
            except Exception as e:
                logger.error(f"Failed to load model {model_type.value}: {e}")
                raise
        
        return self._models[model_type]
    
    async def _process_batch(
        self,
        model: TextEmbeddingModel,
        texts: List[str],
        model_type: EmbeddingModel,
        citation_ids: Optional[List[str]] = None,
        chunk_ids: Optional[List[str]] = None,
        normalize: bool = True
    ) -> List[EmbeddingVector]:
        """Process a batch of texts."""
        try:
            # Preprocess texts
            processed_texts = [self._preprocess_text(text) for text in texts]
            
            # Generate embeddings with retry
            embeddings_data = await self._generate_with_retry(model, processed_texts)
            
            # Create embedding vectors
            embedding_vectors = []
            dimension = self._get_model_dimension(model_type)
            
            for i, (text, embedding) in enumerate(zip(texts, embeddings_data)):
                # Get metadata
                citation_id = citation_ids[i] if citation_ids and i < len(citation_ids) else None
                chunk_id = chunk_ids[i] if chunk_ids and i < len(chunk_ids) else None
                
                # Create vector
                vector = EmbeddingVector(
                    text=text,
                    embedding=embedding,
                    dimension=dimension,
                    citation_id=citation_id,
                    chunk_id=chunk_id,
                    model=model_type
                )
                
                # Normalize if requested
                if normalize:
                    vector.embedding = vector.get_normalized_embedding()
                
                embedding_vectors.append(vector)
            
            return embedding_vectors
            
        except Exception as e:
            logger.error(f"Batch processing error: {e}")
            raise
    
    async def _generate_with_retry(self, model: TextEmbeddingModel, texts: List[str]) -> List[List[float]]:
        """Generate embeddings with retry logic."""
        last_exception = None
        
        for attempt in range(self.config.max_retries):
            try:
                # Use asyncio to make the call non-blocking
                loop = asyncio.get_event_loop()
                embeddings = await loop.run_in_executor(
                    None, 
                    lambda: model.get_embeddings(texts)
                )
                
                # Extract vectors
                return [emb.values for emb in embeddings]
                
            except gcp_exceptions.ResourceExhausted as e:
                logger.warning(f"Rate limit hit, attempt {attempt + 1}: {e}")
                last_exception = e
                
                if attempt < self.config.max_retries - 1:
                    delay = self.config.retry_delay_seconds * (2 ** attempt)
                    await asyncio.sleep(delay)
                
            except Exception as e:
                logger.error(f"Embedding generation error, attempt {attempt + 1}: {e}")
                last_exception = e
                
                if attempt < self.config.max_retries - 1:
                    await asyncio.sleep(self.config.retry_delay_seconds)
        
        raise last_exception or Exception("Max retries exceeded")
    
    def _preprocess_text(self, text: str) -> str:
        """Preprocess text for embedding generation."""
        # Truncate if too long
        if len(text) > self.config.max_text_length:
            text = text[:self.config.max_text_length]
            logger.debug(f"Truncated text to {self.config.max_text_length} characters")
        
        # Clean up text
        text = text.strip()
        
        # Replace multiple whitespace with single space
        import re
        text = re.sub(r'\s+', ' ', text)
        
        return text
    
    def _get_model_dimension(self, model_type: EmbeddingModel) -> int:
        """Get embedding dimension for model type."""
        # Standard dimensions for Vertex AI models
        model_dimensions = {
            EmbeddingModel.VERTEX_AI_MULTILINGUAL: 768,
            EmbeddingModel.VERTEX_AI_ENGLISH: 768,
            EmbeddingModel.VERTEX_AI_CHINESE: 768
        }
        
        return model_dimensions.get(model_type, 768)
    
    async def health_check(self) -> Dict[str, Any]:
        """Check Vertex AI service health."""
        try:
            start_time = time.time()
            
            # Test with a simple embedding
            test_text = "Health check test"
            test_embedding = await self.generate_single_embedding(test_text)
            
            latency_ms = int((time.time() - start_time) * 1000)
            
            return {
                "status": "healthy" if test_embedding else "degraded",
                "project_id": self.config.project_id,
                "location": self.config.location,
                "latency_ms": latency_ms,
                "test_embedding_dimension": len(test_embedding.embedding) if test_embedding else 0,
                "available_models": list(EmbeddingModel),
                "timestamp": time.time()
            }
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "project_id": self.config.project_id,
                "error": str(e),
                "timestamp": time.time()
            }
    
    def get_model_info(self, model_type: EmbeddingModel) -> Dict[str, Any]:
        """Get information about a specific model."""
        return {
            "model_name": model_type.value,
            "dimension": self._get_model_dimension(model_type),
            "max_text_length": self.config.max_text_length,
            "supports_chinese": "multilingual" in model_type.value.lower() or "chinese" in model_type.value.lower(),
            "supports_batch": True
        }


class VertexAIEmbeddingClientMock:
    """Mock Vertex AI embedding client for testing."""
    
    def __init__(self, config: Optional[EmbeddingConfig] = None):
        """Initialize mock client."""
        self.config = config or EmbeddingConfig()
        self.embedding_count = 0
    
    async def generate_embeddings(self, request: EmbeddingRequest) -> EmbeddingResult:
        """Mock embedding generation."""
        self.embedding_count += len(request.texts)
        
        # Simulate processing time
        await asyncio.sleep(0.1)
        
        # Generate mock embeddings
        embeddings = []
        dimension = self._get_model_dimension(request.model)
        
        for i, text in enumerate(request.texts):
            # Create deterministic mock embedding based on text hash
            import hashlib
            text_hash = hashlib.md5(text.encode()).hexdigest()
            
            # Convert hash to float values
            mock_embedding = []
            for j in range(dimension):
                hash_val = int(text_hash[j % len(text_hash)], 16)
                mock_embedding.append((hash_val - 7.5) / 7.5)  # Normalize to [-1, 1]
            
            # Get metadata
            citation_id = request.citation_ids[i] if request.citation_ids and i < len(request.citation_ids) else None
            chunk_id = request.chunk_ids[i] if request.chunk_ids and i < len(request.chunk_ids) else None
            
            vector = EmbeddingVector(
                text=text,
                embedding=mock_embedding,
                dimension=dimension,
                citation_id=citation_id,
                chunk_id=chunk_id,
                model=request.model
            )
            
            if request.normalize_embeddings:
                vector.embedding = vector.get_normalized_embedding()
            
            embeddings.append(vector)
        
        return EmbeddingResult(
            request_id=request.request_id,
            status=EmbeddingStatus.SUCCESS,
            embeddings=embeddings,
            processing_time_ms=100,
            total_texts=len(request.texts),
            successful_embeddings=len(embeddings),
            failed_embeddings=0,
            model_used=request.model,
            embedding_dimension=dimension
        )
    
    async def generate_single_embedding(
        self, 
        text: str, 
        model: EmbeddingModel = EmbeddingModel.VERTEX_AI_MULTILINGUAL,
        normalize: bool = True
    ) -> Optional[EmbeddingVector]:
        """Mock single embedding generation."""
        request = EmbeddingRequest(texts=[text], model=model, normalize_embeddings=normalize)
        result = await self.generate_embeddings(request)
        
        return result.embeddings[0] if result.embeddings else None
    
    async def health_check(self) -> Dict[str, Any]:
        """Mock health check."""
        return {
            "status": "healthy",
            "project_id": "mock-project",
            "location": "mock-location",
            "latency_ms": 50,
            "test_embedding_dimension": 768,
            "embedding_count": self.embedding_count,
            "timestamp": time.time()
        }
    
    def get_model_info(self, model_type: EmbeddingModel) -> Dict[str, Any]:
        """Mock model info."""
        return {
            "model_name": model_type.value,
            "dimension": self._get_model_dimension(model_type),
            "max_text_length": 8192,
            "supports_chinese": True,
            "supports_batch": True
        }
    
    def _get_model_dimension(self, model_type: EmbeddingModel) -> int:
        """Get mock embedding dimension."""
        return 768  # Standard dimension for all mock models
