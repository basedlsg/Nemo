"""Tests for answer composer service (Task 13)."""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime

from services.composer.answer_composer import (
    ChineseAnswerComposer, CitationReference, AnswerSection,
    get_answer_composer, compose_answer
)


class TestCitationReference:
    """Test citation reference dataclass."""
    
    def test_citation_reference_creation(self):
        """Test citation reference creation."""
        citation = CitationReference(
            citation_id="cite-1",
            title="广东省光伏并网管理办法",
            effective_date="2025-01-01",
            url="https://gzpec.cn/solar",
            passage="光伏发电项目并网需要提交相关资料。",
            score=0.9
        )
        
        assert citation.citation_id == "cite-1"
        assert citation.title == "广东省光伏并网管理办法"
        assert citation.effective_date == "2025-01-01"
        assert citation.score == 0.9


class TestAnswerSection:
    """Test answer section dataclass."""
    
    def test_answer_section_creation(self):
        """Test answer section creation."""
        citation = CitationReference(
            citation_id="cite-1",
            title="Test Title",
            effective_date="2025-01-01",
            url="https://example.com",
            passage="Test passage",
            score=0.8
        )
        
        section = AnswerSection(
            title="资料清单",
            bullets=["• 项目备案文件 〔《规定》，生效：2025-01-01〕"],
            citations=[citation]
        )
        
        assert section.title == "资料清单"
        assert len(section.bullets) == 1
        assert len(section.citations) == 1


class TestChineseAnswerComposer:
    """Test Chinese answer composer functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.composer = ChineseAnswerComposer()
        
        self.sample_search_results = [
            {
                "citation_id": "cite-1",
                "passage": "光伏发电项目并网需要提交以下资料：1. 项目备案文件；2. 设备技术参数；3. 安全评估报告。",
                "score": 0.9,
                "metadata": {
                    "title": "广东省光伏并网管理办法",
                    "effective_date": "2025-01-01",
                    "url": "https://gzpec.cn/solar-rules"
                }
            },
            {
                "citation_id": "cite-2",
                "passage": "并网申请受理时限为15个工作日，审批时限为30个工作日。",
                "score": 0.8,
                "metadata": {
                    "title": "分布式光伏接入管理规定",
                    "effective_date": "2024-12-01",
                    "url": "https://gzpec.cn/solar-access"
                }
            }
        ]
        
        self.sample_query = {
            "province": "guangdong",
            "asset": "solar",
            "doc_class": "grid_connection",
            "question": "光伏并网需要什么资料？"
        }
    
    def test_composer_initialization(self):
        """Test composer initialization."""
        assert len(self.composer.province_labels) == 3
        assert len(self.composer.asset_labels) == 4
        assert len(self.composer.doc_class_labels) == 3
        
        assert self.composer.province_labels["guangdong"] == "广东"
        assert self.composer.asset_labels["solar"] == "光伏"
        assert self.composer.doc_class_labels["grid_connection"] == "并网"
    
    def test_extract_citations_valid_results(self):
        """Test citation extraction from valid search results."""
        citations = self.composer._extract_citations(self.sample_search_results, max_citations=10)
        
        assert len(citations) == 2
        assert citations[0].citation_id == "cite-1"
        assert citations[0].title == "广东省光伏并网管理办法"
        assert citations[0].effective_date == "2025-01-01"
        assert citations[0].score == 0.9
        assert "光伏发电项目并网需要提交" in citations[0].passage
    
    def test_extract_citations_missing_fields(self):
        """Test citation extraction with missing required fields."""
        invalid_results = [
            {
                "citation_id": "cite-1",
                "passage": "Some content",
                "score": 0.8,
                "metadata": {
                    # Missing title and effective_date
                    "url": "https://example.com"
                }
            }
        ]
        
        citations = self.composer._extract_citations(invalid_results, max_citations=10)
        
        assert len(citations) == 0  # Should be filtered out
    
    def test_extract_citations_max_limit(self):
        """Test citation extraction with max limit."""
        citations = self.composer._extract_citations(self.sample_search_results, max_citations=1)
        
        assert len(citations) == 1
        assert citations[0].citation_id == "cite-1"  # Should take the first one
    
    def test_extract_key_clause_short_passage(self):
        """Test key clause extraction from short passage."""
        passage = "这是一个短的段落。"
        clause = self.composer._extract_key_clause(passage)
        assert clause == "这是一个短的段落。"
    
    def test_extract_key_clause_long_passage(self):
        """Test key clause extraction from long passage."""
        passage = "这是第一句话。这是第二句话。这是第三句话。" + "很长的内容" * 50
        clause = self.composer._extract_key_clause(passage)
        assert clause == "这是第一句话。"
    
    def test_extract_key_clause_very_long_passage(self):
        """Test key clause extraction from very long passage without sentence boundaries."""
        passage = "这是一个非常长的句子没有句号" * 20
        clause = self.composer._extract_key_clause(passage)
        assert clause.endswith("...")
        assert len(clause) <= 150
    
    def test_extract_key_clause_empty_passage(self):
        """Test key clause extraction from empty passage."""
        clause = self.composer._extract_key_clause("")
        assert clause == "相关规定"
    
    def test_generate_answer_title_with_asset(self):
        """Test answer title generation with asset."""
        title = self.composer._generate_answer_title(self.sample_query)
        assert title == "**并网要点（广东 / 光伏）**"
    
    def test_generate_answer_title_without_asset(self):
        """Test answer title generation without asset."""
        query_without_asset = {
            "province": "shandong",
            "doc_class": "market_rules"
        }
        title = self.composer._generate_answer_title(query_without_asset)
        assert title == "**市场规则要点（山东）**"
    
    def test_generate_answer_title_unknown_labels(self):
        """Test answer title generation with unknown labels."""
        unknown_query = {
            "province": "unknown_province",
            "asset": "unknown_asset",
            "doc_class": "unknown_class"
        }
        title = self.composer._generate_answer_title(unknown_query)
        assert title == "**unknown_class要点（unknown_province / unknown_asset）**"
    
    def test_group_citations_by_topic(self):
        """Test citation grouping by topic."""
        citations = self.composer._extract_citations(self.sample_search_results, max_citations=10)
        sections = self.composer._group_citations_by_topic(citations, self.sample_query)
        
        assert len(sections) >= 1
        
        # Check that citations are properly grouped
        total_bullets = sum(len(section.bullets) for section in sections)
        assert total_bullets == len(citations)
        
        # Check bullet format
        for section in sections:
            for bullet in section.bullets:
                assert bullet.startswith("• ")
                assert "〔《" in bullet
                assert "》，生效：" in bullet
                assert "〕" in bullet
    
    def test_compose_answer_text(self):
        """Test answer text composition."""
        citations = self.composer._extract_citations(self.sample_search_results, max_citations=10)
        sections = self.composer._group_citations_by_topic(citations, self.sample_query)
        title = self.composer._generate_answer_title(self.sample_query)
        
        answer_text = self.composer._compose_answer_text(title, sections)
        
        assert answer_text.startswith("**并网要点（广东 / 光伏）**")
        assert "- " in answer_text  # Section headers
        assert "  • " in answer_text  # Bullet points
        assert "〔《" in answer_text  # Citation format
        assert "》，生效：" in answer_text  # Citation format
    
    def test_compose_answer_success(self):
        """Test successful answer composition."""
        result = self.composer.compose_answer(self.sample_search_results, self.sample_query)
        
        assert result["answer_zh"].startswith("**并网要点（广东 / 光伏）**")
        assert len(result["citations"]) == 2
        assert result["sections"] >= 1
        assert result["total_citations"] == 2
        assert "composed_at" in result
        assert result["query_context"]["province"] == "guangdong"
    
    def test_compose_answer_no_results(self):
        """Test answer composition with no search results."""
        result = self.composer.compose_answer([], self.sample_query)
        
        assert "没有找到相关的一手资料" in result["answer_zh"]
        assert result["citations"] == []
        assert result["total_citations"] == 0
        assert "refusal_reason" in result
    
    def test_compose_answer_invalid_citations(self):
        """Test answer composition with invalid citations."""
        invalid_results = [
            {
                "citation_id": "cite-1",
                "passage": "Some content",
                "score": 0.8,
                "metadata": {
                    # Missing required fields
                    "url": "https://example.com"
                }
            }
        ]
        
        result = self.composer.compose_answer(invalid_results, self.sample_query)
        
        assert "没有找到有效的引用资料" in result["answer_zh"]
        assert result["citations"] == []
        assert "refusal_reason" in result
    
    def test_compose_answer_with_english_summary(self):
        """Test answer composition with English summary."""
        query_with_english = {**self.sample_query, "lang": "en"}
        
        result = self.composer.compose_answer(self.sample_search_results, query_with_english)
        
        assert "**English Summary:**" in result["answer_zh"]
        assert "This response covers" in result["answer_zh"]
        assert "Total citations:" in result["answer_zh"]
    
    def test_generate_english_summary(self):
        """Test English summary generation."""
        citations = self.composer._extract_citations(self.sample_search_results, max_citations=10)
        sections = self.composer._group_citations_by_topic(citations, self.sample_query)
        
        summary = self.composer._generate_english_summary(sections)
        
        assert "This response covers" in summary
        assert "Total citations:" in summary
        assert str(len(citations)) in summary
    
    def test_create_refusal_response(self):
        """Test refusal response creation."""
        refusal = self.composer._create_refusal_response("测试拒绝原因")
        
        assert "抱歉，测试拒绝原因" in refusal["answer_zh"]
        assert refusal["citations"] == []
        assert refusal["total_citations"] == 0
        assert refusal["sections"] == 0
        assert "refusal_reason" in refusal
        assert "composed_at" in refusal
    
    def test_health_check_healthy(self):
        """Test healthy composer health check."""
        health = self.composer.health_check()
        
        assert health["status"] == "healthy"
        assert health["test_composition"] == "success"
        assert health["province_labels"] == 3
        assert health["asset_labels"] == 4
        assert health["doc_class_labels"] == 3
        assert "timestamp" in health
    
    @patch('services.composer.answer_composer.ChineseAnswerComposer.compose_answer')
    def test_health_check_unhealthy(self, mock_compose):
        """Test unhealthy composer health check."""
        mock_compose.side_effect = Exception("Composition failed")
        
        health = self.composer.health_check()
        
        assert health["status"] == "unhealthy"
        assert "error" in health


class TestComposerGlobal:
    """Test global composer functions."""
    
    def test_get_answer_composer_singleton(self):
        """Test that get_answer_composer returns singleton instance."""
        # Clear any existing instance
        import services.composer.answer_composer
        services.composer.answer_composer._answer_composer = None
        
        composer1 = get_answer_composer()
        composer2 = get_answer_composer()
        
        assert composer1 is composer2
        assert isinstance(composer1, ChineseAnswerComposer)
    
    def test_compose_answer_convenience_function(self):
        """Test convenience function for answer composition."""
        search_results = [
            {
                "citation_id": "cite-1",
                "passage": "测试内容",
                "score": 0.8,
                "metadata": {
                    "title": "测试文档",
                    "effective_date": "2025-01-01",
                    "url": "https://example.com"
                }
            }
        ]
        
        query = {
            "province": "guangdong",
            "doc_class": "grid_connection"
        }
        
        answer_text, citations = compose_answer(search_results, query)
        
        assert isinstance(answer_text, str)
        assert isinstance(citations, list)
        assert len(citations) == 1


class TestAnswerComposition:
    """Test complete answer composition scenarios."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.composer = ChineseAnswerComposer()
    
    def test_compose_guangdong_solar_grid_connection(self):
        """Test composition for Guangdong solar grid connection."""
        search_results = [
            {
                "citation_id": "cite-1",
                "passage": "分布式光伏发电项目并网申请需要提交项目备案文件、设备清单和技术参数表。",
                "score": 0.95,
                "metadata": {
                    "title": "广东省分布式光伏并网管理办法",
                    "effective_date": "2025-01-01",
                    "url": "https://gzpec.cn/solar-grid-2025"
                }
            },
            {
                "citation_id": "cite-2",
                "passage": "并网验收应在项目建成后30日内完成，验收合格后方可并网发电。",
                "score": 0.87,
                "metadata": {
                    "title": "光伏发电项目验收标准",
                    "effective_date": "2024-11-15",
                    "url": "https://gzpec.cn/solar-acceptance"
                }
            }
        ]
        
        query = {
            "province": "guangdong",
            "asset": "solar",
            "doc_class": "grid_connection",
            "question": "光伏并网需要什么资料和流程？"
        }
        
        result = self.composer.compose_answer(search_results, query)
        
        # Check answer structure
        assert result["answer_zh"].startswith("**并网要点（广东 / 光伏）**")
        assert "- " in result["answer_zh"]  # Has sections
        assert "  • " in result["answer_zh"]  # Has bullet points
        assert "〔《广东省分布式光伏并网管理办法》，生效：2025-01-01〕" in result["answer_zh"]
        assert "〔《光伏发电项目验收标准》，生效：2024-11-15〕" in result["answer_zh"]
        
        # Check citations
        assert len(result["citations"]) == 2
        assert result["citations"][0]["citation_id"] == "cite-1"
        assert result["citations"][0]["title"] == "广东省分布式光伏并网管理办法"
        
        # Check metadata
        assert result["total_citations"] == 2
        assert result["sections"] >= 1
        assert result["query_context"]["province"] == "guangdong"
        assert result["query_context"]["asset"] == "solar"
    
    def test_compose_shandong_wind_market_rules(self):
        """Test composition for Shandong wind market rules."""
        search_results = [
            {
                "citation_id": "cite-3",
                "passage": "风电项目参与电力市场交易应满足以下条件：装机容量不低于10MW，具备远程监控能力。",
                "score": 0.92,
                "metadata": {
                    "title": "山东省风电市场准入规则",
                    "effective_date": "2024-10-01",
                    "url": "https://sdpxc.cn/wind-market"
                }
            }
        ]
        
        query = {
            "province": "shandong",
            "asset": "wind",
            "doc_class": "market_rules",
            "question": "风电如何参与市场交易？"
        }
        
        result = self.composer.compose_answer(search_results, query)
        
        assert result["answer_zh"].startswith("**市场规则要点（山东 / 风电）**")
        assert "〔《山东省风电市场准入规则》，生效：2024-10-01〕" in result["answer_zh"]
        assert result["total_citations"] == 1
        assert result["query_context"]["province"] == "shandong"
        assert result["query_context"]["asset"] == "wind"
    
    def test_compose_with_english_summary(self):
        """Test composition with English summary."""
        query_with_english = {**self.sample_query, "lang": "en"}
        
        result = self.composer.compose_answer(self.sample_search_results, query_with_english)
        
        assert "**English Summary:**" in result["answer_zh"]
        assert "This response covers" in result["answer_zh"]
        assert "Total citations: 2" in result["answer_zh"]
        
        # Chinese content should still be present
        assert "**并网要点（广东 / 光伏）**" in result["answer_zh"]
    
    def test_compose_inner_mongolia_without_asset(self):
        """Test composition for Inner Mongolia without asset specification."""
        search_results = [
            {
                "citation_id": "cite-4",
                "passage": "电力调度应遵循安全第一、统一调度、分级管理的原则。",
                "score": 0.88,
                "metadata": {
                    "title": "内蒙古电力调度管理规定",
                    "effective_date": "2024-09-01",
                    "url": "https://impex.org.cn/dispatch-rules"
                }
            }
        ]
        
        query = {
            "province": "inner_mongolia",
            "doc_class": "dispatch_ops",
            "question": "电力调度有什么原则？"
        }
        
        result = self.composer.compose_answer(search_results, query)
        
        assert result["answer_zh"].startswith("**调度要点（内蒙古）**")
        assert "〔《内蒙古电力调度管理规定》，生效：2024-09-01〕" in result["answer_zh"]
        assert result["query_context"]["asset"] is None


if __name__ == "__main__":
    pytest.main([__file__])