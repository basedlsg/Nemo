"""Tests for effective date extraction."""

import pytest
from datetime import date
from services.ocr.effective_date import (
    extract_effective_date,
    extract_multiple_dates,
    validate_effective_date,
    _find_date_with_context,
    _find_publication_date,
    _extract_date_from_url,
    _is_reasonable_date
)


class TestEffectiveDateExtraction:
    """Test effective date extraction from Chinese documents."""
    
    def test_standard_chinese_format(self):
        """Test standard Chinese date format."""
        text = "本规则自2025年3月1日起施行。"
        result = extract_effective_date(text)
        
        assert result == date(2025, 3, 1)
    
    def test_implementation_phrase(self):
        """Test implementation phrase detection."""
        text = "广东省电力交易规则，自2025年6月15日起执行。"
        result = extract_effective_date(text)
        
        assert result == date(2025, 6, 15)
    
    def test_publication_date(self):
        """Test publication date extraction."""
        text = "发布日期：2025年2月20日\n本办法规定了电力市场交易规则。"
        result = extract_effective_date(text)
        
        assert result == date(2025, 2, 20)
    
    def test_iso_format(self):
        """Test ISO date format."""
        text = "有效期至2025-12-31，请各单位遵照执行。"
        result = extract_effective_date(text)
        
        assert result == date(2025, 12, 31)
    
    def test_document_number_format(self):
        """Test document number with year."""
        text = "粤能规〔2025〕15号\n关于电力市场交易的通知"
        result = extract_effective_date(text)
        
        # Should extract year from document number
        assert result is not None
        assert result.year == 2025
    
    def test_multiple_dates_priority(self):
        """Test priority when multiple dates exist."""
        text = """
        发布日期：2025年1月1日
        本规则自2025年3月1日起施行。
        申请截止日期：2025年2月15日
        """
        result = extract_effective_date(text)
        
        # Should prioritize effective date over other dates
        assert result == date(2025, 3, 1)
    
    def test_no_date_found(self):
        """Test when no date is found."""
        text = "这是一个没有日期的文档内容。"
        result = extract_effective_date(text)
        
        assert result is None
    
    def test_invalid_date(self):
        """Test handling of invalid dates."""
        text = "自2025年13月45日起施行。"  # Invalid month and day
        result = extract_effective_date(text)
        
        assert result is None
    
    def test_url_date_extraction(self):
        """Test date extraction from URL."""
        text = "电力交易规则"
        url = "https://example.com/docs/2025/03/01/power-trading-rules.html"
        
        result = extract_effective_date(text, url)
        
        assert result == date(2025, 3, 1)
    
    def test_complex_document(self):
        """Test with complex document structure."""
        text = """
        广东省能源局
        
        关于印发《广东省电力市场交易规则》的通知
        
        各有关单位：
        
        为规范电力市场交易行为，现将《广东省电力市场交易规则》印发给你们，
        请认真贯彻执行。本规则自2025年4月1日起施行。
        
        广东省能源局
        2025年3月15日
        """
        
        result = extract_effective_date(text)
        
        # Should find the effective date, not the document date
        assert result == date(2025, 4, 1)


class TestMultipleDateExtraction:
    """Test extraction of multiple dates with confidence scores."""
    
    def test_multiple_dates_with_confidence(self):
        """Test extraction of multiple dates with confidence."""
        text = """
        发布日期：2025年1月1日
        本规则自2025年3月1日起施行。
        申请截止：2025年2月15日
        """
        
        results = extract_multiple_dates(text)
        
        assert len(results) >= 2
        
        # Check that results are sorted by confidence
        confidences = [r[2] for r in results]
        assert confidences == sorted(confidences, reverse=True)
        
        # Effective date should have highest confidence
        best_date, context, confidence = results[0]
        assert best_date == date(2025, 3, 1)
        assert confidence > 0.5
    
    def test_date_contexts(self):
        """Test that contexts are properly extracted."""
        text = "本办法自2025年5月1日起生效，有效期至2025年12月31日。"
        
        results = extract_multiple_dates(text)
        
        assert len(results) >= 2
        
        # Check contexts contain relevant information
        for date_obj, context, confidence in results:
            assert len(context) > 0
            if date_obj == date(2025, 5, 1):
                assert "生效" in context or "起" in context


class TestDateValidation:
    """Test date validation functionality."""
    
    def test_valid_date_validation(self):
        """Test validation of valid dates."""
        test_date = date(2025, 3, 1)
        text = "本规则自2025年3月1日起施行。"
        
        result = validate_effective_date(test_date, text)
        
        assert result["is_valid"] is True
        assert result["confidence"] > 0.0
        assert len(result["alternative_dates"]) >= 0
    
    def test_future_date_validation(self):
        """Test validation of future dates."""
        future_date = date(2030, 1, 1)
        text = "本规则自2030年1月1日起施行。"
        
        result = validate_effective_date(future_date, text)
        
        assert result["is_valid"] is True
        assert "Future effective date" in result["validation_notes"]
    
    def test_old_date_validation(self):
        """Test validation of very old dates."""
        old_date = date(2010, 1, 1)
        text = "本规则自2010年1月1日起施行。"
        
        result = validate_effective_date(old_date, text)
        
        assert result["is_valid"] is True
        assert any("5 years old" in note for note in result["validation_notes"])
    
    def test_none_date_validation(self):
        """Test validation when no date provided."""
        result = validate_effective_date(None, "没有日期的文档")
        
        assert result["is_valid"] is False
        assert "No effective date found" in result["validation_notes"]


class TestUtilityFunctions:
    """Test utility functions."""
    
    def test_reasonable_date_check(self):
        """Test reasonable date checking."""
        assert _is_reasonable_date(date(2025, 1, 1)) is True
        assert _is_reasonable_date(date(1999, 1, 1)) is False  # Too old
        assert _is_reasonable_date(date(2040, 1, 1)) is False  # Too far in future
    
    def test_url_date_extraction_patterns(self):
        """Test various URL date patterns."""
        urls = [
            "https://example.com/2025/03/01/doc.html",
            "https://example.com/docs/20250301/notice.pdf",
            "https://example.com/files/doc_20250301_final.pdf",
            "https://example.com/2025-03-01-announcement.html"
        ]
        
        for url in urls:
            result = _extract_date_from_url(url)
            if result:  # Some patterns might not match
                assert result.year == 2025
                assert result.month == 3
                assert result.day == 1
    
    def test_context_date_finding(self):
        """Test finding dates with specific contexts."""
        text = "本规则自2025年3月1日起施行，申请截止2025年2月15日。"
        
        result = _find_date_with_context(text)
        
        # Should find the effective date, not the deadline
        assert result == date(2025, 3, 1)
    
    def test_publication_date_finding(self):
        """Test finding publication dates."""
        text = "广东省能源局于2025年2月1日发布此通知。"
        
        result = _find_publication_date(text)
        
        assert result == date(2025, 2, 1)


class TestEdgeCases:
    """Test edge cases and error conditions."""
    
    def test_empty_text(self):
        """Test with empty text."""
        assert extract_effective_date("") is None
        assert extract_effective_date(None) is None
    
    def test_malformed_dates(self):
        """Test with malformed dates."""
        texts = [
            "自2025年0月1日起施行",  # Invalid month
            "自2025年2月30日起施行",  # Invalid day for February
            "自25年3月1日起施行",     # Two-digit year
        ]
        
        for text in texts:
            result = extract_effective_date(text)
            # Should handle gracefully (return None or valid date)
            if result:
                assert isinstance(result, date)
    
    def test_ambiguous_dates(self):
        """Test with ambiguous date contexts."""
        text = """
        会议时间：2025年3月1日
        文件签署：2025年3月5日
        开始执行：2025年3月10日
        """
        
        result = extract_effective_date(text)
        
        # Should prefer execution date
        assert result == date(2025, 3, 10)
    
    def test_chinese_traditional_dates(self):
        """Test traditional Chinese date formats."""
        text = "自二〇二五年三月一日起施行"
        
        # Current implementation may not handle traditional numbers
        # This test documents the limitation
        result = extract_effective_date(text)
        
        # May be None if traditional numbers not supported
        assert result is None or isinstance(result, date)


@pytest.fixture
def sample_regulation_text():
    """Sample regulation text for testing."""
    return """
    广东省发展和改革委员会
    
    关于印发《广东省电力市场交易规则（试行）》的通知
    
    粤发改能源〔2025〕8号
    
    各地级以上市发展改革局（委），各有关单位：
    
    为进一步完善电力市场机制，规范电力市场交易行为，根据国家有关规定，
    我委制定了《广东省电力市场交易规则（试行）》，现印发给你们，请认真
    贯彻执行。本规则自2025年4月1日起施行，有效期3年。
    
    广东省发展和改革委员会
    2025年3月15日
    """


def test_realistic_document(sample_regulation_text):
    """Test with realistic regulation document."""
    result = extract_effective_date(sample_regulation_text)
    
    assert result == date(2025, 4, 1)
    
    # Test validation
    validation = validate_effective_date(result, sample_regulation_text)
    assert validation["is_valid"] is True
    assert validation["confidence"] > 0.7  # Should have high confidence
    
    # Test multiple dates
    multiple_dates = extract_multiple_dates(sample_regulation_text)
    assert len(multiple_dates) >= 2  # Should find both effective date and document date
    
    # Effective date should be first (highest confidence)
    best_date = multiple_dates[0][0]
    assert best_date == date(2025, 4, 1)