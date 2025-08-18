"""Effective date extraction for Chinese energy regulation documents."""

import re
import logging
from datetime import date, datetime
from typing import Optional, List, Tuple, Dict, Any

logger = logging.getLogger(__name__)


# Chinese date patterns with various formats
DATE_PATTERNS = [
    # Standard Chinese format: 2025年3月1日
    r"(?P<y>20\d{2})年(?P<m>\d{1,2})月(?P<d>\d{1,2})日",
    
    # Implementation phrases: 自2025年3月1日起施行
    r"自(?P<y>20\d{2})年(?P<m>\d{1,2})月(?P<d>\d{1,2})日起(?:施行|执行|生效|实施)",
    
    # Effective from phrases: 本规则自2025年3月1日起执行
    r"本(?:规则|办法|通知|公告|文件)自(?P<y>20\d{2})年(?P<m>\d{1,2})月(?P<d>\d{1,2})日起(?:施行|执行|生效|实施)",
    
    # ISO-like formats: 2025-03-01, 2025/03/01
    r"(?P<y>20\d{2})[-/](?P<m>\d{1,2})[-/](?P<d>\d{1,2})",
    
    # Publication date: 发布日期：2025年3月1日
    r"(?:发布|公布|颁布|印发)(?:日期|时间)?[：:](?P<y>20\d{2})年(?P<m>\d{1,2})月(?P<d>\d{1,2})日",
    
    # Effective date: 生效日期：2025年3月1日
    r"(?:生效|施行|执行|实施)(?:日期|时间)?[：:](?P<y>20\d{2})年(?P<m>\d{1,2})月(?P<d>\d{1,2})日",
    
    # Document number with date: 粤能规〔2025〕1号
    r"[粤鲁蒙川](?:能|电|发改)(?:规|函|通|发)〔(?P<y>20\d{2})〕\d+号",
    
    # Approval date: 批准日期：2025年3月1日
    r"(?:批准|核准|审批)(?:日期|时间)?[：:](?P<y>20\d{2})年(?P<m>\d{1,2})月(?P<d>\d{1,2})日",
    
    # Meeting date: 会议通过日期：2025年3月1日
    r"(?:会议|委员会)(?:通过|审议|决定)(?:日期|时间)?[：:](?P<y>20\d{2})年(?P<m>\d{1,2})月(?P<d>\d{1,2})日",
]

# Context patterns that indicate effective dates
EFFECTIVE_CONTEXT_PATTERNS = [
    r"自.*?起(?:施行|执行|生效|实施)",
    r"本(?:规则|办法|通知|公告|文件).*?起(?:施行|执行|生效|实施)",
    r"(?:施行|执行|生效|实施)(?:日期|时间)",
    r"有效期.*?至",
    r"废止.*?文件",
]

# Patterns to exclude (likely not effective dates)
EXCLUDE_PATTERNS = [
    r"截止.*?日期",
    r"申请.*?日期",
    r"报送.*?日期",
    r"提交.*?日期",
    r"完成.*?日期",
]


def extract_effective_date(text: str, source_url: Optional[str] = None) -> Optional[date]:
    """
    Extract effective date from Chinese energy regulation document.
    
    Args:
        text: Document text content
        source_url: Source URL for additional context
        
    Returns:
        Effective date if found, None otherwise
    """
    if not text:
        return None
    
    try:
        # First, try to find dates with explicit effective context
        effective_date = _find_date_with_context(text)
        if effective_date:
            logger.info(f"Found effective date with context: {effective_date}")
            return effective_date
        
        # Try to extract from document number/title
        if source_url:
            url_date = _extract_date_from_url(source_url)
            if url_date:
                logger.info(f"Found date from URL: {url_date}")
                return url_date
        
        # Look for publication/approval dates as fallback
        fallback_date = _find_publication_date(text)
        if fallback_date:
            logger.info(f"Found publication date as fallback: {fallback_date}")
            return fallback_date
        
        # Last resort: find any date in the first few paragraphs
        first_date = _find_first_reasonable_date(text)
        if first_date:
            logger.info(f"Found first reasonable date: {first_date}")
            return first_date
        
        logger.warning("No effective date found in document")
        return None
        
    except Exception as e:
        logger.error(f"Error extracting effective date: {e}")
        return None


def _find_date_with_context(text: str) -> Optional[date]:
    """Find dates that appear in effective date contexts."""
    # Look for dates near effective context phrases
    for context_pattern in EFFECTIVE_CONTEXT_PATTERNS:
        context_matches = list(re.finditer(context_pattern, text, re.IGNORECASE))
        
        for context_match in context_matches:
            # Search for dates within 200 characters of the context
            start = max(0, context_match.start() - 100)
            end = min(len(text), context_match.end() + 100)
            context_text = text[start:end]
            
            # Try to find a date in this context
            for pattern in DATE_PATTERNS:
                matches = re.finditer(pattern, context_text, re.IGNORECASE)
                for match in matches:
                    try:
                        extracted_date = _parse_date_match(match, pattern)
                        if extracted_date and _is_reasonable_date(extracted_date):
                            return extracted_date
                    except Exception:
                        continue
    
    return None


def _find_publication_date(text: str) -> Optional[date]:
    """Find publication, approval, or issuance dates."""
    publication_patterns = [
        r"(?:发布|公布|颁布|印发|批准|核准|审批)(?:日期|时间)?[：:](?P<y>20\d{2})年(?P<m>\d{1,2})月(?P<d>\d{1,2})日",
        r"(?P<y>20\d{2})年(?P<m>\d{1,2})月(?P<d>\d{1,2})日(?:发布|公布|颁布|印发|批准|核准|审批)",
    ]
    
    for pattern in publication_patterns:
        matches = re.finditer(pattern, text, re.IGNORECASE)
        for match in matches:
            try:
                extracted_date = _parse_date_match(match, pattern)
                if extracted_date and _is_reasonable_date(extracted_date):
                    return extracted_date
            except Exception:
                continue
    
    return None


def _find_first_reasonable_date(text: str) -> Optional[date]:
    """Find the first reasonable date in the document (first 1000 characters)."""
    # Only look at the beginning of the document
    search_text = text[:1000]
    
    dates_found = []
    
    for pattern in DATE_PATTERNS:
        matches = re.finditer(pattern, search_text, re.IGNORECASE)
        for match in matches:
            try:
                extracted_date = _parse_date_match(match, pattern)
                if extracted_date and _is_reasonable_date(extracted_date):
                    # Check if this date is in an excluded context
                    if not _is_excluded_context(match, search_text):
                        dates_found.append((extracted_date, match.start()))
            except Exception:
                continue
    
    if dates_found:
        # Return the earliest date by position in text
        dates_found.sort(key=lambda x: x[1])
        return dates_found[0][0]
    
    return None


def _extract_date_from_url(url: str) -> Optional[date]:
    """Extract date from URL patterns common in Chinese government sites."""
    if not url:
        return None
    
    # Common URL date patterns
    url_patterns = [
        r"/(\d{4})/(\d{1,2})/(\d{1,2})/",  # /2025/03/01/
        r"/(\d{4})(\d{2})(\d{2})/",        # /20250301/
        r"_(\d{4})(\d{2})(\d{2})_",        # _20250301_
        r"-(\d{4})(\d{2})(\d{2})-",        # -20250301-
        r"(\d{4})-(\d{1,2})-(\d{1,2})",    # 2025-03-01
    ]
    
    for pattern in url_patterns:
        match = re.search(pattern, url)
        if match:
            try:
                if len(match.groups()) == 3:
                    year, month, day = match.groups()
                    extracted_date = date(int(year), int(month), int(day))
                    if _is_reasonable_date(extracted_date):
                        return extracted_date
            except Exception:
                continue
    
    return None


def _parse_date_match(match: re.Match, pattern: str) -> Optional[date]:
    """Parse a regex match into a date object."""
    try:
        groups = match.groupdict()
        
        if 'y' in groups and 'm' in groups and 'd' in groups:
            year = int(groups['y'])
            month = int(groups['m'])
            day = int(groups['d'])
            return date(year, month, day)
        elif 'y' in groups:
            # Only year found (from document numbers)
            year = int(groups['y'])
            # Use January 1st as default for year-only matches
            return date(year, 1, 1)
        
        return None
        
    except (ValueError, KeyError) as e:
        logger.debug(f"Error parsing date match: {e}")
        return None


def _is_reasonable_date(check_date: date) -> bool:
    """Check if a date is reasonable for energy regulation documents."""
    current_date = date.today()
    
    # Must be between 2000 and 10 years in the future
    min_date = date(2000, 1, 1)
    max_date = date(current_date.year + 10, 12, 31)
    
    return min_date <= check_date <= max_date


def _is_excluded_context(match: re.Match, text: str) -> bool:
    """Check if a date match is in an excluded context."""
    # Get surrounding context
    start = max(0, match.start() - 50)
    end = min(len(text), match.end() + 50)
    context = text[start:end]
    
    # Check against exclusion patterns
    for exclude_pattern in EXCLUDE_PATTERNS:
        if re.search(exclude_pattern, context, re.IGNORECASE):
            return True
    
    return False


def extract_multiple_dates(text: str) -> List[Tuple[date, str, float]]:
    """
    Extract multiple dates with context and confidence scores.
    
    Returns:
        List of (date, context, confidence) tuples
    """
    dates_found = []
    
    for pattern in DATE_PATTERNS:
        matches = re.finditer(pattern, text, re.IGNORECASE)
        for match in matches:
            try:
                extracted_date = _parse_date_match(match, pattern)
                if extracted_date and _is_reasonable_date(extracted_date):
                    # Get context around the match
                    start = max(0, match.start() - 30)
                    end = min(len(text), match.end() + 30)
                    context = text[start:end].strip()
                    
                    # Calculate confidence based on pattern type and context
                    confidence = _calculate_date_confidence(pattern, context, match.start(), len(text))
                    
                    dates_found.append((extracted_date, context, confidence))
                    
            except Exception as e:
                logger.debug(f"Error processing date match: {e}")
                continue
    
    # Sort by confidence (highest first)
    dates_found.sort(key=lambda x: x[2], reverse=True)
    
    return dates_found


def _calculate_date_confidence(pattern: str, context: str, position: int, text_length: int) -> float:
    """Calculate confidence score for a date match."""
    confidence = 0.5  # Base confidence
    
    # Higher confidence for explicit effective date patterns
    if "起施行" in pattern or "起执行" in pattern or "起生效" in pattern:
        confidence += 0.4
    
    # Higher confidence for official document patterns
    if "发布" in pattern or "公布" in pattern or "颁布" in pattern:
        confidence += 0.3
    
    # Higher confidence if found early in document
    if position < text_length * 0.1:  # First 10% of document
        confidence += 0.2
    elif position < text_length * 0.3:  # First 30% of document
        confidence += 0.1
    
    # Higher confidence for certain context keywords
    high_confidence_keywords = ["施行", "执行", "生效", "实施", "发布", "公布", "颁布"]
    for keyword in high_confidence_keywords:
        if keyword in context:
            confidence += 0.1
            break
    
    # Lower confidence for excluded contexts
    if _is_excluded_context_simple(context):
        confidence -= 0.3
    
    return min(1.0, max(0.0, confidence))


def _is_excluded_context_simple(context: str) -> bool:
    """Simple check for excluded contexts."""
    exclude_keywords = ["截止", "申请", "报送", "提交", "完成", "到期"]
    return any(keyword in context for keyword in exclude_keywords)


def validate_effective_date(extracted_date: Optional[date], document_text: str) -> Dict[str, Any]:
    """
    Validate and provide metadata about an extracted effective date.
    
    Returns:
        Dictionary with validation results and metadata
    """
    result = {
        "date": extracted_date,
        "is_valid": False,
        "confidence": 0.0,
        "validation_notes": [],
        "alternative_dates": []
    }
    
    if not extracted_date:
        result["validation_notes"].append("No effective date found")
        return result
    
    # Basic validation
    if not _is_reasonable_date(extracted_date):
        result["validation_notes"].append("Date is outside reasonable range")
        return result
    
    result["is_valid"] = True
    
    # Find all dates for comparison
    all_dates = extract_multiple_dates(document_text)
    result["alternative_dates"] = [(d.isoformat(), ctx, conf) for d, ctx, conf in all_dates[:5]]
    
    # Calculate confidence based on multiple factors
    if all_dates:
        # Find the confidence of our selected date
        for found_date, context, confidence in all_dates:
            if found_date == extracted_date:
                result["confidence"] = confidence
                break
    
    # Additional validation notes
    current_date = date.today()
    if extracted_date > current_date:
        result["validation_notes"].append("Future effective date")
    elif (current_date - extracted_date).days > 365 * 5:
        result["validation_notes"].append("Effective date is more than 5 years old")
    
    return result