"""Schemas for ontology mapping service."""

from enum import Enum
from typing import Dict, List, Optional, Any
from uuid import UUID, uuid4
from datetime import datetime

from pydantic import BaseModel, Field


class Jurisdiction(str, Enum):
    """Chinese provinces/jurisdictions."""
    GUANGDONG = "guangdong"
    SHANDONG = "shandong" 
    INNER_MONGOLIA = "inner_mongolia"
    SICHUAN = "sichuan"  # Queued


class MarketCode(str, Enum):
    """Energy market codes."""
    GRID_CONNECTION = "grid_connection"
    MARKET_RULES = "market_rules"
    DISPATCH_OPS = "dispatch_ops"
    RENEWABLE_POLICY = "renewable_policy"
    STORAGE_POLICY = "storage_policy"
    COAL_FLEXIBILITY = "coal_flexibility"


class AssetType(str, Enum):
    """Energy asset types."""
    WIND = "wind"
    SOLAR = "solar"
    BESS = "bess"  # Battery Energy Storage System
    COAL = "coal"
    HYDRO = "hydro"
    NUCLEAR = "nuclear"
    GAS = "gas"
    GENERAL = "general"  # Applies to multiple asset types


class Lifecycle(str, Enum):
    """Asset lifecycle stages."""
    PLANNING = "planning"
    DEVELOPMENT = "development"
    CONSTRUCTION = "construction"
    COMMISSIONING = "commissioning"
    OPERATION = "operation"
    MAINTENANCE = "maintenance"
    DECOMMISSIONING = "decommissioning"
    GENERAL = "general"  # Applies to multiple stages


class RequirementType(str, Enum):
    """Types of regulatory requirements."""
    TECHNICAL = "technical"
    PROCEDURAL = "procedural"
    FINANCIAL = "financial"
    ENVIRONMENTAL = "environmental"
    SAFETY = "safety"
    REPORTING = "reporting"
    COMPLIANCE = "compliance"
    GENERAL = "general"


class ParameterType(str, Enum):
    """Types of parameters in requirements."""
    CAPACITY = "capacity"
    VOLTAGE = "voltage"
    FREQUENCY = "frequency"
    POWER_FACTOR = "power_factor"
    EFFICIENCY = "efficiency"
    TIMELINE = "timeline"
    COST = "cost"
    PERCENTAGE = "percentage"
    DISTANCE = "distance"
    TEMPERATURE = "temperature"
    GENERAL = "general"


class OntologyNode(BaseModel):
    """Base class for ontology nodes."""
    
    node_id: UUID = Field(default_factory=uuid4)
    name: str = Field(..., description="Human-readable name")
    name_zh: str = Field(..., description="Chinese name")
    description: Optional[str] = Field(None, description="Description")
    keywords: List[str] = Field(default_factory=list, description="Keywords for matching")
    keywords_zh: List[str] = Field(default_factory=list, description="Chinese keywords")
    confidence: float = Field(default=1.0, description="Confidence in classification")
    
    class Config:
        use_enum_values = True


class JurisdictionNode(OntologyNode):
    """Jurisdiction/province node."""
    jurisdiction: Jurisdiction
    market_codes: List[MarketCode] = Field(default_factory=list)


class MarketNode(OntologyNode):
    """Market/regulation code node."""
    market_code: MarketCode
    jurisdiction: Jurisdiction
    asset_types: List[AssetType] = Field(default_factory=list)


class AssetNode(OntologyNode):
    """Asset type node."""
    asset_type: AssetType
    market_code: MarketCode
    jurisdiction: Jurisdiction
    lifecycles: List[Lifecycle] = Field(default_factory=list)


class LifecycleNode(OntologyNode):
    """Lifecycle stage node."""
    lifecycle: Lifecycle
    asset_type: AssetType
    market_code: MarketCode
    jurisdiction: Jurisdiction
    requirement_types: List[RequirementType] = Field(default_factory=list)


class RequirementNode(OntologyNode):
    """Requirement type node."""
    requirement_type: RequirementType
    lifecycle: Lifecycle
    asset_type: AssetType
    market_code: MarketCode
    jurisdiction: Jurisdiction
    parameter_types: List[ParameterType] = Field(default_factory=list)


class ParameterNode(OntologyNode):
    """Parameter node."""
    parameter_type: ParameterType
    requirement_type: RequirementType
    lifecycle: Lifecycle
    asset_type: AssetType
    market_code: MarketCode
    jurisdiction: Jurisdiction
    unit: Optional[str] = Field(None, description="Unit of measurement")
    value_range: Optional[str] = Field(None, description="Expected value range")


class CitationMapping(BaseModel):
    """Maps a citation to ontology nodes."""
    
    citation_id: UUID
    jurisdiction: Jurisdiction
    market_code: MarketCode
    asset_type: AssetType
    lifecycle: Lifecycle
    requirement_type: RequirementType
    parameter_type: Optional[ParameterType] = None
    
    # Confidence scores for each level
    jurisdiction_confidence: float = Field(default=1.0)
    market_confidence: float = Field(default=0.0)
    asset_confidence: float = Field(default=0.0)
    lifecycle_confidence: float = Field(default=0.0)
    requirement_confidence: float = Field(default=0.0)
    parameter_confidence: float = Field(default=0.0)
    
    # Metadata
    mapped_at: datetime = Field(default_factory=datetime.utcnow)
    mapped_by: str = Field(default="auto", description="Mapping method")
    
    def get_overall_confidence(self) -> float:
        """Calculate overall mapping confidence."""
        scores = [
            self.jurisdiction_confidence,
            self.market_confidence,
            self.asset_confidence,
            self.lifecycle_confidence,
            self.requirement_confidence
        ]
        
        if self.parameter_confidence > 0:
            scores.append(self.parameter_confidence)
        
        return sum(scores) / len(scores)
    
    def get_ontology_path(self) -> str:
        """Get hierarchical ontology path."""
        path_parts = [
            self.jurisdiction.value,
            self.market_code.value,
            self.asset_type.value,
            self.lifecycle.value,
            self.requirement_type.value
        ]
        
        if self.parameter_type:
            path_parts.append(self.parameter_type.value)
        
        return " → ".join(path_parts)
    
    class Config:
        use_enum_values = True
        json_encoders = {
            UUID: str,
            datetime: lambda v: v.isoformat()
        }


class OntologyMappingResult(BaseModel):
    """Result of ontology mapping operation."""
    
    text_content: str
    mappings: List[CitationMapping] = Field(default_factory=list)
    processing_time_ms: int = Field(default=0)
    
    # Analysis metadata
    total_matches: int = Field(default=0)
    high_confidence_matches: int = Field(default=0)
    avg_confidence: float = Field(default=0.0)
    
    # Detected entities
    detected_jurisdictions: List[str] = Field(default_factory=list)
    detected_assets: List[str] = Field(default_factory=list)
    detected_requirements: List[str] = Field(default_factory=list)
    
    def get_best_mapping(self) -> Optional[CitationMapping]:
        """Get the mapping with highest confidence."""
        if not self.mappings:
            return None
        
        return max(self.mappings, key=lambda m: m.get_overall_confidence())
    
    def get_mappings_by_confidence(self, min_confidence: float = 0.5) -> List[CitationMapping]:
        """Get mappings above confidence threshold."""
        return [
            mapping for mapping in self.mappings
            if mapping.get_overall_confidence() >= min_confidence
        ]


class OntologyConfig(BaseModel):
    """Configuration for ontology mapping."""
    
    # Confidence thresholds
    min_jurisdiction_confidence: float = Field(default=0.8)
    min_market_confidence: float = Field(default=0.6)
    min_asset_confidence: float = Field(default=0.5)
    min_lifecycle_confidence: float = Field(default=0.4)
    min_requirement_confidence: float = Field(default=0.4)
    min_parameter_confidence: float = Field(default=0.3)
    
    # Matching settings
    fuzzy_match_threshold: float = Field(default=0.8)
    keyword_weight: float = Field(default=0.7)
    context_weight: float = Field(default=0.3)
    
    # Processing settings
    max_mappings_per_text: int = Field(default=5)
    enable_fuzzy_matching: bool = Field(default=True)
    enable_context_analysis: bool = Field(default=True)
    
    class Config:
        env_file = ".env"