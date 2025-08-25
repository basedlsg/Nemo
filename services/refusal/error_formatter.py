from fastapi import HTTPException, JSONResponse
from typing import Dict, Any, Optional, Union
from enum import Enum


class RefusalCode(str, Enum):
    """Standard refusal codes for consistent error handling."""
    NO_FIRST_PARTY_CITATION = "no_first_party_citation"
    STALE_CITATION = "stale_citation"
    PROVINCE_MISMATCH = "province_mismatch"
    UNSUPPORTED_DOC_CLASS = "unsupported_doc_class"
    QUERY_TOO_VAGUE = "query_too_vague"
    LANGUAGE_POLICY_VIOLATION = "language_policy_violation"
    SYSTEM_UNAVAILABLE = "system_unavailable"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    INVALID_REQUEST = "invalid_request"


class RefusalHTTPException(HTTPException):
    """Enhanced HTTP exception for refusal responses with structured data."""

    def __init__(
        self,
        code: Union[str, RefusalCode],
        message_zh: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        trace_id: Optional[str] = None,
        status_code: Optional[int] = None
    ):
        self.refusal_code = RefusalCode(code) if isinstance(code, str) else code
        self.message_zh = message_zh
        self.context = context or {}
        self.trace_id = trace_id

        # Determine status code if not provided
        if status_code is None:
            status_code = self._get_default_status_code()

        # Create structured payload
        detail = {
            "error": "refused",
            "code": self.refusal_code.value,
            "message_zh": self.message_zh or self._get_default_message_zh(),
            "context": self.context,
            "trace_id": self.trace_id,
        }

        super().__init__(status_code=status_code, detail=detail)

    def _get_default_status_code(self) -> int:
        """Get default HTTP status code for refusal type."""
        user_error_codes = {
            RefusalCode.NO_FIRST_PARTY_CITATION,
            RefusalCode.STALE_CITATION,
            RefusalCode.PROVINCE_MISMATCH,
            RefusalCode.UNSUPPORTED_DOC_CLASS,
            RefusalCode.QUERY_TOO_VAGUE,
            RefusalCode.LANGUAGE_POLICY_VIOLATION,
            RefusalCode.INVALID_REQUEST,
        }

        if self.refusal_code in user_error_codes:
            return 422  # Unprocessable Entity
        elif self.refusal_code == RefusalCode.RATE_LIMIT_EXCEEDED:
            return 429  # Too Many Requests
        else:
            return 503  # Service Unavailable

    def _get_default_message_zh(self) -> str:
        """Get default Chinese message for refusal code."""
        messages = {
            RefusalCode.NO_FIRST_PARTY_CITATION: "未找到官方一手引用文件",
            RefusalCode.STALE_CITATION: "仅找到已过期的引用文件",
            RefusalCode.PROVINCE_MISMATCH: "查询省份不在支持范围内",
            RefusalCode.UNSUPPORTED_DOC_CLASS: "该省份不支持此文档类别",
            RefusalCode.QUERY_TOO_VAGUE: "查询内容过于模糊，请提供更具体的问题",
            RefusalCode.LANGUAGE_POLICY_VIOLATION: "语言政策违规，请使用中文提问",
            RefusalCode.SYSTEM_UNAVAILABLE: "系统暂时不可用，请稍后重试",
            RefusalCode.RATE_LIMIT_EXCEEDED: "请求频率过高，请稍后重试",
            RefusalCode.INVALID_REQUEST: "请求格式无效，请检查参数",
        }
        return messages.get(self.refusal_code, "系统错误")


class ErrorFormatter:
    """Centralized error formatting and response handling."""

    def __init__(self):
        self.status_code_mapping = {
            RefusalCode.NO_FIRST_PARTY_CITATION: 422,
            RefusalCode.STALE_CITATION: 422,
            RefusalCode.PROVINCE_MISMATCH: 422,
            RefusalCode.UNSUPPORTED_DOC_CLASS: 422,
            RefusalCode.QUERY_TOO_VAGUE: 422,
            RefusalCode.LANGUAGE_POLICY_VIOLATION: 422,
            RefusalCode.INVALID_REQUEST: 422,
            RefusalCode.RATE_LIMIT_EXCEEDED: 429,
            RefusalCode.SYSTEM_UNAVAILABLE: 503,
        }

    def format_refusal_response(
        self,
        code: Union[str, RefusalCode],
        message_zh: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        trace_id: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None
    ) -> JSONResponse:
        """Format a refusal response as JSONResponse with proper headers."""
        refusal_code = RefusalCode(code) if isinstance(code, str) else code
        status_code = self.status_code_mapping.get(refusal_code, 503)

        # Get default message if not provided
        if message_zh is None:
            default_messages = {
                RefusalCode.NO_FIRST_PARTY_CITATION: "未找到官方一手引用文件",
                RefusalCode.STALE_CITATION: "仅找到已过期的引用文件",
                RefusalCode.PROVINCE_MISMATCH: "查询省份不在支持范围内",
                RefusalCode.UNSUPPORTED_DOC_CLASS: "该省份不支持此文档类别",
                RefusalCode.QUERY_TOO_VAGUE: "查询内容过于模糊，请提供更具体的问题",
                RefusalCode.LANGUAGE_POLICY_VIOLATION: "语言政策违规，请使用中文提问",
                RefusalCode.SYSTEM_UNAVAILABLE: "系统暂时不可用，请稍后重试",
                RefusalCode.RATE_LIMIT_EXCEEDED: "请求频率过高，请稍后重试",
                RefusalCode.INVALID_REQUEST: "请求格式无效，请检查参数",
            }
            message_zh = default_messages.get(refusal_code, "系统错误")

        # Build response payload
        payload = {
            "error": "refused",
            "code": refusal_code.value,
            "message_zh": message_zh,
            "context": context or {},
            "trace_id": trace_id,
            "timestamp": self._get_current_timestamp()
        }

        # Add default headers
        response_headers = {
            "Content-Type": "application/json",
            "X-Error-Code": refusal_code.value,
        }
        if trace_id:
            response_headers["X-Trace-ID"] = trace_id
        if headers:
            response_headers.update(headers)

        return JSONResponse(
            status_code=status_code,
            content=payload,
            headers=response_headers
        )

    def format_exception_response(
        self,
        exception: Exception,
        trace_id: Optional[str] = None,
        include_stack_trace: bool = False
    ) -> JSONResponse:
        """Convert an exception into a structured refusal response."""
        # Determine error code and message based on exception type
        if isinstance(exception, RefusalHTTPException):
            return self.format_refusal_response(
                code=exception.refusal_code,
                message_zh=exception.message_zh,
                context=exception.context,
                trace_id=exception.trace_id or trace_id
            )
        elif isinstance(exception, HTTPException):
            # Convert regular HTTPException to refusal format
            error_code = self._map_http_status_to_refusal_code(exception.status_code)
            return self.format_refusal_response(
                code=error_code,
                message_zh=f"HTTP {exception.status_code}: {str(exception.detail)}",
                context={"original_detail": exception.detail},
                trace_id=trace_id
            )
        else:
            # Generic system error
            error_code = RefusalCode.SYSTEM_UNAVAILABLE
            context = {
                "exception_type": type(exception).__name__,
                "exception_message": str(exception)
            }

            if include_stack_trace:
                import traceback
                context["stack_trace"] = traceback.format_exc()

            return self.format_refusal_response(
                code=error_code,
                message_zh="系统内部错误，请稍后重试",
                context=context,
                trace_id=trace_id
            )

    def _map_http_status_to_refusal_code(self, status_code: int) -> RefusalCode:
        """Map HTTP status codes to refusal codes."""
        mapping = {
            400: RefusalCode.INVALID_REQUEST,
            401: RefusalCode.INVALID_REQUEST,
            403: RefusalCode.INVALID_REQUEST,
            404: RefusalCode.INVALID_REQUEST,
            422: RefusalCode.INVALID_REQUEST,
            429: RefusalCode.RATE_LIMIT_EXCEEDED,
            500: RefusalCode.SYSTEM_UNAVAILABLE,
            502: RefusalCode.SYSTEM_UNAVAILABLE,
            503: RefusalCode.SYSTEM_UNAVAILABLE,
            504: RefusalCode.SYSTEM_UNAVAILABLE,
        }
        return mapping.get(status_code, RefusalCode.SYSTEM_UNAVAILABLE)

    def _get_current_timestamp(self) -> str:
        """Get current timestamp in ISO format."""
        from datetime import datetime
        return datetime.utcnow().isoformat()

    def get_status_code_for_code(self, code: Union[str, RefusalCode]) -> int:
        """Get HTTP status code for a refusal code."""
        refusal_code = RefusalCode(code) if isinstance(code, str) else code
        return self.status_code_mapping.get(refusal_code, 503)


# Legacy function for backward compatibility
def create_refusal_exception(code: str, context: dict | None = None, trace_id: str | None = None):
    """Create a refusal exception (legacy function)."""
    payload = {
        "error": "refused",
        "code": code,
        "context": context or {},
        "trace_id": trace_id,
    }
    # Use 422 for policy/user errors, 503 for system
    status = 422 if code in {"no_first_party_citation","query_too_vague","language_policy_violation"} else 503
    # NEVER raise anything but HTTPException here
    return HTTPException(status_code=status, detail=payload)


# Global error formatter instance
_error_formatter: Optional[ErrorFormatter] = None


def get_error_formatter() -> ErrorFormatter:
    """Get global error formatter instance."""
    global _error_formatter
    if _error_formatter is None:
        _error_formatter = ErrorFormatter()
    return _error_formatter


def format_refusal_response(
    code: Union[str, RefusalCode],
    message_zh: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
    trace_id: Optional[str] = None,
    headers: Optional[Dict[str, str]] = None
) -> JSONResponse:
    """Convenience function to format refusal response."""
    formatter = get_error_formatter()
    return formatter.format_refusal_response(
        code=code,
        message_zh=message_zh,
        context=context,
        trace_id=trace_id,
        headers=headers
    )
