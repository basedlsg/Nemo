"""Data models for document discovery service."""

from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, validator

from services.core.models import Province, DocumentClass, AssetType


class DiscoveryStatus(str, Enum):
    """Status of discovery operation."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    RATE_LIMITED = "rate_limited"


class DocumentCandidate(BaseModel):
    """Candidate document found during discovery."""
    
    url: str = Field(..., description="Document URL")
    title: Optional[str] = Field(None, description="Document title")
    snippet: Optional[str] = Field(None, description="Content snippet")
    domain: str = Field(..., description="Source domain")
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0, description="Relevance confidence")
    discovered_at: datetime = Field(default_factory=datetime.utcnow)
    source: str = Field(default="perplexity", description="Discovery source")
    
    @validator("url")
    def validate_url_format(cls, v):
        """Validate URL format."""
        if not v.startswith(("http://", "https://")):
            raise ValueError("URL must start with http:// or https://")
        return v
    
    @validator("domain")
    def validate_domain_format(cls, v):
        """Validate domain format."""
        if not v or "." not in v:
            raise ValueError("Domain must be valid")
        return v.lower()
    
    def is_official_domain(self) -> bool:
        """Check if candidate is from official domain."""
        official_patterns = [
            ".gov.cn",
            "gzpec.cn",
            "gdpec.com.cn", 
            "csg.cn",
            "shandong-electric.com.cn",
            "sgcc.com.cn",
            "nmgdl.cn",
            "scpec.com.cn",
        ]
        
        return any(pattern in self.domain for pattern in official_patterns)
    
    def extract_potential_date(self) -> Optional[str]:
        """Extract potential date from URL or title."""
        import re
        
        content = f"{self.url} {self.title or ''}"
        
        # Look for date patterns
        date_patterns = [
            r'(\d{4})-(\d{1,2})-(\d{1,2})',
            r'(\d{4})年(\d{1,2})月(\d{1,2})日',
            r'(\d{4})/(\d{1,2})/(\d{1,2})',
        ]
        
        for pattern in date_patterns:
            match = re.search(pattern, content)
            if match:
                return match.group(0)
        
        return None
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class DiscoveryQuery(BaseModel):
    """Query for document discovery."""
    
    query_id: UUID = Field(default_factory=uuid4)
    province: Province
    doc_class: DocumentClass
    asset: Optional[AssetType] = None
    keywords: List[str] = Field(default_factory=list)
    date_range: Optional[Dict[str, str]] = Field(None, description="Date range filter")
    domain_filter: List[str] = Field(default_factory=list, description="Allowed domains")
    max_results: int = Field(default=20, ge=1, le=100)
    allow_national_fallback: bool = Field(default=False, description="Allow fallback to national sources")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    def generate_search_query(self) -> str:
        """
        PR1: Compose a strict, province-scoped query.
        Example:
          (并网 验收 办事 指南 资料 清单) (site:gd.gov.cn OR site:gdee.gd.gov.cn OR site:gddrc.gd.gov.cn OR site:csg.cn) after:2023-01-01 before:2023-12-31
        """
        # Base query components - use Chinese keywords from query_normalize
        query_parts = []

        # Province-specific terms
        province_terms = {
            Province.GUANGDONG: ["广东", "粤", "广东省"],
            Province.SHANDONG: ["山东", "鲁", "山东省"],
            Province.INNER_MONGOLIA: ["内蒙古", "蒙", "内蒙古自治区"],
            Province.SICHUAN: ["四川", "川", "四川省"],
            Province.BEIJING: ["北京", "京", "北京市"],
            Province.SHANGHAI: ["上海", "沪", "上海市"]
        }

        if self.province in province_terms:
            query_parts.extend(province_terms[self.province])

        # Document class terms - more comprehensive Chinese keywords
        doc_class_terms = {
            DocumentClass.MARKET_RULES: ["市场规则", "交易规则", "市场管理办法", "电价", "补贴"],
            DocumentClass.GRID_CONNECTION: ["并网", "接入", "并网管理", "接入管理", "并网验收", "办事指南", "资料清单"],
            DocumentClass.DISPATCH_OPS: ["调度", "运行", "调度管理", "运行管理", "调度规则"],
            DocumentClass.TECHNICAL_STANDARDS: ["技术标准", "技术规范", "技术规定", "技术要求", "技术条件", "技术指标"]
        }

        if self.doc_class in doc_class_terms:
            query_parts.extend(doc_class_terms[self.doc_class])

        # Asset-specific terms
        if self.asset:
            asset_terms = {
                AssetType.WIND: ["风电", "风力发电", "陆上风电", "海上风电"],
                AssetType.SOLAR: ["光伏", "太阳能", "分布式光伏", "集中式光伏", "光伏发电"],
                AssetType.BESS: ["储能", "电池储能", "储能系统", "电化学储能"],
                AssetType.COAL_FLEX: ["煤电", "火电", "煤电灵活性", "深度调峰"]
            }

            if self.asset in asset_terms:
                query_parts.extend(asset_terms[self.asset])

        # Add custom keywords
        query_parts.extend(self.keywords)

        # Common regulatory terms
        query_parts.extend(["规定", "办法", "通知", "意见", "细则", "指南"])

        # Create base query
        base_query = " ".join(query_parts[:10])  # Limit to avoid too long queries

        # PR1: Add province-specific site filters
        domains = self.get_domain_allowlist()
        if domains:
            site_parts = []
            for domain in domains:
                if domain.startswith('.'):
                    # Handle wildcard domains like .gov.cn
                    site_parts.append(f"site:*{domain}")
                else:
                    site_parts.append(f"site:{domain}")

            site_filter = " OR ".join(site_parts)
            base_query = f"({base_query}) ({site_filter})"

        # Add date range if specified
        if self.date_range:
            if "start_date" in self.date_range:
                base_query += f" after:{self.date_range['start_date']}"
            if "end_date" in self.date_range:
                base_query += f" before:{self.date_range['end_date']}"

        # PR1: Opt-out of national drift by default
        if not self.allow_national_fallback:
            base_query += " -site:scio.gov.cn -site:nea.gov.cn -site:gov.cn/news"

        return base_query
    
    def get_domain_allowlist(self) -> List[str]:
        """Get domain allowlist for this query."""
        if self.domain_filter:
            return self.domain_filter
        
        # Default allowlist based on province
        base_domains = [".gov.cn"]
        
        province_domains = {
            Province.GUANGDONG: ["gzpec.cn", "gdpec.com.cn", "csg.cn"],
            Province.SHANDONG: ["shandong-electric.com.cn", "sgcc.com.cn"],
            Province.INNER_MONGOLIA: ["nmgdl.cn", "nmg.sgcc.com.cn"],
            Province.SICHUAN: ["sc.sgcc.com.cn", "scpec.com.cn"],
            Province.BEIJING: ["beijing.gov.cn", "bj.gov.cn", "bj.sgcc.com.cn"],
            Province.SHANGHAI: ["shanghai.gov.cn", "sh.gov.cn", "sh.sgcc.com.cn"]
        }
        
        if self.province in province_domains:
            base_domains.extend(province_domains[self.province])
        
        return base_domains
    
    class Config:
        use_enum_values = True
        json_encoders = {
            UUID: str,
            datetime: lambda v: v.isoformat()
        }


class DiscoveryResult(BaseModel):
    """Result of document discovery operation."""
    
    query_id: UUID
    status: DiscoveryStatus
    candidates: List[DocumentCandidate] = Field(default_factory=list)
    total_found: int = Field(default=0)
    filtered_count: int = Field(default=0, description="Candidates filtered by domain allowlist")
    processing_time_ms: Optional[int] = None
    error_message: Optional[str] = None
    rate_limit_reset_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    def get_official_candidates(self) -> List[DocumentCandidate]:
        """Get candidates from official domains only."""
        return [candidate for candidate in self.candidates if candidate.is_official_domain()]
    
    def get_candidates_by_domain(self, domain: str) -> List[DocumentCandidate]:
        """Get candidates from specific domain."""
        return [candidate for candidate in self.candidates if candidate.domain == domain]
    
    def get_high_confidence_candidates(self, threshold: float = 0.7) -> List[DocumentCandidate]:
        """Get candidates with high confidence scores."""
        return [
            candidate for candidate in self.candidates 
            if candidate.confidence_score >= threshold
        ]
    
    def sort_by_confidence(self) -> List[DocumentCandidate]:
        """Sort candidates by confidence score (descending)."""
        return sorted(self.candidates, key=lambda c: c.confidence_score, reverse=True)
    
    def get_summary(self) -> Dict[str, Any]:
        """Get summary statistics of discovery result."""
        official_candidates = self.get_official_candidates()
        
        return {
            "query_id": str(self.query_id),
            "status": self.status,
            "total_candidates": len(self.candidates),
            "official_candidates": len(official_candidates),
            "filtered_candidates": self.filtered_count,
            "avg_confidence": sum(c.confidence_score for c in self.candidates) / len(self.candidates) if self.candidates else 0,
            "domains_found": list(set(c.domain for c in self.candidates)),
            "processing_time_ms": self.processing_time_ms,
            "has_errors": bool(self.error_message)
        }
    
    class Config:
        use_enum_values = True
        json_encoders = {
            UUID: str,
            datetime: lambda v: v.isoformat()
        }


class DiscoveryMetrics(BaseModel):
    """Metrics for discovery service performance."""
    
    total_queries: int = Field(default=0)
    successful_queries: int = Field(default=0)
    failed_queries: int = Field(default=0)
    rate_limited_queries: int = Field(default=0)
    avg_processing_time_ms: float = Field(default=0.0)
    total_candidates_found: int = Field(default=0)
    official_candidates_found: int = Field(default=0)
    unique_domains_discovered: int = Field(default=0)
    last_updated: datetime = Field(default_factory=datetime.utcnow)
    
    def update_with_result(self, result: DiscoveryResult) -> None:
        """Update metrics with discovery result."""
        self.total_queries += 1
        
        if result.status == DiscoveryStatus.COMPLETED:
            self.successful_queries += 1
            self.total_candidates_found += len(result.candidates)
            self.official_candidates_found += len(result.get_official_candidates())
            
            if result.processing_time_ms:
                # Update running average
                total_time = self.avg_processing_time_ms * (self.successful_queries - 1)
                self.avg_processing_time_ms = (total_time + result.processing_time_ms) / self.successful_queries
        
        elif result.status == DiscoveryStatus.FAILED:
            self.failed_queries += 1
        elif result.status == DiscoveryStatus.RATE_LIMITED:
            self.rate_limited_queries += 1
        
        self.last_updated = datetime.utcnow()
    
    def get_success_rate(self) -> float:
        """Calculate success rate."""
        if self.total_queries == 0:
            return 0.0
        return self.successful_queries / self.total_queries
    
    def get_official_candidate_ratio(self) -> float:
        """Calculate ratio of official to total candidates."""
        if self.total_candidates_found == 0:
            return 0.0
        return self.official_candidates_found / self.total_candidates_found
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }