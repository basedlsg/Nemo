"""Unit tests for core utility functions."""

import pytest
from datetime import date, datetime
from uuid import UUID

from services.core.utils import (
    generate_uuid,
    calculate_sha256,
    normalize_text,
    extract_effective_date,
    segment_chinese_text,
    chunk_text,
    clean_html_content,
    format_chinese_date,
    parse_chinese_date,
    generate_citation_id,
    validate_chinese_ratio,
    extract_domain_from_url,
    is_official_domain,
    sanitize_filename,
    format_file_size,
    truncate_text,
    mask_sensitive_data,
)


class TestUuidGeneration:
    """Test UUID generation utilities."""
    
    def test_generate_uuid(self):
        """Test UUID generation."""
        uuid1 = generate_uuid()
        uuid2 = generate_uuid()
        
        assert isinstance(uuid1, UUID)
        assert isinstance(uuid2, UUID)
        assert uuid1 != uuid2  # Should be unique


class TestSha256Calculation:
    """Test SHA256 checksum calculation."""
    
    def test_calculate_sha256_string(self):
        """Test SHA256 calculation for strings."""
        text = "Hello, World!"
        checksum = calculate_sha256(text)
        
        assert isinstance(checksum, str)
        assert len(checksum) == 64  # SHA256 hex length
        
        # Same input should produce same checksum
        checksum2 = calculate_sha256(text)
        assert checksum == checksum2
        
        # Different input should produce different checksum
        checksum3 = calculate_sha256("Different text")
        assert checksum != checksum3
    
    def test_calculate_sha256_bytes(self):
        """Test SHA256 calculation for bytes."""
        data = b"Hello, World!"
        checksum = calculate_sha256(data)
        
        assert isinstance(checksum, str)
        assert len(checksum) == 64
        
        # Same as string version
        string_checksum = calculate_sha256("Hello, World!")
        assert checksum == string_checksum


class TestTextNormalization:
    """Test text normalization utilities."""
    
    def test_normalize_text_basic(self):
        """Test basic text normalization."""
        text = "  这是一个  测试   文本  "
        normalized = normalize_text(text)
        
        assert normalized == "这是一个 测试 文本"
        assert not normalized.startswith(" ")
        assert not normalized.endswith(" ")
    
    def test_normalize_text_with_punctuation_removal(self):
        """Test text normalization with punctuation removal."""
        text = "这是一个，测试！文本？"
        normalized = normalize_text(text, remove_punctuation=True)
        
        assert "，" not in normalized
        assert "！" not in normalized
        assert "？" not in normalized
        assert "这是一个测试文本" == normalized
    
    def test_normalize_text_empty(self):
        """Test normalization of empty text."""
        assert normalize_text("") == ""
        assert normalize_text(None) == ""


class TestEffectiveDateExtraction:
    """Test effective date extraction from text."""
    
    def test_extract_date_chinese_format(self):
        """Test extraction of Chinese date format."""
        text = "本办法自2025年3月1日起施行"
        extracted_date = extract_effective_date(text)
        
        assert extracted_date == date(2025, 3, 1)
    
    def test_extract_date_iso_format(self):
        """Test extraction of ISO date format."""
        text = "发布日期：2025-03-01"
        extracted_date = extract_effective_date(text)
        
        assert extracted_date == date(2025, 3, 1)
    
    def test_extract_date_from_url(self):
        """Test extraction of date from URL."""
        url = "https://gzpec.cn/rules/2025-03-01/solar-grid-connection"
        extracted_date = extract_effective_date("", url)
        
        assert extracted_date == date(2025, 3, 1)
    
    def test_extract_date_no_match(self):
        """Test extraction when no date found."""
        text = "这是一个没有日期的文本"
        extracted_date = extract_effective_date(text)
        
        assert extracted_date is None
    
    def test_extract_date_future_date_ignored(self):
        """Test that future dates are ignored."""
        future_year = datetime.now().year + 2
        text = f"本办法自{future_year}年3月1日起施行"
        extracted_date = extract_effective_date(text)
        
        assert extracted_date is None


class TestChineseTextSegmentation:
    """Test Chinese text segmentation."""
    
    def test_segment_chinese_text(self):
        """Test Chinese text segmentation."""
        text = "分布式光伏发电项目并网验收管理办法"
        segments = segment_chinese_text(text)
        
        assert isinstance(segments, list)
        assert len(segments) > 0
        assert all(isinstance(segment, str) for segment in segments)
        
        # Should contain meaningful words
        assert any(len(segment) > 1 for segment in segments)
    
    def test_segment_empty_text(self):
        """Test segmentation of empty text."""
        segments = segment_chinese_text("")
        assert segments == []
    
    def test_segment_filters_punctuation(self):
        """Test that punctuation is filtered out."""
        text = "测试，文本！"
        segments = segment_chinese_text(text)
        
        # Should not contain pure punctuation
        assert "，" not in segments
        assert "！" not in segments


class TestTextChunking:
    """Test text chunking functionality."""
    
    def test_chunk_text_basic(self):
        """Test basic text chunking."""
        text = "这是第一段。\n\n这是第二段。\n\n这是第三段。"
        chunks = chunk_text(text, max_tokens=50, overlap_tokens=10)
        
        assert isinstance(chunks, list)
        assert len(chunks) > 0
        
        for chunk in chunks:
            assert "chunk_id" in chunk
            assert "content" in chunk
            assert "token_count" in chunk
            assert chunk["token_count"] <= 50
    
    def test_chunk_text_with_overlap(self):
        """Test text chunking with overlap."""
        long_text = "这是一个很长的文本。" * 100
        chunks = chunk_text(long_text, max_tokens=100, overlap_tokens=20)
        
        assert len(chunks) > 1
        
        # Check that chunks have proper IDs
        chunk_ids = [chunk["chunk_id"] for chunk in chunks]
        assert len(set(chunk_ids)) == len(chunk_ids)  # All unique
    
    def test_chunk_empty_text(self):
        """Test chunking of empty text."""
        chunks = chunk_text("")
        assert chunks == []


class TestHtmlCleaning:
    """Test HTML content cleaning."""
    
    def test_clean_html_content(self):
        """Test HTML tag removal."""
        html = "<p>这是一个<strong>测试</strong>文档。</p>"
        cleaned = clean_html_content(html)
        
        assert "<p>" not in cleaned
        assert "<strong>" not in cleaned
        assert "这是一个测试文档。" == cleaned
    
    def test_clean_html_entities(self):
        """Test HTML entity decoding."""
        html = "测试&amp;文档&lt;内容&gt;"
        cleaned = clean_html_content(html)
        
        assert "&amp;" not in cleaned
        assert "&lt;" not in cleaned
        assert "&gt;" not in cleaned
        assert "测试&文档<内容>" == cleaned
    
    def test_clean_empty_html(self):
        """Test cleaning of empty HTML."""
        assert clean_html_content("") == ""
        assert clean_html_content(None) == ""


class TestChineseDateFormatting:
    """Test Chinese date formatting utilities."""
    
    def test_format_chinese_date(self):
        """Test Chinese date formatting."""
        test_date = date(2025, 3, 1)
        formatted = format_chinese_date(test_date)
        
        assert formatted == "2025年3月1日"
    
    def test_parse_chinese_date(self):
        """Test Chinese date parsing."""
        date_str = "2025年3月1日"
        parsed_date = parse_chinese_date(date_str)
        
        assert parsed_date == date(2025, 3, 1)
    
    def test_parse_iso_date(self):
        """Test ISO date parsing."""
        date_str = "2025-03-01"
        parsed_date = parse_chinese_date(date_str)
        
        assert parsed_date == date(2025, 3, 1)
    
    def test_parse_invalid_date(self):
        """Test parsing of invalid date."""
        parsed_date = parse_chinese_date("invalid date")
        assert parsed_date is None


class TestCitationIdGeneration:
    """Test citation ID generation."""
    
    def test_generate_citation_id(self):
        """Test deterministic citation ID generation."""
        url = "https://gzpec.cn/rules/solar"
        checksum = "a" * 64
        
        citation_id = generate_citation_id(url, checksum)
        
        assert isinstance(citation_id, UUID)
        
        # Same inputs should generate same ID
        citation_id2 = generate_citation_id(url, checksum)
        assert citation_id == citation_id2
        
        # Different inputs should generate different ID
        citation_id3 = generate_citation_id(url, "b" * 64)
        assert citation_id != citation_id3


class TestChineseRatioValidation:
    """Test Chinese content ratio validation."""
    
    def test_validate_chinese_ratio_sufficient(self):
        """Test validation with sufficient Chinese content."""
        text = "这是一个中文测试文档"
        assert validate_chinese_ratio(text, min_ratio=0.5) is True
    
    def test_validate_chinese_ratio_insufficient(self):
        """Test validation with insufficient Chinese content."""
        text = "This is mostly English with 一些 Chinese"
        assert validate_chinese_ratio(text, min_ratio=0.5) is False
    
    def test_validate_chinese_ratio_empty(self):
        """Test validation with empty text."""
        assert validate_chinese_ratio("", min_ratio=0.3) is False
        assert validate_chinese_ratio(None, min_ratio=0.3) is False


class TestDomainExtraction:
    """Test domain extraction from URLs."""
    
    def test_extract_domain_from_url(self):
        """Test domain extraction."""
        test_cases = [
            ("https://gzpec.cn/rules/solar", "gzpec.cn"),
            ("http://shandong-electric.com.cn:8080/docs", "shandong-electric.com.cn"),
            ("https://nmgdl.cn/path/to/resource?param=value", "nmgdl.cn"),
        ]
        
        for url, expected_domain in test_cases:
            assert extract_domain_from_url(url) == expected_domain
    
    def test_extract_domain_empty_url(self):
        """Test domain extraction from empty URL."""
        assert extract_domain_from_url("") == ""
        assert extract_domain_from_url(None) == ""


class TestOfficialDomainCheck:
    """Test official domain validation."""
    
    def test_is_official_domain_valid(self):
        """Test validation of official domains."""
        official_urls = [
            "https://gzpec.cn/rules",
            "http://shandong-electric.com.cn/docs",
            "https://nmgdl.cn/dispatch",
            "https://sc.sgcc.com.cn/grid",
        ]
        
        for url in official_urls:
            assert is_official_domain(url) is True
    
    def test_is_official_domain_invalid(self):
        """Test validation of non-official domains."""
        non_official_urls = [
            "https://example.com/test",
            "http://google.com/search",
            "https://github.com/project",
        ]
        
        for url in non_official_urls:
            assert is_official_domain(url) is False


class TestFilenameSanitization:
    """Test filename sanitization."""
    
    def test_sanitize_filename_basic(self):
        """Test basic filename sanitization."""
        filename = "广东省光伏并网管理办法.pdf"
        sanitized = sanitize_filename(filename)
        
        assert sanitized == "广东省光伏并网管理办法.pdf"
    
    def test_sanitize_filename_unsafe_chars(self):
        """Test sanitization of unsafe characters."""
        filename = "test<file>name:with|unsafe*chars?.pdf"
        sanitized = sanitize_filename(filename)
        
        assert "<" not in sanitized
        assert ">" not in sanitized
        assert ":" not in sanitized
        assert "|" not in sanitized
        assert "*" not in sanitized
        assert "?" not in sanitized
    
    def test_sanitize_filename_too_long(self):
        """Test sanitization of overly long filenames."""
        long_filename = "a" * 300 + ".pdf"
        sanitized = sanitize_filename(long_filename)
        
        assert len(sanitized) <= 200
    
    def test_sanitize_filename_empty(self):
        """Test sanitization of empty filename."""
        assert sanitize_filename("") == "untitled"
        assert sanitize_filename(None) == "untitled"


class TestFileSizeFormatting:
    """Test file size formatting."""
    
    def test_format_file_size(self):
        """Test file size formatting."""
        test_cases = [
            (0, "0 B"),
            (1024, "1.0 KB"),
            (1024 * 1024, "1.0 MB"),
            (1024 * 1024 * 1024, "1.0 GB"),
            (1536, "1.5 KB"),
        ]
        
        for size_bytes, expected in test_cases:
            assert format_file_size(size_bytes) == expected


class TestTextTruncation:
    """Test text truncation utilities."""
    
    def test_truncate_text_basic(self):
        """Test basic text truncation."""
        text = "这是一个很长的测试文本"
        truncated = truncate_text(text, max_length=10)
        
        assert len(truncated) <= 10
        assert truncated.endswith("...")
    
    def test_truncate_text_short(self):
        """Test truncation of short text."""
        text = "短文本"
        truncated = truncate_text(text, max_length=10)
        
        assert truncated == text  # Should not be truncated
    
    def test_truncate_text_empty(self):
        """Test truncation of empty text."""
        assert truncate_text("", max_length=10) == ""
        assert truncate_text(None, max_length=10) == ""


class TestSensitiveDataMasking:
    """Test sensitive data masking."""
    
    def test_mask_sensitive_data_basic(self):
        """Test basic data masking."""
        data = "1234567890abcdef"
        masked = mask_sensitive_data(data, visible_chars=4)
        
        assert masked.startswith("1234")
        assert masked.endswith("cdef")
        assert "*" in masked
        assert len(masked) == len(data)
    
    def test_mask_sensitive_data_short(self):
        """Test masking of short data."""
        data = "abc"
        masked = mask_sensitive_data(data, visible_chars=4)
        
        assert masked == "***"  # All masked for short data
    
    def test_mask_sensitive_data_empty(self):
        """Test masking of empty data."""
        assert mask_sensitive_data("") == ""
        assert mask_sensitive_data(None) == ""


if __name__ == "__main__":
    pytest.main([__file__])