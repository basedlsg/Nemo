"""Schemas for embedding generation service."""

from enum import Enum
from typing import List, Dict, Any, Optional
from uuid import UUID, uuid4
from datetime import datetime

from pydantic import BaseModel, Field, validator


class EmbeddingModel(str, Enum):
    """Supported embedding models."""
    VERTEX_AI_MULTILINGUAL = "textembedding-gecko-multilingual@001"
    VERTEX_AI_ENGLISH = "textembedding-gecko@003"
    VERTEX_AI_CHINESE = "textembedding-gecko-multilingual@latest"


class EmbeddingStatus(str, Enum):
    """Status of embedding generation."""
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"


class EmbeddingRequest(BaseModel):
    """Request for embedding generation."""
    
    request_id: UUID = Field(default_factory=uuid4)
    texts: List[str] = Field(..., description="Texts to embed")
    model: EmbeddingModel = Field(default=EmbeddingModel.VERTEX_AI_MULTILINGUAL)
    
    # Metadata
    citation_ids: Optional[List[UUID]] = Field(None, description="Associated citation IDs")
    chunk_ids: Optional[List[str]] = Field(None, description="Associated chunk IDs")
    province: Optional[str] = Field(None, description="Province for geo-sharding")
    doc_class: Optional[str] = Field(None, description="Document class")
    
    # Processing options
    batch_size: int = Field(default=100, description="Batch size for processing")
    normalize_embeddings: bool = Field(default=True, description="L2 normalize embeddings")
    
    @validator("texts")
    def validate_texts_not_empty(cls, v):
        """Validate texts are not empty."""
        if not v:
            raise ValueError("Texts list cannot be empty")
        if any(not text.strip() for text in v):
            raise ValueError("Individual texts cannot be empty")
        return v
    
    @validator("batch_size")
    def validate_batch_size(cls, v):
        """Validate batch size is reasonable."""
        if v < 1 or v > 1000:
            raise ValueError("Batch size must be between 1 and 1000")
        return v
    
    class Config:
        use_enum_values = True


class EmbeddingVector(BaseModel):
    """Individual embedding vector."""
    
    text: str = Field(..., description="Original text")
    embedding: List[float] = Field(..., description="Embedding vector")
    dimension: int = Field(..., description="Vector dimension")
    
    # Metadata
    citation_id: Optional[UUID] = Field(None, description="Associated citation ID")
    chunk_id: Optional[str] = Field(None, description="Associated chunk ID")
    model: EmbeddingModel = Field(..., description="Model used for embedding")
    
    # Quality metrics
    norm: Optional[float] = Field(None, description="L2 norm of vector")
    confidence: Optional[float] = Field(None, description="Model confidence")
    
    @validator("embedding")
    def validate_embedding_dimension(cls, v, values):
        """Validate embedding dimension consistency."""
        if "dimension" in values and len(v) != values["dimension"]:
            raise ValueError(f"Embedding length {len(v)} does not match dimension {values['dimension']}")
        return v
    
    def get_normalized_embedding(self) -> List[float]:
        """Get L2 normalized embedding."""
        import math
        
        if self.norm is None:
            self.norm = math.sqrt(sum(x * x for x in self.embedding))
        
        if self.norm == 0:
            return self.embedding
        
        return [x / self.norm for x in self.embedding]
    
    class Config:
        use_enum_values = True
        json_encoders = {
            UUID: str
        }


class EmbeddingResult(BaseModel):
    """Result of embedding generation."""
    
    request_id: UUID
    status: EmbeddingStatus
    embeddings: List[EmbeddingVector] = Field(default_factory=list)
    
    # Processing metadata
    processing_time_ms: int = Field(default=0)
    total_texts: int = Field(default=0)
    successful_embeddings: int = Field(default=0)
    failed_embeddings: int = Field(default=0)
    
    # Model information
    model_used: EmbeddingModel
    embedding_dimension: int = Field(default=768)
    
    # Error information
    error_message: Optional[str] = None
    failed_texts: List[str] = Field(default_factory=list)
    
    def is_success(self) -> bool:
        """Check if embedding generation was successful."""
        return self.status == EmbeddingStatus.SUCCESS and len(self.embeddings) > 0
    
    def get_success_rate(self) -> float:
        """Calculate success rate."""
        if self.total_texts == 0:
            return 0.0
        return self.successful_embeddings / self.total_texts
    
    def get_embeddings_by_citation(self, citation_id: UUID) -> List[EmbeddingVector]:
        """Get embeddings for specific citation."""
        return [emb for emb in self.embeddings if emb.citation_id == citation_id]
    
    def get_embeddings_matrix(self) -> List[List[float]]:
        """Get embeddings as matrix for batch operations."""
        return [emb.embedding for emb in self.embeddings]
    
    class Config:
        use_enum_values = True
        json_encoders = {
            UUID: str
        }


class VectorStorageRequest(BaseModel):
    """Request for vector storage in AlloyDB."""
    
    storage_id: UUID = Field(default_factory=uuid4)
    embeddings: List[EmbeddingVector] = Field(..., description="Embeddings to store")
    
    # Storage options
    table_name: str = Field(default="citation_embeddings", description="Target table")
    upsert_mode: bool = Field(default=True, description="Use upsert instead of insert")
    create_index: bool = Field(default=False, description="Create vector index after insert")
    
    # Geo-sharding
    province: Optional[str] = Field(None, description="Province for geo-sharding")
    shard_key: Optional[str] = Field(None, description="Custom shard key")
    
    @validator("embeddings")
    def validate_embeddings_not_empty(cls, v):
        """Validate embeddings list is not empty."""
        if not v:
            raise ValueError("Embeddings list cannot be empty")
        return v
    
    class Config:
        use_enum_values = True


class VectorStorageResult(BaseModel):
    """Result of vector storage operation."""
    
    storage_id: UUID
    status: EmbeddingStatus
    
    # Storage metadata
    stored_count: int = Field(default=0)
    updated_count: int = Field(default=0)
    failed_count: int = Field(default=0)
    storage_time_ms: int = Field(default=0)
    
    # Database information
    table_name: str
    shard_info: Optional[Dict[str, Any]] = None
    index_created: bool = Field(default=False)
    
    # Error information
    error_message: Optional[str] = None
    failed_embeddings: List[str] = Field(default_factory=list)
    
    def is_success(self) -> bool:
        """Check if storage was successful."""
        return self.status == EmbeddingStatus.SUCCESS and self.stored_count > 0
    
    def get_total_processed(self) -> int:
        """Get total number of embeddings processed."""
        return self.stored_count + self.updated_count + self.failed_count
    
    class Config:
        use_enum_values = True
        json_encoders = {
            UUID: str
        }


class EmbeddingMetrics(BaseModel):
    """Metrics for embedding service performance."""
    
    # Request metrics
    total_requests: int = Field(default=0)
    successful_requests: int = Field(default=0)
    failed_requests: int = Field(default=0)
    
    # Text metrics
    total_texts_processed: int = Field(default=0)
    total_embeddings_generated: int = Field(default=0)
    total_embeddings_stored: int = Field(default=0)
    
    # Performance metrics
    avg_processing_time_ms: float = Field(default=0.0)
    avg_texts_per_request: float = Field(default=0.0)
    avg_embedding_dimension: float = Field(default=768.0)
    
    # Model usage
    model_usage: Dict[str, int] = Field(default_factory=dict)
    
    # Storage metrics
    storage_success_rate: float = Field(default=0.0)
    avg_storage_time_ms: float = Field(default=0.0)
    
    # Geo-sharding metrics
    province_distribution: Dict[str, int] = Field(default_factory=dict)
    
    last_updated: datetime = Field(default_factory=datetime.utcnow)
    
    def update_with_result(self, result: EmbeddingResult) -> None:
        """Update metrics with embedding result."""
        self.total_requests += 1
        
        if result.is_success():
            self.successful_requests += 1
        else:
            self.failed_requests += 1
        
        self.total_texts_processed += result.total_texts
        self.total_embeddings_generated += result.successful_embeddings
        
        # Update averages
        if self.successful_requests > 0:
            total_time = self.avg_processing_time_ms * (self.successful_requests - 1)
            self.avg_processing_time_ms = (total_time + result.processing_time_ms) / self.successful_requests
        
        if self.total_requests > 0:
            self.avg_texts_per_request = self.total_texts_processed / self.total_requests
        
        # Update model usage
        model_key = result.model_used.value
        self.model_usage[model_key] = self.model_usage.get(model_key, 0) + 1
        
        self.last_updated = datetime.utcnow()
    
    def update_with_storage_result(self, storage_result: VectorStorageResult) -> None:
        """Update metrics with storage result."""
        self.total_embeddings_stored += storage_result.stored_count
        
        # Update storage success rate
        total_storage_attempts = self.total_embeddings_stored + storage_result.failed_count
        if total_storage_attempts > 0:
            self.storage_success_rate = self.total_embeddings_stored / total_storage_attempts
        
        # Update storage time
        if storage_result.stored_count > 0:
            self.avg_storage_time_ms = (
                (self.avg_storage_time_ms + storage_result.storage_time_ms) / 2
            )
        
        self.last_updated = datetime.utcnow()
    
    def get_success_rate(self) -> float:
        """Calculate overall success rate."""
        if self.total_requests == 0:
            return 0.0
        return self.successful_requests / self.total_requests
    
    def get_embeddings_per_second(self) -> float:
        """Calculate embeddings generated per second."""
        if self.avg_processing_time_ms == 0:
            return 0.0
        return 1000.0 / (self.avg_processing_time_ms / self.avg_texts_per_request)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


import os

class EmbeddingConfig(BaseModel):
    """Configuration for embedding service."""
    
    # Google Cloud settings
    project_id: str = Field(default_factory=lambda: os.getenv("PROJECT_ID"))
    location: str = Field(default="us-central1", env="VERTEX_AI_LOCATION")
    
    # Model settings
    default_model: EmbeddingModel = Field(default=EmbeddingModel.VERTEX_AI_MULTILINGUAL)
    max_text_length: int = Field(default=8192, description="Max characters per text")
    embedding_dimension: int = Field(default=768, description="Expected embedding dimension")
    
    # Batch processing
    default_batch_size: int = Field(default=100, env="EMBEDDING_BATCH_SIZE")
    max_concurrent_requests: int = Field(default=10, env="EMBEDDING_MAX_CONCURRENT")
    request_timeout_seconds: int = Field(default=300, env="EMBEDDING_TIMEOUT")
    
    # Retry settings
    max_retries: int = Field(default=3, env="EMBEDDING_MAX_RETRIES")
    retry_delay_seconds: int = Field(default=1, env="EMBEDDING_RETRY_DELAY")
    
    # Storage settings
    alloydb_connection_string: str = Field(default_factory=lambda: os.getenv("ALLOYDB_CONNECTION_STRING"))
    vector_table_name: str = Field(default="citation_embeddings", env="VECTOR_TABLE_NAME")
    enable_vector_index: bool = Field(default=True, env="ENABLE_VECTOR_INDEX")
    
    # Performance settings
    normalize_embeddings: bool = Field(default=True, env="NORMALIZE_EMBEDDINGS")
    cache_embeddings: bool = Field(default=True, env="CACHE_EMBEDDINGS")
    
    class Config:
        env_file = ".env"
