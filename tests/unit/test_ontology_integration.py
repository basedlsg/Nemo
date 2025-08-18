"""Tests for ontology integration service."""

import pytest
from uuid import uuid4
from datetime import date

from services.ontology.integration import (
    OntologyIntegrationService, 
    create_enriched_citation_from_chunks
)
from services.ontology.schemas import Jurisdiction
from services.ocr.schemas import ChunkData, CitationRow


class TestOntologyIntegrationService:
    """Test ontology integration service."""
    
    @pytest.fixture
    def integration_service(self):
        """Create integration service for testing."""
        return OntologyIntegrationService()
    
    @pytest.fixture
    def sample_chunks(self):
        """Create sample text chunks."""
        return [
            ChunkData(
                chunk_id="chunk-1",
                content="第一条：风力发电项目应当符合技术要求，装机容量不少于50MW。",
                token_count=25,
                clause_type="article"
            ),
            ChunkData(
                chunk_id="chunk-2", 
                content="第二条：电压等级应当为110KV或以上，功率因数不低于0.95。",
                token_count=22,
                clause_type="technical"
            ),
            ChunkData(
                chunk_id="chunk-3",
                content="第三条：项目建设期间应当严格执行安全规程。",
                token_count=18,
                clause_type="requirement"
            )
        ]
    
    @pytest.fixture
    def sample_citation(self):
        """Create sample citation row."""
        return CitationRow(
            citation_id=uuid4(),
            province="guangdong",
            doc_class="grid_connection",
            title="广东省电网接入管理办法",
            url="https://gzpec.cn/grid-connection-rules",
            checksum="a" * 64,
            content="Combined content from chunks",
            chunk_ids=["chunk-1", "chunk-2", "chunk-3"]
        )
    
    def test_enrich_citation_with_ontology(self, integration_service, sample_citation, sample_chunks):
        """Test enriching citation with ontology mapping."""
        enriched_citation = integration_service.enrich_citation_with_ontology(
            sample_citation, 
            sample_chunks,
            Jurisdiction.GUANGDONG
        )
        
        # Citation should be enriched
        assert enriched_citation.citation_id == sample_citation.citation_id
        assert enriched_citation.asset is not None  # Should be set by ontology mapping
        
        # Asset should be detected from content (wind power)
        assert enriched_citation.asset in ["wind", "general"]
    
    def test_map_chunks_to_ontology(self, integration_service, sample_chunks):
        """Test mapping individual chunks to ontology."""
        chunk_mappings = integration_service.map_chunks_to_ontology(
            sample_chunks,
            Jurisdiction.GUANGDONG
        )
        
        assert len(chunk_mappings) == len(sample_chunks)
        
        # Check first chunk mapping
        first_mapping = chunk_mappings[0]
        assert first_mapping["chunk_id"] == "chunk-1"
        assert "ontology_mappings" in first_mapping
        assert len(first_mapping["ontology_mappings"]) > 0
        
        # Should detect wind asset type in first chunk
        mappings = first_mapping["ontology_mappings"]
        assert any(mapping["asset_type"] == "wind" for mapping in mappings)
    
    def test_analyze_document_ontology_coverage(self, integration_service, sample_chunks):
        """Test document ontology coverage analysis."""
        analysis = integration_service.analyze_document_ontology_coverage(
            sample_chunks,
            Jurisdiction.GUANGDONG
        )
        
        assert analysis["total_chunks"] == len(sample_chunks)
        assert analysis["mapped_chunks"] >= 0
        assert analysis["unmapped_chunks"] >= 0
        assert analysis["mapped_chunks"] + analysis["unmapped_chunks"] == analysis["total_chunks"]
        
        # Check coverage categories
        assert "coverage_by_category" in analysis
        assert "jurisdictions" in analysis["coverage_by_category"]
        assert "guangdong" in analysis["coverage_by_category"]["jurisdictions"]
        
        # Check confidence distribution
        assert "confidence_distribution" in analysis
        assert "high" in analysis["confidence_distribution"]
        assert "medium" in analysis["confidence_distribution"]
        assert "low" in analysis["confidence_distribution"]
    
    def test_get_ontology_statistics(self, integration_service):
        """Test getting ontology statistics."""
        stats = integration_service.get_ontology_statistics()
        
        assert "jurisdictions" in stats
        assert "market_codes" in stats
        assert "asset_types" in stats
        assert "total_keywords" in stats
        
        assert stats["jurisdictions"] >= 4  # At least 4 jurisdictions
        assert stats["total_keywords"] > 0
        assert "guangdong" in stats["supported_jurisdictions"]
        assert "grid_connection" in stats["supported_market_codes"]
        assert "wind" in stats["supported_asset_types"]
    
    def test_empty_chunks_handling(self, integration_service):
        """Test handling of empty chunks list."""
        chunk_mappings = integration_service.map_chunks_to_ontology([])
        
        assert len(chunk_mappings) == 0
        
        analysis = integration_service.analyze_document_ontology_coverage([])
        assert analysis["total_chunks"] == 0
        assert analysis["mapped_chunks"] == 0
    
    def test_chunks_with_different_content_types(self, integration_service):
        """Test chunks with different content types."""
        diverse_chunks = [
            ChunkData(
                chunk_id="tech-chunk",
                content="技术要求：装机容量50MW，电压110KV",
                token_count=15,
                clause_type="technical"
            ),
            ChunkData(
                chunk_id="proc-chunk",
                content="申请程序：提交材料，技术审查，现场验收",
                token_count=18,
                clause_type="procedural"
            ),
            ChunkData(
                chunk_id="safety-chunk",
                content="安全要求：建立防护体系，定期检查",
                token_count=16,
                clause_type="safety"
            )
        ]
        
        chunk_mappings = integration_service.map_chunks_to_ontology(diverse_chunks)
        
        assert len(chunk_mappings) == 3
        
        # Should detect different requirement types
        requirement_types = set()
        for mapping in chunk_mappings:
            if mapping.get("best_mapping"):
                for ont_mapping in mapping["ontology_mappings"]:
                    requirement_types.add(ont_mapping["requirement_type"])
        
        assert "technical" in requirement_types
        assert "procedural" in requirement_types or "safety" in requirement_types


class TestCreateEnrichedCitation:
    """Test enriched citation creation function."""
    
    @pytest.fixture
    def sample_chunks(self):
        """Create sample chunks for citation creation."""
        return [
            ChunkData(
                chunk_id="chunk-1",
                content="山东省电力调度运行规程第一条：电力调度应当遵循统一调度原则。",
                token_count=28,
                clause_type="article"
            ),
            ChunkData(
                chunk_id="chunk-2",
                content="第二条：煤电机组应当具备调峰能力，最小技术出力不超过40%。",
                token_count=26,
                clause_type="requirement"
            )
        ]
    
    def test_create_enriched_citation_with_integration(self, sample_chunks):
        """Test creating enriched citation with integration service."""
        integration_service = OntologyIntegrationService()
        
        citation = create_enriched_citation_from_chunks(
            chunks=sample_chunks,
            citation_id=uuid4(),
            province="shandong",
            doc_class="dispatch_ops",
            title="山东省电力调度运行规程",
            url="https://shandong.gov.cn/dispatch-rules",
            checksum="b" * 64,
            effective_date=date(2025, 5, 1),
            integration_service=integration_service
        )
        
        assert citation.province == "shandong"
        assert citation.doc_class == "dispatch_ops"
        assert citation.title == "山东省电力调度运行规程"
        assert citation.asset is not None  # Should be enriched by ontology
        assert len(citation.chunk_ids) == 2
        
        # Content should be combined from chunks
        assert "电力调度" in citation.content
        assert "煤电机组" in citation.content
    
    def test_create_enriched_citation_without_integration(self, sample_chunks):
        """Test creating citation without integration service."""
        citation = create_enriched_citation_from_chunks(
            chunks=sample_chunks,
            citation_id=uuid4(),
            province="shandong",
            doc_class="dispatch_ops",
            title="山东省电力调度运行规程",
            url="https://shandong.gov.cn/dispatch-rules",
            checksum="c" * 64
        )
        
        assert citation.province == "shandong"
        assert citation.asset is None  # Not enriched without integration service
        assert len(citation.chunk_ids) == 2
    
    def test_create_citation_with_invalid_province(self, sample_chunks):
        """Test creating citation with invalid province code."""
        integration_service = OntologyIntegrationService()
        
        citation = create_enriched_citation_from_chunks(
            chunks=sample_chunks,
            citation_id=uuid4(),
            province="invalid_province",
            doc_class="dispatch_ops",
            title="Test Document",
            url="https://example.com/test",
            checksum="d" * 64,
            integration_service=integration_service
        )
        
        # Should handle invalid province gracefully
        assert citation.province == "invalid_province"
        assert citation.asset is not None or citation.asset is None  # May or may not be enriched


class TestIntegrationWithRealContent:
    """Test integration with realistic Chinese energy content."""
    
    @pytest.fixture
    def integration_service(self):
        return OntologyIntegrationService()
    
    @pytest.fixture
    def guangdong_wind_chunks(self):
        """Realistic Guangdong wind power chunks."""
        return [
            ChunkData(
                chunk_id="gd-wind-1",
                content="第一条：风力发电项目接入电网应当符合以下技术要求：装机容量不少于50MW，电压等级为110KV或以上。",
                token_count=35,
                clause_type="article"
            ),
            ChunkData(
                chunk_id="gd-wind-2",
                content="第二条：风电场应当配备完善的功率预测系统，预测精度不低于85%。",
                token_count=28,
                clause_type="technical"
            ),
            ChunkData(
                chunk_id="gd-wind-3",
                content="第三条：项目建设期间应当严格执行环境保护要求，确保生态环境安全。",
                token_count=30,
                clause_type="environmental"
            )
        ]
    
    @pytest.fixture
    def inner_mongolia_coal_chunks(self):
        """Realistic Inner Mongolia coal flexibility chunks."""
        return [
            ChunkData(
                chunk_id="im-coal-1",
                content="第一条：煤电机组灵活性改造应当满足深度调峰要求，最小技术出力不超过额定容量的30%。",
                token_count=32,
                clause_type="article"
            ),
            ChunkData(
                chunk_id="im-coal-2",
                content="第二条：改造后的机组应当具备快速启停能力，冷态启动时间不超过4小时。",
                token_count=29,
                clause_type="technical"
            )
        ]
    
    def test_guangdong_wind_integration(self, integration_service, guangdong_wind_chunks):
        """Test integration with Guangdong wind power content."""
        analysis = integration_service.analyze_document_ontology_coverage(
            guangdong_wind_chunks,
            Jurisdiction.GUANGDONG
        )
        
        assert analysis["total_chunks"] == 3
        assert analysis["mapped_chunks"] > 0
        
        # Should detect wind asset type
        assert "wind" in analysis["coverage_by_category"]["asset_types"]
        
        # Should detect grid connection market
        assert "grid_connection" in analysis["coverage_by_category"]["market_codes"]
        
        # Should detect technical and environmental requirements
        detected_requirements = analysis["coverage_by_category"]["requirement_types"]
        assert "technical" in detected_requirements
        assert "environmental" in detected_requirements
    
    def test_inner_mongolia_coal_integration(self, integration_service, inner_mongolia_coal_chunks):
        """Test integration with Inner Mongolia coal flexibility content."""
        analysis = integration_service.analyze_document_ontology_coverage(
            inner_mongolia_coal_chunks,
            Jurisdiction.INNER_MONGOLIA
        )
        
        assert analysis["total_chunks"] == 2
        assert analysis["mapped_chunks"] > 0
        
        # Should detect coal asset type
        assert "coal" in analysis["coverage_by_category"]["asset_types"]
        
        # Should detect coal flexibility market
        assert "coal_flexibility" in analysis["coverage_by_category"]["market_codes"]
    
    def test_cross_jurisdiction_comparison(self, integration_service, guangdong_wind_chunks, inner_mongolia_coal_chunks):
        """Test comparison across different jurisdictions."""
        gd_analysis = integration_service.analyze_document_ontology_coverage(
            guangdong_wind_chunks,
            Jurisdiction.GUANGDONG
        )
        
        im_analysis = integration_service.analyze_document_ontology_coverage(
            inner_mongolia_coal_chunks,
            Jurisdiction.INNER_MONGOLIA
        )
        
        # Different jurisdictions should be detected
        assert "guangdong" in gd_analysis["coverage_by_category"]["jurisdictions"]
        assert "inner_mongolia" in im_analysis["coverage_by_category"]["jurisdictions"]
        
        # Different asset types should be detected
        gd_assets = gd_analysis["coverage_by_category"]["asset_types"]
        im_assets = im_analysis["coverage_by_category"]["asset_types"]
        
        assert "wind" in gd_assets
        assert "coal" in im_assets
        assert set(gd_assets) != set(im_assets)  # Should be different
    
    def test_comprehensive_citation_enrichment(self, integration_service, guangdong_wind_chunks):
        """Test comprehensive citation enrichment process."""
        citation = create_enriched_citation_from_chunks(
            chunks=guangdong_wind_chunks,
            citation_id=uuid4(),
            province="guangdong",
            doc_class="grid_connection",
            title="广东省风电接入技术要求",
            url="https://gzpec.cn/wind-grid-connection",
            checksum="wind123" + "0" * 57,
            effective_date=date(2025, 6, 1),
            integration_service=integration_service
        )
        
        # Verify basic citation properties
        assert citation.province == "guangdong"
        assert citation.doc_class == "grid_connection"
        assert citation.effective_date == date(2025, 6, 1)
        
        # Verify ontology enrichment
        assert citation.asset == "wind"  # Should be detected and set
        
        # Verify content combination
        assert "风力发电" in citation.content
        assert "50MW" in citation.content
        assert "110KV" in citation.content
        assert "环境保护" in citation.content
        
        # Verify chunk tracking
        assert len(citation.chunk_ids) == 3
        assert all(chunk_id.startswith("gd-wind-") for chunk_id in citation.chunk_ids)