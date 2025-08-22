# Chinese government document metadata extraction
# Extracts 文号, 发布机关, 发布日期, 实施日期, 状态 from HTML and PDF documents

import re
import logging
from datetime import datetime
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)

# Regex patterns for Chinese government documents
WENHAO_PATTERNS = [
    r"(?:文号|〔?\d{4}〕?\d+号|发改[^\s〔]+〔\d{4}〕\d+号)",  # 文号/〔2023〕12号/发改能〔2023〕45号
    r"(?:文件编号|编号)[：:]\s*([^\n\r]+)",  # 文件编号：xxx
    r"[^\s（）()]*〔\d{4}〕\d+号",  # 粤能规〔2023〕12号
]

AGENCY_PATTERNS = [
    r"(?:发布机关|印发单位|主送单位|制发机关)[：:]\s*([^\n\r；;]+)",  # 发布机关：xxx
    r"(?:国家|省|市|区|县)?(?:发展改革委|发改委|能源局|工信厅|市场监管局|生态环境厅|自然资源厅)",  # Common agencies
]

STATUS_PATTERNS = [
    r"(现行有效|失效|废止|部分失效|已失效|已废止)",  # Status indicators
]

DATE_PATTERNS = [
    r"(?:发布日期|印发日期|成文日期|实施日期|执行日期)[：:]\s*(\d{4}[年\-/.]\d{1,2}[月\-/.]\d{1,2}日?)",  # 发布日期：2023年6月1日
    r"(\d{4})年(\d{1,2})月(\d{1,2})日",  # 2023年6月1日
    r"(\d{4})[/-](\d{1,2})[/-](\d{1,2})",  # 2023/6/1 or 2023-06-01
]

def extract_wenhao(text: str) -> Optional[str]:
    """Extract document number (文号) from text."""
    for pattern in WENHAO_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            # Return the full matched text, not just groups
            return match.group(0).strip()
    return None

def extract_agency(text: str) -> Optional[str]:
    """Extract publishing agency (发布机关) from text."""
    for pattern in AGENCY_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            # Return the captured group
            agency = match.group(1) if len(match.groups()) > 0 else match.group(0)
            return agency.strip()
    return None

def extract_status(text: str) -> str:
    """Extract document status. Defaults to '现行有效' if not found."""
    for pattern in STATUS_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return "现行有效"

def extract_dates(text: str) -> Tuple[Optional[str], Optional[str]]:
    """Extract publish and effective dates from text."""
    dates = []
    for pattern in DATE_PATTERNS:
        matches = re.findall(pattern, text)
        for match in matches:
            if isinstance(match, tuple):
                # For patterns with groups like (\d{4})年(\d{1,2})月(\d{1,2})日
                if len(match) == 3:
                    year, month, day = match
                    try:
                        # Normalize to YYYY-MM-DD format
                        normalized_date = f"{int(year):04d}-{int(month):02d}-{int(day):02d}"
                        dates.append(normalized_date)
                    except ValueError:
                        continue
                else:
                    dates.append(match[0])
            else:
                dates.append(match)

    # Remove duplicates and sort
    unique_dates = sorted(set(dates))

    # Heuristic: first date is usually publish date, last plausible date is effective
    publish_date = unique_dates[0] if unique_dates else None
    effective_date = unique_dates[-1] if len(unique_dates) > 1 else publish_date

    return publish_date, effective_date

def normalize_date(date_str: str) -> Optional[str]:
    """Normalize various date formats to ISO format (YYYY-MM-DD)."""
    if not date_str:
        return None

    # Handle Chinese format: 2023年6月1日
    chinese_match = re.match(r"(\d{4})年(\d{1,2})月(\d{1,2})日?", date_str)
    if chinese_match:
        year, month, day = chinese_match.groups()
        return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"

    # Handle slash/hyphen formats: 2023/6/1, 2023-06-01
    slash_match = re.match(r"(\d{4})[/-](\d{1,2})[/-](\d{1,2})", date_str)
    if slash_match:
        year, month, day = slash_match.groups()
        return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"

    # If no match, return as-is
    return date_str

def extract_metadata(text: str) -> Dict[str, any]:
    """
    Extract Chinese government document metadata from text.

    Returns:
        Dict with keys: wenhao, agency, status, publish_date, effective_date
    """
    try:
        # Extract components
        wenhao = extract_wenhao(text)
        agency = extract_agency(text)
        status = extract_status(text)
        publish_date, effective_date = extract_dates(text)

        # Normalize dates
        publish_date = normalize_date(publish_date) if publish_date else None
        effective_date = normalize_date(effective_date) if effective_date else effective_date

        metadata = {
            "wenhao": wenhao,
            "agency": agency,
            "status": status,
            "publish_date": publish_date,
            "effective_date": effective_date,
            "extraction_confidence": calculate_confidence(wenhao, agency, status, publish_date)
        }

        logger.debug(f"Extracted metadata: {metadata}")
        return metadata

    except Exception as e:
        logger.error(f"Error extracting metadata: {e}")
        return {
            "wenhao": None,
            "agency": None,
            "status": "现行有效",
            "publish_date": None,
            "effective_date": None,
            "extraction_confidence": 0.0
        }

def calculate_confidence(wenhao: str, agency: str, status: str, publish_date: str) -> float:
    """Calculate confidence score for extracted metadata."""
    confidence = 0.0
    if wenhao: confidence += 0.4
    if agency: confidence += 0.3
    if status != "现行有效": confidence += 0.2  # Bonus for explicit status
    if publish_date: confidence += 0.1
    return min(confidence, 1.0)  # Cap at 1.0
