"""Data models for document verification service."""

from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, validator

from services.discovery.models import DocumentCandidate


class VerificationStatus(str, Enum):
    """Status of verification operation."""
    PENDING = "pending"
    RUNNING = "running"
    VERIFIED = "verified"
    NOT_FOUND = "not_found"
    FAILED = "failed"
    RATE_LIMITED = "rate_limited"


class VerificationMethod(str, Enum):
    """Method used for verification."""
    GOOGLE_CSE = "google_cse"
    DIRECT_ACCESS = "direct_access"
    ROBOTS_TXT = "robots_txt"


class VerificationCandidate(BaseModel):
    """Candidate document with verification results."""
    
    # Original candidate information
    original_url: str = Field(..., description="Original discovered URL")
    title: Optional[str] = Field(None, description="Document title")
    domain: str = Field(..., description="Source domain")
    discovery_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    
    # Verification results
    verification_status: VerificationStatus = Field(default=VerificationStatus.PENDING)
    verification_method: Optional[VerificationMethod] = None
    canonical_url: Optional[str] = Field(None, description="Canonical URL from verification")
    verified_title: Optional[str] = Field(None, description="Title from verification")
    verified_snippet: Optional[str] = Field(None, description="Content snippet from verification")
    verification_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    
    # Metadata
    verified_at: Optional[datetime] = None
    error_message: Optional[str] = None
    http_status_code: Optional[int] = None
    content_type: Optional[str] = None
    content_length: Optional[int] = None
    last_modified: Optional[datetime] = None
    
    @validator("canonical_url")
    def validate_canonical_url(cls, v):
        """Validate canonical URL format."""
        if v and not v.startswith(("http://", "https://")):
            raise ValueError("Canonical URL must start with http:// or https://")
        return v
    
    def is_verified(self) -> bool:
        """Check if candidate is successfully verified."""
        return self.verification_status == VerificationStatus.VERIFIED
    
    def is_accessible(self) -> bool:
        """Check if candidate is accessible (HTTP 200)."""
        return self.http_status_code == 200
    
    def get_final_url(self) -> str:
        """Get final URL (canonical if available, otherwise original)."""
        return self.canonical_url or self.original_url
    
    def get_final_title(self) -> Optional[str]:
        """Get final title (verified if available, otherwise original)."""
        return self.verified_title or self.title
    
    def get_combined_confidence(self) -> float:
        """Get combined confidence score from discovery and verification."""
        if self.verification_status != VerificationStatus.VERIFIED:
            return 0.0
        
        # Weight verification confidence more heavily
        return (self.discovery_confidence * 0.3) + (self.verification_confidence * 0.7)
    
    def extract_metadata(self) -> Dict[str, Any]:
        """Extract metadata for storage."""
        return {
            "original_url": self.original_url,
            "canonical_url": self.canonical_url,
            "domain": self.domain,
            "title": self.get_final_title(),
            "verification_method": self.verification_method.value if self.verification_method else None,
            "http_status_code": self.http_status_code,
            "content_type": self.content_type,
            "content_length": self.content_length,
            "last_modified": self.last_modified.isoformat() if self.last_modified else None,
            "discovery_confidence": self.discovery_confidence,
            "verification_confidence": self.verification_confidence,
            "combined_confidence": self.get_combined_confidence(),
            "verified_at": self.verified_at.isoformat() if self.verified_at else None
        }
    
    class Config:
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class VerificationResult(BaseModel):
    """Result of document verification operation."""
    
    request_id: UUID
    status: VerificationStatus
    candidates: List[VerificationCandidate] = Field(default_factory=list)
    total_candidates: int = Field(default=0)
    verified_candidates: int = Field(default=0)
    not_found_candidates: int = Field(default=0)
    failed_candidates: int = Field(default=0)
    processing_time_ms: Optional[int] = None
    error_message: Optional[str] = None
    rate_limit_reset_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    def get_verified_candidates(self) -> List[VerificationCandidate]:
        """Get successfully verified candidates."""
        return [c for c in self.candidates if c.is_verified()]
    
    def get_accessible_candidates(self) -> List[VerificationCandidate]:
        """Get accessible candidates (HTTP 200)."""
        return [c for c in self.candidates if c.is_accessible()]
    
    def get_high_confidence_candidates(self, threshold: float = 0.7) -> List[VerificationCandidate]:
        """Get candidates with high combined confidence."""
        return [
            c for c in self.candidates 
            if c.get_combined_confidence() >= threshold
        ]
    
    def sort_by_confidence(self) -> List[VerificationCandidate]:
        """Sort candidates by combined confidence (descending)."""
        return sorted(self.candidates, key=lambda c: c.get_combined_confidence(), reverse=True)
    
    def get_verification_rate(self) -> float:
        """Get verification success rate."""
        if self.total_candidates == 0:
            return 0.0
        return self.verified_candidates / self.total_candidates
    
    def get_summary(self) -> Dict[str, Any]:
        """Get summary statistics of verification result."""
        verified_candidates = self.get_verified_candidates()
        
        return {
            "request_id": str(self.request_id),
            "status": self.status,
            "total_candidates": self.total_candidates,
            "verified_candidates": self.verified_candidates,
            "not_found_candidates": self.not_found_candidates,
            "failed_candidates": self.failed_candidates,
            "verification_rate": self.get_verification_rate(),
            "avg_combined_confidence": sum(c.get_combined_confidence() for c in verified_candidates) / len(verified_candidates) if verified_candidates else 0,
            "domains_verified": list(set(c.domain for c in verified_candidates)),
            "processing_time_ms": self.processing_time_ms,
            "has_errors": bool(self.error_message)
        }
    
    class Config:
        use_enum_values = True
        json_encoders = {
            UUID: str,
            datetime: lambda v: v.isoformat()
        }


class VerificationMetrics(BaseModel):
    """Metrics for verification service performance."""
    
    total_requests: int = Field(default=0)
    successful_requests: int = Field(default=0)
    failed_requests: int = Field(default=0)
    rate_limited_requests: int = Field(default=0)
    
    total_candidates_processed: int = Field(default=0)
    verified_candidates: int = Field(default=0)
    not_found_candidates: int = Field(default=0)
    failed_candidates: int = Field(default=0)
    
    avg_processing_time_ms: float = Field(default=0.0)
    avg_verification_rate: float = Field(default=0.0)
    
    google_cse_requests: int = Field(default=0)
    direct_access_checks: int = Field(default=0)
    robots_txt_checks: int = Field(default=0)
    
    last_updated: datetime = Field(default_factory=datetime.utcnow)
    
    def update_with_result(self, result: VerificationResult) -> None:
        """Update metrics with verification result."""
        self.total_requests += 1
        self.total_candidates_processed += result.total_candidates
        
        if result.status == VerificationStatus.VERIFIED:
            self.successful_requests += 1
            self.verified_candidates += result.verified_candidates
            self.not_found_candidates += result.not_found_candidates
            self.failed_candidates += result.failed_candidates
            
            # Update running averages
            if result.processing_time_ms:
                total_time = self.avg_processing_time_ms * (self.successful_requests - 1)
                self.avg_processing_time_ms = (total_time + result.processing_time_ms) / self.successful_requests
            
            if result.total_candidates > 0:
                verification_rate = result.get_verification_rate()
                total_rate = self.avg_verification_rate * (self.successful_requests - 1)
                self.avg_verification_rate = (total_rate + verification_rate) / self.successful_requests
        
        elif result.status == VerificationStatus.FAILED:
            self.failed_requests += 1
        elif result.status == VerificationStatus.RATE_LIMITED:
            self.rate_limited_requests += 1
        
        self.last_updated = datetime.utcnow()
    
    def update_method_count(self, method: VerificationMethod) -> None:
        """Update method-specific counters."""
        if method == VerificationMethod.GOOGLE_CSE:
            self.google_cse_requests += 1
        elif method == VerificationMethod.DIRECT_ACCESS:
            self.direct_access_checks += 1
        elif method == VerificationMethod.ROBOTS_TXT:
            self.robots_txt_checks += 1
    
    def get_success_rate(self) -> float:
        """Calculate overall success rate."""
        if self.total_requests == 0:
            return 0.0
        return self.successful_requests / self.total_requests
    
    def get_overall_verification_rate(self) -> float:
        """Calculate overall verification rate."""
        if self.total_candidates_processed == 0:
            return 0.0
        return self.verified_candidates / self.total_candidates_processed
    
    def get_method_distribution(self) -> Dict[str, int]:
        """Get distribution of verification methods used."""
        return {
            "google_cse": self.google_cse_requests,
            "direct_access": self.direct_access_checks,
            "robots_txt": self.robots_txt_checks
        }
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class CSESearchResult(BaseModel):
    """Individual search result from Google CSE."""
    
    title: str
    link: str
    snippet: Optional[str] = None
    display_link: Optional[str] = None
    formatted_url: Optional[str] = None
    html_title: Optional[str] = None
    html_snippet: Optional[str] = None
    cache_id: Optional[str] = None
    
    def extract_domain(self) -> str:
        """Extract domain from link."""
        try:
            from urllib.parse import urlparse
            parsed = urlparse(self.link)
            return parsed.netloc.lower()
        except Exception:
            return ""
    
    def calculate_relevance_score(self, original_url: str, original_title: Optional[str] = None) -> float:
        """Calculate relevance score compared to original candidate."""
        score = 0.0
        
        # URL similarity (exact match gets highest score)
        if self.link == original_url:
            score += 0.5
        elif original_url in self.link or self.link in original_url:
            score += 0.3
        elif self.extract_domain() == self._extract_domain_from_url(original_url):
            score += 0.2
        
        # Title similarity
        if original_title and self.title:
            title_similarity = self._calculate_text_similarity(self.title, original_title)
            score += title_similarity * 0.3
        
        # Snippet relevance (presence of energy-related terms)
        if self.snippet:
            energy_terms = ["能源", "电力", "光伏", "风电", "储能", "并网", "调度", "市场", "交易"]
            snippet_lower = self.snippet.lower()
            term_matches = sum(1 for term in energy_terms if term in snippet_lower)
            score += min(term_matches * 0.02, 0.2)  # Max 0.2 from snippet
        
        return min(score, 1.0)  # Cap at 1.0
    
    def _extract_domain_from_url(self, url: str) -> str:
        """Extract domain from URL."""
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            return parsed.netloc.lower()
        except Exception:
            return ""
    
    def _calculate_text_similarity(self, text1: str, text2: str) -> float:
        """Calculate simple text similarity."""
        if not text1 or not text2:
            return 0.0
        
        # Simple word-based similarity
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        
        return len(intersection) / len(union) if union else 0.0
    
    class Config:
        extra = "allow"  # Allow additional fields from CSE response