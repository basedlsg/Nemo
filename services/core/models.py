"""Core domain models for geo-adaptive energy assistant."""

import hashlib
from datetime import datetime, date
from enum import Enum
from typing import List, Optional, Dict, Any, Union
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, validator, root_validator


class Province(str, Enum):
    """Supported provinces for energy regulations."""
    
    SHANDONG = "shandong"
    GUANGDONG = "guangdong"
    INNER_MONGOLIA = "inner_mongolia"
    SICHUAN = "sichuan"  # Queued for future release
    
    @classmethod
    def enabled_provinces(cls) -> List[str]:
        """Get list of currently enabled provinces."""
        # Sichuan is queued but not enabled in pilot
        return [cls.SHANDONG, cls.GUANGDONG, cls.INNER_MONGOLIA]
    
    @classmethod
    def is_enabled(cls, province: str) -> bool:
        """Check if province is currently enabled."""
        return province in cls.enabled_provinces()
    
    def display_name_zh(self) -> str:
        """Get Chinese display name for province."""
        names = {
            self.SHANDONG: "山东",
            self.GUANGDONG: "广东", 
            self.INNER_MONGOLIA: "内蒙古",
            self.SICHUAN: "四川"
        }
        return names.get(self, self.value)


class DocumentClass(str, Enum):
    """Document classification for energy regulations."""
    
    MARKET_RULES = "market_rules"
    GRID_CONNECTION = "grid_connection"
    DISPATCH_OPS = "dispatch_ops"
    
    def display_name_zh(self) -> str:
        """Get Chinese display name for document class."""
        names = {
            self.MARKET_RULES: "市场规则",
            self.GRID_CONNECTION: "并网接入",
            self.DISPATCH_OPS: "调度运行"
        }
        return names.get(self, self.value)


class AssetType(str, Enum):
    """Energy asset types supported by the system."""
    
    WIND = "wind"
    SOLAR = "solar"
    BESS = "bess"  # Battery Energy Storage System
    COAL_FLEX = "coal_flex"  # Coal flexibility
    
    def display_name_zh(self) -> str:
        """Get Chinese display name for asset type."""
        names = {
            self.WIND: "风电",
            self.SOLAR: "光伏",
            self.BESS: "储能",
            self.COAL_FLEX: "煤电灵活性"
        }
        return names.get(self, self.value)


class RefusalReason(str, Enum):
    """Specific refusal reasons with exact error codes."""
    
    NO_FIRST_PARTY_CITATION = "no_first_party_citation"
    STALE_CITATION = "stale_citation"
    PROVINCE_MISMATCH = "province_mismatch"
    UNSUPPORTED_DOC_CLASS = "unsupported_doc_class"
    
    def message_zh(self) -> str:
        """Get Chinese explanation for refusal reason."""
        messages = {
            self.NO_FIRST_PARTY_CITATION: "未找到官方一手引用文件",
            self.STALE_CITATION: "仅找到已过期的引用文件",
            self.PROVINCE_MISMATCH: "查询省份不在支持范围内",
            self.UNSUPPORTED_DOC_CLASS: "该省份不支持此文档类别"
        }
        return messages.get(self, "未知拒答原因")


class CitationMetadata(BaseModel):
    """Citation metadata for verification and traceability."""
    
    citation_id: UUID
    title: str = Field(..., min_length=1, max_length=500)
    url: str = Field(..., pattern=r"^https?://[^\s]+$")
    checksum: str = Field(..., min_length=64, max_length=64)  # SHA256
    effective_date: date
    province: Province
    doc_class: DocumentClass
    asset: Optional[AssetType] = None
    
    @validator("checksum")
    def validate_checksum_format(cls, v):
        """Validate SHA256 checksum format."""
        if not all(c in "0123456789abcdef" for c in v.lower()):
            raise ValueError("Checksum must be valid SHA256 hex string")
        return v.lower()
    
    @validator("effective_date")
    def validate_effective_date_not_future(cls, v):
        """Ensure effective date is not in the future."""
        if v > date.today():
            raise ValueError("Effective date cannot be in the future")
        return v
    
    class Config:
        use_enum_values = True
        json_encoders = {
            UUID: str,
            date: lambda v: v.isoformat()
        }


class QueryRequest(BaseModel):
    """Request model for energy regulation queries."""
    
    province: Province
    asset: AssetType
    doc_class: DocumentClass
    question: str = Field(..., min_length=1, max_length=1000)
    user_id: Optional[str] = None
    trace_id: Optional[str] = None
    
    @validator("question")
    def validate_question_content(cls, v):
        """Basic validation for question content."""
        # Remove excessive whitespace
        v = " ".join(v.split())
        
        # Check for minimum meaningful content
        if len(v.strip()) < 3:
            raise ValueError("Question must contain meaningful content")
        
        return v
    
    @root_validator
    def validate_province_enabled(cls, values):
        """Ensure province is currently enabled."""
        province = values.get("province")
        if province and not Province.is_enabled(province):
            raise ValueError(f"Province {province} is not currently enabled")
        return values
    
    def generate_fingerprint(self) -> str:
        """Generate unique fingerprint for query caching."""
        content = f"{self.province}:{self.asset}:{self.doc_class}:{self.question.strip().lower()}"
        return hashlib.sha256(content.encode("utf-8")).hexdigest()
    
    class Config:
        use_enum_values = True


class QueryResponse(BaseModel):
    """Successful response model for energy regulation queries."""
    
    answer_zh: str = Field(..., min_length=1)
    citations: List[CitationMetadata] = Field(..., min_items=1)
    pack_id: Optional[UUID] = None
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    latency_ms: Optional[int] = None
    
    @validator("answer_zh")
    def validate_chinese_content(cls, v):
        """Ensure answer contains Chinese content."""
        # Basic check for Chinese characters
        has_chinese = any('\u4e00' <= char <= '\u9fff' for char in v)
        if not has_chinese:
            raise ValueError("Answer must contain Chinese content")
        return v
    
    @validator("citations")
    def validate_citations_not_empty(cls, v):
        """Ensure at least one citation is provided."""
        if not v:
            raise ValueError("At least one citation is required")
        return v
    
    class Config:
        json_encoders = {
            UUID: str,
            datetime: lambda v: v.isoformat()
        }


class RefusalResponse(BaseModel):
    """Refusal response when no official citations exist."""
    
    status: str = Field(default="refused", const=True)
    reason: RefusalReason
    policy: str = Field(default="first_party_citation_required", const=True)
    message_zh: Optional[str] = None
    ingestion_request_id: Optional[UUID] = None
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    
    @root_validator
    def set_chinese_message(cls, values):
        """Set Chinese message based on refusal reason."""
        reason = values.get("reason")
        if reason and not values.get("message_zh"):
            values["message_zh"] = reason.message_zh()
        return values
    
    class Config:
        use_enum_values = True
        json_encoders = {
            UUID: str,
            datetime: lambda v: v.isoformat()
        }


class CompliancePack(BaseModel):
    """Generated compliance pack with citations and metadata."""
    
    pack_id: UUID = Field(default_factory=uuid4)
    province: Province
    asset: AssetType
    doc_class: DocumentClass
    query_fingerprint: str
    answer_zh: str
    citations: List[CitationMetadata]
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    pack_status: str = Field(default="generated")
    
    @validator("pack_status")
    def validate_pack_status(cls, v):
        """Validate pack status values."""
        valid_statuses = {"generated", "delivered", "expired"}
        if v not in valid_statuses:
            raise ValueError(f"Pack status must be one of: {valid_statuses}")
        return v
    
    @root_validator
    def set_expiration(cls, values):
        """Set default expiration time if not provided."""
        if not values.get("expires_at") and values.get("generated_at"):
            # Default expiration: 7 days from generation
            from datetime import timedelta
            values["expires_at"] = values["generated_at"] + timedelta(days=7)
        return values
    
    def is_expired(self) -> bool:
        """Check if pack has expired."""
        if not self.expires_at:
            return False
        return datetime.utcnow() > self.expires_at
    
    def to_pdf_metadata(self) -> Dict[str, Any]:
        """Generate metadata for PDF generation."""
        return {
            "title": f"{self.province.display_name_zh()}{self.doc_class.display_name_zh()}合规指南",
            "subject": f"{self.asset.display_name_zh()}项目合规要求",
            "author": "地域自适应能源助手",
            "creator": "Geo-Adaptive Energy Assistant",
            "producer": "能源合规智能助手",
            "creation_date": self.generated_at,
            "modification_date": self.generated_at,
            "keywords": [
                self.province.display_name_zh(),
                self.asset.display_name_zh(),
                self.doc_class.display_name_zh(),
                "合规", "能源", "规则"
            ]
        }
    
    class Config:
        use_enum_values = True
        json_encoders = {
            UUID: str,
            datetime: lambda v: v.isoformat()
        }


class IngestionRequest(BaseModel):
    """Request for manual document ingestion."""
    
    request_id: UUID = Field(default_factory=uuid4)
    url: str = Field(..., pattern=r"^https?://[^\s]+$")
    province: Province
    doc_class: DocumentClass
    asset: Optional[AssetType] = None
    priority: str = Field(default="normal")
    requested_by: Optional[str] = None
    requested_at: datetime = Field(default_factory=datetime.utcnow)
    notes: Optional[str] = Field(None, max_length=500)
    
    @validator("priority")
    def validate_priority(cls, v):
        """Validate priority levels."""
        valid_priorities = {"low", "normal", "high", "urgent"}
        if v not in valid_priorities:
            raise ValueError(f"Priority must be one of: {valid_priorities}")
        return v
    
    class Config:
        use_enum_values = True
        json_encoders = {
            UUID: str,
            datetime: lambda v: v.isoformat()
        }


class EvaluationResult(BaseModel):
    """Evaluation results for quality gates."""
    
    evaluation_id: UUID = Field(default_factory=uuid4)
    province: Province
    doc_class: DocumentClass
    evaluation_date: date = Field(default_factory=date.today)
    groundedness_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    citation_precision: Optional[float] = Field(None, ge=0.0, le=1.0)
    refusal_accuracy: Optional[float] = Field(None, ge=0.0, le=1.0)
    avg_latency_ms: Optional[int] = Field(None, ge=0)
    p95_latency_ms: Optional[int] = Field(None, ge=0)
    total_queries: int = Field(default=0, ge=0)
    passed_queries: int = Field(default=0, ge=0)
    refused_queries: int = Field(default=0, ge=0)
    
    def meets_quality_thresholds(
        self,
        min_groundedness: float = 0.9,
        min_citation_precision: float = 0.95,
        min_refusal_accuracy: float = 0.99
    ) -> bool:
        """Check if evaluation meets quality thresholds."""
        return (
            (self.groundedness_score or 0) >= min_groundedness and
            (self.citation_precision or 0) >= min_citation_precision and
            (self.refusal_accuracy or 0) >= min_refusal_accuracy
        )
    
    def get_readiness_status(self) -> str:
        """Get province readiness status based on metrics."""
        if self.meets_quality_thresholds():
            return "ready"
        elif any(score is not None for score in [
            self.groundedness_score, self.citation_precision, self.refusal_accuracy
        ]):
            return "needs_improvement"
        else:
            return "not_evaluated"
    
    class Config:
        use_enum_values = True
        json_encoders = {
            UUID: str,
            date: lambda v: v.isoformat()
        }


class SourceRegistry(BaseModel):
    """Source registry entry for official energy regulation sources."""
    
    domain: str = Field(..., pattern=r"^[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
    province: Province
    label: str = Field(..., min_length=1, max_length=200)
    doc_classes: List[DocumentClass] = Field(default_factory=list)
    cadence: Optional[str] = None  # ISO8601 interval format
    robots_policy: str = Field(default="allow", pattern="^(allow|disallow)$")
    fetch_method: str = Field(default="html", pattern="^(html|pdf|both)$")
    owner: Optional[str] = Field(None, max_length=100)
    enabled: bool = Field(default=True)
    last_crawled_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    @validator("cadence")
    def validate_cadence_format(cls, v):
        """Validate ISO8601 interval format for cadence."""
        if v is None:
            return v
        
        # Basic validation for ISO8601 intervals (P[n]Y[n]M[n]DT[n]H[n]M[n]S or R/start/duration)
        import re
        iso8601_pattern = r"^(R\/\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z\/)?P(\d+Y)?(\d+M)?(\d+D)?(T(\d+H)?(\d+M)?(\d+S)?)?$"
        if not re.match(iso8601_pattern, v):
            raise ValueError("Cadence must be in ISO8601 interval format")
        return v
    
    def is_stale(self, hours_threshold: int = 48) -> bool:
        """Check if source hasn't been crawled recently."""
        if not self.last_crawled_at:
            return True
        
        from datetime import timedelta
        threshold = datetime.utcnow() - timedelta(hours=hours_threshold)
        return self.last_crawled_at < threshold
    
    class Config:
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }