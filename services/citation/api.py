"""Citation pack API service."""
import asyncio
import logging
import os
import tempfile
from typing import List, Dict, Any, Optional
from datetime import datetime

from fastapi import FastAPI, HTTPException, Query, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from services.citation.pack_generator import (
    generate_citation_pack,
    get_pack_generator,
    cleanup_pack_generator,
    CitationData,
    PackMetadata
)

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Citation Pack Service",
    description="Generate citation packs with Chinese PDF support",
    version="1.0.0"
)


class PackGenerationRequest(BaseModel):
    """Request model for pack generation."""
    citations: List[Dict[str, Any]]
    query: str
    province: str
    asset_type: str
    doc_class: str
    format_type: str = Field(default="pdf", pattern="^(pdf|html)$")
    language: str = Field(default="zh-CN")


class PackGenerationResponse(BaseModel):
    """Response model for pack generation."""
    pack_id: str
    format: str
    file_path: Optional[str] = None
    content: Optional[str] = None
    summary: Dict[str, Any]
    generated_at: str


@app.post("/generate", response_model=PackGenerationResponse)
async def generate_pack(request: PackGenerationRequest):
    """Generate citation pack in specified format."""
    try:
        logger.info(f"Generating {request.format_type} pack for query: {request.query}")
        
        # Validate citations
        if not request.citations:
            raise HTTPException(
                status_code=400,
                detail="At least one citation is required"
            )
        
        # Generate pack
        result = await generate_citation_pack(
            citations=request.citations,
            query=request.query,
            province=request.province,
            asset_type=request.asset_type,
            doc_class=request.doc_class,
            format_type=request.format_type
        )
        
        return PackGenerationResponse(**result)
        
    except Exception as e:
        logger.error(f"Failed to generate pack: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Pack generation failed: {str(e)}"
        )


@app.get("/download/{pack_id}")
async def download_pack(
    pack_id: str,
    background_tasks: BackgroundTasks
):
    """Download generated pack file."""
    try:
        # For demo purposes, we'll generate a sample pack
        # In production, this would retrieve from storage
        
        # Sample citation data
        sample_citations = [
            {
                "citation_id": "GD-SOLAR-001",
                "title": "广东省分布式光伏发电项目管理暂行办法",
                "content": "为规范广东省分布式光伏发电项目管理，促进分布式光伏发电健康有序发展，根据国家发展改革委、国家能源局相关政策文件，结合我省实际，制定本办法。",
                "effective_date": "2023-01-01",
                "source_url": "https://drc.gd.gov.cn/gkmlpt/content/3/3297/post_3297749.html",
                "province": "广东",
                "asset_type": "分布式光伏",
                "doc_class": "管理办法",
                "confidence_score": 0.95
            }
        ]
        
        # Generate PDF
        result = await generate_citation_pack(
            citations=sample_citations,
            query="分布式光伏并网要求",
            province="广东",
            asset_type="分布式光伏",
            doc_class="管理办法",
            format_type="pdf"
        )
        
        file_path = result["file_path"]
        
        # Schedule cleanup
        background_tasks.add_task(cleanup_temp_file, file_path)
        
        return FileResponse(
            path=file_path,
            filename=f"citation_pack_{pack_id}.pdf",
            media_type="application/pdf"
        )
        
    except Exception as e:
        logger.error(f"Failed to download pack {pack_id}: {e}")
        raise HTTPException(
            status_code=404,
            detail=f"Pack not found: {pack_id}"
        )


@app.get("/preview/{pack_id}")
async def preview_pack(pack_id: str):
    """Preview pack as HTML."""
    try:
        # Sample citation data for preview
        sample_citations = [
            {
                "citation_id": "GD-SOLAR-001",
                "title": "广东省分布式光伏发电项目管理暂行办法",
                "content": "为规范广东省分布式光伏发电项目管理，促进分布式光伏发电健康有序发展，根据国家发展改革委、国家能源局相关政策文件，结合我省实际，制定本办法。分布式光伏发电项目是指在用户场地附近建设，运行方式以用户侧自发自用、多余电量上网，且在配电系统平衡调节为特征的光伏发电设施。",
                "effective_date": "2023-01-01",
                "source_url": "https://drc.gd.gov.cn/gkmlpt/content/3/3297/post_3297749.html",
                "province": "广东",
                "asset_type": "分布式光伏",
                "doc_class": "管理办法",
                "confidence_score": 0.95
            },
            {
                "citation_id": "GD-SOLAR-002",
                "title": "广东电力市场交易规则（2024年版）",
                "content": "为规范广东电力市场交易行为，维护市场秩序，保障各类市场主体合法权益，根据《电力法》《电力市场运营基本规则》等法律法规，制定本规则。新能源发电企业参与市场交易，享受优先发电权，但需承担相应的市场责任。",
                "effective_date": "2024-01-01",
                "source_url": "https://drc.gd.gov.cn/gkmlpt/content/3/3298/post_3298123.html",
                "province": "广东",
                "asset_type": "分布式光伏",
                "doc_class": "交易规则",
                "confidence_score": 0.88
            }
        ]
        
        # Generate HTML preview
        result = await generate_citation_pack(
            citations=sample_citations,
            query="分布式光伏并网要求",
            province="广东",
            asset_type="分布式光伏",
            doc_class="管理办法",
            format_type="html"
        )
        
        return JSONResponse(
            content={
                "pack_id": pack_id,
                "html_content": result["content"],
                "summary": result["summary"]
            }
        )
        
    except Exception as e:
        logger.error(f"Failed to preview pack {pack_id}: {e}")
        raise HTTPException(
            status_code=404,
            detail=f"Pack not found: {pack_id}"
        )


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    try:
        # Test pack generator
        generator = await get_pack_generator()
        
        return {
            "status": "healthy",
            "service": "citation_pack",
            "version": "1.0.0",
            "timestamp": datetime.utcnow().isoformat(),
            "capabilities": {
                "pdf_generation": True,
                "html_generation": True,
                "chinese_fonts": True,
                "template_rendering": True
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


@app.get("/templates")
async def list_templates():
    """List available templates."""
    try:
        generator = await get_pack_generator()
        template_dir = generator.template_dir
        
        templates = []
        if os.path.exists(template_dir):
            for file in os.listdir(template_dir):
                if file.endswith('.html'):
                    templates.append({
                        "name": file,
                        "path": os.path.join(template_dir, file),
                        "size": os.path.getsize(os.path.join(template_dir, file))
                    })
        
        return {
            "templates": templates,
            "template_dir": template_dir,
            "total_templates": len(templates)
        }
        
    except Exception as e:
        logger.error(f"Failed to list templates: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Template listing failed: {str(e)}"
        )


@app.get("/stats")
async def get_stats():
    """Get service statistics."""
    try:
        return {
            "service": "citation_pack",
            "version": "1.0.0",
            "uptime": "running",
            "features": {
                "pdf_generation": True,
                "html_generation": True,
                "chinese_support": True,
                "template_system": True,
                "background_tasks": True
            },
            "supported_formats": ["pdf", "html"],
            "supported_languages": ["zh-CN", "en"],
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to get stats: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Stats retrieval failed: {str(e)}"
        )


async def cleanup_temp_file(file_path: str):
    """Clean up temporary file."""
    try:
        if os.path.exists(file_path):
            os.unlink(file_path)
            logger.info(f"Cleaned up temporary file: {file_path}")
    except Exception as e:
        logger.warning(f"Failed to cleanup temp file {file_path}: {e}")


@app.on_event("startup")
async def startup_event():
    """Initialize service on startup."""
    logger.info("Citation Pack Service starting up...")
    
    try:
        # Initialize pack generator
        generator = await get_pack_generator()
        logger.info("Pack generator initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize pack generator: {e}")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    logger.info("Citation Pack Service shutting down...")
    
    try:
        await cleanup_pack_generator()
        logger.info("Pack generator cleaned up successfully")
        
    except Exception as e:
        logger.error(f"Failed to cleanup pack generator: {e}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)