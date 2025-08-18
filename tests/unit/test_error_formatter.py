"""Tests for error formatter (Task 16)."""

import pytest
from unittest.mock import Mock, patch
from fastapi import HTTPException
from fastapi.responses import JSONResponse

from services.refusal.error_formatter import (
    ErrorFormatter, RefusalHTTPException, 
    get_error_formatter, format_refusal_response, create_refusal_exception
)
from services.refusal.refusal_handler import RefusalCode, RefusalResponse


class TestRefusalHTTPException:
    """Test RefusalHTTPException class."""
    
    def test_refusal_http_exception_creation(self):
        """Test RefusalHTTPException creation."""
        refusal_response = RefusalResponse(
            code=RefusalCode.NO_FIRST_PARTY_CITATION,
            message_zh="没有找到官方资料",
            message_en="No official sources found",
            suggestion_zh="请尝试其他关键词",
            suggestion_en="Try other keywords"
        )
        
        exception = RefusalHTTPException(
            refusal_response=refusal_response,
            status_code=422,
            headers={"X-Trace-ID": "test-123"}
        )
        
        assert exception.refusal_response == refusal_response
        assert exception.status_code == 422
        assert exception.detail == "没有找到官方资料"
        assert exception.headers == {"X-Trace-ID": "test-123"}
    
    def test_refusal_http_exception_default_status(self):
        """Test RefusalHTTPException with default status code."""
        refusal_response = RefusalResponse(
            code=RefusalCode.STALE_CITATION,
            message_zh="资料过时",
            message_en="Sources outdated",
            suggestion_zh="查询最新资料",
            suggestion_en="Check latest sources"
        )
        
        exception = RefusalHTTPException(refusal_response=refusal_response)
        
        assert exception.status_code == 422  # Default status code


class TestErrorFormatter:
    """Test error formatter functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.formatter = ErrorFormatter()
        
        self.sample_refusal = RefusalResponse(
            code=RefusalCode.NO_FIRST_PARTY_CITATION,
            message_zh="没有找到来自官方一手来源的相关资料。",
            message_en="Sorry, no official first-party sources found for your query.",
            suggestion_zh="请尝试使用更具体的关键词，或选择不同的省份和资产类型。",
            suggestion_en="Try using more specific keywords or select different province/asset types.",
            policy_info={
                "policy_category": "citation_quality",
                "citation_policy": {"requires_first_party": True, "min_citations": 1}
            },
            timestamp="2025-01-14T10:00:00Z"
        )
    
    def test_formatter_initialization(self):
        """Test formatter initialization."""
        assert self.formatter.refusal_handler is not None
        assert len(self.formatter.status_code_mapping) > 0
        
        # Check some key status code mappings
        assert self.formatter.status_code_mapping[RefusalCode.NO_FIRST_PARTY_CITATION] == 422
        assert self.formatter.status_code_mapping[RefusalCode.RATE_LIMIT_EXCEEDED] == 429
        assert self.formatter.status_code_mapping[RefusalCode.RETRIEVAL_FAILED] == 503
        assert self.formatter.status_code_mapping[RefusalCode.QUERY_TOO_VAGUE] == 400
    
    def test_format_refusal_response_basic(self):
        """Test basic refusal response formatting."""
        response = self.formatter.format_refusal_response(
            self.sample_refusal,
            trace_id="test-format-1"
        )
        
        assert isinstance(response, JSONResponse)
        assert response.status_code == 422
        
        # Check headers
        headers = dict(response.headers)
        assert headers["Content-Type"] == "application/json"
        assert headers["X-Refusal-Code"] == "no_first_party_citation"
        assert headers["X-Refusal-Category"] == "citation_quality"
        assert headers["X-Trace-ID"] == "test-format-1"
        
        # Check response body (would need to decode JSON in real test)
        # For now, just verify it's not empty
        assert response.body is not None
    
    def test_format_refusal_response_with_debug(self):
        """Test refusal response formatting with debug information."""
        refusal_with_debug = RefusalResponse(
            code=RefusalCode.RETRIEVAL_FAILED,
            message_zh="检索系统暂时无法处理您的查询。",
            message_en="Retrieval system temporarily unable to process your query.",
            suggestion_zh="请稍后重试，或联系技术支持获取帮助。",
            suggestion_en="Please try again later or contact technical support for assistance.",
            debug_info={"error_details": "Connection timeout", "retry_count": 3}
        )
        
        response = self.formatter.format_refusal_response(
            refusal_with_debug,
            trace_id="test-debug-1",
            include_debug=True
        )
        
        assert response.status_code == 503  # Service unavailable for retrieval failed
        
        # Headers should include refusal category
        headers = dict(response.headers)
        assert headers["X-Refusal-Category"] == "system_error"
    
    def test_format_refusal_response_different_status_codes(self):
        """Test different refusal codes map to correct HTTP status codes."""
        test_cases = [
            (RefusalCode.NO_FIRST_PARTY_CITATION, 422),
            (RefusalCode.RATE_LIMIT_EXCEEDED, 429),
            (RefusalCode.RETRIEVAL_FAILED, 503),
            (RefusalCode.QUERY_TOO_VAGUE, 400),
            (RefusalCode.PROVINCE_MISMATCH, 422)
        ]
        
        for refusal_code, expected_status in test_cases:
            refusal = RefusalResponse(
                code=refusal_code,
                message_zh="测试消息",
                message_en="Test message",
                suggestion_zh="测试建议",
                suggestion_en="Test suggestion"
            )
            
            response = self.formatter.format_refusal_response(refusal)
            assert response.status_code == expected_status
    
    def test_format_exception_response_refusal_http_exception(self):
        """Test formatting RefusalHTTPException."""
        exception = RefusalHTTPException(
            refusal_response=self.sample_refusal,
            status_code=422
        )
        
        response = self.formatter.format_exception_response(
            exception,
            trace_id="test-refusal-exception-1"
        )
        
        assert response.status_code == 422
        
        headers = dict(response.headers)
        assert headers["X-Refusal-Code"] == "no_first_party_citation"
        assert headers["X-Trace-ID"] == "test-refusal-exception-1"
    
    def test_format_exception_response_http_exception(self):
        """Test formatting standard HTTPException."""
        exception = HTTPException(status_code=400, detail="Bad request")
        
        response = self.formatter.format_exception_response(
            exception,
            trace_id="test-http-exception-1"
        )
        
        assert response.status_code == 400
        
        headers = dict(response.headers)
        assert headers["X-Trace-ID"] == "test-http-exception-1"
    
    def test_format_exception_response_general_exception(self):
        """Test formatting general exception."""
        exception = ValueError("Invalid input value")
        context = {"province": "guangdong", "asset": "solar"}
        
        response = self.formatter.format_exception_response(
            exception,
            trace_id="test-general-exception-1",
            context=context
        )
        
        # Should be formatted as a refusal response
        assert response.status_code in [400, 422, 503]  # Depends on classification
        
        headers = dict(response.headers)
        assert headers["X-Trace-ID"] == "test-general-exception-1"
    
    def test_create_refusal_exception(self):
        """Test creating RefusalHTTPException."""
        context = {"province": "shandong", "doc_class": "market_rules"}
        
        exception = self.formatter.create_refusal_exception(
            code=RefusalCode.PROVINCE_MISMATCH,
            context=context,
            custom_message="自定义省份不匹配消息",
            trace_id="test-create-exception-1"
        )
        
        assert isinstance(exception, RefusalHTTPException)
        assert exception.status_code == 422
        assert exception.refusal_response.code == RefusalCode.PROVINCE_MISMATCH
        assert exception.refusal_response.message_zh == "自定义省份不匹配消息"
        assert exception.refusal_response.policy_info is not None
        assert exception.headers["X-Trace-ID"] == "test-create-exception-1"
    
    def test_classify_exception_timeout(self):
        """Test exception classification for timeout errors."""
        timeout_exception = Exception("Connection timeout occurred")
        
        code = self.formatter._classify_exception(timeout_exception)
        assert code == RefusalCode.RETRIEVAL_FAILED
    
    def test_classify_exception_rate_limit(self):
        """Test exception classification for rate limit errors."""
        rate_limit_exception = Exception("Rate limit exceeded")
        
        code = self.formatter._classify_exception(rate_limit_exception)
        assert code == RefusalCode.RATE_LIMIT_EXCEEDED
    
    def test_classify_exception_overload(self):
        """Test exception classification for overload errors."""
        overload_exception = Exception("System overload detected")
        
        code = self.formatter._classify_exception(overload_exception)
        assert code == RefusalCode.SYSTEM_OVERLOAD
    
    def test_classify_exception_validation(self):
        """Test exception classification for validation errors."""
        validation_exception = Exception("Invalid input validation failed")
        
        code = self.formatter._classify_exception(validation_exception)
        assert code == RefusalCode.QUERY_TOO_VAGUE
    
    def test_classify_exception_default(self):
        """Test exception classification for unknown errors."""
        unknown_exception = Exception("Unknown error occurred")
        
        code = self.formatter._classify_exception(unknown_exception)
        assert code == RefusalCode.SYSTEM_OVERLOAD  # Default fallback
    
    def test_get_refusal_category(self):
        """Test refusal category determination."""
        test_cases = [
            (RefusalCode.NO_FIRST_PARTY_CITATION, "citation_quality"),
            (RefusalCode.STALE_CITATION, "citation_quality"),
            (RefusalCode.PROVINCE_MISMATCH, "geographic_scope"),
            (RefusalCode.CROSS_PROVINCE_LEAKAGE, "geographic_scope"),
            (RefusalCode.LANGUAGE_POLICY_VIOLATION, "content_policy"),
            (RefusalCode.UNSAFE_CONTENT, "content_policy"),
            (RefusalCode.RETRIEVAL_FAILED, "system_error"),
            (RefusalCode.COMPOSITION_FAILED, "system_error"),
            (RefusalCode.QUERY_TOO_VAGUE, "query_quality"),
            (RefusalCode.QUERY_TOO_COMPLEX, "query_quality"),
            (RefusalCode.RATE_LIMIT_EXCEEDED, "general")  # Not in specific categories
        ]
        
        for refusal_code, expected_category in test_cases:
            category = self.formatter._get_refusal_category(refusal_code)
            assert category == expected_category
    
    def test_create_fallback_error_response(self):
        """Test fallback error response creation."""
        response = self.formatter._create_fallback_error_response("test-fallback-1")
        
        assert response.status_code == 500
        
        headers = dict(response.headers)
        assert headers["Content-Type"] == "application/json"
        assert headers["X-Trace-ID"] == "test-fallback-1"
    
    def test_get_error_statistics(self):
        """Test error statistics retrieval."""
        # Create some refusals to generate statistics
        self.formatter.refusal_handler.create_refusal(RefusalCode.NO_FIRST_PARTY_CITATION)
        self.formatter.refusal_handler.create_refusal(RefusalCode.RATE_LIMIT_EXCEEDED)
        self.formatter.refusal_handler.create_refusal(RefusalCode.RETRIEVAL_FAILED)
        
        stats = self.formatter.get_error_statistics()
        
        assert stats["total_refusals"] == 3
        assert "refusal_by_code" in stats
        assert "top_refusal_codes" in stats
        assert "status_code_distribution" in stats
        assert "timestamp" in stats
        
        # Check status code distribution
        distribution = stats["status_code_distribution"]
        assert "422" in distribution  # NO_FIRST_PARTY_CITATION
        assert "429" in distribution  # RATE_LIMIT_EXCEEDED
        assert "503" in distribution  # RETRIEVAL_FAILED
    
    def test_calculate_status_code_distribution(self):
        """Test status code distribution calculation."""
        refusal_stats = {
            "refusal_by_code": {
                "no_first_party_citation": 5,
                "rate_limit_exceeded": 3,
                "retrieval_failed": 2,
                "unknown_code": 1  # Should default to 422
            }
        }
        
        distribution = self.formatter._calculate_status_code_distribution(refusal_stats)
        
        assert distribution["422"] == 6  # 5 + 1 (unknown defaults to 422)
        assert distribution["429"] == 3
        assert distribution["503"] == 2


class TestErrorFormatterGlobal:
    """Test global error formatter functions."""
    
    def test_get_error_formatter_singleton(self):
        """Test that get_error_formatter returns singleton instance."""
        # Clear any existing instance
        import services.refusal.error_formatter
        services.refusal.error_formatter._error_formatter = None
        
        formatter1 = get_error_formatter()
        formatter2 = get_error_formatter()
        
        assert formatter1 is formatter2
        assert isinstance(formatter1, ErrorFormatter)
    
    def test_format_refusal_response_convenience_function(self):
        """Test convenience function for formatting refusal responses."""
        refusal = RefusalResponse(
            code=RefusalCode.STALE_CITATION,
            message_zh="资料过时",
            message_en="Sources outdated",
            suggestion_zh="查询最新资料",
            suggestion_en="Check latest sources"
        )
        
        response = format_refusal_response(
            refusal,
            trace_id="test-convenience-1",
            include_debug=True
        )
        
        assert isinstance(response, JSONResponse)
        assert response.status_code == 422
        
        headers = dict(response.headers)
        assert headers["X-Trace-ID"] == "test-convenience-1"
    
    def test_create_refusal_exception_convenience_function(self):
        """Test convenience function for creating refusal exceptions."""
        context = {"province": "guangdong", "asset": "wind"}
        
        exception = create_refusal_exception(
            code=RefusalCode.ASSET_NOT_SUPPORTED,
            context=context,
            custom_message="风电在广东暂不支持",
            trace_id="test-convenience-exception-1"
        )
        
        assert isinstance(exception, RefusalHTTPException)
        assert exception.status_code == 422
        assert exception.refusal_response.code == RefusalCode.ASSET_NOT_SUPPORTED
        assert exception.refusal_response.message_zh == "风电在广东暂不支持"


class TestErrorFormatterScenarios:
    """Test error formatter with realistic scenarios."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.formatter = ErrorFormatter()
    
    def test_no_citations_scenario_guangdong_solar(self):
        """Test no citations scenario formatting for Guangdong solar."""
        context = {
            "province": "guangdong",
            "doc_class": "grid_connection",
            "asset": "solar",
            "lang": "zh-CN"
        }
        
        exception = self.formatter.create_refusal_exception(
            code=RefusalCode.NO_FIRST_PARTY_CITATION,
            context=context,
            trace_id="gd-solar-no-citations"
        )
        
        response = self.formatter.format_refusal_response(
            exception.refusal_response,
            trace_id="gd-solar-no-citations"
        )
        
        assert response.status_code == 422
        
        headers = dict(response.headers)
        assert headers["X-Refusal-Code"] == "no_first_party_citation"
        assert headers["X-Refusal-Category"] == "citation_quality"
        assert headers["X-Trace-ID"] == "gd-solar-no-citations"
    
    def test_rate_limit_scenario(self):
        """Test rate limit exceeded scenario formatting."""
        context = {
            "province": "shandong",
            "user_id": "user123",
            "requests_in_window": 61,
            "window_limit": 60
        }
        
        exception = self.formatter.create_refusal_exception(
            code=RefusalCode.RATE_LIMIT_EXCEEDED,
            context=context,
            trace_id="rate-limit-test"
        )
        
        response = self.formatter.format_refusal_response(
            exception.refusal_response,
            trace_id="rate-limit-test"
        )
        
        assert response.status_code == 429  # Too Many Requests
        
        headers = dict(response.headers)
        assert headers["X-Refusal-Code"] == "rate_limit_exceeded"
        assert headers["X-Refusal-Category"] == "general"
    
    def test_system_error_scenario(self):
        """Test system error scenario formatting."""
        context = {"province": "inner_mongolia", "doc_class": "dispatch_ops"}
        
        exception = self.formatter.create_refusal_exception(
            code=RefusalCode.RETRIEVAL_FAILED,
            context=context,
            trace_id="system-error-test"
        )
        
        response = self.formatter.format_refusal_response(
            exception.refusal_response,
            trace_id="system-error-test",
            include_debug=True
        )
        
        assert response.status_code == 503  # Service Unavailable
        
        headers = dict(response.headers)
        assert headers["X-Refusal-Code"] == "retrieval_failed"
        assert headers["X-Refusal-Category"] == "system_error"
    
    def test_validation_error_scenario(self):
        """Test validation error scenario formatting."""
        context = {"province": "guangdong", "question": "太模糊的问题"}
        
        exception = self.formatter.create_refusal_exception(
            code=RefusalCode.QUERY_TOO_VAGUE,
            context=context,
            trace_id="validation-error-test"
        )
        
        response = self.formatter.format_refusal_response(
            exception.refusal_response,
            trace_id="validation-error-test"
        )
        
        assert response.status_code == 400  # Bad Request
        
        headers = dict(response.headers)
        assert headers["X-Refusal-Code"] == "query_too_vague"
        assert headers["X-Refusal-Category"] == "query_quality"
    
    def test_policy_violation_scenario(self):
        """Test policy violation scenario formatting."""
        context = {
            "province": "guangdong",
            "detected_provinces": ["shandong", "inner_mongolia"],
            "expected_province": "guangdong"
        }
        
        exception = self.formatter.create_refusal_exception(
            code=RefusalCode.CROSS_PROVINCE_LEAKAGE,
            context=context,
            trace_id="policy-violation-test"
        )
        
        response = self.formatter.format_refusal_response(
            exception.refusal_response,
            trace_id="policy-violation-test"
        )
        
        assert response.status_code == 422  # Unprocessable Entity
        
        headers = dict(response.headers)
        assert headers["X-Refusal-Code"] == "cross_province_leakage"
        assert headers["X-Refusal-Category"] == "geographic_scope"


if __name__ == "__main__":
    pytest.main([__file__])