"""Core domain models and validation for geo-adaptive energy assistant."""

from .models import (
    Province,
    DocumentClass,
    AssetType,
    CitationMetadata,
    CompliancePack,
    QueryRequest,
    QueryResponse,
    RefusalResponse,
)
from .validation import (
    validate_province,
    validate_doc_class,
    validate_asset_type,
    validate_checksum,
    validate_effective_date,
    generate_query_fingerprint,
)
from .utils import (
    generate_uuid,
    calculate_sha256,
    normalize_text,
    extract_effective_date,
)

__all__ = [
    # Models
    "Province",
    "DocumentClass", 
    "AssetType",
    "CitationMetadata",
    "CompliancePack",
    "QueryRequest",
    "QueryResponse",
    "RefusalResponse",
    # Validation
    "validate_province",
    "validate_doc_class",
    "validate_asset_type",
    "validate_checksum",
    "validate_effective_date",
    "generate_query_fingerprint",
    # Utils
    "generate_uuid",
    "calculate_sha256",
    "normalize_text",
    "extract_effective_date",
]