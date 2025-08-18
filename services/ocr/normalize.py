"""Chinese text normalization and table extraction for energy documents."""

import re
import unicodedata
import logging
from typing import Dict, List, Any, Optional, Tuple

from .schemas import TableData, NormalizedContent

logger = logging.getLogger(__name__)


def normalize_cjk(text: str) -> str:
    """Normalize Chinese, Japanese, Korean text with proper spacing and punctuation."""
    if not text:
        return ""
    
    try:
        # Normalize Unicode to canonical form
        text = unicodedata.normalize("NFKC", text)
        
        # Normalize whitespace but preserve Chinese punctuation
        text = re.sub(r"[ \t\r\f\v]+", " ", text)  # Collapse horizontal whitespace
        text = re.sub(r"\n{3,}", "\n\n", text)     # Limit consecutive newlines
        
        # Clean up common OCR artifacts
        text = re.sub(r"[^\S\n]{2,}", " ", text)   # Multiple non-newline whitespace
        text = re.sub(r"([。！？；：])\s+", r"\1", text)  # Remove space after Chinese punctuation
        text = re.sub(r"\s+([。！？；：])", r"\1", text)  # Remove space before Chinese punctuation
        
        # Fix common OCR spacing issues with Chinese text
        text = re.sub(r"([一-龯])\s+([一-龯])", r"\1\2", text)  # Remove spaces between Chinese characters
        text = re.sub(r"([0-9])\s+([年月日])", r"\1\2", text)   # Fix date formatting
        text = re.sub(r"第\s+([一二三四五六七八九十百千万]+)\s+条", r"第\1条", text)  # Fix article numbering
        
        # Normalize quotation marks
        text = re.sub(r'[""]', '"', text)
        text = re.sub(r"['']", "'", text)
        
        return text.strip()
        
    except Exception as e:
        logger.warning(f"Error normalizing CJK text: {e}")
        return text.strip()


def extract_text_from_segments(text_segments: List[Dict], full_text: str) -> str:
    """Extract text from Document AI text segments."""
    if not text_segments or not full_text:
        return ""
    
    extracted_parts = []
    for segment in text_segments:
        start = segment.get("start_index", 0)
        end = segment.get("end_index", len(full_text))
        
        if 0 <= start < len(full_text) and start < end <= len(full_text):
            extracted_parts.append(full_text[start:end])
    
    return "".join(extracted_parts)


def extract_tables_from_page(page: Dict[str, Any], full_text: str) -> List[TableData]:
    """Extract tables from a Document AI page."""
    tables = []
    
    for table_data in page.get("tables", []):
        try:
            # Extract header rows
            header_rows = []
            for row in table_data.get("header_rows", []):
                cells = []
                for cell in row.get("cells", []):
                    layout = cell.get("layout", {})
                    text_anchor = layout.get("text_anchor", {})
                    segments = text_anchor.get("text_segments", [])
                    cell_text = extract_text_from_segments(segments, full_text)
                    cells.append(normalize_cjk(cell_text))
                header_rows.append(cells)
            
            # Extract body rows
            body_rows = []
            for row in table_data.get("body_rows", []):
                cells = []
                for cell in row.get("cells", []):
                    layout = cell.get("layout", {})
                    text_anchor = layout.get("text_anchor", {})
                    segments = text_anchor.get("text_segments", [])
                    cell_text = extract_text_from_segments(segments, full_text)
                    cells.append(normalize_cjk(cell_text))
                body_rows.append(cells)
            
            # Convert to markdown format
            all_rows = header_rows + body_rows
            if not all_rows:
                continue
            
            # Determine column count
            max_cols = max(len(row) for row in all_rows) if all_rows else 0
            if max_cols == 0:
                continue
            
            # Pad rows to same length
            for row in all_rows:
                while len(row) < max_cols:
                    row.append("")
            
            # Build markdown table
            markdown_lines = []
            
            # Add header if exists
            if header_rows:
                header_line = "| " + " | ".join(header_rows[0]) + " |"
                separator_line = "| " + " | ".join(["---"] * max_cols) + " |"
                markdown_lines.append(header_line)
                markdown_lines.append(separator_line)
                
                # Add remaining header rows as body
                for row in header_rows[1:]:
                    row_line = "| " + " | ".join(row) + " |"
                    markdown_lines.append(row_line)
            
            # Add body rows
            for row in body_rows:
                row_line = "| " + " | ".join(row) + " |"
                markdown_lines.append(row_line)
            
            markdown = "\n".join(markdown_lines)
            
            # Extract caption if available
            caption = ""
            # Look for table caption in nearby text (simplified approach)
            
            table = TableData(
                markdown=markdown,
                caption=caption,
                row_count=len(all_rows),
                col_count=max_cols,
                confidence=0.9  # Default confidence
            )
            
            tables.append(table)
            
        except Exception as e:
            logger.warning(f"Error extracting table: {e}")
            continue
    
    return tables


def extract_paragraphs_from_doc(doc: Dict[str, Any]) -> List[str]:
    """Extract and normalize paragraphs from Document AI output."""
    full_text = doc.get("text", "")
    if not full_text:
        return []
    
    paragraphs = []
    
    # Method 1: Use Document AI blocks if available
    for page in doc.get("pages", []):
        for block in page.get("blocks", []):
            layout = block.get("layout", {})
            text_anchor = layout.get("text_anchor", {})
            segments = text_anchor.get("text_segments", [])
            
            if segments:
                block_text = extract_text_from_segments(segments, full_text)
                normalized = normalize_cjk(block_text)
                
                if normalized and len(normalized.strip()) > 10:  # Filter out very short blocks
                    paragraphs.append(normalized)
    
    # Method 2: Fallback to simple paragraph splitting if no blocks
    if not paragraphs:
        # Split by double newlines and normalize
        raw_paragraphs = full_text.split('\n\n')
        for para in raw_paragraphs:
            normalized = normalize_cjk(para)
            if normalized and len(normalized.strip()) > 10:
                paragraphs.append(normalized)
    
    # Method 3: Final fallback - split by single newlines
    if not paragraphs:
        raw_lines = full_text.split('\n')
        current_para = []
        
        for line in raw_lines:
            line = line.strip()
            if not line:
                if current_para:
                    para_text = normalize_cjk(' '.join(current_para))
                    if para_text and len(para_text) > 10:
                        paragraphs.append(para_text)
                    current_para = []
            else:
                current_para.append(line)
        
        # Add final paragraph
        if current_para:
            para_text = normalize_cjk(' '.join(current_para))
            if para_text and len(para_text) > 10:
                paragraphs.append(para_text)
    
    return paragraphs


def detect_language(text: str) -> Optional[str]:
    """Detect document language (simplified Chinese detection)."""
    if not text:
        return None
    
    # Count Chinese characters
    chinese_chars = sum(1 for char in text if '\u4e00' <= char <= '\u9fff')
    total_chars = len([c for c in text if c.isalnum()])
    
    if total_chars == 0:
        return None
    
    chinese_ratio = chinese_chars / total_chars
    
    if chinese_ratio >= 0.3:
        return "zh-CN"
    elif chinese_ratio >= 0.1:
        return "zh-mixed"
    else:
        return "other"


def doc_to_normalized_content(doc: Dict[str, Any]) -> NormalizedContent:
    """Convert Document AI output to normalized content structure."""
    try:
        # Extract paragraphs
        paragraphs = extract_paragraphs_from_doc(doc)
        
        # Extract tables from all pages
        tables = []
        full_text = doc.get("text", "")
        
        for page in doc.get("pages", []):
            page_tables = extract_tables_from_page(page, full_text)
            tables.extend(page_tables)
        
        # Detect language
        combined_text = "\n".join(paragraphs)
        language = detect_language(combined_text)
        
        # Count pages
        page_count = len(doc.get("pages", []))
        
        return NormalizedContent(
            paragraphs=paragraphs,
            tables=tables,
            effective_date=None,  # Will be set by effective_date.py
            language=language,
            page_count=page_count
        )
        
    except Exception as e:
        logger.error(f"Error converting document to normalized content: {e}")
        return NormalizedContent(
            paragraphs=[],
            tables=[],
            effective_date=None,
            language=None,
            page_count=0
        )


def merge_short_paragraphs(paragraphs: List[str], min_length: int = 50) -> List[str]:
    """Merge very short paragraphs with adjacent ones to improve chunking."""
    if not paragraphs:
        return []
    
    merged = []
    current = ""
    
    for para in paragraphs:
        if len(current) < min_length and current:
            # Merge with previous
            current = current + "\n" + para
        else:
            if current:
                merged.append(current)
            current = para
    
    # Add final paragraph
    if current:
        merged.append(current)
    
    return merged


def clean_ocr_artifacts(text: str) -> str:
    """Clean common OCR artifacts from Chinese text."""
    if not text:
        return text
    
    # Remove common OCR errors
    text = re.sub(r"[|｜]", "", text)  # Remove vertical bars
    text = re.sub(r"[□■▪▫]", "", text)  # Remove box characters
    text = re.sub(r"[^\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff\w\s\n\r\t.,;:!?()[]{}\"'""''—–-]", "", text)  # Keep only Chinese, alphanumeric, and basic punctuation
    
    # Fix spacing around numbers and units
    text = re.sub(r"(\d+)\s*(千瓦|兆瓦|万千瓦|千伏|万伏|千米|公里|米|厘米|毫米|吨|千克|公斤|克|升|毫升|小时|分钟|秒|年|月|日|天)", r"\1\2", text)
    
    # Fix common character substitutions
    replacements = {
        "O": "0",  # Letter O to zero in numbers
        "l": "1",  # Lowercase L to one in numbers (context-dependent)
        "S": "5",  # In some contexts
    }
    
    # Apply replacements carefully (only in numeric contexts)
    for old, new in replacements.items():
        # Only replace if surrounded by digits
        text = re.sub(rf"(\d){old}(\d)", rf"\1{new}\2", text)
    
    return text


def extract_document_metadata(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Extract metadata from Document AI document."""
    metadata = {
        "page_count": len(doc.get("pages", [])),
        "text_length": len(doc.get("text", "")),
        "has_tables": False,
        "table_count": 0,
        "paragraph_count": 0,
        "avg_confidence": 0.0,
        "language": None
    }
    
    # Count tables and calculate confidence
    confidence_scores = []
    table_count = 0
    
    for page in doc.get("pages", []):
        # Count tables
        tables = page.get("tables", [])
        table_count += len(tables)
        
        # Collect confidence scores
        for block in page.get("blocks", []):
            layout = block.get("layout", {})
            if "confidence" in layout:
                confidence_scores.append(layout["confidence"])
    
    metadata["has_tables"] = table_count > 0
    metadata["table_count"] = table_count
    
    if confidence_scores:
        metadata["avg_confidence"] = sum(confidence_scores) / len(confidence_scores)
    
    # Extract paragraphs for counting
    paragraphs = extract_paragraphs_from_doc(doc)
    metadata["paragraph_count"] = len(paragraphs)
    
    # Detect language
    full_text = doc.get("text", "")
    metadata["language"] = detect_language(full_text)
    
    return metadata