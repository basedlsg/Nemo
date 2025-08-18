"""Ontology mapping service for Chinese energy regulation text."""

import re
import time
import logging
from typing import List, Dict, Set, Optional, Tuple
from collections import defaultdict

from fuzzywuzzy import fuzz, process

from .schemas import (
    CitationMapping, OntologyMappingResult, OntologyConfig,
    Jurisdiction, MarketCode, AssetType, Lifecycle, RequirementType, ParameterType
)
from .knowledge_base import EnergyOntologyKB

logger = logging.getLogger(__name__)


class OntologyMapper:
    """Maps Chinese energy regulation text to structured ontology."""
    
    def __init__(self, config: Optional[OntologyConfig] = None):
        """Initialize ontology mapper."""
        self.config = config or OntologyConfig()
        self.kb = EnergyOntologyKB()
        
        # Compile regex patterns for efficiency
        self._compile_patterns()
        
        logger.info("Initialized ontology mapper")
    
    def map_text_to_ontology(self, text: str, known_jurisdiction: Optional[Jurisdiction] = None) -> OntologyMappingResult:
        """
        Map text content to ontology structure.
        
        Args:
            text: Text content to map
            known_jurisdiction: Known jurisdiction if available
            
        Returns:
            Ontology mapping result with confidence scores
        """
        start_time = time.time()
        
        try:
            logger.info(f"Mapping text to ontology ({len(text)} characters)")
            
            # Step 1: Extract entities and keywords
            entities = self._extract_entities(text)
            
            # Step 2: Determine jurisdiction
            jurisdiction = known_jurisdiction or self._determine_jurisdiction(text, entities)
            
            # Step 3: Map to ontology hierarchy
            mappings = self._create_mappings(text, entities, jurisdiction)
            
            # Step 4: Calculate result metadata
            processing_time = int((time.time() - start_time) * 1000)
            
            result = OntologyMappingResult(
                text_content=text,
                mappings=mappings,
                processing_time_ms=processing_time,
                total_matches=len(mappings),
                high_confidence_matches=len([m for m in mappings if m.get_overall_confidence() >= 0.7]),
                avg_confidence=sum(m.get_overall_confidence() for m in mappings) / len(mappings) if mappings else 0.0,
                detected_jurisdictions=entities.get("jurisdictions", []),
                detected_assets=entities.get("assets", []),
                detected_requirements=entities.get("requirements", [])
            )
            
            logger.info(f"Ontology mapping complete: {len(mappings)} mappings, "
                       f"avg confidence: {result.avg_confidence:.2f}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error mapping text to ontology: {e}")
            return OntologyMappingResult(
                text_content=text,
                processing_time_ms=int((time.time() - start_time) * 1000)
            )
    
    def _extract_entities(self, text: str) -> Dict[str, List[str]]:
        """Extract entities and keywords from text."""
        entities = {
            "jurisdictions": [],
            "markets": [],
            "assets": [],
            "lifecycles": [],
            "requirements": [],
            "parameters": []
        }
        
        # Convert to lowercase for matching
        text_lower = text.lower()
        
        # Extract jurisdiction entities
        for keyword in self.kb.keyword_to_jurisdiction:
            if keyword in text_lower:
                jurisdiction = self.kb.get_jurisdiction_by_keyword(keyword)
                if jurisdiction and jurisdiction.value not in entities["jurisdictions"]:
                    entities["jurisdictions"].append(jurisdiction.value)
        
        # Extract market entities
        for keyword in self.kb.keyword_to_market:
            if keyword in text_lower:
                market = self.kb.get_market_by_keyword(keyword)
                if market and market.value not in entities["markets"]:
                    entities["markets"].append(market.value)
        
        # Extract asset entities
        for keyword in self.kb.keyword_to_asset:
            if keyword in text_lower:
                asset = self.kb.get_asset_by_keyword(keyword)
                if asset and asset.value not in entities["assets"]:
                    entities["assets"].append(asset.value)
        
        # Extract lifecycle entities
        for keyword in self.kb.keyword_to_lifecycle:
            if keyword in text_lower:
                lifecycle = self.kb.get_lifecycle_by_keyword(keyword)
                if lifecycle and lifecycle.value not in entities["lifecycles"]:
                    entities["lifecycles"].append(lifecycle.value)
        
        # Extract requirement entities
        for keyword in self.kb.keyword_to_requirement:
            if keyword in text_lower:
                requirement = self.kb.get_requirement_by_keyword(keyword)
                if requirement and requirement.value not in entities["requirements"]:
                    entities["requirements"].append(requirement.value)
        
        # Extract parameter entities
        for keyword in self.kb.keyword_to_parameter:
            if keyword in text_lower:
                parameter = self.kb.get_parameter_by_keyword(keyword)
                if parameter and parameter.value not in entities["parameters"]:
                    entities["parameters"].append(parameter.value)
        
        return entities
    
    def _determine_jurisdiction(self, text: str, entities: Dict[str, List[str]]) -> Jurisdiction:
        """Determine jurisdiction from text and entities."""
        
        # Check explicit jurisdiction mentions
        if entities["jurisdictions"]:
            jurisdiction_str = entities["jurisdictions"][0]
            try:
                return Jurisdiction(jurisdiction_str)
            except ValueError:
                pass
        
        # Check for jurisdiction-specific patterns
        jurisdiction_patterns = {
            Jurisdiction.GUANGDONG: [
                r"广东省?", r"粤", r"珠三角", r"gzpec", r"guangdong"
            ],
            Jurisdiction.SHANDONG: [
                r"山东省?", r"鲁", r"shandong", r"渤海湾"
            ],
            Jurisdiction.INNER_MONGOLIA: [
                r"内蒙古", r"蒙", r"inner.?mongolia"
            ],
            Jurisdiction.SICHUAN: [
                r"四川省?", r"川", r"sichuan", r"成都"
            ]
        }
        
        text_lower = text.lower()
        jurisdiction_scores = {}
        
        for jurisdiction, patterns in jurisdiction_patterns.items():
            score = 0
            for pattern in patterns:
                matches = len(re.findall(pattern, text_lower, re.IGNORECASE))
                score += matches
            
            if score > 0:
                jurisdiction_scores[jurisdiction] = score
        
        if jurisdiction_scores:
            return max(jurisdiction_scores.items(), key=lambda x: x[1])[0]
        
        # Default to Guangdong if no clear jurisdiction
        return Jurisdiction.GUANGDONG
    
    def _create_mappings(
        self, 
        text: str, 
        entities: Dict[str, List[str]], 
        jurisdiction: Jurisdiction
    ) -> List[CitationMapping]:
        """Create ontology mappings from extracted entities."""
        
        mappings = []
        
        # If no specific entities found, create a general mapping
        if not any(entities.values()):
            general_mapping = self._create_general_mapping(text, jurisdiction)
            if general_mapping:
                mappings.append(general_mapping)
            return mappings
        
        # Create mappings for each combination of detected entities
        market_codes = [MarketCode(m) for m in entities["markets"]] or [MarketCode.GRID_CONNECTION]
        asset_types = [AssetType(a) for a in entities["assets"]] or [AssetType.GENERAL]
        lifecycles = [Lifecycle(l) for l in entities["lifecycles"]] or [Lifecycle.GENERAL]
        requirements = [RequirementType(r) for r in entities["requirements"]] or [RequirementType.GENERAL]
        parameters = [ParameterType(p) for p in entities["parameters"]] if entities["parameters"] else [None]
        
        # Limit combinations to avoid explosion
        max_mappings = self.config.max_mappings_per_text
        mapping_count = 0
        
        for market in market_codes[:2]:  # Limit markets
            for asset in asset_types[:2]:  # Limit assets
                for lifecycle in lifecycles[:2]:  # Limit lifecycles
                    for requirement in requirements[:2]:  # Limit requirements
                        for parameter in parameters[:2]:  # Limit parameters
                            if mapping_count >= max_mappings:
                                break
                            
                            mapping = self._create_specific_mapping(
                                text, jurisdiction, market, asset, lifecycle, requirement, parameter
                            )
                            
                            if mapping and mapping.get_overall_confidence() >= 0.3:
                                mappings.append(mapping)
                                mapping_count += 1
        
        # Sort by confidence and return top mappings
        mappings.sort(key=lambda m: m.get_overall_confidence(), reverse=True)
        return mappings[:max_mappings]
    
    def _create_general_mapping(self, text: str, jurisdiction: Jurisdiction) -> Optional[CitationMapping]:
        """Create a general mapping when no specific entities are detected."""
        
        # Determine most likely market code based on text content
        market_code = self._infer_market_code(text)
        
        mapping = CitationMapping(
            citation_id=None,  # Will be set by caller
            jurisdiction=jurisdiction,
            market_code=market_code,
            asset_type=AssetType.GENERAL,
            lifecycle=Lifecycle.GENERAL,
            requirement_type=RequirementType.GENERAL,
            parameter_type=None,
            jurisdiction_confidence=0.8,
            market_confidence=0.4,
            asset_confidence=0.3,
            lifecycle_confidence=0.3,
            requirement_confidence=0.3,
            parameter_confidence=0.0
        )
        
        return mapping
    
    def _create_specific_mapping(
        self,
        text: str,
        jurisdiction: Jurisdiction,
        market: MarketCode,
        asset: AssetType,
        lifecycle: Lifecycle,
        requirement: RequirementType,
        parameter: Optional[ParameterType]
    ) -> Optional[CitationMapping]:
        """Create specific mapping with confidence calculation."""
        
        # Calculate confidence scores
        jurisdiction_conf = self._calculate_jurisdiction_confidence(text, jurisdiction)
        market_conf = self._calculate_market_confidence(text, market)
        asset_conf = self._calculate_asset_confidence(text, asset)
        lifecycle_conf = self._calculate_lifecycle_confidence(text, lifecycle)
        requirement_conf = self._calculate_requirement_confidence(text, requirement)
        parameter_conf = self._calculate_parameter_confidence(text, parameter) if parameter else 0.0
        
        # Check minimum thresholds
        if (jurisdiction_conf < self.config.min_jurisdiction_confidence or
            market_conf < self.config.min_market_confidence or
            asset_conf < self.config.min_asset_confidence):
            return None
        
        mapping = CitationMapping(
            citation_id=None,  # Will be set by caller
            jurisdiction=jurisdiction,
            market_code=market,
            asset_type=asset,
            lifecycle=lifecycle,
            requirement_type=requirement,
            parameter_type=parameter,
            jurisdiction_confidence=jurisdiction_conf,
            market_confidence=market_conf,
            asset_confidence=asset_conf,
            lifecycle_confidence=lifecycle_conf,
            requirement_confidence=requirement_conf,
            parameter_confidence=parameter_conf
        )
        
        return mapping
    
    def _calculate_jurisdiction_confidence(self, text: str, jurisdiction: Jurisdiction) -> float:
        """Calculate confidence for jurisdiction mapping."""
        node = self.kb.jurisdictions[jurisdiction]
        return self._calculate_keyword_confidence(text, node.keywords + node.keywords_zh)
    
    def _calculate_market_confidence(self, text: str, market: MarketCode) -> float:
        """Calculate confidence for market code mapping."""
        node = self.kb.markets[market]
        return self._calculate_keyword_confidence(text, node.keywords + node.keywords_zh)
    
    def _calculate_asset_confidence(self, text: str, asset: AssetType) -> float:
        """Calculate confidence for asset type mapping."""
        node = self.kb.assets[asset]
        return self._calculate_keyword_confidence(text, node.keywords + node.keywords_zh)
    
    def _calculate_lifecycle_confidence(self, text: str, lifecycle: Lifecycle) -> float:
        """Calculate confidence for lifecycle mapping."""
        node = self.kb.lifecycles[lifecycle]
        return self._calculate_keyword_confidence(text, node.keywords + node.keywords_zh)
    
    def _calculate_requirement_confidence(self, text: str, requirement: RequirementType) -> float:
        """Calculate confidence for requirement type mapping."""
        node = self.kb.requirements[requirement]
        return self._calculate_keyword_confidence(text, node.keywords + node.keywords_zh)
    
    def _calculate_parameter_confidence(self, text: str, parameter: Optional[ParameterType]) -> float:
        """Calculate confidence for parameter type mapping."""
        if not parameter:
            return 0.0
        
        node = self.kb.parameters[parameter]
        return self._calculate_keyword_confidence(text, node.keywords + node.keywords_zh)
    
    def _calculate_keyword_confidence(self, text: str, keywords: List[str]) -> float:
        """Calculate confidence based on keyword matches."""
        if not keywords:
            return 0.0
        
        text_lower = text.lower()
        total_score = 0.0
        max_possible_score = 0.0
        
        for keyword in keywords:
            keyword_lower = keyword.lower()
            max_possible_score += 1.0
            
            # Exact match
            if keyword_lower in text_lower:
                total_score += 1.0
            # Fuzzy match if enabled
            elif self.config.enable_fuzzy_matching:
                # Use fuzzy matching for partial matches
                words = text_lower.split()
                best_ratio = 0
                
                for word in words:
                    ratio = fuzz.ratio(keyword_lower, word) / 100.0
                    if ratio > best_ratio:
                        best_ratio = ratio
                
                if best_ratio >= self.config.fuzzy_match_threshold:
                    total_score += best_ratio
        
        return total_score / max_possible_score if max_possible_score > 0 else 0.0
    
    def _infer_market_code(self, text: str) -> MarketCode:
        """Infer most likely market code from text content."""
        text_lower = text.lower()
        
        # Check for specific market indicators
        if any(keyword in text_lower for keyword in ["并网", "接入", "grid", "connection"]):
            return MarketCode.GRID_CONNECTION
        elif any(keyword in text_lower for keyword in ["市场", "交易", "market", "trading"]):
            return MarketCode.MARKET_RULES
        elif any(keyword in text_lower for keyword in ["调度", "运行", "dispatch", "operation"]):
            return MarketCode.DISPATCH_OPS
        elif any(keyword in text_lower for keyword in ["可再生", "新能源", "renewable"]):
            return MarketCode.RENEWABLE_POLICY
        elif any(keyword in text_lower for keyword in ["储能", "storage", "battery"]):
            return MarketCode.STORAGE_POLICY
        elif any(keyword in text_lower for keyword in ["煤电", "火电", "coal", "thermal"]):
            return MarketCode.COAL_FLEXIBILITY
        else:
            return MarketCode.GRID_CONNECTION  # Default
    
    def _compile_patterns(self):
        """Compile regex patterns for efficient matching."""
        # Compile common patterns
        self.capacity_pattern = re.compile(r'(\d+(?:\.\d+)?)\s*(?:MW|兆瓦|千瓦|KW)', re.IGNORECASE)
        self.voltage_pattern = re.compile(r'(\d+(?:\.\d+)?)\s*(?:KV|千伏|伏)', re.IGNORECASE)
        self.percentage_pattern = re.compile(r'(\d+(?:\.\d+)?)\s*%', re.IGNORECASE)
        self.timeline_pattern = re.compile(r'(\d+)\s*(?:天|日|月|年|days?|months?|years?)', re.IGNORECASE)
    
    def extract_parameter_values(self, text: str) -> Dict[ParameterType, List[str]]:
        """Extract specific parameter values from text."""
        values = defaultdict(list)
        
        # Extract capacity values
        capacity_matches = self.capacity_pattern.findall(text)
        if capacity_matches:
            values[ParameterType.CAPACITY].extend(capacity_matches)
        
        # Extract voltage values
        voltage_matches = self.voltage_pattern.findall(text)
        if voltage_matches:
            values[ParameterType.VOLTAGE].extend(voltage_matches)
        
        # Extract percentage values
        percentage_matches = self.percentage_pattern.findall(text)
        if percentage_matches:
            values[ParameterType.PERCENTAGE].extend(percentage_matches)
        
        # Extract timeline values
        timeline_matches = self.timeline_pattern.findall(text)
        if timeline_matches:
            values[ParameterType.TIMELINE].extend(timeline_matches)
        
        return dict(values)
    
    def get_mapping_summary(self, mappings: List[CitationMapping]) -> Dict[str, Any]:
        """Get summary statistics for mappings."""
        if not mappings:
            return {"total": 0}
        
        summary = {
            "total": len(mappings),
            "avg_confidence": sum(m.get_overall_confidence() for m in mappings) / len(mappings),
            "high_confidence": len([m for m in mappings if m.get_overall_confidence() >= 0.7]),
            "medium_confidence": len([m for m in mappings if 0.4 <= m.get_overall_confidence() < 0.7]),
            "low_confidence": len([m for m in mappings if m.get_overall_confidence() < 0.4]),
            "jurisdictions": list(set(m.jurisdiction.value for m in mappings)),
            "market_codes": list(set(m.market_code.value for m in mappings)),
            "asset_types": list(set(m.asset_type.value for m in mappings)),
            "best_mapping": mappings[0].get_ontology_path() if mappings else None
        }
        
        return summary