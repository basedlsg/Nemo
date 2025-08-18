"""Error response formatting for HTTP APIs with structured refusal handling."""

import logging
from typing import Dict, Any, Optional
from datetime import datetime

from fastapi import HTTPException
from fastapi.responses import JSONResponse

from .refusal_handler import RefusalResponse, RefusalCode, get_refusal_handler

logger = logging.getLogger(__name__)


class RefusalHTTPException(HTTPException):
    """Custom HTTP exception for refusal responses."""
    
    def __init__(
        self,
        refusal_response: RefusalResponse,
        status_code: int = 422,
        headers: Optional[Dict[str, str]] = None
    ):
        self.refusal_response = refusal_response
        super().__init__(
            status_code=status_code,
            detail=refusal_response.message_zh,
            headers=headers
        )


class ErrorFormatter:
    """
    Error response formatter that converts refusals and exceptions into structured HTTP responses.
    
    Features:
    - Standardized HTTP status codes for different error types
    - Bilingual error messages with fallback support
    - Structured error responses with debugging information
    - Request tracing and logging integration
    - Policy information for transparency
    """
    
    def __init__(self):
        """Initialize error formatter."""
        self.refusal_handler = get_refusal_handler()
        
        # HTTP status code mapping for refusal codes
        self.status_code_mapping = {
            # 422 - Unprocessable Entity (Policy violations, content issues)
            RefusalCode.NO_FIRST_PARTY_CITATION: 422,
            RefusalCode.STALE_CITATION: 422,
            RefusalCode.INSUFFICIENT_CITATIONS: 422,
            RefusalCode.CITATION_QUALITY_LOW: 422,
            RefusalCode.PROVINCE_MISMATCH: 422,
            RefusalCode.ASSET_NOT_SUPPORTED: 422,
            RefusalCode.DOC_CLASS_UNAVAILABLE: 422,
            RefusalCode.CROSS_PROVINCE_LEAKAGE: 422,
            RefusalCode.LANGUAGE_POLICY_VIOLATION: 422,
            RefusalCode.UNSAFE_CONTENT: 422,
            RefusalCode.CONFLICTING_REQUIREMENTS: 422,
            
            # 400 - Bad Request (Client input issues)
            RefusalCode.QUERY_TOO_VAGUE: 400,
            RefusalCode.QUERY_TOO_COMPLEX: 400,
            RefusalCode.PROMPT_INJECTION: 400,
            
            # 429 - Too Many Requests (Rate limiting)
            RefusalCode.RATE_LIMIT_EXCEEDED: 429,
            
            # 503 - Service Unavailable (System issues)
            RefusalCode.RETRIEVAL_FAILED: 503,
            RefusalCode.COMPOSITION_FAILED: 503,
            RefusalCode.GUARDRAILS_FAILED: 503,
            RefusalCode.SYSTEM_OVERLOAD: 503,
        }
    
    def format_refusal_response(
        self,
        refusal: RefusalResponse,
        trace_id: Optional[str] = None,
        include_debug: bool = False
    ) -> JSONResponse:
        """
        Format refusal response as structured HTTP JSON response.
        
        Args:
            refusal: Refusal response to format
            trace_id: Optional trace ID for request tracking
            include_debug: Whether to include debug information
            
        Returns:
            Structured JSON response with appropriate HTTP status code
        """
        try:
            # Determine HTTP status code
            status_code = self.status_code_mapping.get(refusal.code, 422)
            
            # Build response body
            response_body = {
                "error": "query_refused",
                "refusal_code": refusal.code.value,
                "message": refusal.message_zh,
                "message_en": refusal.message_en,
                "suggestion": refusal.suggestion_zh,
                "suggestion_en": refusal.suggestion_en,
                "timestamp": refusal.timestamp,
                "trace_id": trace_id
            }
            
            # Add policy information if available
            if refusal.policy_info:
                response_body["policy_info"] = refusal.policy_info
            
            # Add debug information if requested and available
            if include_debug and refusal.debug_info:
                response_body["debug_info"] = refusal.debug_info
            
            # Create response headers
            headers = {
                "Content-Type": "application/json",
                "X-Refusal-Code": refusal.code.value,
                "X-Refusal-Category": self._get_refusal_category(refusal.code)
            }
            
            if trace_id:
                headers["X-Trace-ID"] = trace_id
            
            logger.info(f"[{trace_id}] Formatted refusal response: {refusal.code.value} -> HTTP {status_code}")
            
            return JSONResponse(
                status_code=status_code,
                content=response_body,
                headers=headers
            )
            
        except Exception as e:
            logger.error(f"[{trace_id}] Failed to format refusal response: {e}")
            return self._create_fallback_error_response(trace_id)
    
    def format_exception_response(
        self,
        exception: Exception,
        trace_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> JSONResponse:
        """
        Format general exception as structured HTTP response.
        
        Args:
            exception: Exception to format
            trace_id: Optional trace ID for request tracking
            context: Optional context information
            
        Returns:
            Structured JSON error response
        """
        try:
            # Handle RefusalHTTPException specially
            if isinstance(exception, RefusalHTTPException):
                return self.format_refusal_response(
                    exception.refusal_response,
                    trace_id=trace_id
                )
            
            # Handle standard HTTPException
            if isinstance(exception, HTTPException):
                return self._format_http_exception(exception, trace_id)
            
            # Handle general exceptions
            return self._format_general_exception(exception, trace_id, context)
            
        except Exception as e:
            logger.error(f"[{trace_id}] Failed to format exception response: {e}")
            return self._create_fallback_error_response(trace_id)
    
    def create_refusal_exception(
        self,
        code: RefusalCode,
        context: Optional[Dict[str, Any]] = None,
        custom_message: Optional[str] = None,
        trace_id: Optional[str] = None
    ) -> RefusalHTTPException:
        """
        Create RefusalHTTPException from refusal code.
        
        Args:
            code: Refusal code
            context: Optional query context
            custom_message: Optional custom message
            trace_id: Optional trace ID
            
        Returns:
            RefusalHTTPException ready to be raised
        """
        refusal = self.refusal_handler.create_refusal(
            code=code,
            context=context,
            custom_message=custom_message,
            trace_id=trace_id
        )
        
        status_code = self.status_code_mapping.get(code, 422)
        
        return RefusalHTTPException(
            refusal_response=refusal,
            status_code=status_code,
            headers={"X-Trace-ID": trace_id} if trace_id else None
        )
    
    def _format_http_exception(
        self,
        exception: HTTPException,
        trace_id: Optional[str]
    ) -> JSONResponse:
        """Format standard HTTPException."""
        response_body = {
            "error": "http_error",
            "status_code": exception.status_code,
            "message": str(exception.detail),
            "timestamp": datetime.utcnow().isoformat(),
            "trace_id": trace_id
        }
        
        headers = {"Content-Type": "application/json"}
        if trace_id:
            headers["X-Trace-ID"] = trace_id
        
        return JSONResponse(
            status_code=exception.status_code,
            content=response_body,
            headers=headers
        )
    
    def _format_general_exception(
        self,
        exception: Exception,
        trace_id: Optional[str],
        context: Optional[Dict[str, Any]]
    ) -> JSONResponse:
        """Format general exception as internal server error."""
        # Determine refusal code based on exception type
        refusal_code = self._classify_exception(exception)
        
        # Create refusal response
        refusal = self.refusal_handler.create_refusal(
            code=refusal_code,
            context=context,
            debug_info={"exception_type": type(exception).__name__, "exception_message": str(exception)},
            trace_id=trace_id
        )
        
        return self.format_refusal_response(refusal, trace_id, include_debug=False)
    
    def _classify_exception(self, exception: Exception) -> RefusalCode:
        """Classify exception into appropriate refusal code."""
        exception_type = type(exception).__name__
        exception_message = str(exception).lower()
        
        # Classification based on exception type and message
        if "timeout" in exception_message or "connection" in exception_message:
            return RefusalCode.RETRIEVAL_FAILED
        elif "rate" in exception_message or "limit" in exception_message:
            return RefusalCode.RATE_LIMIT_EXCEEDED
        elif "overload" in exception_message or "capacity" in exception_message:
            return RefusalCode.SYSTEM_OVERLOAD
        elif "validation" in exception_message or "invalid" in exception_message:
            return RefusalCode.QUERY_TOO_VAGUE
        else:
            return RefusalCode.SYSTEM_OVERLOAD  # Default fallback
    
    def _get_refusal_category(self, code: RefusalCode) -> str:
        """Get refusal category for response headers."""
        if code in [RefusalCode.NO_FIRST_PARTY_CITATION, RefusalCode.STALE_CITATION]:
            return "citation_quality"
        elif code in [RefusalCode.PROVINCE_MISMATCH, RefusalCode.CROSS_PROVINCE_LEAKAGE]:
            return "geographic_scope"
        elif code in [RefusalCode.LANGUAGE_POLICY_VIOLATION, RefusalCode.UNSAFE_CONTENT]:
            return "content_policy"
        elif code in [RefusalCode.RETRIEVAL_FAILED, RefusalCode.COMPOSITION_FAILED]:
            return "system_error"
        elif code in [RefusalCode.QUERY_TOO_VAGUE, RefusalCode.QUERY_TOO_COMPLEX]:
            return "query_quality"
        else:
            return "general"
    
    def _create_fallback_error_response(self, trace_id: Optional[str]) -> JSONResponse:
        """Create fallback error response when formatting fails."""
        response_body = {
            "error": "internal_error",
            "message": "系统内部错误，请稍后重试。",
            "message_en": "Internal system error, please try again later.",
            "suggestion": "请联系技术支持获取帮助。",
            "suggestion_en": "Please contact technical support for assistance.",
            "timestamp": datetime.utcnow().isoformat(),
            "trace_id": trace_id
        }
        
        headers = {"Content-Type": "application/json"}
        if trace_id:
            headers["X-Trace-ID"] = trace_id
        
        return JSONResponse(
            status_code=500,
            content=response_body,
            headers=headers
        )
    
    def get_error_statistics(self) -> Dict[str, Any]:
        """Get error formatting statistics."""
        refusal_stats = self.refusal_handler.get_refusal_stats()
        
        return {
            "total_refusals": refusal_stats["total_refusals"],
            "refusal_by_code": refusal_stats["refusal_by_code"],
            "top_refusal_codes": self.refusal_handler.get_top_refusal_codes(5),
            "status_code_distribution": self._calculate_status_code_distribution(refusal_stats),
            "timestamp": datetime.utcnow().isoformat()
        }
    
    def _calculate_status_code_distribution(self, refusal_stats: Dict[str, Any]) -> Dict[str, int]:
        """Calculate distribution of HTTP status codes."""
        distribution = {}
        
        for code_str, count in refusal_stats["refusal_by_code"].items():
            try:
                refusal_code = RefusalCode(code_str)
                status_code = self.status_code_mapping.get(refusal_code, 422)
                distribution[str(status_code)] = distribution.get(str(status_code), 0) + count
            except ValueError:
                # Handle unknown refusal codes
                distribution["422"] = distribution.get("422", 0) + count
        
        return distribution


# Global error formatter instance
_error_formatter: Optional[ErrorFormatter] = None


def get_error_formatter() -> ErrorFormatter:
    """Get global error formatter instance."""
    global _error_formatter
    if _error_formatter is None:
        _error_formatter = ErrorFormatter()
    return _error_formatter


def format_refusal_response(
    refusal: RefusalResponse,
    trace_id: Optional[str] = None,
    include_debug: bool = False
) -> JSONResponse:
    """
    Convenience function for formatting refusal responses.
    
    Args:
        refusal: Refusal response to format
        trace_id: Optional trace ID
        include_debug: Whether to include debug information
        
    Returns:
        Structured JSON response
    """
    formatter = get_error_formatter()
    return formatter.format_refusal_response(refusal, trace_id, include_debug)


def create_refusal_exception(
    code: RefusalCode,
    context: Optional[Dict[str, Any]] = None,
    custom_message: Optional[str] = None,
    trace_id: Optional[str] = None
) -> RefusalHTTPException:
    """
    Convenience function for creating refusal exceptions.
    
    Args:
        code: Refusal code
        context: Optional query context
        custom_message: Optional custom message
        trace_id: Optional trace ID
        
    Returns:
        RefusalHTTPException ready to be raised
    """
    formatter = get_error_formatter()
    return formatter.create_refusal_exception(code, context, custom_message, trace_id)


if __name__ == "__main__":
    # Quick test of error formatter
    def test_error_formatter():
        print("=== Error Formatter Test ===")
        
        formatter = ErrorFormatter()
        
        # Test refusal response formatting
        print("\n--- Refusal Response Formatting ---")
        
        from .refusal_handler import RefusalHandler, RefusalCode
        
        handler = RefusalHandler()
        refusal = handler.create_refusal(
            code=RefusalCode.NO_FIRST_PARTY_CITATION,
            context={"province": "guangdong", "asset": "solar"},
            trace_id="test-format-1"
        )
        
        response = formatter.format_refusal_response(refusal, "test-format-1")
        
        print(f"Status code: {response.status_code}")
        print(f"Headers: {dict(response.headers)}")
        print(f"Body keys: {list(response.body.decode('utf-8'))}")
        
        # Test exception creation
        print("\n--- Exception Creation ---")
        
        exception = formatter.create_refusal_exception(
            code=RefusalCode.RATE_LIMIT_EXCEEDED,
            context={"province": "shandong"},
            trace_id="test-exception-1"
        )
        
        print(f"Exception type: {type(exception).__name__}")
        print(f"Status code: {exception.status_code}")
        print(f"Refusal code: {exception.refusal_response.code}")
        
        # Test statistics
        print("\n--- Error Statistics ---")
        stats = formatter.get_error_statistics()
        print(f"Total refusals: {stats['total_refusals']}")
        print(f"Status code distribution: {stats['status_code_distribution']}")
    
    test_error_formatter()