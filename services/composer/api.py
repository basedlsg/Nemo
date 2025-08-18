"""Answer composer service API for Task 13."""

import logging
import time
from typing import List, Dict, Any
from datetime import datetime

from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel, Field

from .answer_composer import get_answer_composer, ChineseAnswerComposer

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Geo-Adaptive Energy Assistant - Answer Composer",
    description="Quote-first Chinese answer composition with inline citations",
    version="1.0.0"
)


class ComposerRequest(BaseModel):
    """Answer composition request model."""
    
    search_results: List[Dict[str, Any]] = Field(..., description="Search results from retriever")
    query: Dict[str, Any] = Field(..., description="Original query parameters")
    max_citations: int = Field(default=10, ge=1, le=20, description="Maximum citations to include")


class ComposerResponse(BaseModel):
    """Answer composition response model."""
    
    answer_zh: str = Field(..., description="Chinese answer with inline citations")
    citations: List[Dict[str, Any]] = Field(..., description="Citation metadata")
    sections: int = Field(..., description="Number of answer sections")
    total_citations: int = Field(..., description="Total citations used")
    processing_time_ms: int = Field(..., description="Processing time in milliseconds")
    composed_at: str = Field(..., description="Composition timestamp")
    query_context: Dict[str, Any] = Field(..., description="Query context information")


class HealthResponse(BaseModel):
    """Health check response model."""
    
    status: str = Field(..., description="Service health status")
    test_composition: str = Field(..., description="Test composition result")
    province_labels: int = Field(..., description="Number of province labels")
    asset_labels: int = Field(..., description="Number of asset labels")
    doc_class_labels: int = Field(..., description="Number of doc class labels")
    timestamp: str = Field(..., description="Health check timestamp")


@app.post("/compose", response_model=ComposerResponse)
async def compose_answer(
    request: ComposerRequest,
    composer: ChineseAnswerComposer = Depends(get_answer_composer)
) -> ComposerResponse:
    """
    Compose Chinese answer with inline citations from search results.
    
    Creates quote-first responses with structured sections and inline citations.
    Every bullet point must reference at least one citation_id.
    """
    start_time = time.time()
    
    try:
        # Validate search results
        if not request.search_results:
            raise HTTPException(
                status_code=400,
                detail="Search results cannot be empty"
            )
        
        # Validate query parameters
        required_query_fields = ["province", "doc_class"]
        for field in required_query_fields:
            if field not in request.query:
                raise HTTPException(
                    status_code=400,
                    detail=f"Query missing required field: {field}"
                )
        
        # Compose answer
        result = composer.compose_answer(
            search_results=request.search_results,
            query=request.query,
            max_citations=request.max_citations
        )
        
        processing_time_ms = int((time.time() - start_time) * 1000)
        
        # Check if composition was successful
        if not result.get("answer_zh"):
            raise HTTPException(
                status_code=422,
                detail="Could not compose answer from provided search results"
            )
        
        # Check if answer has citations (policy requirement)
        if not result.get("citations"):
            raise HTTPException(
                status_code=422,
                detail="Answer must include at least one citation"
            )
        
        response = ComposerResponse(
            answer_zh=result["answer_zh"],
            citations=result["citations"],
            sections=result.get("sections", 0),
            total_citations=result.get("total_citations", 0),
            processing_time_ms=processing_time_ms,
            composed_at=result["composed_at"],
            query_context=result.get("query_context", {})
        )
        
        logger.info(f"Answer composed: {len(response.answer_zh)} chars, {response.total_citations} citations in {processing_time_ms}ms")
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Answer composition failed: {e}")
        raise HTTPException(status_code=500, detail="Internal composition error")


@app.get("/health", response_model=HealthResponse)
async def health_check(
    composer: ChineseAnswerComposer = Depends(get_answer_composer)
) -> HealthResponse:
    """Check answer composer service health."""
    try:
        health_data = composer.health_check()
        
        return HealthResponse(
            status=health_data["status"],
            test_composition=health_data.get("test_composition", "unknown"),
            province_labels=health_data.get("province_labels", 0),
            asset_labels=health_data.get("asset_labels", 0),
            doc_class_labels=health_data.get("doc_class_labels", 0),
            timestamp=health_data["timestamp"]
        )
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return HealthResponse(
            status="unhealthy",
            test_composition="failed",
            province_labels=0,
            asset_labels=0,
            doc_class_labels=0,
            timestamp=datetime.utcnow().isoformat()
        )


@app.get("/templates")
async def get_templates() -> Dict[str, Any]:
    """Get information about answer templates and formatting."""
    return {
        "template_format": {
            "title": "**{topic}要点（{province} / {asset}）**",
            "section": "- {section_title}：",
            "bullet": "  • {clause} 〔《{title}》，生效：{date}〕",
            "refusal": "（若找不到一手来源：直接拒答并说明）"
        },
        "supported_languages": ["zh-CN", "en"],
        "default_language": "zh-CN",
        "citation_format": "inline with title and effective date",
        "max_citations_per_answer": 20,
        "sections": [
            "资料清单", "受理与时限", "技术要求", 
            "安全规定", "并网条件", "市场准入", "相关规定"
        ]
    }


@app.get("/")
async def root():
    """Root endpoint with service information."""
    return {
        "service": "geo-adaptive-energy-assistant-composer",
        "version": "1.0.0",
        "description": "Quote-first Chinese answer composition with inline citations",
        "endpoints": {
            "compose": "POST /compose - Compose answer from search results",
            "health": "GET /health - Health check",
            "templates": "GET /templates - Template information"
        },
        "features": [
            "Quote-first Chinese responses",
            "Inline citations with titles and dates",
            "Structured sections by topic",
            "Optional English summaries",
            "Citation validation and filtering"
        ],
        "requirements": [
            "Every bullet point must reference at least one citation",
            "Citations must have title and effective_date",
            "Answer must be in Chinese unless lang=en",
            "Refusal if no valid clauses survive policy"
        ]
    }


# Error handlers
@app.exception_handler(422)
async def composition_error_handler(request, exc):
    return {
        "error": "Composition failed",
        "detail": str(exc.detail),
        "suggestion": "Ensure search results contain valid citations with required metadata",
        "timestamp": datetime.utcnow().isoformat()
    }


@app.exception_handler(500)
async def internal_error_handler(request, exc):
    logger.error(f"Internal server error: {exc}")
    return {
        "error": "Internal composition error",
        "timestamp": datetime.utcnow().isoformat()
    }


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "services.composer.api:app",
        host="0.0.0.0",
        port=8003,
        log_level="info",
        reload=True
    )