"""Data models for source registry configuration."""

from datetime import datetime
from typing import List, Dict, Optional, Any
from enum import Enum

from pydantic import BaseModel, Field, validator, root_validator

from services.core.models import Province, DocumentClass


class Priority(str, Enum):
    """Source priority levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class FetchMethod(str, Enum):
    """Document fetch methods."""
    HTML = "html"
    PDF = "pdf"
    BOTH = "both"


class RobotsPolicy(str, Enum):
    """Robots.txt policy."""
    ALLOW = "allow"
    DISALLOW = "disallow"


class SourceSelectors(BaseModel):
    """CSS selectors for content extraction."""
    
    index: str = Field(..., description="Selector for finding document links")
    content: Optional[str] = Field(None, description="Selector for extracting main content")
    
    class Config:
        extra = "allow"  # Allow additional selectors


class SourceConfig(BaseModel):
    """Configuration for a single source."""
    
    domain: str = Field(..., pattern=r"^[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
    label: str = Field(..., min_length=1, max_length=200)
    label_en: Optional[str] = Field(None, max_length=200)
    doc_classes: List[DocumentClass] = Field(..., min_items=1)
    cadence: str = Field(..., description="ISO8601 interval for crawling frequency")
    robots: RobotsPolicy = Field(default=RobotsPolicy.ALLOW)
    fetch_method: FetchMethod = Field(default=FetchMethod.HTML)
    selectors: SourceSelectors
    effective_date_locator: str = Field(..., description="CSS selector or regex for date extraction")
    owner: str = Field(..., max_length=100)
    priority: Priority = Field(default=Priority.MEDIUM)
    enabled: bool = Field(default=True)
    url_patterns: Optional[List[str]] = Field(None, description="URL patterns to match")
    
    @validator("cadence")
    def validate_cadence_format(cls, v):
        """Validate ISO8601 interval format."""
        import re
        # Basic validation for ISO8601 intervals
        iso8601_pattern = r"^R\/\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z\/P(\d+Y)?(\d+M)?(\d+D)?(T(\d+H)?(\d+M)?(\d+S)?)?$"
        if not re.match(iso8601_pattern, v):
            raise ValueError("Cadence must be in ISO8601 interval format")
        return v
    
    @validator("effective_date_locator")
    def validate_date_locator(cls, v):
        """Validate effective date locator format."""
        if not v:
            raise ValueError("Effective date locator is required")
        
        # Check if it's a CSS selector or regex pattern
        if v.startswith("regex:"):
            # Validate regex pattern
            import re
            try:
                pattern = v[6:]  # Remove "regex:" prefix
                re.compile(pattern)
            except re.error as e:
                raise ValueError(f"Invalid regex pattern: {e}")
        elif not any(char in v for char in ['.', '#', '[', ':']):
            # Should look like a CSS selector
            raise ValueError("Date locator must be CSS selector or regex: pattern")
        
        return v
    
    def get_crawl_interval_hours(self) -> int:
        """Extract crawl interval in hours from cadence."""
        import re
        
        # Parse ISO8601 interval to extract hours
        match = re.search(r'P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?)?', self.cadence)
        if not match:
            return 24  # Default to daily
        
        days, hours, minutes, seconds = match.groups()
        
        total_hours = 0
        if days:
            total_hours += int(days) * 24
        if hours:
            total_hours += int(hours)
        if minutes:
            total_hours += int(minutes) / 60
        if seconds:
            total_hours += int(seconds) / 3600
        
        return max(1, int(total_hours))  # At least 1 hour
    
    def is_stale(self, last_crawled: Optional[datetime] = None) -> bool:
        """Check if source needs crawling based on cadence."""
        if not last_crawled:
            return True
        
        from datetime import timedelta
        interval_hours = self.get_crawl_interval_hours()
        threshold = datetime.utcnow() - timedelta(hours=interval_hours)
        
        return last_crawled < threshold
    
    class Config:
        use_enum_values = True


class GlobalConfig(BaseModel):
    """Global configuration settings."""
    
    default_cadence: str = Field(default="R/2025-01-01T00:00:00Z/P1D")
    default_robots: RobotsPolicy = Field(default=RobotsPolicy.ALLOW)
    default_fetch_method: FetchMethod = Field(default=FetchMethod.HTML)
    default_priority: Priority = Field(default=Priority.MEDIUM)
    
    # Rate limiting
    requests_per_minute: int = Field(default=30, ge=1, le=1000)
    concurrent_requests: int = Field(default=5, ge=1, le=50)
    
    # Retry settings
    max_retries: int = Field(default=3, ge=0, le=10)
    retry_delay_seconds: int = Field(default=60, ge=1)
    backoff_multiplier: float = Field(default=2.0, ge=1.0, le=10.0)
    
    # Content validation
    min_content_length: int = Field(default=100, ge=1)
    max_content_length: int = Field(default=1000000, ge=1000)
    required_chinese_ratio: float = Field(default=0.3, ge=0.0, le=1.0)
    
    # Quality gates
    min_success_rate: float = Field(default=0.8, ge=0.0, le=1.0)
    max_error_rate: float = Field(default=0.1, ge=0.0, le=1.0)
    
    # Monitoring
    health_check_interval: str = Field(default="PT1H")
    stale_threshold_hours: int = Field(default=48, ge=1)
    
    class Config:
        use_enum_values = True


class AssetMapping(BaseModel):
    """Asset-specific source mappings."""
    
    priority_domains: List[str] = Field(default_factory=list)
    doc_classes: List[DocumentClass] = Field(default_factory=list)
    
    class Config:
        use_enum_values = True


class RegistryConfig(BaseModel):
    """Complete registry configuration."""
    
    version: str = Field(..., pattern=r"^\d+\.\d+$")
    last_updated: str = Field(..., description="ISO date string")
    maintainer: str = Field(..., max_length=100)
    
    # Province sources
    guangdong: List[SourceConfig] = Field(default_factory=list)
    shandong: List[SourceConfig] = Field(default_factory=list)
    inner_mongolia: List[SourceConfig] = Field(default_factory=list)
    sichuan: List[SourceConfig] = Field(default_factory=list)
    
    # Configuration
    global_config: GlobalConfig = Field(default_factory=GlobalConfig)
    asset_mappings: Dict[str, AssetMapping] = Field(default_factory=dict)
    
    @validator("last_updated")
    def validate_last_updated(cls, v):
        """Validate last updated date format."""
        try:
            datetime.fromisoformat(v)
        except ValueError:
            raise ValueError("last_updated must be valid ISO date string")
        return v
    
    def get_sources_by_province(self, province: Province) -> List[SourceConfig]:
        """Get all sources for a province."""
        province_sources = {
            Province.GUANGDONG: self.guangdong,
            Province.SHANDONG: self.shandong,
            Province.INNER_MONGOLIA: self.inner_mongolia,
            Province.SICHUAN: self.sichuan,
        }
        return province_sources.get(province, [])
    
    def get_enabled_sources_by_province(self, province: Province) -> List[SourceConfig]:
        """Get enabled sources for a province."""
        sources = self.get_sources_by_province(province)
        return [source for source in sources if source.enabled]
    
    def get_sources_by_domain(self, domain: str) -> List[SourceConfig]:
        """Get all sources matching a domain."""
        all_sources = (
            self.guangdong + self.shandong + 
            self.inner_mongolia + self.sichuan
        )
        return [source for source in all_sources if source.domain == domain]
    
    def get_sources_by_doc_class(
        self, 
        province: Province, 
        doc_class: DocumentClass
    ) -> List[SourceConfig]:
        """Get sources for specific province and document class."""
        province_sources = self.get_enabled_sources_by_province(province)
        return [
            source for source in province_sources 
            if doc_class in source.doc_classes
        ]
    
    def get_priority_sources_for_asset(
        self, 
        province: Province, 
        asset: str
    ) -> List[SourceConfig]:
        """Get priority sources for specific asset type."""
        if asset not in self.asset_mappings:
            return self.get_enabled_sources_by_province(province)
        
        asset_mapping = self.asset_mappings[asset]
        province_sources = self.get_enabled_sources_by_province(province)
        
        # Filter by priority domains and doc classes
        priority_sources = []
        for source in province_sources:
            if (source.domain in asset_mapping.priority_domains and
                any(doc_class in asset_mapping.doc_classes for doc_class in source.doc_classes)):
                priority_sources.append(source)
        
        # Sort by priority
        priority_order = {
            Priority.URGENT: 0,
            Priority.HIGH: 1,
            Priority.MEDIUM: 2,
            Priority.LOW: 3
        }
        
        return sorted(priority_sources, key=lambda s: priority_order.get(s.priority, 3))
    
    def get_stale_sources(self, threshold_hours: Optional[int] = None) -> List[SourceConfig]:
        """Get sources that need crawling."""
        if threshold_hours is None:
            threshold_hours = self.global_config.stale_threshold_hours
        
        all_sources = (
            self.guangdong + self.shandong + 
            self.inner_mongolia + self.sichuan
        )
        
        stale_sources = []
        for source in all_sources:
            if source.enabled and source.is_stale():
                stale_sources.append(source)
        
        return stale_sources
    
    def validate_source_coverage(self) -> Dict[str, Any]:
        """Validate that all provinces have adequate source coverage."""
        coverage_report = {}
        
        for province in [Province.GUANGDONG, Province.SHANDONG, Province.INNER_MONGOLIA]:
            sources = self.get_enabled_sources_by_province(province)
            
            # Check document class coverage
            covered_doc_classes = set()
            for source in sources:
                covered_doc_classes.update(source.doc_classes)
            
            missing_doc_classes = set(DocumentClass) - covered_doc_classes
            
            coverage_report[province.value] = {
                "total_sources": len(sources),
                "enabled_sources": len([s for s in sources if s.enabled]),
                "covered_doc_classes": list(covered_doc_classes),
                "missing_doc_classes": list(missing_doc_classes),
                "high_priority_sources": len([s for s in sources if s.priority == Priority.HIGH]),
                "coverage_complete": len(missing_doc_classes) == 0
            }
        
        return coverage_report
    
    class Config:
        use_enum_values = True