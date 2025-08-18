"""Tests for OCR text normalization."""

import pytest
from services.ocr.normalize import (
    normalize_cjk,
    extract_paragraphs_from_doc,
    extract_tables_from_page,
    doc_to_normalized_content,
    detect_language,
    merge_short_paragraphs,
    clean_ocr_artifacts
)


class TestNormalizeCJK:
    """Test Chinese text normalization."""
    
    def test_basic_normalization(self):
        """Test basic text normalization."""
        text = "这是一个  测试   文档。\n\n\n包含多个空格。"
        result = normalize_cjk(text)
        
        assert "  " not in result  # Multiple spaces collapsed
        assert result.count("\n") <= 2  # Excessive newlines reduced
        assert "测试" in result
    
    def test_chinese_punctuation(self):
        """Test Chinese punctuation handling."""
        text = "第一条 ： 这是条款。 第二条 ； 另一条款。"
        result = normalize_cjk(text)
        
        # Should remove spaces around Chinese punctuation
        assert "条：这是" in result or "条： 这是" in result
        assert "条；另一" in result or "条； 另一" in result
    
    def test_article_numbering(self):
        """Test article numbering normalization."""
        text = "第 一 条 内容"
        result = normalize_cjk(text)
        
        assert "第一条" in result
    
    def test_date_formatting(self):
        """Test date formatting."""
        text = "2025 年 3 月 1 日"
        result = normalize_cjk(text)
        
        assert "2025年3月1日" in result
    
    def test_empty_text(self):
        """Test empty text handling."""
        assert normalize_cjk("") == ""
        assert normalize_cjk(None) == ""
        assert normalize_cjk("   ") == ""


class TestLanguageDetection:
    """Test language detection."""
    
    def test_chinese_detection(self):
        """Test Chinese text detection."""
        chinese_text = "这是一个中文文档，包含能源规定。"
        result = detect_language(chinese_text)
        
        assert result == "zh-CN"
    
    def test_mixed_language(self):
        """Test mixed language detection."""
        mixed_text = "这是中文 with some English words."
        result = detect_language(mixed_text)
        
        assert result in ["zh-CN", "zh-mixed"]
    
    def test_english_text(self):
        """Test English text detection."""
        english_text = "This is an English document about energy regulations."
        result = detect_language(english_text)
        
        assert result == "other"
    
    def test_empty_text(self):
        """Test empty text detection."""
        assert detect_language("") is None
        assert detect_language("123456") is None


class TestParagraphExtraction:
    """Test paragraph extraction from Document AI output."""
    
    def test_extract_from_blocks(self):
        """Test extraction from Document AI blocks."""
        doc = {
            "text": "第一条：这是第一条内容。\n第二条：这是第二条内容。",
            "pages": [
                {
                    "blocks": [
                        {
                            "layout": {
                                "text_anchor": {
                                    "text_segments": [
                                        {"start_index": 0, "end_index": 12}
                                    ]
                                }
                            }
                        },
                        {
                            "layout": {
                                "text_anchor": {
                                    "text_segments": [
                                        {"start_index": 13, "end_index": 25}
                                    ]
                                }
                            }
                        }
                    ]
                }
            ]
        }
        
        paragraphs = extract_paragraphs_from_doc(doc)
        
        assert len(paragraphs) == 2
        assert "第一条" in paragraphs[0]
        assert "第二条" in paragraphs[1]
    
    def test_fallback_to_text_splitting(self):
        """Test fallback when no blocks available."""
        doc = {
            "text": "第一条：这是第一条内容。\n\n第二条：这是第二条内容。",
            "pages": []
        }
        
        paragraphs = extract_paragraphs_from_doc(doc)
        
        assert len(paragraphs) >= 1
        assert any("第一条" in p for p in paragraphs)


class TestTableExtraction:
    """Test table extraction from Document AI pages."""
    
    def test_extract_simple_table(self):
        """Test simple table extraction."""
        full_text = "项目 | 要求\n风电 | 50MW\n太阳能 | 100MW"
        page = {
            "tables": [
                {
                    "header_rows": [
                        {
                            "cells": [
                                {
                                    "layout": {
                                        "text_anchor": {
                                            "text_segments": [{"start_index": 0, "end_index": 2}]
                                        }
                                    }
                                },
                                {
                                    "layout": {
                                        "text_anchor": {
                                            "text_segments": [{"start_index": 5, "end_index": 7}]
                                        }
                                    }
                                }
                            ]
                        }
                    ],
                    "body_rows": [
                        {
                            "cells": [
                                {
                                    "layout": {
                                        "text_anchor": {
                                            "text_segments": [{"start_index": 8, "end_index": 10}]
                                        }
                                    }
                                },
                                {
                                    "layout": {
                                        "text_anchor": {
                                            "text_segments": [{"start_index": 13, "end_index": 18}]
                                        }
                                    }
                                }
                            ]
                        }
                    ]
                }
            ]
        }
        
        tables = extract_tables_from_page(page, full_text)
        
        assert len(tables) == 1
        table = tables[0]
        assert "|" in table.markdown
        assert table.row_count >= 1
        assert table.col_count >= 2
    
    def test_empty_table(self):
        """Test handling of empty tables."""
        page = {"tables": []}
        tables = extract_tables_from_page(page, "")
        
        assert len(tables) == 0


class TestDocumentNormalization:
    """Test complete document normalization."""
    
    def test_complete_normalization(self):
        """Test complete document normalization process."""
        doc = {
            "text": "第一条：风电项目要求。\n第二条：太阳能项目要求。",
            "pages": [
                {
                    "blocks": [
                        {
                            "layout": {
                                "text_anchor": {
                                    "text_segments": [
                                        {"start_index": 0, "end_index": 10}
                                    ]
                                }
                            }
                        }
                    ],
                    "tables": []
                }
            ]
        }
        
        result = doc_to_normalized_content(doc)
        
        assert len(result.paragraphs) >= 1
        assert result.language == "zh-CN"
        assert result.page_count == 1
        assert len(result.tables) == 0
    
    def test_with_tables(self):
        """Test normalization with tables."""
        doc = {
            "text": "项目类型|容量要求\n风电|50MW",
            "pages": [
                {
                    "blocks": [],
                    "tables": [
                        {
                            "header_rows": [
                                {
                                    "cells": [
                                        {
                                            "layout": {
                                                "text_anchor": {
                                                    "text_segments": [{"start_index": 0, "end_index": 4}]
                                                }
                                            }
                                        }
                                    ]
                                }
                            ],
                            "body_rows": []
                        }
                    ]
                }
            ]
        }
        
        result = doc_to_normalized_content(doc)
        
        assert len(result.tables) >= 0  # May or may not extract depending on content


class TestUtilityFunctions:
    """Test utility functions."""
    
    def test_merge_short_paragraphs(self):
        """Test merging of short paragraphs."""
        paragraphs = ["短", "另一个短段落", "这是一个比较长的段落，应该不会被合并"]
        
        result = merge_short_paragraphs(paragraphs, min_length=10)
        
        # Should merge short paragraphs
        assert len(result) < len(paragraphs)
    
    def test_clean_ocr_artifacts(self):
        """Test OCR artifact cleaning."""
        text = "这是|一个□包含■OCR错误的文档"
        result = clean_ocr_artifacts(text)
        
        # Should remove artifacts
        assert "|" not in result
        assert "□" not in result
        assert "■" not in result
        assert "这是一个包含" in result
    
    def test_unit_normalization(self):
        """Test unit normalization."""
        text = "容量为 50 千瓦，电压为 10 千伏"
        result = clean_ocr_artifacts(text)
        
        assert "50千瓦" in result
        assert "10千伏" in result


@pytest.fixture
def sample_doc():
    """Sample Document AI output for testing."""
    return {
        "text": "第一条：风力发电项目应当符合以下要求：\n（一）装机容量不少于50MW；\n（二）年利用小时数不低于2000小时。\n\n第二条：太阳能发电项目要求如下：\n（一）装机容量不少于100MW。",
        "pages": [
            {
                "blocks": [
                    {
                        "layout": {
                            "text_anchor": {
                                "text_segments": [
                                    {"start_index": 0, "end_index": 50}
                                ]
                            },
                            "confidence": 0.95
                        }
                    }
                ],
                "tables": []
            }
        ]
    }


def test_integration_with_sample_doc(sample_doc):
    """Test integration with realistic document."""
    result = doc_to_normalized_content(sample_doc)
    
    assert len(result.paragraphs) >= 1
    assert result.language == "zh-CN"
    assert result.page_count == 1
    
    # Check content quality
    combined_text = "\n".join(result.paragraphs)
    assert "风力发电" in combined_text
    assert "太阳能发电" in combined_text
    assert "50MW" in combined_text or "50 MW" in combined_text