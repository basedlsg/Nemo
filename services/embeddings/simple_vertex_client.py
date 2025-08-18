"""Simple Vertex AI client for embedding generation without complex imports."""

import asyncio
import logging
import time
import hashlib
from typing import List, Optional

logger = logging.getLogger(__name__)


class VertexEmbeddingClient:
    """Simple embedding client that generates mock embeddings for development."""
    
    def __init__(self):
        """Initialize simple embedding client."""
        self.embedding_count = 0
        logger.info("Initialized simple embedding client (mock mode)")
    
    async def embed_text(self, text: str) -> List[float]:
        """Generate a mock embedding for text."""
        try:
            # Simulate processing time
            await asyncio.sleep(0.01)
            
            # Generate deterministic mock embedding based on text hash
            text_hash = hashlib.md5(text.encode()).hexdigest()
            
            # Create 768-dimensional embedding
            embedding = []
            for i in range(768):
                # Use hash characters to generate float values
                hash_char = text_hash[i % len(text_hash)]
                hash_val = int(hash_char, 16)
                # Normalize to [-1, 1] range
                normalized_val = (hash_val - 7.5) / 7.5
                embedding.append(normalized_val)
            
            self.embedding_count += 1
            
            # Normalize the embedding vector
            import math
            magnitude = math.sqrt(sum(x * x for x in embedding))
            if magnitude > 0:
                embedding = [x / magnitude for x in embedding]
            
            logger.debug(f"Generated embedding for text (length: {len(text)})")
            return embedding
            
        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}")
            # Return zero vector as fallback
            return [0.0] * 768
    
    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts."""
        embeddings = []
        for text in texts:
            embedding = await self.embed_text(text)
            embeddings.append(embedding)
        return embeddings
    
    async def health_check(self) -> dict:
        """Check client health."""
        return {
            "status": "healthy",
            "mode": "mock",
            "embeddings_generated": self.embedding_count,
            "dimension": 768,
            "timestamp": time.time()
        }