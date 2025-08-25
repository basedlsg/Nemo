"""Schemas for Gemini service integration."""

from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings


class GeminiConfig(BaseSettings):
    """Configuration for Gemini integration."""

    api_key: str = Field(..., alias="GOOGLE_API_KEY")
    model: str = Field(default="gemini-1.5-pro", alias="GEMINI_MODEL")
    temperature: float = Field(default=0.1, alias="GEMINI_TEMPERATURE")
    max_tokens: int = Field(default=4000, alias="GEMINI_MAX_TOKENS")
    max_input_tokens: int = Field(default=32000, alias="GEMINI_MAX_INPUT_TOKENS")
    timeout: int = Field(default=30, alias="GEMINI_TIMEOUT")

    class Config:
        env_file = ".env"
        populate_by_name = True
        extra = "ignore"  # Allow extra fields in env file


class GeminiRequest(BaseModel):
    """Request model for Gemini answer generation."""

    question: str = Field(..., description="User's question")
    document_structure: 'DocumentStructure' = Field(..., description="Structured document content")
    query_context: Dict[str, Any] = Field(..., description="Query context (province, asset, etc.)")
    max_citations: int = Field(default=10, description="Maximum citations to include")


class GeminiResponse(BaseModel):
    """Response model from Gemini answer generation."""

    answer_zh: str = Field(..., description="Generated answer in Chinese")
    citations: List[Dict[str, Any]] = Field(..., description="Citations used in answer")
    sections: List[Dict[str, Any]] = Field(default_factory=list, description="Structured sections")
    confidence_score: float = Field(default=0.0, description="Confidence in answer quality")
    grounding_score: float = Field(default=0.0, description="Grounding in source documents")
    processing_time_ms: int = Field(default=0, description="Processing time in milliseconds")
    generated_at: datetime = Field(default_factory=datetime.utcnow)


class DocumentStructure(BaseModel):
    """Structured representation of document content."""

    title: str = Field(..., description="Document title")
    url: str = Field(..., description="Source URL")
    sections: List['DocumentSection'] = Field(default_factory=list, description="Document sections")
    tables: List[Dict[str, Any]] = Field(default_factory=list, description="Extracted tables")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Document metadata")


class DocumentSection(BaseModel):
    """Individual section within a document."""

    section_type: str = Field(..., description="Type of section (article, requirement, procedure, etc.)")
    title: str = Field(..., description="Section title or number")
    content: str = Field(..., description="Section content")
    subsections: List['DocumentSection'] = Field(default_factory=list, description="Nested subsections")
    start_position: int = Field(default=0, description="Character position in original document")
    end_position: int = Field(default=0, description="End character position")
    confidence: float = Field(default=1.0, description="Confidence in section extraction")


class GroundingResult(BaseModel):
    """Result of answer grounding validation."""

    is_grounded: bool = Field(default=False, description="Whether answer is grounded in sources")
    grounding_score: float = Field(default=0.0, description="Grounding confidence score")
    grounded_phrases: List[str] = Field(default_factory=list, description="Phrases found in source documents")
    ungrounded_phrases: List[str] = Field(default_factory=list, description="Phrases not found in sources")
    citation_coverage: float = Field(default=0.0, description="Percentage of answer covered by citations")
    validation_details: Dict[str, Any] = Field(default_factory=dict, description="Detailed validation results")


class AnswerValidationResult(BaseModel):
    """Complete answer validation result."""

    grounding: GroundingResult = Field(..., description="Grounding validation result")
    overall_score: float = Field(default=0.0, description="Overall answer quality score")
    is_valid: bool = Field(default=False, description="Whether answer passes validation")
    issues: List[str] = Field(default_factory=list, description="Validation issues found")
    recommendations: List[str] = Field(default_factory=list, description="Improvement recommendations")
