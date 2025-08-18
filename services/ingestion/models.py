"""Data models for document ingestion service."""

from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any, Union
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, validator

from services.core.models import Province, DocumentClass, AssetType


class FetchStatus(str, Enum):
    """Status of document fetch operation."""
    PENDING = "pending"
    FETCHING = "fetching"
    SUCCESS = "success"
    FAILED = "failed"
    ROBOTS_BLOCKED = "robots_blocked"
    RATE_LIMITED = "rate_limited"
    TIMEOUT = "timeout"
    NOT_FOUND = "not_found"


class StorageStatus(str, Enum):
    """Status of document storage operation."""
    PENDING = "pending"
    STORING = "storing"
    STORED = "stored"
    FAILED = "failed"
    DUPLICATE = "duplicate"


class DocumentFormat(str, Enum):
    """Document format types."""
    HTML = "html"
    PDF = "pdf"
    XML = "xml"
    JSON = "json"
    TEXT = "text"
    UNKNOWN = "unknown"


class DocumentSnapshot(BaseModel):
    """Immutable document snapshot with metadata."""
    
    snapshot_id: UUID = Field(default_factory=uuid4)
    original_url: str = Field(..., description="Original document URL")
    canonical_url: Optional[str] = Field(None, description="Canonical URL after redirects")
    domain: str = Field(..., description="Source domain")
    
    # Content
    content: bytes = Field(..., description="Raw document content")
    content_type: str = Field(..., description="MIME content type")
    content_length: int = Field(..., description="Content length in bytes")
    content_encoding: Optional[str] = Field(None, description="Content encoding")
    
    # Checksums and integrity
    sha256_checksum: str = Field(..., description="SHA256 checksum of content")
    md5_checksum: Optional[str] = Field(None, description="MD5 checksum for compatibility")
    
    # Metadata
    title: Optional[str] = Field(None, description="Document title")
    language: Optional[str] = Field(None, description="Document language")
    effective_date: Optional[datetime] = Field(None, description="Document effective date")
    last_modified: Optional[datetime] = Field(None, description="Last modified date from headers")
    
    # HTTP metadata
    http_status_code: int = Field(..., description="HTTP response status code")
    http_headers: Dict[str, str] = Field(default_factory=dict, description="HTTP response headers")
    redirect_chain: List[str] = Field(default_factory=list, description="Redirect chain URLs")
    
    # Storage metadata
    storage_path: str = Field(..., description="Storage path in object storage")
    storage_bucket: str = Field(..., description="Storage bucket name")
    stored_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Classification
    province: Optional[Province] = None
    doc_class: Optional[DocumentClass] = None
    asset: Optional[AssetType] = None
    
    @validator("content")
    def validate_content_not_empty(cls, v):
        """Validate content is not empty."""
        if not v:
            raise ValueError("Content cannot be empty")
        return v
    
    @validator("sha256_checksum")
    def validate_sha256_format(cls, v):
        """Validate SHA256 checksum format."""
        if len(v) != 64 or not all(c in "0123456789abcdef" for c in v.lower()):
            raise ValueError("Invalid SHA256 checksum format")
        return v.lower()
    
    @validator("content_length")
    def validate_content_length_matches(cls, v, values):
        """Validate content length matches actual content."""
        if "content" in values and len(values["content"]) != v:
            raise ValueError("Content length does not match actual content size")
        return v
    
    def get_document_format(self) -> DocumentFormat:
        """Determine document format from content type."""
        content_type_lower = self.content_type.lower()
        
        if "text/html" in content_type_lower:
            return DocumentFormat.HTML
        elif "application/pdf" in content_type_lower:
            return DocumentFormat.PDF
        elif "application/xml" in content_type_lower or "text/xml" in content_type_lower:
            return DocumentFormat.XML
        elif "application/json" in content_type_lower:
            return DocumentFormat.JSON
        elif "text/plain" in content_type_lower:
            return DocumentFormat.TEXT
        else:
            return DocumentFormat.UNKNOWN
    
    def is_chinese_content(self) -> bool:
        """Check if document likely contains Chinese content."""
        try:
            # Decode content and check for Chinese characters
            if self.get_document_format() in [DocumentFormat.HTML, DocumentFormat.TEXT, DocumentFormat.XML]:
                text_content = self.content.decode('utf-8', errors='ignore')
                chinese_chars = sum(1 for char in text_content if '\u4e00' <= char <= '\u9fff')
                total_chars = len([c for c in text_content if c.isalnum()])
                
                if total_chars > 0:
                    return (chinese_chars / total_chars) >= 0.1  # At least 10% Chinese
            
            return False
        except Exception:
            return False
    
    def get_size_mb(self) -> float:
        """Get content size in megabytes."""
        return self.content_length / (1024 * 1024)
    
    def get_storage_key(self) -> str:
        """Generate storage key for object storage."""
        # Format: domain/year/month/checksum[:8]/filename
        stored_date = self.stored_at
        domain_safe = self.domain.replace(".", "_")
        checksum_prefix = self.sha256_checksum[:8]
        
        # Extract filename from URL
        try:
            from urllib.parse import urlparse
            parsed = urlparse(self.original_url)
            filename = parsed.path.split('/')[-1] or "document"
            
            # Sanitize filename
            import re
            filename = re.sub(r'[^\w\-_\.]', '_', filename)
            if not filename.endswith(('.html', '.pdf', '.xml', '.json', '.txt')):
                format_ext = {
                    DocumentFormat.HTML: '.html',
                    DocumentFormat.PDF: '.pdf',
                    DocumentFormat.XML: '.xml',
                    DocumentFormat.JSON: '.json',
                    DocumentFormat.TEXT: '.txt'
                }.get(self.get_document_format(), '.bin')
                filename += format_ext
        except Exception:
            filename = f"document_{checksum_prefix}.bin"
        
        return f"{domain_safe}/{stored_date.year:04d}/{stored_date.month:02d}/{checksum_prefix}/{filename}"
    
    def to_metadata_dict(self) -> Dict[str, Any]:
        """Convert to metadata dictionary for storage."""
        return {
            "snapshot_id": str(self.snapshot_id),
            "original_url": self.original_url,
            "canonical_url": self.canonical_url,
            "domain": self.domain,
            "content_type": self.content_type,
            "content_length": self.content_length,
            "content_encoding": self.content_encoding,
            "sha256_checksum": self.sha256_checksum,
            "md5_checksum": self.md5_checksum,
            "title": self.title,
            "language": self.language,
            "effective_date": self.effective_date.isoformat() if self.effective_date else None,
            "last_modified": self.last_modified.isoformat() if self.last_modified else None,
            "http_status_code": self.http_status_code,
            "redirect_chain": self.redirect_chain,
            "storage_path": self.storage_path,
            "storage_bucket": self.storage_bucket,
            "stored_at": self.stored_at.isoformat(),
            "province": self.province.value if self.province else None,
            "doc_class": self.doc_class.value if self.doc_class else None,
            "asset": self.asset.value if self.asset else None,
            "document_format": self.get_document_format().value,
            "is_chinese_content": self.is_chinese_content(),
            "size_mb": self.get_size_mb()
        }
    
    class Config:
        use_enum_values = True
        json_encoders = {
            UUID: str,
            datetime: lambda v: v.isoformat(),
            bytes: lambda v: f"<{len(v)} bytes>"  # Don't serialize actual content
        }


class FetchResult(BaseModel):
    """Result of document fetch operation."""
    
    url: str
    status: FetchStatus
    snapshot: Optional[DocumentSnapshot] = None
    error_message: Optional[str] = None
    fetch_time_ms: Optional[int] = None
    redirect_count: int = Field(default=0)
    robots_txt_allowed: Optional[bool] = None
    user_agent_used: Optional[str] = None
    
    def is_success(self) -> bool:
        """Check if fetch was successful."""
        return self.status == FetchStatus.SUCCESS and self.snapshot is not None
    
    def get_final_url(self) -> str:
        """Get final URL after redirects."""
        if self.snapshot and self.snapshot.canonical_url:
            return self.snapshot.canonical_url
        return self.url
    
    class Config:
        use_enum_values = True


class StorageResult(BaseModel):
    """Result of document storage operation."""
    
    snapshot_id: UUID
    status: StorageStatus
    storage_path: Optional[str] = None
    storage_bucket: Optional[str] = None
    error_message: Optional[str] = None
    storage_time_ms: Optional[int] = None
    duplicate_of: Optional[UUID] = None
    
    def is_success(self) -> bool:
        """Check if storage was successful."""
        return self.status == StorageStatus.STORED
    
    def is_duplicate(self) -> bool:
        """Check if document was a duplicate."""
        return self.status == StorageStatus.DUPLICATE
    
    class Config:
        use_enum_values = True
        json_encoders = {
            UUID: str
        }


class IngestionMetrics(BaseModel):
    """Metrics for ingestion service performance."""
    
    total_fetch_attempts: int = Field(default=0)
    successful_fetches: int = Field(default=0)
    failed_fetches: int = Field(default=0)
    robots_blocked_fetches: int = Field(default=0)
    timeout_fetches: int = Field(default=0)
    
    total_storage_attempts: int = Field(default=0)
    successful_storage: int = Field(default=0)
    failed_storage: int = Field(default=0)
    duplicate_storage: int = Field(default=0)
    
    total_bytes_fetched: int = Field(default=0)
    total_bytes_stored: int = Field(default=0)
    
    avg_fetch_time_ms: float = Field(default=0.0)
    avg_storage_time_ms: float = Field(default=0.0)
    
    documents_by_format: Dict[str, int] = Field(default_factory=dict)
    documents_by_domain: Dict[str, int] = Field(default_factory=dict)
    documents_by_province: Dict[str, int] = Field(default_factory=dict)
    
    last_updated: datetime = Field(default_factory=datetime.utcnow)
    
    def update_with_fetch_result(self, result: FetchResult) -> None:
        """Update metrics with fetch result."""
        self.total_fetch_attempts += 1
        
        if result.status == FetchStatus.SUCCESS:
            self.successful_fetches += 1
            if result.snapshot:
                self.total_bytes_fetched += result.snapshot.content_length
                
                # Update format distribution
                doc_format = result.snapshot.get_document_format().value
                self.documents_by_format[doc_format] = self.documents_by_format.get(doc_format, 0) + 1
                
                # Update domain distribution
                domain = result.snapshot.domain
                self.documents_by_domain[domain] = self.documents_by_domain.get(domain, 0) + 1
                
                # Update province distribution
                if result.snapshot.province:
                    province = result.snapshot.province.value
                    self.documents_by_province[province] = self.documents_by_province.get(province, 0) + 1
        
        elif result.status == FetchStatus.FAILED:
            self.failed_fetches += 1
        elif result.status == FetchStatus.ROBOTS_BLOCKED:
            self.robots_blocked_fetches += 1
        elif result.status == FetchStatus.TIMEOUT:
            self.timeout_fetches += 1
        
        # Update average fetch time
        if result.fetch_time_ms and self.successful_fetches > 0:
            total_time = self.avg_fetch_time_ms * (self.successful_fetches - 1)
            self.avg_fetch_time_ms = (total_time + result.fetch_time_ms) / self.successful_fetches
        
        self.last_updated = datetime.utcnow()
    
    def update_with_storage_result(self, result: StorageResult) -> None:
        """Update metrics with storage result."""
        self.total_storage_attempts += 1
        
        if result.status == StorageStatus.STORED:
            self.successful_storage += 1
        elif result.status == StorageStatus.FAILED:
            self.failed_storage += 1
        elif result.status == StorageStatus.DUPLICATE:
            self.duplicate_storage += 1
        
        # Update average storage time
        if result.storage_time_ms and self.successful_storage > 0:
            total_time = self.avg_storage_time_ms * (self.successful_storage - 1)
            self.avg_storage_time_ms = (total_time + result.storage_time_ms) / self.successful_storage
        
        self.last_updated = datetime.utcnow()
    
    def get_fetch_success_rate(self) -> float:
        """Calculate fetch success rate."""
        if self.total_fetch_attempts == 0:
            return 0.0
        return self.successful_fetches / self.total_fetch_attempts
    
    def get_storage_success_rate(self) -> float:
        """Calculate storage success rate."""
        if self.total_storage_attempts == 0:
            return 0.0
        return self.successful_storage / self.total_storage_attempts
    
    def get_duplicate_rate(self) -> float:
        """Calculate duplicate detection rate."""
        if self.total_storage_attempts == 0:
            return 0.0
        return self.duplicate_storage / self.total_storage_attempts
    
    def get_total_size_mb(self) -> float:
        """Get total size in megabytes."""
        return self.total_bytes_stored / (1024 * 1024)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }