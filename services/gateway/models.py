"""Request and response models for the API gateway."""

from typing import List, Dict, Any, Optional
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, validator


class Province(str, Enum):
    """Supported provinces."""
    GUANGDONG = "guangdong"
    SHANDONG = "shandong"
    INNER_MONGOLIA = "inner_mongolia"


class Asset(str, Enum):
    """Supported asset types."""
    WIND = "wind"
    SOLAR = "solar"
    BESS = "bess"
    COAL_FLEX = "coal_flex"


class DocClass(str, Enum):
    """Supported document classes."""
    MARKET_RULES = "market_rules"
    GRID_CONNECTION = "grid_connection"
    DISPATCH_OPS = "dispatch_ops"


class Language(str, Enum):
    """Supported languages."""
    CHINESE = "zh-CN"
    ENGLISH = "en"


class QueryRequest(BaseModel):
    """Main query request model."""
    
    question: str = Field(..., min_length=1, max_length=500, description="User question in Chinese")
    province: Province = Field(..., description="Province for geo-specific search")
    doc_class: DocClass = Field(..., description="Document class for scoped search")
    asset: Optional[Asset] = Field(None, description="Asset type for targeted search")
    lang: Language = Field(default=Language.CHINESE, description="Response language preference")
    max_citations: int = Field(default=10, ge=1, le=20, description="Maximum citations to return")
    
    @validator('question')
    def validate_question(cls, v):
        """Validate question content."""
        if not v.strip():
            raise ValueError("Question cannot be empty")
        return v.strip()


class CitationMetadata(BaseModel):
    """Citation metadata in response."""
    
    citation_id: str = Field(..., description="Unique citation identifier")
    title: str = Field(..., description="Document title")
    url: str = Field(..., description="Source URL")
    effective_date: str = Field(..., description="Document effective date")
    score: float = Field(..., ge=0.0, le=1.0, description="Relevance score")
    passage: str = Field(..., description="Relevant text passage")


class QueryResponse(BaseModel):
    """Main query response model."""
    
    answer_zh: str = Field(..., description="Chinese answer with inline citations")
    citations: List[CitationMetadata] = Field(..., description="Citation metadata list")
    sections: int = Field(..., description="Number of answer sections")
    total_citations: int = Field(..., description="Total citations used")
    processing_time_ms: int = Field(..., description="Total processing time in milliseconds")
    composed_at: str = Field(..., description="Response composition timestamp")
    query_context: Dict[str, Any] = Field(..., description="Query context information")
    trace_id: str = Field(..., description="Request trace identifier")


class RefusalResponse(BaseModel):
    """Refusal response when query cannot be answered."""
    
    error: str = Field(..., description="Error type")
    reason: str = Field(..., description="Refusal reason")
    policy_violated: Optional[str] = Field(None, description="Policy that was violated")
    suggestion: str = Field(..., description="Suggestion for user")
    trace_id: str = Field(..., description="Request trace identifier")
    timestamp: str = Field(..., description="Refusal timestamp")


class HealthResponse(BaseModel):
    """Gateway health check response."""
    
    status: str = Field(..., description="Overall gateway health status")
    services: Dict[str, str] = Field(..., description="Individual service health status")
    version: str = Field(..., description="Gateway version")
    timestamp: str = Field(..., description="Health check timestamp")


class ServiceStats(BaseModel):
    """Service statistics response."""
    
    total_queries: int = Field(..., description="Total queries processed")
    successful_queries: int = Field(..., description="Successfully answered queries")
    refusal_rate: float = Field(..., ge=0.0, le=1.0, description="Refusal rate percentage")
    avg_processing_time_ms: float = Field(..., description="Average processing time")
    province_distribution: Dict[str, int] = Field(..., description="Query distribution by province")
    doc_class_distribution: Dict[str, int] = Field(..., description="Query distribution by doc class")
    asset_distribution: Dict[str, int] = Field(..., description="Query distribution by asset")
    timestamp: str = Field(..., description="Statistics timestamp")


class ValidationError(BaseModel):
    """Validation error response."""
    
    error: str = Field(..., description="Error type")
    field: str = Field(..., description="Field that failed validation")
    message: str = Field(..., description="Validation error message")
    allowed_values: Optional[List[str]] = Field(None, description="Allowed values for enum fields")
    timestamp: str = Field(..., description="Error timestamp")


# Request validation helpers
def validate_province_asset_combination(province: Province, asset: Optional[Asset]) -> bool:
    """Validate that province and asset combination is supported."""
    # All provinces support all assets currently
    # This could be extended for province-specific asset restrictions
    return True


def validate_doc_class_asset_combination(doc_class: DocClass, asset: Optional[Asset]) -> bool:
    """Validate that doc_class and asset combination makes sense."""
    # Some combinations might not make sense (e.g., coal_flex with grid_connection in some contexts)
    # For now, allow all combinations
    return True


# Response formatting helpers
def format_processing_time(start_time: datetime, end_time: datetime) -> int:
    """Format processing time in milliseconds."""
    return int((end_time - start_time).total_seconds() * 1000)


def generate_trace_id() -> str:
    """Generate unique trace ID for request tracking."""
    import uuid
    return f"gaea-{uuid.uuid4().hex[:12]}"


def create_query_context(request: QueryRequest, trace_id: str) -> Dict[str, Any]:
    """Create query context for logging and response."""
    return {
        "province": request.province.value,
        "doc_class": request.doc_class.value,
        "asset": request.asset.value if request.asset else None,
        "lang": request.lang.value,
        "max_citations": request.max_citations,
        "trace_id": trace_id,
        "question_length": len(request.question)
    }