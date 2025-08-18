"""Validation utilities for geo-adaptive energy assistant."""

import hashlib
import re
from datetime import datetime, date
from typing import Optional, List, Dict, Any
from uuid import UUID

from .models import Province, DocumentClass, AssetType, RefusalReason


def validate_province(province: str) -> str:
    """Validate and normalize province input."""
    if not province:
        raise ValueError("Province is required")
    
    province = province.lower().strip()
    
    # Handle common variations
    province_mappings = {
        "山东": Province.SHANDONG,
        "shandong": Province.SHANDONG,
        "sd": Province.SHANDONG,
        "广东": Province.GUANGDONG,
        "guangdong": Province.GUANGDONG,
        "gd": Province.GUANGDONG,
        "内蒙古": Province.INNER_MONGOLIA,
        "inner_mongolia": Province.INNER_MONGOLIA,
        "inner-mongolia": Province.INNER_MONGOLIA,
        "innermongolia": Province.INNER_MONGOLIA,
        "nm": Province.INNER_MONGOLIA,
        "四川": Province.SICHUAN,
        "sichuan": Province.SICHUAN,
        "sc": Province.SICHUAN,
    }
    
    normalized = province_mappings.get(province)
    if not normalized:
        raise ValueError(f"Unsupported province: {province}")
    
    # Check if province is enabled
    if not Province.is_enabled(normalized):
        raise ValueError(f"Province {normalized} is not currently enabled")
    
    return normalized


def validate_doc_class(doc_class: str) -> str:
    """Validate and normalize document class input."""
    if not doc_class:
        raise ValueError("Document class is required")
    
    doc_class = doc_class.lower().strip()
    
    # Handle common variations
    doc_class_mappings = {
        "market_rules": DocumentClass.MARKET_RULES,
        "market-rules": DocumentClass.MARKET_RULES,
        "marketrules": DocumentClass.MARKET_RULES,
        "市场规则": DocumentClass.MARKET_RULES,
        "市场": DocumentClass.MARKET_RULES,
        "grid_connection": DocumentClass.GRID_CONNECTION,
        "grid-connection": DocumentClass.GRID_CONNECTION,
        "gridconnection": DocumentClass.GRID_CONNECTION,
        "并网接入": DocumentClass.GRID_CONNECTION,
        "并网": DocumentClass.GRID_CONNECTION,
        "接入": DocumentClass.GRID_CONNECTION,
        "dispatch_ops": DocumentClass.DISPATCH_OPS,
        "dispatch-ops": DocumentClass.DISPATCH_OPS,
        "dispatchops": DocumentClass.DISPATCH_OPS,
        "调度运行": DocumentClass.DISPATCH_OPS,
        "调度": DocumentClass.DISPATCH_OPS,
        "运行": DocumentClass.DISPATCH_OPS,
    }
    
    normalized = doc_class_mappings.get(doc_class)
    if not normalized:
        raise ValueError(f"Unsupported document class: {doc_class}")
    
    return normalized


def validate_asset_type(asset: str) -> str:
    """Validate and normalize asset type input."""
    if not asset:
        raise ValueError("Asset type is required")
    
    asset = asset.lower().strip()
    
    # Handle common variations
    asset_mappings = {
        "wind": AssetType.WIND,
        "风电": AssetType.WIND,
        "风力": AssetType.WIND,
        "风能": AssetType.WIND,
        "solar": AssetType.SOLAR,
        "光伏": AssetType.SOLAR,
        "太阳能": AssetType.SOLAR,
        "pv": AssetType.SOLAR,
        "bess": AssetType.BESS,
        "battery": AssetType.BESS,
        "储能": AssetType.BESS,
        "电池": AssetType.BESS,
        "storage": AssetType.BESS,
        "coal_flex": AssetType.COAL_FLEX,
        "coal-flex": AssetType.COAL_FLEX,
        "coalflex": AssetType.COAL_FLEX,
        "煤电灵活性": AssetType.COAL_FLEX,
        "煤电": AssetType.COAL_FLEX,
        "coal": AssetType.COAL_FLEX,
    }
    
    normalized = asset_mappings.get(asset)
    if not normalized:
        raise ValueError(f"Unsupported asset type: {asset}")
    
    return normalized


def validate_checksum(checksum: str) -> str:
    """Validate SHA256 checksum format."""
    if not checksum:
        raise ValueError("Checksum is required")
    
    checksum = checksum.lower().strip()
    
    # Check length (SHA256 is 64 hex characters)
    if len(checksum) != 64:
        raise ValueError("Checksum must be 64 characters long (SHA256)")
    
    # Check hex format
    if not all(c in "0123456789abcdef" for c in checksum):
        raise ValueError("Checksum must contain only hexadecimal characters")
    
    return checksum


def validate_effective_date(effective_date: date) -> date:
    """Validate effective date constraints."""
    if not effective_date:
        raise ValueError("Effective date is required")
    
    # Check if date is not in the future
    if effective_date > date.today():
        raise ValueError("Effective date cannot be in the future")
    
    # Check if date is not too old (reasonable limit)
    from datetime import timedelta
    min_date = date.today() - timedelta(days=365 * 10)  # 10 years ago
    if effective_date < min_date:
        raise ValueError("Effective date cannot be more than 10 years old")
    
    return effective_date


def validate_url(url: str) -> str:
    """Validate URL format and domain restrictions."""
    if not url:
        raise ValueError("URL is required")
    
    url = url.strip()
    
    # Basic URL format validation
    url_pattern = re.compile(
        r"^https?://"  # http:// or https://
        r"(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|"  # domain...
        r"localhost|"  # localhost...
        r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"  # ...or ip
        r"(?::\d+)?"  # optional port
        r"(?:/?|[/?]\S+)$", re.IGNORECASE
    )
    
    if not url_pattern.match(url):
        raise ValueError("Invalid URL format")
    
    # Check for allowed domains (official sources only)
    allowed_domains = [
        ".gov.cn",
        "gzpec.cn",
        "bjpec.cn", 
        "shandong-electric.com.cn",
        "nmgdl.cn",
        "sc.sgcc.com.cn",
    ]
    
    domain_allowed = any(domain in url.lower() for domain in allowed_domains)
    if not domain_allowed:
        raise ValueError(f"URL domain not in allowlist. Allowed domains: {allowed_domains}")
    
    return url


def validate_chinese_content(text: str, min_chinese_ratio: float = 0.3) -> str:
    """Validate that text contains sufficient Chinese content."""
    if not text:
        raise ValueError("Text content is required")
    
    text = text.strip()
    
    # Count Chinese characters
    chinese_chars = sum(1 for char in text if '\u4e00' <= char <= '\u9fff')
    total_chars = len([c for c in text if c.isalnum()])
    
    if total_chars == 0:
        raise ValueError("Text must contain alphanumeric content")
    
    chinese_ratio = chinese_chars / total_chars
    if chinese_ratio < min_chinese_ratio:
        raise ValueError(f"Text must contain at least {min_chinese_ratio*100}% Chinese characters")
    
    return text


def generate_query_fingerprint(
    province: str,
    asset: str,
    doc_class: str,
    question: str
) -> str:
    """Generate unique fingerprint for query caching and analytics."""
    # Normalize inputs
    province = validate_province(province)
    asset = validate_asset_type(asset)
    doc_class = validate_doc_class(doc_class)
    
    # Normalize question text
    question = question.strip().lower()
    # Remove extra whitespace
    question = re.sub(r'\s+', ' ', question)
    # Remove common punctuation that doesn't affect meaning
    question = re.sub(r'[？?！!。.，,；;：:]', '', question)
    
    # Create fingerprint content
    content = f"{province}:{asset}:{doc_class}:{question}"
    
    # Generate SHA256 hash
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def validate_embedding_vector(embedding: List[float], expected_dim: int = 1536) -> List[float]:
    """Validate embedding vector format and dimensions."""
    if not embedding:
        raise ValueError("Embedding vector is required")
    
    if not isinstance(embedding, list):
        raise ValueError("Embedding must be a list of floats")
    
    if len(embedding) != expected_dim:
        raise ValueError(f"Embedding must have exactly {expected_dim} dimensions")
    
    # Check that all values are valid floats
    try:
        validated = [float(x) for x in embedding]
    except (ValueError, TypeError):
        raise ValueError("All embedding values must be valid numbers")
    
    # Check for reasonable value ranges (typical for normalized embeddings)
    for i, val in enumerate(validated):
        if abs(val) > 10.0:  # Reasonable upper bound
            raise ValueError(f"Embedding value at index {i} is out of reasonable range: {val}")
    
    return validated


def validate_trace_id(trace_id: str) -> str:
    """Validate trace ID format for observability."""
    if not trace_id:
        raise ValueError("Trace ID is required")
    
    trace_id = trace_id.strip()
    
    # Check format (UUID or hex string)
    if len(trace_id) == 36:  # UUID format
        try:
            UUID(trace_id)
        except ValueError:
            raise ValueError("Invalid UUID format for trace ID")
    elif len(trace_id) in [16, 32]:  # Hex string format
        if not all(c in "0123456789abcdef" for c in trace_id.lower()):
            raise ValueError("Trace ID must be valid hexadecimal")
    else:
        raise ValueError("Trace ID must be UUID or 16/32 character hex string")
    
    return trace_id


def validate_query_request(request_data: Dict[str, Any]) -> Dict[str, Any]:
    """Comprehensive validation for query requests."""
    validated = {}
    
    # Required fields
    required_fields = ["province", "asset", "doc_class", "question"]
    for field in required_fields:
        if field not in request_data:
            raise ValueError(f"Missing required field: {field}")
    
    # Validate each field
    validated["province"] = validate_province(request_data["province"])
    validated["asset"] = validate_asset_type(request_data["asset"])
    validated["doc_class"] = validate_doc_class(request_data["doc_class"])
    
    # Validate question
    question = request_data["question"]
    if not isinstance(question, str) or len(question.strip()) < 3:
        raise ValueError("Question must be a non-empty string with at least 3 characters")
    
    validated["question"] = question.strip()
    
    # Optional fields
    if "user_id" in request_data:
        user_id = request_data["user_id"]
        if user_id and (not isinstance(user_id, str) or len(user_id.strip()) == 0):
            raise ValueError("User ID must be a non-empty string if provided")
        validated["user_id"] = user_id.strip() if user_id else None
    
    if "trace_id" in request_data:
        trace_id = request_data["trace_id"]
        if trace_id:
            validated["trace_id"] = validate_trace_id(trace_id)
        else:
            validated["trace_id"] = None
    
    return validated


def validate_citation_metadata(citation_data: Dict[str, Any]) -> Dict[str, Any]:
    """Comprehensive validation for citation metadata."""
    validated = {}
    
    # Required fields
    required_fields = ["title", "url", "checksum", "effective_date", "province", "doc_class"]
    for field in required_fields:
        if field not in citation_data:
            raise ValueError(f"Missing required field: {field}")
    
    # Validate each field
    validated["title"] = citation_data["title"].strip()
    if not validated["title"] or len(validated["title"]) > 500:
        raise ValueError("Title must be non-empty and max 500 characters")
    
    validated["url"] = validate_url(citation_data["url"])
    validated["checksum"] = validate_checksum(citation_data["checksum"])
    
    # Handle date conversion
    effective_date = citation_data["effective_date"]
    if isinstance(effective_date, str):
        try:
            effective_date = datetime.fromisoformat(effective_date).date()
        except ValueError:
            raise ValueError("Invalid date format for effective_date")
    
    validated["effective_date"] = validate_effective_date(effective_date)
    validated["province"] = validate_province(citation_data["province"])
    validated["doc_class"] = validate_doc_class(citation_data["doc_class"])
    
    # Optional asset field
    if "asset" in citation_data and citation_data["asset"]:
        validated["asset"] = validate_asset_type(citation_data["asset"])
    else:
        validated["asset"] = None
    
    return validated


class ValidationError(Exception):
    """Custom exception for validation errors."""
    
    def __init__(self, message: str, field: Optional[str] = None, code: Optional[str] = None):
        self.message = message
        self.field = field
        self.code = code
        super().__init__(message)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        result = {"message": self.message}
        if self.field:
            result["field"] = self.field
        if self.code:
            result["code"] = self.code
        return result


def safe_validate(validator_func, value, field_name: str):
    """Safely run validation with proper error handling."""
    try:
        return validator_func(value)
    except ValueError as e:
        raise ValidationError(str(e), field=field_name, code="validation_error")
    except Exception as e:
        raise ValidationError(f"Unexpected validation error: {str(e)}", field=field_name, code="internal_error")