"""Tests for refusal handler (Task 16)."""

import pytest
from datetime import datetime

from services.refusal.refusal_handler import (
    RefusalHandler, RefusalCode, RefusalResponse,
    get_refusal_handler, create_refusal
)


class TestRefusalCode:
    """Test refusal code enum."""
    
    def test_refusal_code_values(self):
        """Test that refusal codes have expected values."""
        assert RefusalCode.NO_FIRST_PARTY_CITATION.value == "no_first_party_citation"
        assert RefusalCode.STALE_CITATION.value == "stale_citation"
        assert RefusalCode.PROVINCE_MISMATCH.value == "province_mismatch"
        assert RefusalCode.LANGUAGE_POLICY_VIOLATION.value == "language_policy_violation"
        assert RefusalCode.RETRIEVAL_FAILED.value == "retrieval_failed"
        assert RefusalCode.QUERY_TOO_VAGUE.value == "query_too_vague"
    
    def test_refusal_code_enum_creation(self):
        """Test creating refusal codes from strings."""
        assert RefusalCode("no_first_party_citation") == RefusalCode.NO_FIRST_PARTY_CITATION
        assert RefusalCode("rate_limit_exceeded") == RefusalCode.RATE_LIMIT_EXCEEDED
        
        with pytest.raises(ValueError):
            RefusalCode("invalid_code")


class TestRefusalResponse:
    """Test refusal response dataclass."""
    
    def test_refusal_response_creation(self):
        """Test refusal response creation."""
        response = RefusalResponse(
            code=RefusalCode.NO_FIRST_PARTY_CITATION,
            message_zh="没有找到官方资料",
            message_en="No official sources found",
            suggestion_zh="请尝试其他关键词",
            suggestion_en="Try other keywords"
        )
        
        assert response.code == RefusalCode.NO_FIRST_PARTY_CITATION
        assert response.message_zh == "没有找到官方资料"
        assert response.message_en == "No official sources found"
        assert response.suggestion_zh == "请尝试其他关键词"
        assert response.suggestion_en == "Try other keywords"
        assert response.policy_info is None
        assert response.debug_info is None
        assert response.timestamp is not None
    
    def test_refusal_response_with_optional_fields(self):
        """Test refusal response with optional fields."""
        policy_info = {"requires_first_party": True}
        debug_info = {"trace_id": "test-123"}
        
        response = RefusalResponse(
            code=RefusalCode.STALE_CITATION,
            message_zh="资料过时",
            message_en="Sources outdated",
            suggestion_zh="查询最新资料",
            suggestion_en="Check latest sources",
            policy_info=policy_info,
            debug_info=debug_info,
            timestamp="2025-01-14T10:00:00Z"
        )
        
        assert response.policy_info == policy_info
        assert response.debug_info == debug_info
        assert response.timestamp == "2025-01-14T10:00:00Z"


class TestRefusalHandler:
    """Test refusal handler functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.handler = RefusalHandler()
    
    def test_handler_initialization(self):
        """Test handler initialization."""
        assert len(self.handler.refusal_templates) > 0
        assert self.handler.refusal_stats["total_refusals"] == 0
        assert self.handler.refusal_stats["refusal_by_code"] == {}
        assert self.handler.refusal_stats["refusal_by_province"] == {}
        assert self.handler.refusal_stats["refusal_by_doc_class"] == {}
        assert self.handler.refusal_stats["refusal_by_asset"] == {}
    
    def test_refusal_templates_loaded(self):
        """Test that refusal templates are properly loaded."""
        # Check that all refusal codes have templates
        expected_codes = [
            RefusalCode.NO_FIRST_PARTY_CITATION,
            RefusalCode.STALE_CITATION,
            RefusalCode.PROVINCE_MISMATCH,
            RefusalCode.LANGUAGE_POLICY_VIOLATION,
            RefusalCode.RETRIEVAL_FAILED,
            RefusalCode.QUERY_TOO_VAGUE,
            RefusalCode.RATE_LIMIT_EXCEEDED
        ]
        
        for code in expected_codes:
            assert code in self.handler.refusal_templates
            template = self.handler.refusal_templates[code]
            assert "message_zh" in template
            assert "message_en" in template
            assert "suggestion_zh" in template
            assert "suggestion_en" in template
            assert len(template["message_zh"]) > 0
            assert len(template["message_en"]) > 0
    
    def test_create_refusal_basic(self):
        """Test basic refusal creation."""
        refusal = self.handler.create_refusal(
            code=RefusalCode.NO_FIRST_PARTY_CITATION,
            trace_id="test-basic-1"
        )
        
        assert isinstance(refusal, RefusalResponse)
        assert refusal.code == RefusalCode.NO_FIRST_PARTY_CITATION
        assert "没有找到来自官方一手来源" in refusal.message_zh
        assert "no official first-party sources" in refusal.message_en.lower()
        assert len(refusal.suggestion_zh) > 0
        assert len(refusal.suggestion_en) > 0
        assert refusal.timestamp is not None
        
        # Check statistics updated
        assert self.handler.refusal_stats["total_refusals"] == 1
        assert self.handler.refusal_stats["refusal_by_code"]["no_first_party_citation"] == 1
    
    def test_create_refusal_with_context(self):
        """Test refusal creation with context."""
        context = {
            "province": "guangdong",
            "doc_class": "grid_connection",
            "asset": "solar",
            "lang": "zh-CN"
        }
        
        refusal = self.handler.create_refusal(
            code=RefusalCode.NO_FIRST_PARTY_CITATION,
            context=context,
            trace_id="test-context-1"
        )
        
        assert refusal.policy_info is not None
        assert refusal.policy_info["applicable_scope"]["province"] == "guangdong"
        assert refusal.policy_info["applicable_scope"]["asset"] == "solar"
        assert refusal.policy_info["policy_category"] == "citation_quality"
        
        # Check personalized message
        assert "广东省电力交易中心" in refusal.suggestion_zh
        
        # Check statistics updated with context
        assert self.handler.refusal_stats["refusal_by_province"]["guangdong"] == 1
        assert self.handler.refusal_stats["refusal_by_doc_class"]["grid_connection"] == 1
        assert self.handler.refusal_stats["refusal_by_asset"]["solar"] == 1
    
    def test_create_refusal_with_custom_message(self):
        """Test refusal creation with custom message."""
        custom_message = "自定义错误消息"
        
        refusal = self.handler.create_refusal(
            code=RefusalCode.RETRIEVAL_FAILED,
            custom_message=custom_message,
            trace_id="test-custom-1"
        )
        
        assert refusal.message_zh == custom_message
        # English message should still come from template
        assert "retrieval system" in refusal.message_en.lower()
    
    def test_create_refusal_with_debug_info(self):
        """Test refusal creation with debug information."""
        debug_info = {
            "error_details": "Connection timeout",
            "retry_count": 3,
            "service": "retriever"
        }
        
        refusal = self.handler.create_refusal(
            code=RefusalCode.RETRIEVAL_FAILED,
            debug_info=debug_info,
            trace_id="test-debug-1"
        )
        
        assert refusal.debug_info == debug_info
    
    def test_create_refusal_unknown_code(self):
        """Test refusal creation with unknown code."""
        # Create a mock unknown code by patching the templates
        original_templates = self.handler.refusal_templates.copy()
        del self.handler.refusal_templates[RefusalCode.RETRIEVAL_FAILED]
        
        refusal = self.handler.create_refusal(
            code=RefusalCode.RETRIEVAL_FAILED,
            trace_id="test-unknown-1"
        )
        
        # Should use default template
        assert "系统暂时无法处理" in refusal.message_zh
        assert "temporarily unable" in refusal.message_en.lower()
        
        # Restore templates
        self.handler.refusal_templates = original_templates
    
    def test_generate_policy_info_citation_policy(self):
        """Test policy info generation for citation-related refusals."""
        context = {"province": "guangdong", "asset": "solar"}
        
        policy_info = self.handler._generate_policy_info(
            RefusalCode.NO_FIRST_PARTY_CITATION, context
        )
        
        assert policy_info["policy_category"] == "citation_quality"
        assert "citation_policy" in policy_info
        assert policy_info["citation_policy"]["requires_first_party"] is True
        assert policy_info["citation_policy"]["min_citations"] == 1
    
    def test_generate_policy_info_geo_policy(self):
        """Test policy info generation for geographic refusals."""
        context = {"province": "shandong", "doc_class": "market_rules"}
        
        policy_info = self.handler._generate_policy_info(
            RefusalCode.PROVINCE_MISMATCH, context
        )
        
        assert policy_info["policy_category"] == "geographic_scope"
        assert "geo_policy" in policy_info
        assert policy_info["geo_policy"]["strict_province_matching"] is True
        assert "guangdong" in policy_info["geo_policy"]["supported_provinces"]
    
    def test_generate_policy_info_language_policy(self):
        """Test policy info generation for language refusals."""
        context = {"lang": "en"}
        
        policy_info = self.handler._generate_policy_info(
            RefusalCode.LANGUAGE_POLICY_VIOLATION, context
        )
        
        assert policy_info["policy_category"] == "content_policy"
        assert "language_policy" in policy_info
        assert policy_info["language_policy"]["primary_language"] == "zh-CN"
        assert policy_info["language_policy"]["english_summary_allowed"] is True
    
    def test_personalize_refusal_guangdong(self):
        """Test refusal personalization for Guangdong."""
        context = {"province": "guangdong", "asset": "solar"}
        
        refusal = RefusalResponse(
            code=RefusalCode.NO_FIRST_PARTY_CITATION,
            message_zh="原始消息",
            message_en="Original message",
            suggestion_zh="原始建议",
            suggestion_en="Original suggestion"
        )
        
        personalized = self.handler._personalize_refusal(refusal, context)
        
        assert "广东省电力交易中心" in personalized.suggestion_zh
    
    def test_personalize_refusal_asset_not_supported(self):
        """Test refusal personalization for unsupported asset."""
        context = {"province": "shandong", "asset": "wind"}
        
        refusal = RefusalResponse(
            code=RefusalCode.ASSET_NOT_SUPPORTED,
            message_zh="原始消息",
            message_en="Original message",
            suggestion_zh="原始建议",
            suggestion_en="Original suggestion"
        )
        
        personalized = self.handler._personalize_refusal(refusal, context)
        
        assert "山东省" in personalized.message_zh
        assert "风电" in personalized.message_zh
    
    def test_get_refusal_stats(self):
        """Test refusal statistics retrieval."""
        # Create some refusals to generate stats
        contexts = [
            {"province": "guangdong", "asset": "solar"},
            {"province": "guangdong", "asset": "wind"},
            {"province": "shandong", "doc_class": "market_rules"}
        ]
        
        codes = [
            RefusalCode.NO_FIRST_PARTY_CITATION,
            RefusalCode.STALE_CITATION,
            RefusalCode.NO_FIRST_PARTY_CITATION
        ]
        
        for context, code in zip(contexts, codes):
            self.handler.create_refusal(code=code, context=context)
        
        stats = self.handler.get_refusal_stats()
        
        assert stats["total_refusals"] == 3
        assert stats["refusal_by_code"]["no_first_party_citation"] == 2
        assert stats["refusal_by_code"]["stale_citation"] == 1
        assert stats["refusal_by_province"]["guangdong"] == 2
        assert stats["refusal_by_province"]["shandong"] == 1
        assert stats["refusal_by_asset"]["solar"] == 1
        assert stats["refusal_by_asset"]["wind"] == 1
        assert "timestamp" in stats
    
    def test_get_refusal_rate(self):
        """Test refusal rate calculation."""
        # No refusals initially
        assert self.handler.get_refusal_rate(100) == 0.0
        
        # Create some refusals
        for _ in range(15):
            self.handler.create_refusal(RefusalCode.NO_FIRST_PARTY_CITATION)
        
        # 15 refusals out of 100 total queries = 15%
        assert self.handler.get_refusal_rate(100) == 0.15
        
        # Handle zero total queries
        assert self.handler.get_refusal_rate(0) == 0.0
    
    def test_get_top_refusal_codes(self):
        """Test top refusal codes retrieval."""
        # Create refusals with different frequencies
        codes_and_counts = [
            (RefusalCode.NO_FIRST_PARTY_CITATION, 5),
            (RefusalCode.STALE_CITATION, 3),
            (RefusalCode.PROVINCE_MISMATCH, 2),
            (RefusalCode.RETRIEVAL_FAILED, 1)
        ]
        
        for code, count in codes_and_counts:
            for _ in range(count):
                self.handler.create_refusal(code)
        
        top_codes = self.handler.get_top_refusal_codes(3)
        
        assert len(top_codes) == 3
        assert top_codes[0]["code"] == "no_first_party_citation"
        assert top_codes[0]["count"] == 5
        assert top_codes[0]["percentage"] == 5/11  # 5 out of 11 total
        
        assert top_codes[1]["code"] == "stale_citation"
        assert top_codes[1]["count"] == 3
        
        assert top_codes[2]["code"] == "province_mismatch"
        assert top_codes[2]["count"] == 2
    
    def test_health_check_healthy(self):
        """Test healthy refusal handler health check."""
        health = self.handler.health_check()
        
        assert health["status"] == "healthy"
        assert health["templates_loaded"] > 0
        assert health["total_refusals"] == 0  # No refusals created yet
        assert health["unique_codes"] == 0
        assert "timestamp" in health
    
    def test_health_check_with_refusals(self):
        """Test health check after creating refusals."""
        # Create some refusals
        self.handler.create_refusal(RefusalCode.NO_FIRST_PARTY_CITATION)
        self.handler.create_refusal(RefusalCode.STALE_CITATION)
        
        health = self.handler.health_check()
        
        assert health["status"] == "healthy"
        assert health["total_refusals"] == 2
        assert health["unique_codes"] == 2
    
    def test_create_fallback_refusal(self):
        """Test fallback refusal creation."""
        fallback = self.handler._create_fallback_refusal("test-fallback-1")
        
        assert fallback.code == RefusalCode.SYSTEM_OVERLOAD
        assert "系统出现异常" in fallback.message_zh
        assert "system error" in fallback.message_en.lower()
        assert fallback.debug_info["fallback"] is True
        assert fallback.debug_info["trace_id"] == "test-fallback-1"


class TestRefusalHandlerGlobal:
    """Test global refusal handler functions."""
    
    def test_get_refusal_handler_singleton(self):
        """Test that get_refusal_handler returns singleton instance."""
        # Clear any existing instance
        import services.refusal.refusal_handler
        services.refusal.refusal_handler._refusal_handler = None
        
        handler1 = get_refusal_handler()
        handler2 = get_refusal_handler()
        
        assert handler1 is handler2
        assert isinstance(handler1, RefusalHandler)
    
    def test_create_refusal_convenience_function(self):
        """Test convenience function for creating refusals."""
        refusal = create_refusal(
            code=RefusalCode.RATE_LIMIT_EXCEEDED,
            context={"province": "guangdong"},
            custom_message="自定义限流消息",
            trace_id="test-convenience-1"
        )
        
        assert isinstance(refusal, RefusalResponse)
        assert refusal.code == RefusalCode.RATE_LIMIT_EXCEEDED
        assert refusal.message_zh == "自定义限流消息"
        assert refusal.policy_info is not None


class TestRefusalHandlerScenarios:
    """Test refusal handler with realistic scenarios."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.handler = RefusalHandler()
    
    def test_no_citations_guangdong_solar(self):
        """Test no citations scenario for Guangdong solar."""
        context = {
            "province": "guangdong",
            "doc_class": "grid_connection",
            "asset": "solar",
            "lang": "zh-CN",
            "question": "广东省光伏电站并网需要什么资料？"
        }
        
        refusal = self.handler.create_refusal(
            code=RefusalCode.NO_FIRST_PARTY_CITATION,
            context=context,
            trace_id="gd-solar-no-citations"
        )
        
        assert refusal.code == RefusalCode.NO_FIRST_PARTY_CITATION
        assert "没有找到来自官方一手来源" in refusal.message_zh
        assert "广东省电力交易中心" in refusal.suggestion_zh
        assert refusal.policy_info["citation_policy"]["requires_first_party"] is True
        assert refusal.policy_info["applicable_scope"]["province"] == "guangdong"
        assert refusal.policy_info["applicable_scope"]["asset"] == "solar"
    
    def test_stale_citations_shandong_wind(self):
        """Test stale citations scenario for Shandong wind."""
        context = {
            "province": "shandong",
            "doc_class": "market_rules",
            "asset": "wind",
            "lang": "zh-CN"
        }
        
        refusal = self.handler.create_refusal(
            code=RefusalCode.STALE_CITATION,
            context=context,
            debug_info={"oldest_citation_date": "2023-01-01", "cutoff_date": "2024-01-01"},
            trace_id="sd-wind-stale"
        )
        
        assert refusal.code == RefusalCode.STALE_CITATION
        assert "可能已过时" in refusal.message_zh
        assert "查询最新的官方文件" in refusal.suggestion_zh
        assert refusal.debug_info["oldest_citation_date"] == "2023-01-01"
        assert refusal.policy_info["citation_policy"]["max_age_days"] == 365
    
    def test_province_mismatch_inner_mongolia(self):
        """Test province mismatch scenario for Inner Mongolia."""
        context = {
            "province": "inner_mongolia",
            "doc_class": "dispatch_ops",
            "asset": "coal_flex",
            "lang": "zh-CN"
        }
        
        refusal = self.handler.create_refusal(
            code=RefusalCode.PROVINCE_MISMATCH,
            context=context,
            debug_info={"detected_provinces": ["guangdong", "shandong"], "expected_province": "inner_mongolia"},
            trace_id="im-coal-mismatch"
        )
        
        assert refusal.code == RefusalCode.PROVINCE_MISMATCH
        assert "与指定省份的政策范围不匹配" in refusal.message_zh
        assert refusal.policy_info["geo_policy"]["strict_province_matching"] is True
        assert "inner_mongolia" in refusal.policy_info["geo_policy"]["supported_provinces"]
    
    def test_rate_limit_exceeded(self):
        """Test rate limit exceeded scenario."""
        context = {
            "province": "guangdong",
            "user_id": "user123",
            "requests_in_window": 61,
            "window_limit": 60
        }
        
        refusal = self.handler.create_refusal(
            code=RefusalCode.RATE_LIMIT_EXCEEDED,
            context=context,
            debug_info={"requests_in_window": 61, "limit": 60, "reset_time": "2025-01-14T11:00:00Z"},
            trace_id="rate-limit-test"
        )
        
        assert refusal.code == RefusalCode.RATE_LIMIT_EXCEEDED
        assert "查询频率超过限制" in refusal.message_zh
        assert "等待一段时间" in refusal.suggestion_zh
        assert refusal.debug_info["requests_in_window"] == 61
    
    def test_language_policy_violation(self):
        """Test language policy violation scenario."""
        context = {
            "province": "guangdong",
            "lang": "en",
            "detected_language": "en",
            "required_language": "zh-CN"
        }
        
        refusal = self.handler.create_refusal(
            code=RefusalCode.LANGUAGE_POLICY_VIOLATION,
            context=context,
            trace_id="lang-policy-test"
        )
        
        assert refusal.code == RefusalCode.LANGUAGE_POLICY_VIOLATION
        assert "中文优先的语言政策" in refusal.message_zh
        assert "使用中文提交查询" in refusal.suggestion_zh
        assert refusal.policy_info["language_policy"]["primary_language"] == "zh-CN"
        assert refusal.policy_info["language_policy"]["english_summary_allowed"] is True
    
    def test_system_overload(self):
        """Test system overload scenario."""
        context = {
            "current_load": 95,
            "max_load": 80,
            "active_requests": 150,
            "max_requests": 100
        }
        
        refusal = self.handler.create_refusal(
            code=RefusalCode.SYSTEM_OVERLOAD,
            context=context,
            debug_info={"cpu_usage": 95, "memory_usage": 88, "queue_length": 50},
            trace_id="overload-test"
        )
        
        assert refusal.code == RefusalCode.SYSTEM_OVERLOAD
        assert "系统当前负载过高" in refusal.message_zh
        assert "稍后重试" in refusal.suggestion_zh
        assert refusal.debug_info["cpu_usage"] == 95


if __name__ == "__main__":
    pytest.main([__file__])