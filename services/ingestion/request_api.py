"""Ingestion request API service."""
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from fastapi import FastAPI, HTTPException, Query, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ValidationError

from services.ingestion.request_handler import (
    IngestionRequest,
    IngestionRequestResponse,
    StoredIngestionRequest,
    RequestStatus,
    Priority,
    get_request_handler,
    submit_ingestion_request,
    get_ingestion_request_stats
)

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Ingestion Request Service",
    description="Handle ingestion requests for missing regulatory data",
    version="1.0.0"
)


class RequestStatusUpdate(BaseModel):
    """Request status update model."""
    status: RequestStatus
    reviewer_notes: Optional[str] = None


@app.post("/request", response_model=IngestionRequestResponse)
async def submit_request(request: IngestionRequest):
    """Submit new ingestion request."""
    try:
        logger.info(f"Submitting ingestion request for {request.province}/{request.asset_type}")
        
        # Validate request eligibility
        handler = await get_request_handler()
        eligibility = await handler.validate_request_eligibility(request.refusal_code)
        
        if not eligibility.get('eligible', False):
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "Request not eligible for ingestion",
                    "reason": eligibility.get('reason', 'Unknown reason'),
                    "alternative": eligibility.get('alternative', 'Please contact support'),
                    "refusal_code": request.refusal_code
                }
            )
        
        # Submit request
        response = await handler.submit_request(request)
        
        logger.info(f"Ingestion request submitted successfully: {response.request_id}")
        return response
        
    except ValidationError as e:
        logger.error(f"Validation error in ingestion request: {e}")
        raise HTTPException(
            status_code=422,
            detail={
                "error": "Validation failed",
                "details": e.errors()
            }
        )
    except Exception as e:
        logger.error(f"Failed to submit ingestion request: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Request submission failed: {str(e)}"
        )


@app.get("/request/{request_id}")
async def get_request(request_id: str):
    """Get ingestion request by ID."""
    try:
        handler = await get_request_handler()
        request = await handler.get_request(request_id)
        
        if not request:
            raise HTTPException(
                status_code=404,
                detail=f"Request not found: {request_id}"
            )
        
        return {
            "request": request.__dict__,
            "retrieved_at": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get request {request_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Request retrieval failed: {str(e)}"
        )


@app.put("/request/{request_id}/status")
async def update_request_status(request_id: str, update: RequestStatusUpdate):
    """Update request status."""
    try:
        handler = await get_request_handler()
        success = await handler.update_request_status(
            request_id, 
            update.status, 
            update.reviewer_notes
        )
        
        if not success:
            raise HTTPException(
                status_code=404,
                detail=f"Request not found: {request_id}"
            )
        
        return {
            "request_id": request_id,
            "status": update.status.value,
            "updated_at": datetime.utcnow().isoformat(),
            "message": f"Request status updated to {update.status.value}"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update request status: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Status update failed: {str(e)}"
        )


@app.get("/requests")
async def list_requests(
    status: Optional[RequestStatus] = Query(None, description="Filter by status"),
    priority: Optional[Priority] = Query(None, description="Filter by priority"),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of requests to return")
):
    """List ingestion requests with optional filters."""
    try:
        handler = await get_request_handler()
        requests = await handler.list_requests(status, priority, limit)
        
        return {
            "requests": [req.__dict__ for req in requests],
            "total_returned": len(requests),
            "filters": {
                "status": status.value if status else None,
                "priority": priority.value if priority else None,
                "limit": limit
            },
            "retrieved_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to list requests: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Request listing failed: {str(e)}"
        )


@app.get("/stats")
async def get_stats():
    """Get ingestion request statistics."""
    try:
        stats = await get_ingestion_request_stats()
        return stats
        
    except Exception as e:
        logger.error(f"Failed to get stats: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Stats retrieval failed: {str(e)}"
        )


@app.get("/eligibility/{refusal_code}")
async def check_eligibility(refusal_code: str):
    """Check if refusal code is eligible for ingestion request."""
    try:
        handler = await get_request_handler()
        eligibility = await handler.validate_request_eligibility(refusal_code)
        
        return {
            "refusal_code": refusal_code,
            "eligibility": eligibility,
            "checked_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to check eligibility for {refusal_code}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Eligibility check failed: {str(e)}"
        )


@app.get("/help/refusal-codes")
async def get_refusal_codes_help():
    """Get help information about refusal codes."""
    try:
        refusal_codes = {
            "no_first_party_citation": {
                "description": "No first-party citations found for the query",
                "description_zh": "未找到相关的第一方引用文献",
                "severity": "medium",
                "category": "citation_quality",
                "can_request_ingestion": True,
                "typical_resolution": "Add relevant official documents to the database"
            },
            "stale_citation": {
                "description": "Citations found but they are outdated",
                "description_zh": "找到引用文献但已过时",
                "severity": "high",
                "category": "citation_quality",
                "can_request_ingestion": True,
                "typical_resolution": "Update documents with latest versions"
            },
            "insufficient_citations": {
                "description": "Not enough citations to provide comprehensive answer",
                "description_zh": "引用文献不足，无法提供全面回答",
                "severity": "medium",
                "category": "citation_quality",
                "can_request_ingestion": True,
                "typical_resolution": "Add more relevant documents"
            },
            "province_mismatch": {
                "description": "Query province doesn't match available data",
                "description_zh": "查询省份与可用数据不匹配",
                "severity": "medium",
                "category": "geographic_scope",
                "can_request_ingestion": True,
                "typical_resolution": "Add province-specific documents"
            },
            "cross_province_leakage": {
                "description": "Query violates geographic scope policies",
                "description_zh": "查询违反地理范围政策",
                "severity": "high",
                "category": "geographic_scope",
                "can_request_ingestion": False,
                "typical_resolution": "Rephrase query to focus on single province"
            },
            "language_policy_violation": {
                "description": "Query violates language policies",
                "description_zh": "查询违反语言政策",
                "severity": "medium",
                "category": "content_policy",
                "can_request_ingestion": False,
                "typical_resolution": "Use Chinese for queries"
            },
            "unsafe_content": {
                "description": "Content violates safety policies",
                "description_zh": "内容违反安全政策",
                "severity": "high",
                "category": "content_policy",
                "can_request_ingestion": False,
                "typical_resolution": "Rephrase query with appropriate content"
            },
            "prompt_injection": {
                "description": "Query contains potential security risks",
                "description_zh": "查询包含潜在安全风险",
                "severity": "high",
                "category": "security",
                "can_request_ingestion": False,
                "typical_resolution": "Use standard query format"
            },
            "system_overload": {
                "description": "System is temporarily overloaded",
                "description_zh": "系统暂时过载",
                "severity": "low",
                "category": "system",
                "can_request_ingestion": False,
                "typical_resolution": "Try again later"
            },
            "retrieval_failed": {
                "description": "Document retrieval system failed",
                "description_zh": "文档检索系统失败",
                "severity": "low",
                "category": "system",
                "can_request_ingestion": False,
                "typical_resolution": "Try again or contact support"
            }
        }
        
        return {
            "refusal_codes": refusal_codes,
            "categories": {
                "citation_quality": "Issues with document availability or quality",
                "geographic_scope": "Issues with geographic coverage or scope",
                "content_policy": "Issues with content policy compliance",
                "security": "Security-related issues",
                "system": "System or technical issues"
            },
            "severity_levels": {
                "low": "Minor issue, system can handle gracefully",
                "medium": "Moderate issue, may require user action",
                "high": "Serious issue, requires immediate attention"
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to get refusal codes help: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Help retrieval failed: {str(e)}"
        )


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    try:
        handler = await get_request_handler()
        stats = await handler.get_request_stats()
        
        return {
            "status": "healthy",
            "service": "ingestion_request",
            "version": "1.0.0",
            "timestamp": datetime.utcnow().isoformat(),
            "stats_summary": {
                "total_requests": stats.get("total_requests", 0),
                "active_requests": sum(
                    count for status, count in stats.get("status_distribution", {}).items()
                    if status in ["submitted", "under_review", "in_progress"]
                )
            }
        }
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
        )


@app.on_event("startup")
async def startup_event():
    """Initialize service on startup."""
    logger.info("Ingestion Request Service starting up...")
    
    try:
        # Initialize request handler
        handler = await get_request_handler()
        logger.info("Request handler initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize request handler: {e}")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    logger.info("Ingestion Request Service shutting down...")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)