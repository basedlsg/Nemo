"""Main API gateway for the Geo-Adaptive Energy Assistant."""

import logging
import asyncio
from typing import Dict, Any, Optional
from datetime import datetime

from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from .models import (
    QueryRequest, QueryResponse, RefusalResponse, HealthResponse, 
    ServiceStats, ValidationError, generate_trace_id
)
from .middleware import setup_middleware
from .orchestrator import get_orchestrator, QueryOrchestrator
from services.online.query_online import router as online_router

logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Geo-Adaptive Energy Assistant - API Gateway",
    description="Main API gateway for Chinese energy regulation queries with geo-specific responses",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Setup CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Setup middleware
setup_middleware(app)

# Include online router
app.include_router(online_router, prefix="", tags=["online"])


@app.post("/query", response_model=QueryResponse)
async def query_energy_regulations(
    request: QueryRequest,
    http_request: Request,
    orchestrator: QueryOrchestrator = Depends(get_orchestrator)
) -> Dict[str, Any]:
    """
    Query energy regulations with geo-specific responses.
    
    This endpoint orchestrates the complete RAG pipeline:
    1. Hybrid search for relevant citations (Retriever)
    2. Policy validation and safety checks (Guardrails)  
    3. Quote-first Chinese answer composition (Composer)
    
    Returns structured Chinese responses with inline citations.
    """
    try:
        # Get trace ID from middleware
        trace_id = getattr(http_request.state, 'trace_id', generate_trace_id())
        
        logger.info(f"[{trace_id}] Processing query: province={request.province.value}, doc_class={request.doc_class.value}, asset={request.asset.value if request.asset else None}")
        
        # Process query through orchestrator
        result = await orchestrator.process_query(request, trace_id)
        
        # Check if result is a refusal
        if "error" in result:
            # Return 422 for policy violations/refusals
            return JSONResponse(
                status_code=422,
                content=result
            )
        
        # Return successful response
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        tb_str = traceback.format_exc()
        logger.error(f"Query processing failed: {e}\n{tb_str}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error during query processing: {e}"
        )


@app.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """
    Check overall gateway health and service status.
    
    Returns health status of all integrated services:
    - Retriever service
    - Guardrails service  
    - Composer service
    - Database connectivity
    """
    try:
        # Check individual service health
        services = {}
        
        # Mock service health checks - replace with actual HTTP calls
        services["retriever"] = "healthy"  # await check_retriever_health()
        services["guardrails"] = "healthy"  # await check_guardrails_health()
        services["composer"] = "healthy"  # await check_composer_health()
        
        # Test database connectivity using connection manager
        try:
            from services.database.connection_manager import get_connection_manager
            
            manager = get_connection_manager()
            connection_result = await manager.get_connection_info()
            
            if connection_result.success:
                services["database"] = f"healthy ({connection_result.strategy.value})"
            else:
                services["database"] = f"error: {connection_result.error_message} ({connection_result.strategy.value})"
                
        except Exception as db_e:
            import traceback
            error_details = f"{type(db_e).__name__}: {str(db_e)}"
            services["database"] = f"error: {error_details}"
        
        # Determine overall status
        overall_status = "healthy" if all(status == "healthy" for status in services.values()) else "degraded"
        
        return HealthResponse(
            status=overall_status,
            services=services,
            version="1.0.0",
            timestamp=datetime.utcnow().isoformat()
        )
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return HealthResponse(
            status="unhealthy",
            services={"error": str(e)},
            version="1.0.0",
            timestamp=datetime.utcnow().isoformat()
        )


@app.get("/stats", response_model=ServiceStats)
async def get_service_statistics(
    orchestrator: QueryOrchestrator = Depends(get_orchestrator)
) -> ServiceStats:
    """
    Get service statistics and usage metrics.
    
    Returns:
    - Total queries processed
    - Success/refusal rates
    - Average processing times
    - Distribution by province, doc_class, and asset
    """
    try:
        stats_data = orchestrator.get_stats()
        
        return ServiceStats(
            total_queries=stats_data["total_queries"],
            successful_queries=stats_data["successful_queries"],
            refusal_rate=stats_data["refusal_rate"],
            avg_processing_time_ms=stats_data["avg_processing_time_ms"],
            province_distribution=stats_data["province_distribution"],
            doc_class_distribution=stats_data["doc_class_distribution"],
            asset_distribution=stats_data["asset_distribution"],
            timestamp=stats_data["timestamp"]
        )
        
    except Exception as e:
        logger.error(f"Stats retrieval failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve statistics")


@app.get("/provinces")
async def get_supported_provinces() -> Dict[str, Any]:
    """Get list of supported provinces with Chinese labels."""
    return {
        "provinces": [
            {"code": "guangdong", "label": "广东省", "label_en": "Guangdong"},
            {"code": "shandong", "label": "山东省", "label_en": "Shandong"},
            {"code": "inner_mongolia", "label": "内蒙古自治区", "label_en": "Inner Mongolia"}
        ],
        "total": 3
    }


@app.get("/assets")
async def get_supported_assets() -> Dict[str, Any]:
    """Get list of supported asset types with Chinese labels."""
    return {
        "assets": [
            {"code": "wind", "label": "风电", "label_en": "Wind Power"},
            {"code": "solar", "label": "光伏", "label_en": "Solar Power"},
            {"code": "bess", "label": "储能", "label_en": "Battery Energy Storage"},
            {"code": "coal_flex", "label": "煤电", "label_en": "Coal Power (Flexible)"}
        ],
        "total": 4
    }


@app.get("/doc_classes")
async def get_supported_doc_classes() -> Dict[str, Any]:
    """Get list of supported document classes with Chinese labels."""
    return {
        "doc_classes": [
            {"code": "market_rules", "label": "市场规则", "label_en": "Market Rules"},
            {"code": "grid_connection", "label": "并网规定", "label_en": "Grid Connection"},
            {"code": "dispatch_ops", "label": "调度运行", "label_en": "Dispatch Operations"}
        ],
        "total": 3
    }


@app.get("/database/test")
async def test_database():
    """Test database connectivity and data with comprehensive diagnostics."""
    import os
    import traceback
    
    try:
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            return {"error": "No DATABASE_URL environment variable"}
        
        # Parse the database URL to show connection details (without password)
        try:
            from urllib.parse import urlparse
            parsed = urlparse(database_url)
            connection_info = {
                "host": parsed.hostname,
                "port": parsed.port,
                "database": parsed.path.lstrip('/'),
                "username": parsed.username
            }
        except Exception as parse_e:
            connection_info = {"parse_error": str(parse_e)}
        
        # Run comprehensive network diagnostics
        from services.database.network_diagnostics import test_database_connectivity
        network_report = await test_database_connectivity(database_url)
        
        # Try database health check if network connectivity works
        database_health = None
        if network_report.overall_status.value == "success":
            try:
                from services.database.init import check_database_health
                database_health = await check_database_health(database_url)
            except Exception as db_e:
                database_health = {
                    "status": "unhealthy",
                    "error": f"Database health check failed: {str(db_e)}"
                }
        
        return {
            "connection_info": connection_info,
            "network_diagnostics": {
                "overall_status": network_report.overall_status.value,
                "tests": {name: {
                    "status": test.status.value,
                    "response_time_ms": test.response_time_ms,
                    "error_message": test.error_message,
                    "details": test.details
                } for name, test in network_report.tests.items()},
                "recommendations": network_report.recommendations,
                "timestamp": network_report.timestamp
            },
            "database_health": database_health
        }
        
    except Exception as e:
        return {
            "error": f"Unexpected error: {type(e).__name__}: {str(e)}",
            "traceback": traceback.format_exc()
        }


@app.get("/database/diagnostics")
async def database_network_diagnostics():
    """Run detailed network diagnostics for database connectivity."""
    import os
    
    try:
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            return {"error": "No DATABASE_URL environment variable"}
        
        from services.database.network_diagnostics import test_database_connectivity
        report = await test_database_connectivity(database_url)
        
        return {
            "target": f"{report.target_host}:{report.target_port}",
            "overall_status": report.overall_status.value,
            "tests": {name: {
                "test_name": test.test_name,
                "status": test.status.value,
                "response_time_ms": test.response_time_ms,
                "error_message": test.error_message,
                "details": test.details
            } for name, test in report.tests.items()},
            "recommendations": report.recommendations,
            "timestamp": report.timestamp
        }
        
    except Exception as e:
        import traceback
        return {
            "error": f"Diagnostics failed: {type(e).__name__}: {str(e)}",
            "traceback": traceback.format_exc()
        }


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "service": "geo-adaptive-energy-assistant-gateway",
        "version": "1.0.0",
        "description": "Main API gateway for Chinese energy regulation queries",
        "endpoints": {
            "query": "POST /query - Submit energy regulation query",
            "health": "GET /health - Service health check",
            "stats": "GET /stats - Usage statistics",
            "provinces": "GET /provinces - Supported provinces",
            "assets": "GET /assets - Supported asset types",
            "doc_classes": "GET /doc_classes - Supported document classes",
            "database_test": "GET /database/test - Test database connectivity",
            "database_diagnostics": "GET /database/diagnostics - Network diagnostics",
            "real_data_search": "GET /data/search - Search real regulatory data",
            "real_data_provinces": "GET /data/provinces - Get provinces from real data",
            "real_data_assets": "GET /data/assets - Get asset types from real data"
        },
        "features": [
            "Geo-specific energy regulation queries",
            "Quote-first Chinese responses with inline citations",
            "Multi-province support (Guangdong, Shandong, Inner Mongolia)",
            "Multi-asset support (Wind, Solar, BESS, Coal)",
            "Policy-based safety guardrails",
            "Real regulatory data with SQLite fallback",
            "Network diagnostics and connection management",
            "Structured logging and request tracing"
        ],
        "pipeline": [
            "1. Hybrid Search (Vector + BM25) - Retriever Service",
            "2. Policy Validation - Guardrails Service", 
            "3. Answer Composition - Composer Service",
            "4. Response Formatting - Gateway"
        ],
        "supported_languages": ["zh-CN", "en"],
        "default_language": "zh-CN"
    }


# Error handlers
@app.exception_handler(422)
async def validation_error_handler(request: Request, exc: HTTPException):
    """Handle validation errors with structured response."""
    trace_id = getattr(request.state, 'trace_id', generate_trace_id())
    
    return JSONResponse(
        status_code=422,
        content=ValidationError(
            error="Validation failed",
            field="request",
            message=str(exc.detail),
            timestamp=datetime.utcnow().isoformat()
        ).dict(),
        headers={"X-Trace-ID": trace_id}
    )


@app.exception_handler(429)
async def rate_limit_error_handler(request: Request, exc: HTTPException):
    """Handle rate limiting errors."""
    trace_id = getattr(request.state, 'trace_id', generate_trace_id())
    
    return JSONResponse(
        status_code=429,
        content={
            "error": "Rate limit exceeded",
            "message": str(exc.detail),
            "suggestion": "Please wait before making another request",
            "trace_id": trace_id,
            "timestamp": datetime.utcnow().isoformat()
        },
        headers={"X-Trace-ID": trace_id}
    )


@app.exception_handler(500)
async def internal_error_handler(request: Request, exc: Exception):
    """Handle internal server errors."""
    trace_id = getattr(request.state, 'trace_id', generate_trace_id())
    
    logger.error(f"[{trace_id}] Internal server error: {exc}")
    
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "message": "An unexpected error occurred",
            "suggestion": "Please try again later or contact support",
            "trace_id": trace_id,
            "timestamp": datetime.utcnow().isoformat()
        },
        headers={"X-Trace-ID": trace_id}
    )


# Startup and shutdown events
@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    logger.info("Starting Geo-Adaptive Energy Assistant Gateway")
    
    # Initialize database with real data if needed (non-blocking)
    try:
        import os
        database_url = os.getenv("DATABASE_URL")
        if database_url:
            # Start database initialization in background to avoid startup timeout
            import asyncio
            from services.database.init import init_database
            from services.database.seed_data import check_and_seed_if_empty
            
            async def init_and_seed_in_background():
                try:
                    # First initialize database schema
                    init_success = await init_database(database_url)
                    if init_success:
                        logger.info("Database schema initialized successfully")
                        # Then seed with data
                        await check_and_seed_if_empty(database_url)
                        logger.info("Database initialization and seeding completed")
                    else:
                        logger.warning("Database schema initialization failed, using fallback data")
                except Exception as e:
                    logger.warning(f"Database initialization failed, will use fallback data: {e}")
            
            # Start initialization task in background
            asyncio.create_task(init_and_seed_in_background())
            logger.info("Database initialization started in background")
    except Exception as e:
        logger.warning(f"Failed to start database initialization: {e}")
    
    # Initialize orchestrator
    orchestrator = get_orchestrator()
    
    logger.info("Gateway startup completed")


@app.get("/data/search")
async def search_real_regulatory_data(
    query: str,
    province: Optional[str] = None,
    limit: int = 10
):
    """Search real regulatory data using current database connection strategy."""
    try:
        from services.database.connection_manager import get_connection_manager
        
        manager = get_connection_manager()
        results = await manager.search_regulatory_data(query, province, limit)
        
        return {
            "query": query,
            "province_filter": province,
            "limit": limit,
            **results
        }
        
    except Exception as e:
        import traceback
        return {
            "error": f"Search failed: {type(e).__name__}: {str(e)}",
            "traceback": traceback.format_exc()
        }


@app.get("/data/provinces")
async def get_real_data_provinces():
    """Get list of provinces from real regulatory data."""
    try:
        from services.database.connection_manager import get_connection_manager
        
        manager = get_connection_manager()
        results = await manager.get_provinces()
        
        return results
        
    except Exception as e:
        import traceback
        return {
            "error": f"Failed to get provinces: {type(e).__name__}: {str(e)}",
            "traceback": traceback.format_exc()
        }


@app.get("/data/assets")
async def get_real_data_asset_types():
    """Get list of asset types from real regulatory data."""
    try:
        from services.database.connection_manager import get_connection_manager
        
        manager = get_connection_manager()
        results = await manager.get_asset_types()
        
        return results
        
    except Exception as e:
        import traceback
        return {
            "error": f"Failed to get asset types: {type(e).__name__}: {str(e)}",
            "traceback": traceback.format_exc()
        }


@app.get("/data/test")
async def test_real_data_functionality():
    """Test real data functionality with SQLite fallback."""
    try:
        from services.database.sqlite_fallback import test_sqlite_fallback
        
        results = await test_sqlite_fallback()
        return results
        
    except Exception as e:
        import traceback
        return {
            "error": f"Real data test failed: {type(e).__name__}: {str(e)}",
            "traceback": traceback.format_exc()
        }


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    logger.info("Shutting down Geo-Adaptive Energy Assistant Gateway")


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "services.gateway.api:app",
        host="0.0.0.0",
        port=8000,
        log_level="info",
        reload=True
    )
