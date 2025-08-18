"""Pydantic models for OCR service input/output."""

from datetime import date, datetime
from enum import Enum
from typing import Dict, List, Optional, Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, validator


class OcrStatus(str, Enum):
    """Status of OCR processing operation."""
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"  # Some pages failed but others succeeded


class DocumentFormat(str, Enum):
    """Supported document formats for OCR."""
    PDF = "pdf"
    HTML = "html"
    XML = "xml"
    JSON = "json"
    TEXT = "text"
    IMAGE = "image"


class OcrJob(BaseModel):
    """Input job for OCR processing."""
    
    job_id: UUID = Field(default_factory=uuid4)
    gcs_uri: str = Field(..., description="GCS URI of document snapshot")
    province: str = Field(..., description="Province code")
    doc_class: str = Field(..., description="Document class")
    source_url: str = Field(..., description="Original source URL")
    checksum: str = Field(..., description="SHA256 checksum")
    title: Optional[str] = Field(None, description="Document title")
    source_domain: Optional[str] = Field(None, description="Source domain")
    trace_id: Optional[str] = Field(None, description="Trace ID for logging")
    
    @validator("checksum")
    def validate_checksum_format(cls, v):
        """Validate SHA256 checksum format."""
        if len(v) != 64 or not all(c in "0123456789abcdef" for c in v.lower()):
            raise ValueError("Invalid SHA256 checksum format")
        return v.lower()
    
    class Config:
        use_enum_values = True


class TableData(BaseModel):
    """Extracted table data."""
    
    markdown: str = Field(..., description="Table in markdown format")
    caption: Optional[str] = Field(None, description="Table caption")
    row_count: int = Field(default=0, description="Number of rows")
    col_count: int = Field(default=0, description="Number of columns")
    confidence: Optional[float] = Field(None, description="Extraction confidence")


class NormalizedContent(BaseModel):
    """Normalized document content."""
    
    paragraphs: List[str] = Field(default_factory=list, description="Normalized paragraphs")
    tables: List[TableData] = Field(default_factory=list, description="Extracted tables")
    effective_date: Optional[date] = Field(None, description="Document effective date")
    language: Optional[str] = Field(None, description="Detected language")
    page_count: int = Field(default=0, description="Number of pages processed")
    
    class Config:
        json_encoders = {
            date: lambda v: v.isoformat()
        }


class ChunkData(BaseModel):
    """Text chunk for citation."""
    
    chunk_id: str = Field(..., description="Unique chunk identifier")
    content: str = Field(..., description="Chunk content")
    start_char: int = Field(default=0, description="Start character position")
    end_char: int = Field(default=0, description="End character position")
    token_count: int = Field(default=0, description="Estimated token count")
    clause_type: Optional[str] = Field(None, description="Type of clause")


class CitationRow(BaseModel):
    """Citation row for database insertion."""
    
    citation_id: UUID = Field(default_factory=uuid4)
    province: str = Field(..., description="Province code")
    doc_class: str = Field(..., description="Document class")
    asset: Optional[str] = Field(None, description="Asset type")
    title: str = Field(..., description="Document title")
    url: str = Field(..., description="Source URL")
    effective_date: Optional[date] = Field(None, description="Effective date")
    checksum: str = Field(..., description="SHA256 checksum")
    content: str = Field(..., description="Normalized content")
    chunk_ids: List[str] = Field(default_factory=list, description="Associated chunk IDs")
    
    class Config:
        use_enum_values = True
        json_encoders = {
            UUID: str,
            date: lambda v: v.isoformat()
        }


class OcrResult(BaseModel):
    """Result of OCR processing operation."""
    
    job_id: UUID
    status: OcrStatus
    citation_id: Optional[UUID] = None
    normalized_content: Optional[NormalizedContent] = None
    chunks: List[ChunkData] = Field(default_factory=list)
    
    # Processing metadata
    processing_time_ms: Optional[int] = None
    pages_processed: int = Field(default=0)
    tables_extracted: int = Field(default=0)
    effective_date_found: bool = Field(default=False)
    
    # Storage paths
    parsed_gcs_path: Optional[str] = None
    normalized_gcs_path: Optional[str] = None
    
    # Error information
    error_message: Optional[str] = None
    error_details: Optional[Dict[str, Any]] = None
    
    def is_success(self) -> bool:
        """Check if OCR processing was successful."""
        return self.status == OcrStatus.SUCCESS and self.citation_id is not None
    
    def get_success_rate(self) -> float:
        """Calculate processing success rate."""
        if self.pages_processed == 0:
            return 0.0
        
        if self.status == OcrStatus.SUCCESS:
            return 1.0
        elif self.status == OcrStatus.PARTIAL:
            # Estimate based on available data
            return 0.7  # Partial success
        else:
            return 0.0
    
    class Config:
        use_enum_values = True
        json_encoders = {
            UUID: str
        }


class OcrMetrics(BaseModel):
    """Metrics for OCR service performance."""
    
    total_jobs: int = Field(default=0)
    successful_jobs: int = Field(default=0)
    failed_jobs: int = Field(default=0)
    partial_jobs: int = Field(default=0)
    
    total_pages_processed: int = Field(default=0)
    total_tables_extracted: int = Field(default=0)
    effective_dates_found: int = Field(default=0)
    
    avg_processing_time_ms: float = Field(default=0.0)
    avg_pages_per_job: float = Field(default=0.0)
    
    # Distribution by format
    jobs_by_format: Dict[str, int] = Field(default_factory=dict)
    jobs_by_province: Dict[str, int] = Field(default_factory=dict)
    jobs_by_doc_class: Dict[str, int] = Field(default_factory=dict)
    
    last_updated: datetime = Field(default_factory=datetime.utcnow)
    
    def update_with_result(self, result: OcrResult) -> None:
        """Update metrics with OCR result."""
        self.total_jobs += 1
        
        if result.status == OcrStatus.SUCCESS:
            self.successful_jobs += 1
        elif result.status == OcrStatus.FAILED:
            self.failed_jobs += 1
        elif result.status == OcrStatus.PARTIAL:
            self.partial_jobs += 1
        
        if result.pages_processed > 0:
            self.total_pages_processed += result.pages_processed
        
        if result.tables_extracted > 0:
            self.total_tables_extracted += result.tables_extracted
        
        if result.effective_date_found:
            self.effective_dates_found += 1
        
        # Update averages
        if result.processing_time_ms and self.successful_jobs > 0:
            total_time = self.avg_processing_time_ms * (self.successful_jobs - 1)
            self.avg_processing_time_ms = (total_time + result.processing_time_ms) / self.successful_jobs
        
        if self.total_jobs > 0:
            self.avg_pages_per_job = self.total_pages_processed / self.total_jobs
        
        self.last_updated = datetime.utcnow()
    
    def get_success_rate(self) -> float:
        """Calculate overall success rate."""
        if self.total_jobs == 0:
            return 0.0
        return self.successful_jobs / self.total_jobs
    
    def get_effective_date_hit_rate(self) -> float:
        """Calculate effective date extraction hit rate."""
        if self.total_jobs == 0:
            return 0.0
        return self.effective_dates_found / self.total_jobs
    
    def get_tables_per_job(self) -> float:
        """Calculate average tables extracted per job."""
        if self.total_jobs == 0:
            return 0.0
        return self.total_tables_extracted / self.total_jobs
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class OcrConfig(BaseModel):
    """Configuration for OCR service."""
    
    # Google Document AI settings
    project_id: str = Field(..., env="PROJECT_ID")
    processor_id: str = Field(..., env="DOC_AI_PROCESSOR_ID")
    processor_location: str = Field(default="us", env="DOC_AI_LOCATION")
    
    # Processing settings
    max_pages_per_job: int = Field(default=100, env="OCR_MAX_PAGES")
    timeout_seconds: int = Field(default=300, env="OCR_TIMEOUT")  # 5 minutes
    max_retries: int = Field(default=3, env="OCR_MAX_RETRIES")
    
    # Chunking settings
    max_tokens_per_chunk: int = Field(default=800, env="CHUNK_MAX_TOKENS")
    chunk_overlap_tokens: int = Field(default=100, env="CHUNK_OVERLAP_TOKENS")
    
    # Storage settings
    parsed_bucket: str = Field(..., env="GCS_PARSED_BUCKET")
    normalized_bucket: str = Field(..., env="GCS_NORMALIZED_BUCKET")
    
    # Quality thresholds
    min_confidence_threshold: float = Field(default=0.7, env="OCR_MIN_CONFIDENCE")
    effective_date_hit_rate_target: float = Field(default=0.8, env="EFFECTIVE_DATE_TARGET")
    
    class Config:
        env_file = ".env"