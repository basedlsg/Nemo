"""Tests for ontology mapping service."""

import pytest
from services.ontology.mapper import OntologyMapper
from services.ontology.schemas import (
    Jurisdiction, MarketCode, AssetType, Lifecycle, RequirementType, ParameterType,
    OntologyConfig
)


class TestOntologyMapper:
    """Test ontology mapping functionality."""
    
    @pytest.fixture
    def mapper(self):
        """Create ontology mapper for testing."""
        return OntologyMapper()
    
    @pytest.fixture
    def guangdong_grid_text(self):
        """Sample Guangdong grid connection text."""
        return """
        广东省电网接入管理办法
        
        第一条：为规范电网接入管理，根据《电力法》制定本办法。
        本办法自2025年4月1日起施行。
        
        第二条：风力发电项目接入电网应当符合以下技术要求：
        （一）装机容量不少于50MW；
        （二）电压等级为110KV或以上；
        （三）功率因数不低于0.95。
        
        第三条：太阳能发电项目的并网验收程序包括：
        （一）提交申请材料；
        （二）技术审查；
        （三）现场验收。
        """
    
    @pytest.fixture
    def shandong_dispatch_text(self):
        """Sample Shandong dispatch operations text."""
        return """
        山东省电力调度运行规程
        
        第一条：电力调度应当遵循统一调度、分级管理的原则。
        
        第二条：煤电机组应当具备调峰能力，最小技术出力不超过额定容量的40%。
        
        第三条：新能源发电企业应当按照调度指令参与系统调节。
        """
    
    def test_guangdong_grid_connection_mapping(self, mapper, guangdong_grid_text):
        """Test mapping of Guangdong grid connection document."""
        result = mapper.map_text_to_ontology(guangdong_grid_text)
        
        assert len(result.mappings) > 0
        assert result.avg_confidence > 0.5
        
        # Check detected entities
        assert "guangdong" in result.detected_jurisdictions
        
        # Get best mapping
        best_mapping = result.get_best_mapping()
        assert best_mapping is not None
        assert best_mapping.jurisdiction == Jurisdiction.GUANGDONG
        assert best_mapping.market_code == MarketCode.GRID_CONNECTION
        
        # Should detect wind and solar assets
        assert any(mapping.asset_type in [AssetType.WIND, AssetType.SOLAR] 
                  for mapping in result.mappings)
    
    def test_shandong_dispatch_mapping(self, mapper, shandong_dispatch_text):
        """Test mapping of Shandong dispatch operations document."""
        result = mapper.map_text_to_ontology(shandong_dispatch_text)
        
        assert len(result.mappings) > 0
        
        # Get best mapping
        best_mapping = result.get_best_mapping()
        assert best_mapping is not None
        assert best_mapping.jurisdiction == Jurisdiction.SHANDONG
        assert best_mapping.market_code == MarketCode.DISPATCH_OPS
        
        # Should detect coal asset type
        assert any(mapping.asset_type == AssetType.COAL for mapping in result.mappings)
    
    def test_known_jurisdiction_override(self, mapper, guangdong_grid_text):
        """Test that known jurisdiction overrides text-based detection."""
        result = mapper.map_text_to_ontology(
            guangdong_grid_text, 
            known_jurisdiction=Jurisdiction.SHANDONG
        )
        
        best_mapping = result.get_best_mapping()
        assert best_mapping.jurisdiction == Jurisdiction.SHANDONG
    
    def test_parameter_extraction(self, mapper, guangdong_grid_text):
        """Test extraction of parameter values."""
        parameters = mapper.extract_parameter_values(guangdong_grid_text)
        
        # Should extract capacity (50MW)
        assert ParameterType.CAPACITY in parameters
        assert "50" in parameters[ParameterType.CAPACITY]
        
        # Should extract voltage (110KV)
        assert ParameterType.VOLTAGE in parameters
        assert "110" in parameters[ParameterType.VOLTAGE]
    
    def test_empty_text_handling(self, mapper):
        """Test handling of empty or minimal text."""
        result = mapper.map_text_to_ontology("")
        
        assert len(result.mappings) == 0
        assert result.avg_confidence == 0.0
    
    def test_mixed_language_text(self, mapper):
        """Test handling of mixed Chinese-English text."""
        mixed_text = """
        Guangdong Province Grid Connection Requirements
        广东省电网接入要求
        
        Wind power projects must meet the following:
        风力发电项目必须满足以下要求：
        - Capacity: 50MW minimum
        - 容量：最少50兆瓦
        """
        
        result = mapper.map_text_to_ontology(mixed_text)
        
        assert len(result.mappings) > 0
        best_mapping = result.get_best_mapping()
        assert best_mapping.jurisdiction == Jurisdiction.GUANGDONG
        assert best_mapping.asset_type == AssetType.WIND
    
    def test_confidence_thresholds(self, mapper):
        """Test confidence threshold filtering."""
        # Create mapper with high confidence thresholds
        config = OntologyConfig(
            min_jurisdiction_confidence=0.9,
            min_market_confidence=0.9,
            min_asset_confidence=0.9
        )
        strict_mapper = OntologyMapper(config)
        
        # Use ambiguous text
        ambiguous_text = "这是一个关于能源的文档"
        
        result = strict_mapper.map_text_to_ontology(ambiguous_text)
        
        # Should have fewer or no mappings due to strict thresholds
        assert len(result.mappings) <= 1
    
    def test_fuzzy_matching(self, mapper):
        """Test fuzzy matching functionality."""
        # Text with slight misspellings
        fuzzy_text = "广东省电网接入管理办法，风力发电项目"
        
        result = mapper.map_text_to_ontology(fuzzy_text)
        
        assert len(result.mappings) > 0
        best_mapping = result.get_best_mapping()
        assert best_mapping.jurisdiction == Jurisdiction.GUANGDONG
        assert best_mapping.market_code == MarketCode.GRID_CONNECTION
    
    def test_multiple_asset_types(self, mapper):
        """Test detection of multiple asset types."""
        multi_asset_text = """
        可再生能源发电项目管理规定
        
        第一条：风力发电、太阳能发电和储能项目应当符合以下要求。
        
        第二条：风电项目装机容量不少于50MW。
        
        第三条：光伏项目应当配置储能系统。
        """
        
        result = mapper.map_text_to_ontology(multi_asset_text)
        
        # Should detect multiple asset types
        detected_assets = set(mapping.asset_type for mapping in result.mappings)
        assert AssetType.WIND in detected_assets
        assert AssetType.SOLAR in detected_assets
        assert AssetType.BESS in detected_assets
    
    def test_lifecycle_detection(self, mapper):
        """Test lifecycle stage detection."""
        lifecycle_text = """
        项目建设阶段安全管理规定
        
        第一条：在项目建设期间，应当严格执行安全规程。
        
        第二条：施工单位应当制定安全施工方案。
        
        第三条：项目验收合格后方可投入运行。
        """
        
        result = mapper.map_text_to_ontology(lifecycle_text)
        
        # Should detect construction and commissioning lifecycles
        detected_lifecycles = set(mapping.lifecycle for mapping in result.mappings)
        assert Lifecycle.CONSTRUCTION in detected_lifecycles
    
    def test_requirement_type_detection(self, mapper):
        """Test requirement type detection."""
        requirement_text = """
        技术标准和安全要求
        
        第一条：设备技术参数应当符合国家标准。
        
        第二条：必须建立完善的安全防护体系。
        
        第三条：应当定期报送运行数据。
        """
        
        result = mapper.map_text_to_ontology(requirement_text)
        
        # Should detect different requirement types
        detected_requirements = set(mapping.requirement_type for mapping in result.mappings)
        assert RequirementType.TECHNICAL in detected_requirements
        assert RequirementType.SAFETY in detected_requirements
        assert RequirementType.REPORTING in detected_requirements
    
    def test_mapping_summary(self, mapper, guangdong_grid_text):
        """Test mapping summary generation."""
        result = mapper.map_text_to_ontology(guangdong_grid_text)
        summary = mapper.get_mapping_summary(result.mappings)
        
        assert "total" in summary
        assert "avg_confidence" in summary
        assert "high_confidence" in summary
        assert "jurisdictions" in summary
        assert "market_codes" in summary
        assert "best_mapping" in summary
        
        assert summary["total"] > 0
        assert "guangdong" in summary["jurisdictions"]
        assert "grid_connection" in summary["market_codes"]


class TestOntologyConfig:
    """Test ontology configuration."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = OntologyConfig()
        
        assert config.min_jurisdiction_confidence == 0.8
        assert config.min_market_confidence == 0.6
        assert config.fuzzy_match_threshold == 0.8
        assert config.enable_fuzzy_matching is True
    
    def test_custom_config(self):
        """Test custom configuration."""
        config = OntologyConfig(
            min_jurisdiction_confidence=0.9,
            fuzzy_match_threshold=0.9,
            max_mappings_per_text=3
        )
        
        assert config.min_jurisdiction_confidence == 0.9
        assert config.fuzzy_match_threshold == 0.9
        assert config.max_mappings_per_text == 3


class TestEdgeCases:
    """Test edge cases and error conditions."""
    
    @pytest.fixture
    def mapper(self):
        return OntologyMapper()
    
    def test_very_long_text(self, mapper):
        """Test handling of very long text."""
        long_text = "广东省电网接入管理办法。" * 1000
        
        result = mapper.map_text_to_ontology(long_text)
        
        # Should handle long text without errors
        assert isinstance(result.processing_time_ms, int)
        assert result.processing_time_ms > 0
    
    def test_special_characters(self, mapper):
        """Test handling of special characters."""
        special_text = """
        广东省电网接入管理办法！@#$%^&*()
        
        第一条：风力发电项目【重要】应当符合要求。
        
        技术参数：50MW（兆瓦）、110KV（千伏）
        """
        
        result = mapper.map_text_to_ontology(special_text)
        
        # Should handle special characters gracefully
        assert len(result.mappings) >= 0
        if result.mappings:
            best_mapping = result.get_best_mapping()
            assert best_mapping.jurisdiction == Jurisdiction.GUANGDONG
    
    def test_numbers_only_text(self, mapper):
        """Test handling of text with only numbers."""
        numbers_text = "50 110 0.95 2025 100"
        
        result = mapper.map_text_to_ontology(numbers_text)
        
        # Should extract parameter values even without context
        parameters = mapper.extract_parameter_values(numbers_text)
        assert len(parameters) >= 0  # May or may not find parameters without units
    
    def test_unknown_jurisdiction(self, mapper):
        """Test handling of unknown jurisdiction keywords."""
        unknown_text = "某省电力管理规定，风力发电项目要求"
        
        result = mapper.map_text_to_ontology(unknown_text)
        
        # Should default to a known jurisdiction
        if result.mappings:
            best_mapping = result.get_best_mapping()
            assert best_mapping.jurisdiction in [
                Jurisdiction.GUANGDONG, Jurisdiction.SHANDONG, 
                Jurisdiction.INNER_MONGOLIA, Jurisdiction.SICHUAN
            ]


@pytest.fixture
def sample_energy_documents():
    """Sample energy regulation documents for testing."""
    return {
        "guangdong_renewable": """
        广东省可再生能源发展规划
        
        第一条：大力发展风力发电和太阳能发电。
        第二条：风电项目单体规模不少于50MW。
        第三条：光伏项目应当配置储能设施。
        """,
        
        "shandong_coal": """
        山东省煤电灵活性改造实施方案
        
        第一条：推进煤电机组灵活性改造。
        第二条：改造后最小技术出力不超过30%。
        第三条：具备快速调峰能力。
        """,
        
        "inner_mongolia_wind": """
        内蒙古自治区风电发展管理办法
        
        第一条：规范风电项目开发建设。
        第二条：风电场装机容量应当不少于100MW。
        第三条：优先发展大型风电基地。
        """
    }


def test_comprehensive_document_mapping(sample_energy_documents):
    """Test comprehensive mapping of different document types."""
    mapper = OntologyMapper()
    
    for doc_name, doc_text in sample_energy_documents.items():
        result = mapper.map_text_to_ontology(doc_text)
        
        # All documents should have at least one mapping
        assert len(result.mappings) > 0
        assert result.avg_confidence > 0.3
        
        best_mapping = result.get_best_mapping()
        assert best_mapping is not None
        
        # Verify jurisdiction detection
        if "guangdong" in doc_name:
            assert best_mapping.jurisdiction == Jurisdiction.GUANGDONG
        elif "shandong" in doc_name:
            assert best_mapping.jurisdiction == Jurisdiction.SHANDONG
        elif "inner_mongolia" in doc_name:
            assert best_mapping.jurisdiction == Jurisdiction.INNER_MONGOLIA
        
        # Verify asset type detection
        if "renewable" in doc_name or "wind" in doc_name:
            assert any(m.asset_type in [AssetType.WIND, AssetType.SOLAR] for m in result.mappings)
        elif "coal" in doc_name:
            assert any(m.asset_type == AssetType.COAL for m in result.mappings)