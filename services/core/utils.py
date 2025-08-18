"""Utility functions for geo-adaptive energy assistant."""

import hashlib
import re
from datetime import datetime, date
from typing import Optional, List, Dict, Any, Union
from uuid import UUID, uuid4

import jieba
from opencc import OpenCC


def generate_uuid() -> UUID:
    """Generate a new UUID4."""
    return uuid4()


def calculate_sha256(content: Union[str, bytes]) -> str:
    """Calculate SHA256 checksum of content."""
    if isinstance(content, str):
        content = content.encode("utf-8")
    
    return hashlib.sha256(content).hexdigest()


def normalize_text(text: str, remove_punctuation: bool = False) -> str:
    """Normalize Chinese text for processing."""
    if not text:
        return ""
    
    # Convert traditional Chinese to simplified
    cc = OpenCC('t2s')  # Traditional to Simplified
    text = cc.convert(text)
    
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    
    # Optionally remove punctuation
    if remove_punctuation:
        # Remove Chinese and English punctuation
        punctuation_pattern = r'[，。！？；：""''（）【】《》、\.,!?;:"\'()\[\]<>]'
        text = re.sub(punctuation_pattern, '', text)
    
    return text


def extract_effective_date(text: str, url: str = "") -> Optional[date]:
    """Extract effective date from document text or URL."""
    if not text and not url:
        return None
    
    # Combine text and URL for date extraction
    content = f"{text} {url}"
    
    # Common date patterns in Chinese documents
    date_patterns = [
        # YYYY年MM月DD日
        r'(\d{4})年(\d{1,2})月(\d{1,2})日',
        # YYYY-MM-DD
        r'(\d{4})-(\d{1,2})-(\d{1,2})',
        # YYYY/MM/DD
        r'(\d{4})/(\d{1,2})/(\d{1,2})',
        # YYYY.MM.DD
        r'(\d{4})\.(\d{1,2})\.(\d{1,2})',
        # 自YYYY年MM月DD日起
        r'自(\d{4})年(\d{1,2})月(\d{1,2})日起',
        # 发布日期：YYYY-MM-DD
        r'发布日期[：:](\d{4})-(\d{1,2})-(\d{1,2})',
        # 生效日期：YYYY-MM-DD
        r'生效日期[：:](\d{4})-(\d{1,2})-(\d{1,2})',
    ]
    
    for pattern in date_patterns:
        matches = re.findall(pattern, content)
        if matches:
            try:
                # Take the first match
                year, month, day = matches[0]
                extracted_date = date(int(year), int(month), int(day))
                
                # Validate date is reasonable (not in future, not too old)
                if extracted_date <= date.today():
                    return extracted_date
            except (ValueError, IndexError):
                continue
    
    return None


def segment_chinese_text(text: str) -> List[str]:
    """Segment Chinese text into words using jieba."""
    if not text:
        return []
    
    # Use jieba for Chinese word segmentation
    words = jieba.lcut(text)
    
    # Filter out single characters and punctuation
    filtered_words = []
    for word in words:
        word = word.strip()
        if len(word) > 1 and not re.match(r'^[，。！？；：""''（）【】《》、\.,!?;:"\'()\[\]<>\s]+$', word):
            filtered_words.append(word)
    
    return filtered_words


def chunk_text(
    text: str,
    max_tokens: int = 800,
    overlap_tokens: int = 100,
    chunk_separator: str = "\n\n"
) -> List[Dict[str, Any]]:
    """Chunk text into smaller segments with overlap for embeddings."""
    if not text:
        return []
    
    # Rough token estimation (Chinese characters + spaces)
    def estimate_tokens(text: str) -> int:
        # Approximate: 1 Chinese character ≈ 1.5 tokens, 1 English word ≈ 1 token
        chinese_chars = sum(1 for char in text if '\u4e00' <= char <= '\u9fff')
        other_chars = len(text) - chinese_chars
        return int(chinese_chars * 1.5 + other_chars * 0.5)
    
    # Split text into paragraphs first
    paragraphs = text.split(chunk_separator)
    
    chunks = []
    current_chunk = ""
    current_tokens = 0
    chunk_id = 1
    
    for paragraph in paragraphs:
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        
        para_tokens = estimate_tokens(paragraph)
        
        # If paragraph alone exceeds max_tokens, split it further
        if para_tokens > max_tokens:
            # Split by sentences
            sentences = re.split(r'[。！？；]', paragraph)
            for sentence in sentences:
                sentence = sentence.strip()
                if not sentence:
                    continue
                
                sentence_tokens = estimate_tokens(sentence)
                
                if current_tokens + sentence_tokens > max_tokens and current_chunk:
                    # Save current chunk
                    chunks.append({
                        "chunk_id": f"chunk_{chunk_id:03d}",
                        "content": current_chunk.strip(),
                        "token_count": current_tokens,
                        "start_pos": len("".join(c["content"] for c in chunks)),
                        "end_pos": len("".join(c["content"] for c in chunks)) + len(current_chunk)
                    })
                    
                    # Start new chunk with overlap
                    if overlap_tokens > 0 and current_chunk:
                        overlap_text = current_chunk[-overlap_tokens:]
                        current_chunk = overlap_text + sentence
                        current_tokens = estimate_tokens(current_chunk)
                    else:
                        current_chunk = sentence
                        current_tokens = sentence_tokens
                    
                    chunk_id += 1
                else:
                    current_chunk += sentence
                    current_tokens += sentence_tokens
        else:
            # Check if adding this paragraph exceeds max_tokens
            if current_tokens + para_tokens > max_tokens and current_chunk:
                # Save current chunk
                chunks.append({
                    "chunk_id": f"chunk_{chunk_id:03d}",
                    "content": current_chunk.strip(),
                    "token_count": current_tokens,
                    "start_pos": len("".join(c["content"] for c in chunks)),
                    "end_pos": len("".join(c["content"] for c in chunks)) + len(current_chunk)
                })
                
                # Start new chunk with overlap
                if overlap_tokens > 0 and current_chunk:
                    overlap_text = current_chunk[-overlap_tokens:]
                    current_chunk = overlap_text + chunk_separator + paragraph
                    current_tokens = estimate_tokens(current_chunk)
                else:
                    current_chunk = paragraph
                    current_tokens = para_tokens
                
                chunk_id += 1
            else:
                if current_chunk:
                    current_chunk += chunk_separator + paragraph
                else:
                    current_chunk = paragraph
                current_tokens += para_tokens
    
    # Add final chunk if exists
    if current_chunk.strip():
        chunks.append({
            "chunk_id": f"chunk_{chunk_id:03d}",
            "content": current_chunk.strip(),
            "token_count": current_tokens,
            "start_pos": len("".join(c["content"] for c in chunks)),
            "end_pos": len("".join(c["content"] for c in chunks)) + len(current_chunk)
        })
    
    return chunks


def clean_html_content(html: str) -> str:
    """Clean HTML content and extract text."""
    if not html:
        return ""
    
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', '', html)
    
    # Decode HTML entities
    import html as html_module
    text = html_module.unescape(text)
    
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text


def format_chinese_date(date_obj: date) -> str:
    """Format date in Chinese style."""
    return f"{date_obj.year}年{date_obj.month}月{date_obj.day}日"


def parse_chinese_date(date_str: str) -> Optional[date]:
    """Parse Chinese date format to date object."""
    if not date_str:
        return None
    
    # Try different Chinese date formats
    patterns = [
        (r'(\d{4})年(\d{1,2})月(\d{1,2})日', lambda m: date(int(m[0]), int(m[1]), int(m[2]))),
        (r'(\d{4})-(\d{1,2})-(\d{1,2})', lambda m: date(int(m[0]), int(m[1]), int(m[2]))),
        (r'(\d{4})/(\d{1,2})/(\d{1,2})', lambda m: date(int(m[0]), int(m[1]), int(m[2]))),
    ]
    
    for pattern, converter in patterns:
        match = re.search(pattern, date_str)
        if match:
            try:
                return converter(match.groups())
            except ValueError:
                continue
    
    return None


def generate_citation_id(url: str, checksum: str) -> UUID:
    """Generate deterministic citation ID based on URL and checksum."""
    content = f"{url}:{checksum}"
    hash_bytes = hashlib.sha256(content.encode("utf-8")).digest()
    
    # Convert first 16 bytes to UUID
    return UUID(bytes=hash_bytes[:16])


def validate_chinese_ratio(text: str, min_ratio: float = 0.3) -> bool:
    """Check if text has sufficient Chinese content."""
    if not text:
        return False
    
    chinese_chars = sum(1 for char in text if '\u4e00' <= char <= '\u9fff')
    total_chars = len([c for c in text if c.isalnum()])
    
    if total_chars == 0:
        return False
    
    return (chinese_chars / total_chars) >= min_ratio


def extract_domain_from_url(url: str) -> str:
    """Extract domain from URL."""
    if not url:
        return ""
    
    # Remove protocol
    domain = re.sub(r'^https?://', '', url)
    
    # Remove path and query parameters
    domain = domain.split('/')[0]
    domain = domain.split('?')[0]
    
    # Remove port
    domain = domain.split(':')[0]
    
    return domain.lower()


def is_official_domain(url: str) -> bool:
    """Check if URL is from an official domain."""
    domain = extract_domain_from_url(url)
    
    official_domains = [
        ".gov.cn",
        "gzpec.cn",
        "bjpec.cn",
        "shandong-electric.com.cn", 
        "nmgdl.cn",
        "sc.sgcc.com.cn",
    ]
    
    return any(official in domain for official in official_domains)


def sanitize_filename(filename: str) -> str:
    """Sanitize filename for safe file system usage."""
    if not filename:
        return "untitled"
    
    # Remove or replace unsafe characters
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    
    # Remove control characters
    filename = re.sub(r'[\x00-\x1f\x7f]', '', filename)
    
    # Limit length
    if len(filename) > 200:
        filename = filename[:200]
    
    # Ensure not empty
    if not filename.strip():
        filename = "untitled"
    
    return filename.strip()


def format_file_size(size_bytes: int) -> str:
    """Format file size in human readable format."""
    if size_bytes == 0:
        return "0 B"
    
    size_names = ["B", "KB", "MB", "GB", "TB"]
    import math
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)
    
    return f"{s} {size_names[i]}"


def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """Truncate text to specified length with suffix."""
    if not text or len(text) <= max_length:
        return text
    
    return text[:max_length - len(suffix)] + suffix


def mask_sensitive_data(data: str, mask_char: str = "*", visible_chars: int = 4) -> str:
    """Mask sensitive data showing only first/last few characters."""
    if not data or len(data) <= visible_chars * 2:
        return mask_char * len(data) if data else ""
    
    visible_start = data[:visible_chars]
    visible_end = data[-visible_chars:]
    masked_middle = mask_char * (len(data) - visible_chars * 2)
    
    return f"{visible_start}{masked_middle}{visible_end}"