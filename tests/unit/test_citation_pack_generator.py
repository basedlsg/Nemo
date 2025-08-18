"""Tests for citation pack generator."""
import pytest
import asyncio
import tempfile
import os
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime

from services.citation.pack_generator import (
    CitationPackGenerator,
    CitationData,
    PackMetadata,
    generate_citation_pack,
    get_pack_generator
)


class TestCitationData:
    """Test CitationData model."""
    
    def test_citation_data_creation(self):
        """Test creating CitationData instance."""
        citation = CitationData(
            citation_id="TEST-001",
            title="测试文档",
            content="这是一个测试文档的内容。",
            effective_date="2023-01-01",
            province="广东",
            asset_type="分布式光伏",
            doc_class="管理办法"
        )
        
        assert citation.citation_id == "TEST-001"
        assert citation.title == "测试文档"
        assert citation.content == "这是一个测试文档的内容。"
        assert citation.province == "广东"
    
    def test_citation_data_optional_fields(self):
        """Test CitationData with optional fields."""
        citation = CitationData(
            citation_id="TEST-002",
            title="测试文档2",
            content="内容2",
            effective_date="2023-02-01",
            province="山东",
            asset_type="风电",
            doc_class="实施细则",
            source_url="https://example.com/doc2",
            page_number=5,
            confidence_score=0.95
        )
        
        assert citation.source_url == "https://example.com/doc2"
        assert citation.page_number == 5
        assert citation.confidence_score == 0.95


class TestPackMetadata:
    """Test PackMetadata model."""
    
    def test_pack_metadata_creation(self):
        """Test creating PackMetadata instance."""
        metadata = PackMetadata(
            query="分布式光伏并网要求",
            province="广东",
            asset_type="分布式光伏",
            doc_class="管理办法",
            total_citations=5,
            pack_id="test_pack_001"
        )
        
        assert metadata.query == "分布式光伏并网要求"
        assert metadata.province == "广东"
        assert metadata.total_citations == 5
        assert metadata.language == "zh-CN"  # Default value
    
    def test_pack_metadata_generated_at(self):
        """Test generated_at field is automatically set."""
        metadata = PackMetadata(
            query="测试查询",
            province="山东",
            asset_type="风电",
            doc_class="实施细则",
            total_citations=3,
            pack_id="test_pack_002"
        )
        
        assert metadata.generated_at is not None
        # Should be a valid ISO format timestamp
        datetime.fromisoformat(metadata.generated_at.replace('Z', '+00:00'))


class TestCitationPackGenerator:
    """Test CitationPackGenerator class."""
    
    @pytest.fixture
    def sample_citations(self):
        """Sample citations for testing."""
        return [
            CitationData(
                citation_id="GD-SOLAR-001",
                title="广东省分布式光伏发电项目管理暂行办法",
                content="为规范广东省分布式光伏发电项目管理，促进分布式光伏发电健康有序发展，根据国家发展改革委、国家能源局相关政策文件，结合我省实际，制定本办法。",
                effective_date="2023-01-01",
                source_url="https://drc.gd.gov.cn/test1.html",
                province="广东",
                asset_type="分布式光伏",
                doc_class="管理办法",
                confidence_score=0.95
            ),
            CitationData(
                citation_id="GD-SOLAR-002",
                title="广东电力市场交易规则",
                content="为规范广东电力市场交易行为，维护市场秩序，保障各类市场主体合法权益，制定本规则。",
                effective_date="2024-01-01",
                source_url="https://drc.gd.gov.cn/test2.html",
                province="广东",
                asset_type="分布式光伏",
                doc_class="交易规则",
                confidence_score=0.88
            )
        ]
    
    @pytest.fixture
    def sample_metadata(self):
        """Sample metadata for testing."""
        return PackMetadata(
            query="分布式光伏并网要求",
            province="广东",
            asset_type="分布式光伏",
            doc_class="管理办法",
            total_citations=2,
            pack_id="test_pack_001"
        )
    
    def test_generator_initialization(self):
        """Test generator initialization."""
        with tempfile.TemporaryDirectory() as temp_dir:
            generator = CitationPackGenerator(template_dir=temp_dir)
            assert generator.template_dir == temp_dir
            assert generator.jinja_env is not None
            assert generator._browser is None
    
    @pytest.mark.asyncio
    async def test_generate_html_pack(self, sample_citations, sample_metadata):
        """Test HTML pack generation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create template file
            template_path = os.path.join(temp_dir, "citation_pack.html")
            with open(template_path, 'w', encoding='utf-8') as f:
                f.write("""
                <html>
                <head><title>{{ metadata.query }}</title></head>
                <body>
                    <h1>{{ metadata.query }}</h1>
                    <p>Citations: {{ citations|length }}</p>
                    {% for citation in citations %}
                    <div>{{ citation.title }}</div>
                    {% endfor %}
                </body>
                </html>
                """)
            
            generator = CitationPackGenerator(template_dir=temp_dir)
            html_content = await generator.generate_html_pack(sample_citations, sample_metadata)
            
            assert "分布式光伏并网要求" in html_content
            assert "Citations: 2" in html_content
            assert "广东省分布式光伏发电项目管理暂行办法" in html_content
            assert "广东电力市场交易规则" in html_content
    
    @pytest.mark.asyncio
    async def test_generate_pack_summary(self, sample_citations, sample_metadata):
        """Test pack summary generation."""
        generator = CitationPackGenerator()
        summary = await generator.generate_pack_summary(sample_citations, sample_metadata)
        
        assert summary["pack_metadata"]["query"] == "分布式光伏并网要求"
        assert summary["statistics"]["total_citations"] == 2
        assert summary["statistics"]["unique_provinces"] == 1
        assert summary["coverage"]["provinces"] == ["广东"]
        assert summary["coverage"]["asset_types"] == ["分布式光伏"]
        assert "confidence_stats" in summary
        assert summary["confidence_stats"]["average"] == 0.915  # (0.95 + 0.88) / 2
    
    def test_group_citations_by_topic(self, sample_citations):
        """Test citation grouping by topic."""
        generator = CitationPackGenerator()
        grouped = generator._group_citations_by_topic(sample_citations)
        
        # Should group by keywords in title/content
        assert len(grouped) > 0
        
        # Check that citations are properly grouped
        total_citations = sum(len(cites) for cites in grouped.values())
        assert total_citations == len(sample_citations)
    
    @pytest.mark.asyncio
    async def test_browser_management(self):
        """Test browser instance management."""
        generator = CitationPackGenerator()
        
        # Initially no browser
        assert generator._browser is None
        
        # Mock browser for testing
        with patch('services.citation.pack_generator.launch') as mock_launch:
            mock_browser = AsyncMock()
            mock_launch.return_value = mock_browser
            
            browser = await generator._get_browser()
            assert browser == mock_browser
            assert generator._browser == mock_browser
            
            # Should reuse existing browser
            browser2 = await generator._get_browser()
            assert browser2 == mock_browser
            mock_launch.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_close_browser(self):
        """Test browser cleanup."""
        generator = CitationPackGenerator()
        
        # Mock browser
        mock_browser = AsyncMock()
        generator._browser = mock_browser
        
        await generator.close()
        
        mock_browser.close.assert_called_once()
        assert generator._browser is None


class TestPackGenerationFunctions:
    """Test pack generation utility functions."""
    
    @pytest.mark.asyncio
    async def test_generate_citation_pack_pdf(self):
        """Test PDF pack generation."""
        citations = [
            {
                "citation_id": "TEST-001",
                "title": "测试文档",
                "content": "这是测试内容。",
                "effective_date": "2023-01-01",
                "province": "广东",
                "asset_type": "分布式光伏",
                "doc_class": "管理办法"
            }
        ]
        
        with patch('services.citation.pack_generator.CitationPackGenerator') as mock_generator_class:
            mock_generator = AsyncMock()
            mock_generator_class.return_value = mock_generator
            mock_generator.generate_pdf_pack.return_value = "/tmp/test.pdf"
            mock_generator.generate_pack_summary.return_value = {"test": "summary"}
            
            with patch('services.citation.pack_generator.get_pack_generator', return_value=mock_generator):
                result = await generate_citation_pack(
                    citations=citations,
                    query="测试查询",
                    province="广东",
                    asset_type="分布式光伏",
                    doc_class="管理办法",
                    format_type="pdf"
                )
                
                assert result["format"] == "pdf"
                assert result["file_path"] == "/tmp/test.pdf"
                assert "pack_id" in result
                assert "summary" in result
    
    @pytest.mark.asyncio
    async def test_generate_citation_pack_html(self):
        """Test HTML pack generation."""
        citations = [
            {
                "citation_id": "TEST-002",
                "title": "测试文档2",
                "content": "这是测试内容2。",
                "effective_date": "2023-02-01",
                "province": "山东",
                "asset_type": "风电",
                "doc_class": "实施细则"
            }
        ]
        
        with patch('services.citation.pack_generator.CitationPackGenerator') as mock_generator_class:
            mock_generator = AsyncMock()
            mock_generator_class.return_value = mock_generator
            mock_generator.generate_html_pack.return_value = "<html>test</html>"
            mock_generator.generate_pack_summary.return_value = {"test": "summary"}
            
            with patch('services.citation.pack_generator.get_pack_generator', return_value=mock_generator):
                result = await generate_citation_pack(
                    citations=citations,
                    query="测试查询2",
                    province="山东",
                    asset_type="风电",
                    doc_class="实施细则",
                    format_type="html"
                )
                
                assert result["format"] == "html"
                assert result["content"] == "<html>test</html>"
                assert "pack_id" in result
                assert "summary" in result
    
    @pytest.mark.asyncio
    async def test_generate_citation_pack_invalid_format(self):
        """Test pack generation with invalid format."""
        citations = [{"citation_id": "TEST-003", "title": "Test", "content": "Content", "effective_date": "2023-01-01"}]
        
        with pytest.raises(ValueError, match="Unsupported format type"):
            await generate_citation_pack(
                citations=citations,
                query="测试",
                province="广东",
                asset_type="测试",
                doc_class="测试",
                format_type="invalid"
            )
    
    @pytest.mark.asyncio
    async def test_get_pack_generator_singleton(self):
        """Test pack generator singleton behavior."""
        with patch('services.citation.pack_generator.CitationPackGenerator') as mock_class:
            mock_instance = AsyncMock()
            mock_class.return_value = mock_instance
            
            # Clear global instance
            import services.citation.pack_generator
            services.citation.pack_generator._pack_generator = None
            
            # First call should create instance
            generator1 = await get_pack_generator()
            assert generator1 == mock_instance
            mock_class.assert_called_once()
            
            # Second call should return same instance
            generator2 = await get_pack_generator()
            assert generator2 == mock_instance
            mock_class.assert_called_once()  # Still only called once


class TestErrorHandling:
    """Test error handling in pack generation."""
    
    @pytest.mark.asyncio
    async def test_html_generation_error(self):
        """Test error handling in HTML generation."""
        generator = CitationPackGenerator()
        
        # Mock template loading to raise error
        with patch.object(generator.jinja_env, 'get_template', side_effect=Exception("Template error")):
            citations = [CitationData(
                citation_id="TEST",
                title="Test",
                content="Content",
                effective_date="2023-01-01",
                province="Test",
                asset_type="Test",
                doc_class="Test"
            )]
            metadata = PackMetadata(
                query="Test",
                province="Test",
                asset_type="Test",
                doc_class="Test",
                total_citations=1,
                pack_id="test"
            )
            
            with pytest.raises(Exception, match="Template error"):
                await generator.generate_html_pack(citations, metadata)
    
    @pytest.mark.asyncio
    async def test_summary_generation_error(self):
        """Test error handling in summary generation."""
        generator = CitationPackGenerator()
        
        # Create invalid citation data
        citations = [CitationData(
            citation_id="TEST",
            title="Test",
            content="Content",
            effective_date="invalid-date",  # Invalid date format
            province="Test",
            asset_type="Test",
            doc_class="Test"
        )]
        metadata = PackMetadata(
            query="Test",
            province="Test",
            asset_type="Test",
            doc_class="Test",
            total_citations=1,
            pack_id="test"
        )
        
        # Should handle error gracefully
        summary = await generator.generate_pack_summary(citations, metadata)
        assert "pack_metadata" in summary
        assert "statistics" in summary