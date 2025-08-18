"""SQLAlchemy models for geo-adaptive energy assistant."""

from datetime import datetime, date
from typing import Optional, List
from uuid import UUID, uuid4

from sqlalchemy import (
    Column, String, Text, DateTime, Date, Integer, Boolean, 
    ForeignKey, CheckConstraint, Index, ARRAY, DECIMAL
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from pgvector.sqlalchemy import Vector
from pydantic import BaseModel, Field, validator

Base = declarative_base()


class Citation(Base):
    """Citation model for energy regulation documents."""
    
    __tablename__ = "citations"
    
    citation_id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    province = Column(String, nullable=False, index=True)
    doc_class = Column(String, nullable=False, index=True)
    asset = Column(String, nullable=True)
    title = Column(Text, nullable=False)
    url = Column(Text, nullable=False)
    effective_date = Column(Date, nullable=False)
    checksum = Column(String, nullable=False, unique=True)
    content = Column(Text, nullable=False)
    embedding = Column(Vector(1536))
    superseded_by = Column(PG_UUID(as_uuid=True), ForeignKey("citations.citation_id"))
    chunk_id = Column(String, nullable=True)
    parent_citation_id = Column(PG_UUID(as_uuid=True), ForeignKey("citations.citation_id"))
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # Relationships
    superseding_citation = relationship("Citation", remote_side=[citation_id], foreign_keys=[superseded_by])
    parent_citation = relationship("Citation", remote_side=[citation_id], foreign_keys=[parent_citation_id])
    
    # Constraints
    __table_args__ = (
        CheckConstraint(
            "doc_class IN ('market_rules', 'grid_connection', 'dispatch_ops')",
            name="valid_doc_class"
        ),
        CheckConstraint(
            "asset IS NULL OR asset IN ('wind', 'solar', 'bess', 'coal_flex')",
            name="valid_asset"
        ),
        Index("cit_idx", "province", "doc_class", "asset"),
        Index("cit_effective_idx", "province", "doc_class", "effective_date"),
        Index("cit_embedding_idx", "embedding", postgresql_using="ivfflat"),
        Index("cit_checksum_idx", "checksum"),
    )


class Pack(Base):
    """Pack model for generated compliance documents."""
    
    __tablename__ = "packs"
    
    pack_id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    created_at = Column(DateTime, default=func.now())
    province = Column(String)
    asset = Column(String)
    doc_class = Column(String)
    query_fingerprint = Column(String, nullable=False)
    citation_ids = Column(ARRAY(PG_UUID(as_uuid=True)), nullable=False)
    answer_zh = Column(Text)
    pack_status = Column(String, default="generated")
    
    __table_args__ = (
        CheckConstraint(
            "pack_status IN ('generated', 'delivered', 'expired')",
            name="valid_pack_status"
        ),
        Index("pack_qf_idx", "query_fingerprint"),
        Index("pack_created_idx", "created_at"),
        Index("pack_province_idx", "province", "doc_class", "asset"),
    )


class Source(Base):
    """Source model for official energy regulation sources."""
    
    __tablename__ = "sources"
    
    domain = Column(String, primary_key=True)
    province = Column(String)
    label = Column(String)
    cadence = Column(String)
    robots = Column(String, default="allow")
    last_crawled_at = Column(DateTime)
    owner = Column(String)
    doc_classes = Column(ARRAY(String), default=[])
    fetch_method = Column(String, default="html")
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    __table_args__ = (
        CheckConstraint(
            "robots IN ('allow', 'disallow')",
            name="valid_robots"
        ),
        CheckConstraint(
            "fetch_method IN ('html', 'pdf', 'both')",
            name="valid_fetch_method"
        ),
        Index("sources_province_idx", "province"),
        Index("sources_enabled_idx", "enabled"),
        Index("sources_crawl_idx", "last_crawled_at"),
    )


class EvaluationMetric(Base):
    """Evaluation metrics for quality gates."""
    
    __tablename__ = "evaluation_metrics"
    
    metric_id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    province = Column(String, nullable=False)
    doc_class = Column(String, nullable=False)
    evaluation_date = Column(Date, nullable=False, default=func.current_date())
    groundedness_score = Column(DECIMAL(3, 2))
    citation_precision = Column(DECIMAL(3, 2))
    refusal_accuracy = Column(DECIMAL(3, 2))
    avg_latency_ms = Column(Integer)
    p95_latency_ms = Column(Integer)
    total_queries = Column(Integer, default=0)
    passed_queries = Column(Integer, default=0)
    refused_queries = Column(Integer, default=0)
    created_at = Column(DateTime, default=func.now())
    
    __table_args__ = (
        CheckConstraint(
            "groundedness_score >= 0 AND groundedness_score <= 1",
            name="valid_groundedness"
        ),
        CheckConstraint(
            "citation_precision >= 0 AND citation_precision <= 1",
            name="valid_precision"
        ),
        CheckConstraint(
            "refusal_accuracy >= 0 AND refusal_accuracy <= 1",
            name="valid_refusal_accuracy"
        ),
        Index("eval_metrics_province_idx", "province", "doc_class", "evaluation_date"),
        Index("eval_metrics_date_idx", "evaluation_date"),
    )


class QueryLog(Base):
    """Query logs for observability."""
    
    __tablename__ = "query_logs"
    
    log_id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    trace_id = Column(String, nullable=False)
    user_id = Column(String)
    province = Column(String)
    doc_class = Column(String)
    asset = Column(String)
    question_hash = Column(String)
    verdict = Column(String)
    refusal_reason = Column(String)
    citation_ids = Column(ARRAY(PG_UUID(as_uuid=True)))
    latency_ms = Column(Integer)
    created_at = Column(DateTime, default=func.now())
    
    __table_args__ = (
        CheckConstraint(
            "verdict IN ('ok', 'refused', 'error')",
            name="valid_verdict"
        ),
        Index("query_logs_trace_idx", "trace_id"),
        Index("query_logs_created_idx", "created_at"),
        Index("query_logs_verdict_idx", "verdict"),
        Index("query_logs_province_idx", "province", "doc_class"),
    )


class IngestionJob(Base):
    """Ingestion job tracking."""
    
    __tablename__ = "ingestion_jobs"
    
    job_id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    source_domain = Column(String, ForeignKey("sources.domain"), nullable=False)
    url = Column(Text, nullable=False)
    job_status = Column(String, default="pending")
    job_type = Column(String, default="discovery")
    error_message = Column(Text)
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)
    scheduled_at = Column(DateTime, default=func.now())
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    created_at = Column(DateTime, default=func.now())
    
    # Relationship
    source = relationship("Source", backref="ingestion_jobs")
    
    __table_args__ = (
        CheckConstraint(
            "job_status IN ('pending', 'processing', 'completed', 'failed', 'retrying')",
            name="valid_job_status"
        ),
        CheckConstraint(
            "job_type IN ('discovery', 'verification', 'ingestion', 'ocr', 'normalization')",
            name="valid_job_type"
        ),
        Index("ingestion_jobs_status_idx", "job_status"),
        Index("ingestion_jobs_domain_idx", "source_domain"),
        Index("ingestion_jobs_scheduled_idx", "scheduled_at"),
    )


# Pydantic models for API serialization
class CitationResponse(BaseModel):
    """Citation response model."""
    
    citation_id: UUID
    title: str
    url: str
    checksum: str
    effective_date: date
    province: str
    doc_class: str
    asset: Optional[str] = None
    
    class Config:
        from_attributes = True


class CitationCreate(BaseModel):
    """Citation creation model."""
    
    province: str = Field(..., pattern="^(shandong|guangdong|inner_mongolia|sichuan)$")
    doc_class: str = Field(..., pattern="^(market_rules|grid_connection|dispatch_ops)$")
    asset: Optional[str] = Field(None, pattern="^(wind|solar|bess|coal_flex)$")
    title: str = Field(..., min_length=1, max_length=500)
    url: str = Field(..., pattern="^https?://")
    effective_date: date
    checksum: str = Field(..., min_length=64, max_length=64)  # SHA256
    content: str = Field(..., min_length=1)
    embedding: Optional[List[float]] = Field(None, min_items=1536, max_items=1536)
    chunk_id: Optional[str] = None
    parent_citation_id: Optional[UUID] = None


class PackResponse(BaseModel):
    """Pack response model."""
    
    pack_id: UUID
    created_at: datetime
    province: Optional[str]
    asset: Optional[str]
    doc_class: Optional[str]
    citation_ids: List[UUID]
    pack_status: str
    
    class Config:
        from_attributes = True


class SourceResponse(BaseModel):
    """Source response model."""
    
    domain: str
    province: Optional[str]
    label: Optional[str]
    cadence: Optional[str]
    robots: str
    last_crawled_at: Optional[datetime]
    owner: Optional[str]
    doc_classes: List[str]
    fetch_method: str
    enabled: bool
    
    class Config:
        from_attributes = True


class SourceCreate(BaseModel):
    """Source creation model."""
    
    domain: str = Field(..., pattern="^[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$")
    province: Optional[str] = Field(None, pattern="^(shandong|guangdong|inner_mongolia|sichuan)$")
    label: Optional[str] = Field(None, max_length=200)
    cadence: Optional[str] = None  # ISO8601 interval
    robots: str = Field("allow", pattern="^(allow|disallow)$")
    owner: Optional[str] = Field(None, max_length=100)
    doc_classes: List[str] = Field(default_factory=list)
    fetch_method: str = Field("html", pattern="^(html|pdf|both)$")
    enabled: bool = True
    
    @validator("doc_classes")
    def validate_doc_classes(cls, v):
        valid_classes = {"market_rules", "grid_connection", "dispatch_ops"}
        for doc_class in v:
            if doc_class not in valid_classes:
                raise ValueError(f"Invalid doc_class: {doc_class}")
        return v


class EvaluationMetricResponse(BaseModel):
    """Evaluation metric response model."""
    
    metric_id: UUID
    province: str
    doc_class: str
    evaluation_date: date
    groundedness_score: Optional[float]
    citation_precision: Optional[float]
    refusal_accuracy: Optional[float]
    avg_latency_ms: Optional[int]
    p95_latency_ms: Optional[int]
    total_queries: int
    passed_queries: int
    refused_queries: int
    
    class Config:
        from_attributes = True


class QueryLogCreate(BaseModel):
    """Query log creation model."""
    
    trace_id: str
    user_id: Optional[str] = None
    province: Optional[str] = None
    doc_class: Optional[str] = None
    asset: Optional[str] = None
    question_hash: Optional[str] = None
    verdict: str = Field(..., pattern="^(ok|refused|error)$")
    refusal_reason: Optional[str] = None
    citation_ids: Optional[List[UUID]] = None
    latency_ms: Optional[int] = None