"""Radar API service for market signals dashboard."""
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from fastapi import FastAPI, HTTPException, Query, Depends, Response
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import ValidationError
import io

from services.radar.market_signals import (
    MarketSignalsService,
    MarketSignalFilter,
    SignalType,
    SignalPriority,
    Province,
    AssetType,
    get_market_signals_service
)

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Radar Service",
    description="Market signals dashboard for energy regulatory radar",
    version="1.0.0"
)


@app.get("/signals")
async def get_signals(
    provinces: Optional[List[str]] = Query(None, description="Filter by provinces"),
    asset_types: Optional[List[str]] = Query(None, description="Filter by asset types"),
    signal_types: Optional[List[str]] = Query(None, description="Filter by signal types"),
    priorities: Optional[List[str]] = Query(None, description="Filter by priorities"),
    date_from: Optional[str] = Query(None, description="Filter from date (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="Filter to date (YYYY-MM-DD)"),
    keywords: Optional[str] = Query(None, description="Search keywords"),
    min_impact_score: Optional[float] = Query(None, ge=0.0, le=1.0, description="Minimum impact score"),
    limit: int = Query(50, ge=1, le=200, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Offset for pagination")
):
    """Get market signals with filtering and pagination."""
    try:
        # Validate and convert enum values
        validated_provinces = None
        if provinces:
            try:
                validated_provinces = [Province(p) for p in provinces]
            except ValueError as e:
                raise HTTPException(status_code=400, detail=f"Invalid province: {e}")
        
        validated_asset_types = None
        if asset_types:
            try:
                validated_asset_types = [AssetType(a) for a in asset_types]
            except ValueError as e:
                raise HTTPException(status_code=400, detail=f"Invalid asset type: {e}")
        
        validated_signal_types = None
        if signal_types:
            try:
                validated_signal_types = [SignalType(s) for s in signal_types]
            except ValueError as e:
                raise HTTPException(status_code=400, detail=f"Invalid signal type: {e}")
        
        validated_priorities = None
        if priorities:
            try:
                validated_priorities = [SignalPriority(p) for p in priorities]
            except ValueError as e:
                raise HTTPException(status_code=400, detail=f"Invalid priority: {e}")
        
        # Create filter
        filters = MarketSignalFilter(
            provinces=validated_provinces,
            asset_types=validated_asset_types,
            signal_types=validated_signal_types,
            priorities=validated_priorities,
            date_from=date_from,
            date_to=date_to,
            keywords=keywords,
            min_impact_score=min_impact_score,
            limit=limit,
            offset=offset
        )
        
        # Get signals
        service = await get_market_signals_service()
        result = await service.get_signals(filters)
        
        return result
        
    except ValidationError as e:
        logger.error(f"Validation error in get_signals: {e}")
        raise HTTPException(
            status_code=422,
            detail={
                "error": "Validation failed",
                "details": e.errors()
            }
        )
    except Exception as e:
        logger.error(f"Failed to get signals: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Signal retrieval failed: {str(e)}"
        )


@app.get("/signals/{signal_id}")
async def get_signal(signal_id: str):
    """Get specific signal by ID."""
    try:
        service = await get_market_signals_service()
        signal = await service.get_signal_by_id(signal_id)
        
        if not signal:
            raise HTTPException(
                status_code=404,
                detail=f"Signal not found: {signal_id}"
            )
        
        return {
            "signal": signal.__dict__,
            "retrieved_at": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get signal {signal_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Signal retrieval failed: {str(e)}"
        )


@app.get("/signals/export/csv")
async def export_signals_csv(
    provinces: Optional[List[str]] = Query(None),
    asset_types: Optional[List[str]] = Query(None),
    signal_types: Optional[List[str]] = Query(None),
    priorities: Optional[List[str]] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    keywords: Optional[str] = Query(None),
    min_impact_score: Optional[float] = Query(None, ge=0.0, le=1.0)
):
    """Export filtered signals to CSV."""
    try:
        # Validate and convert enum values (same as get_signals)
        validated_provinces = None
        if provinces:
            validated_provinces = [Province(p) for p in provinces]
        
        validated_asset_types = None
        if asset_types:
            validated_asset_types = [AssetType(a) for a in asset_types]
        
        validated_signal_types = None
        if signal_types:
            validated_signal_types = [SignalType(s) for s in signal_types]
        
        validated_priorities = None
        if priorities:
            validated_priorities = [SignalPriority(p) for p in priorities]
        
        # Create filter (no pagination for export)
        filters = MarketSignalFilter(
            provinces=validated_provinces,
            asset_types=validated_asset_types,
            signal_types=validated_signal_types,
            priorities=validated_priorities,
            date_from=date_from,
            date_to=date_to,
            keywords=keywords,
            min_impact_score=min_impact_score,
            limit=1000,  # Large limit for export
            offset=0
        )
        
        # Export to CSV
        service = await get_market_signals_service()
        csv_content = await service.export_signals_csv(filters)
        
        # Create filename with timestamp
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        filename = f"market_signals_{timestamp}.csv"
        
        # Return as streaming response
        return StreamingResponse(
            io.StringIO(csv_content),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except Exception as e:
        logger.error(f"Failed to export signals CSV: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"CSV export failed: {str(e)}"
        )


@app.get("/stats")
async def get_stats():
    """Get market signals statistics."""
    try:
        service = await get_market_signals_service()
        stats = await service.get_signal_stats()
        return stats
        
    except Exception as e:
        logger.error(f"Failed to get stats: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Stats retrieval failed: {str(e)}"
        )


@app.get("/enums")
async def get_enums():
    """Get available enum values for filtering."""
    try:
        return {
            "provinces": {
                "guangdong": {"value": "guangdong", "label": "广东", "label_en": "Guangdong"},
                "shandong": {"value": "shandong", "label": "山东", "label_en": "Shandong"},
                "inner_mongolia": {"value": "inner_mongolia", "label": "内蒙古", "label_en": "Inner Mongolia"}
            },
            "asset_types": {
                "solar": {"value": "solar", "label": "分布式光伏", "label_en": "Solar PV"},
                "wind": {"value": "wind", "label": "风电", "label_en": "Wind Power"},
                "battery": {"value": "battery", "label": "储能", "label_en": "Battery Storage"},
                "coal_flexibility": {"value": "coal_flexibility", "label": "煤电灵活性", "label_en": "Coal Flexibility"}
            },
            "signal_types": {
                "tender": {"value": "tender", "label": "招标公告", "label_en": "Tender"},
                "notice": {"value": "notice", "label": "通知公告", "label_en": "Notice"},
                "policy_update": {"value": "policy_update", "label": "政策更新", "label_en": "Policy Update"},
                "market_change": {"value": "market_change", "label": "市场变化", "label_en": "Market Change"},
                "regulatory_change": {"value": "regulatory_change", "label": "监管变化", "label_en": "Regulatory Change"}
            },
            "priorities": {
                "low": {"value": "low", "label": "低", "label_en": "Low"},
                "medium": {"value": "medium", "label": "中", "label_en": "Medium"},
                "high": {"value": "high", "label": "高", "label_en": "High"},
                "critical": {"value": "critical", "label": "紧急", "label_en": "Critical"}
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to get enums: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Enum retrieval failed: {str(e)}"
        )


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    try:
        service = await get_market_signals_service()
        stats = await service.get_signal_stats()
        
        return {
            "status": "healthy",
            "service": "radar",
            "version": "1.0.0",
            "timestamp": datetime.utcnow().isoformat(),
            "stats_summary": {
                "total_signals": stats.get("total_signals", 0),
                "recent_activity": stats.get("recent_activity", {}).get("count", 0),
                "upcoming_deadlines": stats.get("upcoming_deadlines", {}).get("count", 0)
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
    logger.info("Radar Service starting up...")
    
    try:
        # Initialize market signals service
        service = await get_market_signals_service()
        logger.info("Market signals service initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize market signals service: {e}")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    logger.info("Radar Service shutting down...")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)