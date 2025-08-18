"""Middleware for API gateway request processing and validation."""

import logging
import time
import json
from typing import Dict, Any, Optional
from datetime import datetime

from fastapi import Request, Response, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from .models import Province, Asset, DocClass, generate_trace_id

logger = logging.getLogger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for structured request logging."""
    
    async def dispatch(self, request: Request, call_next):
        """Process request with structured logging."""
        start_time = time.time()
        trace_id = generate_trace_id()
        
        # Add trace_id to request state
        request.state.trace_id = trace_id
        request.state.start_time = start_time
        
        # Log incoming request
        await self._log_request(request, trace_id)
        
        try:
            response = await call_next(request)
            
            # Log successful response
            processing_time = (time.time() - start_time) * 1000
            await self._log_response(request, response, trace_id, processing_time, "success")
            
            # Add trace_id to response headers
            response.headers["X-Trace-ID"] = trace_id
            response.headers["X-Processing-Time-MS"] = str(int(processing_time))
            
            return response
            
        except Exception as e:
            # Log error response
            processing_time = (time.time() - start_time) * 1000
            await self._log_error(request, e, trace_id, processing_time)
            
            # Return structured error response
            return JSONResponse(
                status_code=500,
                content={
                    "error": "Internal server error",
                    "trace_id": trace_id,
                    "timestamp": datetime.utcnow().isoformat()
                },
                headers={"X-Trace-ID": trace_id}
            )
    
    async def _log_request(self, request: Request, trace_id: str):
        """Log incoming request with structured format."""
        try:
            # Extract query parameters
            query_params = dict(request.query_params)
            
            # Try to extract body for POST requests
            body = None
            if request.method == "POST":
                try:
                    body_bytes = await request.body()
                    if body_bytes:
                        body = json.loads(body_bytes.decode())
                        # Re-set body for downstream processing
                        request._body = body_bytes
                except Exception:
                    body = {"error": "Could not parse body"}
            
            log_data = {
                "event": "request_received",
                "trace_id": trace_id,
                "method": request.method,
                "path": str(request.url.path),
                "query_params": query_params,
                "body": body,
                "client_ip": request.client.host if request.client else None,
                "user_agent": request.headers.get("user-agent"),
                "timestamp": datetime.utcnow().isoformat()
            }
            
            logger.info(json.dumps(log_data, ensure_ascii=False))
            
        except Exception as e:
            logger.error(f"Failed to log request: {e}")
    
    async def _log_response(self, request: Request, response: Response, trace_id: str, processing_time: float, status: str):
        """Log response with structured format."""
        try:
            log_data = {
                "event": "request_completed",
                "trace_id": trace_id,
                "status": status,
                "status_code": response.status_code,
                "processing_time_ms": int(processing_time),
                "path": str(request.url.path),
                "method": request.method,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            logger.info(json.dumps(log_data, ensure_ascii=False))
            
        except Exception as e:
            logger.error(f"Failed to log response: {e}")
    
    async def _log_error(self, request: Request, error: Exception, trace_id: str, processing_time: float):
        """Log error with structured format."""
        try:
            log_data = {
                "event": "request_error",
                "trace_id": trace_id,
                "error_type": type(error).__name__,
                "error_message": str(error),
                "processing_time_ms": int(processing_time),
                "path": str(request.url.path),
                "method": request.method,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            logger.error(json.dumps(log_data, ensure_ascii=False))
            
        except Exception as e:
            logger.error(f"Failed to log error: {e}")


class ValidationMiddleware(BaseHTTPMiddleware):
    """Middleware for request validation and preprocessing."""
    
    async def dispatch(self, request: Request, call_next):
        """Validate request parameters and preprocessing."""
        try:
            # Skip validation for health checks and docs
            if request.url.path in ["/health", "/docs", "/openapi.json", "/redoc"]:
                return await call_next(request)
            
            # Validate query endpoints
            if request.url.path == "/query" and request.method == "POST":
                await self._validate_query_request(request)
            
            return await call_next(request)
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Validation middleware error: {e}")
            raise HTTPException(status_code=500, detail="Validation error")
    
    async def _validate_query_request(self, request: Request):
        """Validate query request parameters."""
        try:
            # Parse request body
            body_bytes = await request.body()
            if not body_bytes:
                raise HTTPException(status_code=400, detail="Request body is required")
            
            try:
                body = json.loads(body_bytes.decode())
            except json.JSONDecodeError:
                raise HTTPException(status_code=400, detail="Invalid JSON in request body")
            
            # Re-set body for downstream processing
            request._body = body_bytes
            
            # Validate required fields
            required_fields = ["question", "province", "doc_class"]
            for field in required_fields:
                if field not in body:
                    raise HTTPException(
                        status_code=400, 
                        detail=f"Missing required field: {field}"
                    )
            
            # Validate enum values
            try:
                Province(body["province"])
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid province: {body['province']}. Allowed values: {[p.value for p in Province]}"
                )
            
            try:
                DocClass(body["doc_class"])
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid doc_class: {body['doc_class']}. Allowed values: {[d.value for d in DocClass]}"
                )
            
            # Validate optional asset field
            if "asset" in body and body["asset"] is not None:
                try:
                    Asset(body["asset"])
                except ValueError:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Invalid asset: {body['asset']}. Allowed values: {[a.value for a in Asset]}"
                    )
            
            # Validate question length
            question = body.get("question", "")
            if not question or not question.strip():
                raise HTTPException(status_code=400, detail="Question cannot be empty")
            
            if len(question) > 500:
                raise HTTPException(status_code=400, detail="Question too long (max 500 characters)")
            
            # Validate max_citations if provided
            if "max_citations" in body:
                max_citations = body["max_citations"]
                if not isinstance(max_citations, int) or max_citations < 1 or max_citations > 20:
                    raise HTTPException(
                        status_code=400,
                        detail="max_citations must be an integer between 1 and 20"
                    )
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Query validation error: {e}")
            raise HTTPException(status_code=400, detail="Request validation failed")


class RateLimitingMiddleware(BaseHTTPMiddleware):
    """Simple rate limiting middleware."""
    
    def __init__(self, app, requests_per_minute: int = 60):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.request_counts: Dict[str, Dict[str, Any]] = {}
    
    async def dispatch(self, request: Request, call_next):
        """Apply rate limiting based on client IP."""
        try:
            # Skip rate limiting for health checks
            if request.url.path in ["/health", "/docs", "/openapi.json", "/redoc"]:
                return await call_next(request)
            
            client_ip = request.client.host if request.client else "unknown"
            current_time = time.time()
            current_minute = int(current_time // 60)
            
            # Clean old entries
            self._cleanup_old_entries(current_minute)
            
            # Check rate limit
            if client_ip in self.request_counts:
                client_data = self.request_counts[client_ip]
                if client_data["minute"] == current_minute:
                    if client_data["count"] >= self.requests_per_minute:
                        raise HTTPException(
                            status_code=429,
                            detail=f"Rate limit exceeded: {self.requests_per_minute} requests per minute"
                        )
                    client_data["count"] += 1
                else:
                    # New minute, reset count
                    self.request_counts[client_ip] = {"minute": current_minute, "count": 1}
            else:
                # New client
                self.request_counts[client_ip] = {"minute": current_minute, "count": 1}
            
            return await call_next(request)
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Rate limiting error: {e}")
            return await call_next(request)
    
    def _cleanup_old_entries(self, current_minute: int):
        """Clean up old rate limiting entries."""
        try:
            # Remove entries older than 2 minutes
            cutoff_minute = current_minute - 2
            to_remove = [
                ip for ip, data in self.request_counts.items()
                if data["minute"] < cutoff_minute
            ]
            for ip in to_remove:
                del self.request_counts[ip]
        except Exception as e:
            logger.error(f"Failed to cleanup rate limit entries: {e}")


# Middleware configuration
def setup_middleware(app):
    """Setup all middleware for the gateway."""
    # Add middleware in reverse order (last added is executed first)
    app.add_middleware(RateLimitingMiddleware, requests_per_minute=60)
    app.add_middleware(ValidationMiddleware)
    app.add_middleware(RequestLoggingMiddleware)
    
    return app