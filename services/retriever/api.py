"""Retriever service API for Task 11."""

import logging
import time
from typing import List, Dict, Any, Optional
from datetime import datetime

from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel, Field

from .hybrid_search import get_retriever_client, RetrieverClient

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Geo-Adaptive Energy Assistant - Retriever Service",
    description="Hybrid search service for energy regulation citations",
    version="1.0.0"
)


class SearchRequest(BaseModel):
    """Search request model."""
    
    question: str = Field(..., description="User question to search for")
    province: str = Field(..., description="Province filter (guangdong, shandong, inner_mongolia)")
    doc_class: str = Field(..., description="Document class (market_rules, grid_connection, dispatch_ops)")
    asset: Optional[str] = Field(None, description="Asset filter (wind, solar, bess, coal_flex)")
    limit: int = Field(default=20, ge=1, le=100, description="Maximum results to return")


class SearchResult(BaseModel):
    """Search result model."""
    
    citation_id: str = Field(..., description="Citation identifier")
    passage: str = Field(..., description="Relevant text passage")
    score: float = Field(..., description="Combined relevance score")
    vector_score: float = Field(..., description="Vector similarity score")
    bm25_score: float = Field(..., description="BM25 text relevance score")
    metadata: Dict[str, Any] = Field(..., description="Citation metadata")


class SearchResponse(BaseModel):
    """Search response model."""
    
    results: List[SearchResult] = Field(..., description="Search results")
    total_found: int = Field(..., description="Number of results found")
    processing_time_ms: int = Field(..., description="Processing time in milliseconds")
    search_params: Dict[str, Any] = Field(..., description="Search parameters used")


class HealthResponse(BaseModel):
    """Health check response model."""
    
    status: str = Field(..., description="Service health status")
    latency_ms: Optional[int] = Field(None, description="Health check latency")
    citation_count: Optional[int] = Field(None, description="Total citations available")
    embedding_service: Optional[Dict[str, Any]] = Field(None, description="Embedding service status")
    timestamp: str = Field(..., description="Health check timestamp")


@app.post("/search", response_model=SearchResponse)
async def search_citations(
    request: SearchRequest,
    retriever: RetrieverClient = Depends(get_retriever_client)
) -> SearchResponse:
    """
    Search for relevant citations using hybrid vector + BM25 scoring.
    
    Target performance: p95 < 600ms
    """
    start_time = time.time()
    
    try:
        # Validate province and doc_class
        valid_provinces = {"guangdong", "shandong", "inner_mongolia"}
        valid_doc_classes = {"market_rules", "grid_connection", "dispatch_ops"}
        
        if request.province not in valid_provinces:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid province. Must be one of: {', '.join(valid_provinces)}"
            )
        
        if request.doc_class not in valid_doc_classes:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid doc_class. Must be one of: {', '.join(valid_doc_classes)}"
            )
        
        # Perform search
        results = await retriever.search(
            province=request.province,
            doc_class=request.doc_class,
            question=request.question,
            asset=request.asset,
            limit=request.limit
        )
        
        processing_time_ms = int((time.time() - start_time) * 1000)
        
        # Convert to response format
        search_results = [
            SearchResult(
                citation_id=result["citation_id"],
                passage=result["passage"],
                score=result["score"],
                vector_score=result["vector_score"],
                bm25_score=result["bm25_score"],
                metadata=result["metadata"]
            )
            for result in results
        ]
        
        response = SearchResponse(
            results=search_results,
            total_found=len(search_results),
            processing_time_ms=processing_time_ms,
            search_params={
                "question": request.question,
                "province": request.province,
                "doc_class": request.doc_class,
                "asset": request.asset,
                "limit": request.limit
            }
        )
        
        # Log performance
        if processing_time_ms > 600:  # p95 target
            logger.warning(f"Slow search: {processing_time_ms}ms > 600ms target")
        
        logger.info(f"Search completed: {len(search_results)} results in {processing_time_ms}ms")
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Search failed: {e}")
        raise HTTPException(status_code=500, detail="Internal search error")


@app.get("/health", response_model=HealthResponse)
async def health_check(
    retriever: RetrieverClient = Depends(get_retriever_client)
) -> HealthResponse:
    """Check retriever service health."""
    try:
        health_data = await retriever.health_check()
        
        return HealthResponse(
            status=health_data["status"],
            latency_ms=health_data.get("latency_ms"),
            citation_count=health_data.get("citation_count"),
            embedding_service=health_data.get("embedding_service"),
            timestamp=health_data["timestamp"]
        )
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return HealthResponse(
            status="unhealthy",
            timestamp=datetime.utcnow().isoformat()
        )


@app.get("/stats")
async def get_statistics(
    retriever: RetrieverClient = Depends(get_retriever_client)
) -> Dict[str, Any]:
    """Get retriever service statistics."""
    try:
        stats = await retriever.get_stats()
        return {
            "service": "retriever",
            "stats": stats,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to get stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to get statistics")


@app.get("/")
async def root():
    """Root endpoint with service information."""
    return {
        "service": "geo-adaptive-energy-assistant-retriever",
        "version": "1.0.0",
        "description": "Hybrid search service for energy regulation citations",
        "endpoints": {
            "search": "POST /search - Search for relevant citations",
            "health": "GET /health - Health check",
            "stats": "GET /stats - Service statistics"
        },
        "performance_targets": {
            "p95_latency_ms": 600,
            "hybrid_scoring": "α * vector_cosine + (1-α) * BM25, α=0.6"
        }
    }


# Error handlers
@app.exception_handler(404)
async def not_found_handler(request, exc):
    return {"error": "Endpoint not found", "available_endpoints": ["/search", "/health", "/stats"]}


@app.exception_handler(500)
async def internal_error_handler(request, exc):
    logger.error(f"Internal server error: {exc}")
    return {"error": "Internal server error", "timestamp": datetime.utcnow().isoformat()}


if __name__ == "__main__":
    import uvicorn
    
    # Run the retriever service
    uvicorn.run(
        "services.retriever.api:app",
        host="0.0.0.0",
        port=8001,
        log_level="info",
        reload=True
    )