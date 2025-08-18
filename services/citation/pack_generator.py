"""Citation pack generator with Chinese PDF support."""
import asyncio
import logging
import tempfile
import os
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path
import json

from pyppeteer import launch
from jinja2 import Environment, FileSystemLoader
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class CitationData(BaseModel):
    """Citation data for pack generation."""
    citation_id: str
    title: str
    content: str
    effective_date: str
    source_url: Optional[str] = None
    province: str
    asset_type: str
    doc_class: str
    page_number: Optional[int] = None
    confidence_score: Optional[float] = None


class PackMetadata(BaseModel):
    """Pack metadata for generation."""
    query: str
    province: str
    asset_type: str
    doc_class: str
    language: str = "zh-CN"
    generated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    total_citations: int
    pack_id: str


class CitationPackGenerator:
    """Generates citation packs with Chinese PDF support."""
    
    def __init__(self, template_dir: str = None):
        """Initialize pack generator with template directory."""
        if template_dir is None:
            template_dir = os.path.join(os.path.dirname(__file__), "templates")
        
        self.template_dir = template_dir
        self.jinja_env = Environment(
            loader=FileSystemLoader(template_dir),
            autoescape=True
        )
        
        # Ensure template directory exists
        os.makedirs(template_dir, exist_ok=True)
        
        # Browser instance for PDF generation
        self._browser = None
    
    async def _get_browser(self):
        """Get or create browser instance."""
        if self._browser is None:
            self._browser = await launch(
                headless=True,
                args=[
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-gpu',
                    '--font-render-hinting=none',
                    '--disable-font-subpixel-positioning',
                ]
            )
        return self._browser
    
    async def generate_html_pack(
        self, 
        citations: List[CitationData], 
        metadata: PackMetadata
    ) -> str:
        """Generate HTML citation pack."""
        try:
            # Load template
            template = self.jinja_env.get_template("citation_pack.html")
            
            # Prepare template data
            template_data = {
                "metadata": metadata.dict(),
                "citations": [citation.dict() for citation in citations],
                "generated_timestamp": datetime.utcnow().strftime("%Y年%m月%d日 %H:%M:%S"),
                "total_citations": len(citations)
            }
            
            # Render HTML
            html_content = template.render(**template_data)
            
            logger.info(f"Generated HTML pack with {len(citations)} citations for query: {metadata.query}")
            return html_content
            
        except Exception as e:
            logger.error(f"Failed to generate HTML pack: {e}")
            raise
    
    async def generate_pdf_pack(
        self, 
        citations: List[CitationData], 
        metadata: PackMetadata,
        output_path: Optional[str] = None
    ) -> str:
        """Generate PDF citation pack with Chinese font support."""
        try:
            # Generate HTML first
            html_content = await self.generate_html_pack(citations, metadata)
            
            # Get browser instance
            browser = await self._get_browser()
            page = await browser.newPage()
            
            # Set viewport for consistent rendering
            await page.setViewport({'width': 1200, 'height': 800})
            
            # Load HTML content
            await page.setContent(html_content, waitUntil='networkidle0')
            
            # Generate PDF with Chinese font support
            pdf_options = {
                'format': 'A4',
                'margin': {
                    'top': '20mm',
                    'right': '15mm',
                    'bottom': '20mm',
                    'left': '15mm'
                },
                'printBackground': True,
                'preferCSSPageSize': True
            }
            
            if output_path:
                pdf_options['path'] = output_path
            
            pdf_buffer = await page.pdf(**pdf_options)
            
            await page.close()
            
            # Save to file if path provided
            if output_path:
                logger.info(f"Generated PDF pack saved to: {output_path}")
                return output_path
            else:
                # Save to temporary file
                with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp_file:
                    tmp_file.write(pdf_buffer)
                    temp_path = tmp_file.name
                
                logger.info(f"Generated PDF pack saved to temporary file: {temp_path}")
                return temp_path
                
        except Exception as e:
            logger.error(f"Failed to generate PDF pack: {e}")
            raise
    
    async def generate_pack_summary(
        self, 
        citations: List[CitationData], 
        metadata: PackMetadata
    ) -> Dict[str, Any]:
        """Generate pack summary with statistics."""
        try:
            # Calculate statistics
            total_citations = len(citations)
            provinces = list(set(c.province for c in citations))
            asset_types = list(set(c.asset_type for c in citations))
            doc_classes = list(set(c.doc_class for c in citations))
            
            # Date range analysis
            dates = [c.effective_date for c in citations if c.effective_date]
            date_range = {
                "earliest": min(dates) if dates else None,
                "latest": max(dates) if dates else None
            }
            
            # Confidence score analysis
            scores = [c.confidence_score for c in citations if c.confidence_score is not None]
            confidence_stats = {
                "average": sum(scores) / len(scores) if scores else None,
                "min": min(scores) if scores else None,
                "max": max(scores) if scores else None
            }
            
            # Source analysis
            sources = list(set(c.source_url for c in citations if c.source_url))
            
            summary = {
                "pack_metadata": metadata.dict(),
                "statistics": {
                    "total_citations": total_citations,
                    "unique_provinces": len(provinces),
                    "unique_asset_types": len(asset_types),
                    "unique_doc_classes": len(doc_classes),
                    "unique_sources": len(sources)
                },
                "coverage": {
                    "provinces": provinces,
                    "asset_types": asset_types,
                    "doc_classes": doc_classes,
                    "sources": sources[:10]  # Limit to first 10 sources
                },
                "date_range": date_range,
                "confidence_stats": confidence_stats,
                "generated_at": datetime.utcnow().isoformat()
            }
            
            logger.info(f"Generated pack summary for {total_citations} citations")
            return summary
            
        except Exception as e:
            logger.error(f"Failed to generate pack summary: {e}")
            raise
    
    def _group_citations_by_topic(self, citations: List[CitationData]) -> Dict[str, List[CitationData]]:
        """Group citations by topic for better organization."""
        topics = {
            "并网条件": [],
            "技术要求": [],
            "管理办法": [],
            "市场规则": [],
            "安全规定": [],
            "其他": []
        }
        
        for citation in citations:
            # Simple keyword-based topic classification
            content_lower = citation.content.lower()
            title_lower = citation.title.lower()
            
            if any(keyword in content_lower or keyword in title_lower 
                   for keyword in ["并网", "接入", "连接"]):
                topics["并网条件"].append(citation)
            elif any(keyword in content_lower or keyword in title_lower 
                     for keyword in ["技术", "标准", "规范", "要求"]):
                topics["技术要求"].append(citation)
            elif any(keyword in content_lower or keyword in title_lower 
                     for keyword in ["管理", "办法", "规定", "制度"]):
                topics["管理办法"].append(citation)
            elif any(keyword in content_lower or keyword in title_lower 
                     for keyword in ["市场", "交易", "价格", "竞价"]):
                topics["市场规则"].append(citation)
            elif any(keyword in content_lower or keyword in title_lower 
                     for keyword in ["安全", "保护", "防护", "监控"]):
                topics["安全规定"].append(citation)
            else:
                topics["其他"].append(citation)
        
        # Remove empty topics
        return {topic: cites for topic, cites in topics.items() if cites}
    
    async def close(self):
        """Close browser instance."""
        if self._browser:
            await self._browser.close()
            self._browser = None


# Global generator instance
_pack_generator = None


async def get_pack_generator() -> CitationPackGenerator:
    """Get or create global pack generator instance."""
    global _pack_generator
    
    if _pack_generator is None:
        _pack_generator = CitationPackGenerator()
    
    return _pack_generator


async def generate_citation_pack(
    citations: List[Dict[str, Any]], 
    query: str,
    province: str,
    asset_type: str,
    doc_class: str,
    format_type: str = "pdf",
    output_path: Optional[str] = None
) -> Dict[str, Any]:
    """Generate citation pack with specified format."""
    try:
        # Convert to CitationData objects
        citation_objects = []
        for citation in citations:
            citation_objects.append(CitationData(
                citation_id=citation.get("citation_id", ""),
                title=citation.get("title", ""),
                content=citation.get("content", ""),
                effective_date=citation.get("effective_date", ""),
                source_url=citation.get("source_url"),
                province=citation.get("province", province),
                asset_type=citation.get("asset_type", asset_type),
                doc_class=citation.get("doc_class", doc_class),
                page_number=citation.get("page_number"),
                confidence_score=citation.get("confidence_score")
            ))
        
        # Create pack metadata
        pack_id = f"{province}_{asset_type}_{doc_class}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        metadata = PackMetadata(
            query=query,
            province=province,
            asset_type=asset_type,
            doc_class=doc_class,
            total_citations=len(citation_objects),
            pack_id=pack_id
        )
        
        # Get generator
        generator = await get_pack_generator()
        
        # Generate pack based on format
        if format_type.lower() == "pdf":
            file_path = await generator.generate_pdf_pack(
                citation_objects, metadata, output_path
            )
            pack_summary = await generator.generate_pack_summary(
                citation_objects, metadata
            )
            
            return {
                "pack_id": pack_id,
                "format": "pdf",
                "file_path": file_path,
                "summary": pack_summary,
                "generated_at": datetime.utcnow().isoformat()
            }
            
        elif format_type.lower() == "html":
            html_content = await generator.generate_html_pack(
                citation_objects, metadata
            )
            pack_summary = await generator.generate_pack_summary(
                citation_objects, metadata
            )
            
            return {
                "pack_id": pack_id,
                "format": "html",
                "content": html_content,
                "summary": pack_summary,
                "generated_at": datetime.utcnow().isoformat()
            }
            
        else:
            raise ValueError(f"Unsupported format type: {format_type}")
            
    except Exception as e:
        logger.error(f"Failed to generate citation pack: {e}")
        raise


async def cleanup_pack_generator():
    """Cleanup global pack generator."""
    global _pack_generator
    
    if _pack_generator:
        await _pack_generator.close()
        _pack_generator = None