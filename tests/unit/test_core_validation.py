"""Unit tests for core validation utilities."""

import pytest
from datetime import date, timedelta
from uuid import uuid4

from services.core.validation import (
    validate_province,
    validate_doc_class,
    validate_asset_type,
    validate_checksum,
    validate_effective_date,
    validate_url,
    validate_chinese_content,
    generate_query_fingerprint,
    validate_embedding_vector,
    validate_trace_id,
    validate_query_request,
    validate_citation_metadata,
    ValidationError,
    safe_validate,
)
from services.core.models import Province, DocumentClass, AssetType


class TestProvinceValidation:
    """Test province validation functionality."""
    
    def test_valid_provinces(self):
        """Test validation of valid provinces."""
        assert validate_province("guangdong") == Province.GUANGDONG
        assert validate_province("shandong") == Province.SHANDONG
        assert validate_province("inner_mongolia") == Province.INNER_MONGOLIA
        
        # Test Chinese names
        assert validate_province("广东") == Province.GUANGDONG
        assert validate_province("山东") == Province.SHANDONG
        assert validate_province("内蒙古") == Province.INNER_MONGOLIA
        
        # Test abbreviations
        assert validate_province("gd") == Province.GUANGDONG
        assert validate_province("sd") == Province.SHANDONG
        assert validate_province("nm") == Province.INNER_MONGOLIA
    
    def test_invalid_provinces(self):
        """Test validation of invalid provinces."""
        with pytest.raises(ValueError, match="Unsupported province"):
            validate_province("beijing")
        
        with pytest.raises(ValueError, match="Province is required"):
            validate_province("")
        
        with pytest.raises(ValueError, match="Province is required"):
            validate_province(None)
    
    def test_disabled_province(self):
        """Test validation of disabled provinces."""
        with pytest.raises(ValueError, match="not currently enabled"):
            validate_province("sichuan")  # Queued but not enabled
    
    def test_case_insensitive(self):
        """Test case insensitive validation."""
        assert validate_province("GUANGDONG") == Province.GUANGDONG
        assert validate_province("GuangDong") == Province.GUANGDONG
        assert validate_province("  guangdong  ") == Province.GUANGDONG


class TestDocumentClassValidation:
    """Test document class validation functionality."""
    
    def test_valid_doc_classes(self):
        """Test validation of valid document classes."""
        assert validate_doc_class("market_rules") == DocumentClass.MARKET_RULES
        assert validate_doc_class("grid_connection") == DocumentClass.GRID_CONNECTION
        assert validate_doc_class("dispatch_ops") == DocumentClass.DISPATCH_OPS
        
        # Test Chinese names
        assert validate_doc_class("市场规则") == DocumentClass.MARKET_RULES
        assert validate_doc_class("并网接入") == DocumentClass.GRID_CONNECTION
        assert validate_doc_class("调度运行") == DocumentClass.DISPATCH_OPS
        
        # Test variations
        assert validate_doc_class("market-rules") == DocumentClass.MARKET_RULES
        assert validate_doc_class("grid-connection") == DocumentClass.GRID_CONNECTION
        assert validate_doc_class("dispatch-ops") == DocumentClass.DISPATCH_OPS
    
    def test_invalid_doc_classes(self):
        """Test validation of invalid document classes."""
        with pytest.raises(ValueError, match="Unsupported document class"):
            validate_doc_class("invalid_class")
        
        with pytest.raises(ValueError, match="Document class is required"):
            validate_doc_class("")


class TestAssetTypeValidation:
    """Test asset type validation functionality."""
    
    def test_valid_asset_types(self):
        """Test validation of valid asset types."""
        assert validate_asset_type("wind") == AssetType.WIND
        assert validate_asset_type("solar") == AssetType.SOLAR
        assert validate_asset_type("bess") == AssetType.BESS
        assert validate_asset_type("coal_flex") == AssetType.COAL_FLEX
        
        # Test Chinese names
        assert validate_asset_type("风电") == AssetType.WIND
        assert validate_asset_type("光伏") == AssetType.SOLAR
        assert validate_asset_type("储能") == AssetType.BESS
        assert validate_asset_type("煤电灵活性") == AssetType.COAL_FLEX
        
        # Test variations
        assert validate_asset_type("pv") == AssetType.SOLAR
        assert validate_asset_type("battery") == AssetType.BESS
        assert validate_asset_type("coal-flex") == AssetType.COAL_FLEX
    
    def test_invalid_asset_types(self):
        """Test validation of invalid asset types."""
        with pytest.raises(ValueError, match="Unsupported asset type"):
            validate_asset_type("nuclear")
        
        with pytest.raises(ValueError, match="Asset type is required"):
            validate_asset_type("")


class TestChecksumValidation:
    """Test checksum validation functionality."""
    
    def test_valid_checksums(self):
        """Test validation of valid checksums."""
        valid_checksum = "a" * 64
        assert validate_checksum(valid_checksum) == valid_checksum
        
        # Test mixed case
        mixed_case = "A1b2C3d4" + "e" * 56
        assert validate_checksum(mixed_case) == mixed_case.lower()
        
        # Test with spaces (should be stripped)
        with_spaces = "  " + "f" * 64 + "  "
        assert validate_checksum(with_spaces) == "f" * 64
    
    def test_invalid_checksums(self):
        """Test validation of invalid checksums."""
        # Wrong length
        with pytest.raises(ValueError, match="must be 64 characters long"):
            validate_checksum("abc123")
        
        # Invalid characters
        with pytest.raises(ValueError, match="hexadecimal characters"):
            validate_checksum("g" * 64)
        
        # Empty checksum
        with pytest.raises(ValueError, match="Checksum is required"):
            validate_checksum("")


class TestEffectiveDateValidation:
    """Test effective date validation functionality."""
    
    def test_valid_dates(self):
        """Test validation of valid dates."""
        today = date.today()
        yesterday = today - timedelta(days=1)
        
        assert validate_effective_date(today) == today
        assert validate_effective_date(yesterday) == yesterday
        
        # Test older date (within 10 years)
        old_date = today - timedelta(days=365 * 2)
        assert validate_effective_date(old_date) == old_date
    
    def test_invalid_dates(self):
        """Test validation of invalid dates."""
        # Future date
        future_date = date.today() + timedelta(days=1)
        with pytest.raises(ValueError, match="cannot be in the future"):
            validate_effective_date(future_date)
        
        # Too old date
        too_old = date.today() - timedelta(days=365 * 11)
        with pytest.raises(ValueError, match="cannot be more than 10 years old"):
            validate_effective_date(too_old)
        
        # None date
        with pytest.raises(ValueError, match="Effective date is required"):
            validate_effective_date(None)


class TestUrlValidation:
    """Test URL validation functionality."""
    
    def test_valid_urls(self):
        """Test validation of valid URLs."""
        valid_urls = [
            "https://gzpec.cn/rules/solar",
            "http://shandong-electric.com.cn/docs/wind",
            "https://nmgdl.cn/dispatch/coal",
            "https://sc.sgcc.com.cn/grid/connection",
        ]
        
        for url in valid_urls:
            assert validate_url(url) == url
    
    def test_invalid_urls(self):
        """Test validation of invalid URLs."""
        # Invalid format
        with pytest.raises(ValueError, match="Invalid URL format"):
            validate_url("not-a-url")
        
        # Not allowed domain
        with pytest.raises(ValueError, match="URL domain not in allowlist"):
            validate_url("https://example.com/test")
        
        # Empty URL
        with pytest.raises(ValueError, match="URL is required"):
            validate_url("")


class TestChineseContentValidation:
    """Test Chinese content validation functionality."""
    
    def test_valid_chinese_content(self):
        """Test validation of valid Chinese content."""
        chinese_text = "根据广东省相关规定，分布式光伏发电项目需要满足以下条件"
        assert validate_chinese_content(chinese_text) == chinese_text
        
        # Mixed Chinese and English
        mixed_text = "根据规定，solar power projects需要满足条件"
        assert validate_chinese_content(mixed_text) == mixed_text
    
    def test_invalid_chinese_content(self):
        """Test validation of invalid Chinese content."""
        # No Chinese content
        with pytest.raises(ValueError, match="at least.*Chinese characters"):
            validate_chinese_content("This is only English content")
        
        # Empty content
        with pytest.raises(ValueError, match="Text content is required"):
            validate_chinese_content("")
        
        # Insufficient Chinese ratio
        with pytest.raises(ValueError, match="at least.*Chinese characters"):
            validate_chinese_content("Only a few 中文 characters here")


class TestQueryFingerprintGeneration:
    """Test query fingerprint generation."""
    
    def test_fingerprint_generation(self):
        """Test query fingerprint generation."""
        fingerprint = generate_query_fingerprint(
            "guangdong", "solar", "grid_connection", "并网验收需要哪些资料？"
        )
        
        assert isinstance(fingerprint, str)
        assert len(fingerprint) == 64  # SHA256 hex length
        
        # Same inputs should generate same fingerprint
        fingerprint2 = generate_query_fingerprint(
            "guangdong", "solar", "grid_connection", "并网验收需要哪些资料？"
        )
        assert fingerprint == fingerprint2
        
        # Different inputs should generate different fingerprint
        fingerprint3 = generate_query_fingerprint(
            "shandong", "solar", "grid_connection", "并网验收需要哪些资料？"
        )
        assert fingerprint != fingerprint3
    
    def test_fingerprint_normalization(self):
        """Test fingerprint normalization of inputs."""
        # Different case and spacing should generate same fingerprint
        fp1 = generate_query_fingerprint(
            "guangdong", "solar", "grid_connection", "并网验收需要哪些资料？"
        )
        fp2 = generate_query_fingerprint(
            "GUANGDONG", "SOLAR", "GRID_CONNECTION", "  并网验收需要哪些资料？  "
        )
        assert fp1 == fp2
        
        # Punctuation normalization
        fp3 = generate_query_fingerprint(
            "guangdong", "solar", "grid_connection", "并网验收需要哪些资料？！。"
        )
        fp4 = generate_query_fingerprint(
            "guangdong", "solar", "grid_connection", "并网验收需要哪些资料"
        )
        assert fp3 == fp4


class TestEmbeddingVectorValidation:
    """Test embedding vector validation."""
    
    def test_valid_embedding(self):
        """Test validation of valid embedding vectors."""
        valid_embedding = [0.1] * 1536
        result = validate_embedding_vector(valid_embedding)
        assert len(result) == 1536
        assert all(isinstance(x, float) for x in result)
    
    def test_invalid_embedding_dimensions(self):
        """Test validation of invalid embedding dimensions."""
        # Wrong dimension
        with pytest.raises(ValueError, match="exactly 1536 dimensions"):
            validate_embedding_vector([0.1] * 512)
        
        # Empty embedding
        with pytest.raises(ValueError, match="Embedding vector is required"):
            validate_embedding_vector([])
    
    def test_invalid_embedding_values(self):
        """Test validation of invalid embedding values."""
        # Non-numeric values
        with pytest.raises(ValueError, match="valid numbers"):
            validate_embedding_vector(["not_a_number"] * 1536)
        
        # Out of range values
        with pytest.raises(ValueError, match="out of reasonable range"):
            validate_embedding_vector([100.0] * 1536)


class TestTraceIdValidation:
    """Test trace ID validation."""
    
    def test_valid_trace_ids(self):
        """Test validation of valid trace IDs."""
        # UUID format
        uuid_trace = str(uuid4())
        assert validate_trace_id(uuid_trace) == uuid_trace
        
        # 16-char hex
        hex16_trace = "a" * 16
        assert validate_trace_id(hex16_trace) == hex16_trace
        
        # 32-char hex
        hex32_trace = "b" * 32
        assert validate_trace_id(hex32_trace) == hex32_trace
    
    def test_invalid_trace_ids(self):
        """Test validation of invalid trace IDs."""
        # Invalid UUID
        with pytest.raises(ValueError, match="Invalid UUID format"):
            validate_trace_id("not-a-uuid-format-string")
        
        # Invalid hex
        with pytest.raises(ValueError, match="valid hexadecimal"):
            validate_trace_id("g" * 16)
        
        # Wrong length
        with pytest.raises(ValueError, match="UUID or 16/32 character hex"):
            validate_trace_id("abc")


class TestQueryRequestValidation:
    """Test comprehensive query request validation."""
    
    @pytest.fixture
    def valid_request_data(self):
        """Valid request data for testing."""
        return {
            "province": "guangdong",
            "asset": "solar",
            "doc_class": "grid_connection",
            "question": "并网验收需要哪些资料？",
            "user_id": "test_user",
            "trace_id": str(uuid4())
        }
    
    def test_valid_request_validation(self, valid_request_data):
        """Test validation of valid request."""
        result = validate_query_request(valid_request_data)
        
        assert result["province"] == Province.GUANGDONG
        assert result["asset"] == AssetType.SOLAR
        assert result["doc_class"] == DocumentClass.GRID_CONNECTION
        assert result["question"] == "并网验收需要哪些资料？"
        assert result["user_id"] == "test_user"
    
    def test_missing_required_fields(self, valid_request_data):
        """Test validation with missing required fields."""
        for field in ["province", "asset", "doc_class", "question"]:
            invalid_data = valid_request_data.copy()
            del invalid_data[field]
            
            with pytest.raises(ValueError, match=f"Missing required field: {field}"):
                validate_query_request(invalid_data)
    
    def test_invalid_question(self, valid_request_data):
        """Test validation of invalid questions."""
        # Too short
        invalid_data = valid_request_data.copy()
        invalid_data["question"] = "？"
        with pytest.raises(ValueError, match="at least 3 characters"):
            validate_query_request(invalid_data)
        
        # Empty
        invalid_data["question"] = ""
        with pytest.raises(ValueError, match="at least 3 characters"):
            validate_query_request(invalid_data)


class TestCitationMetadataValidation:
    """Test comprehensive citation metadata validation."""
    
    @pytest.fixture
    def valid_citation_data(self):
        """Valid citation data for testing."""
        return {
            "title": "广东省分布式光伏并网管理办法",
            "url": "https://gzpec.cn/rules/solar",
            "checksum": "a" * 64,
            "effective_date": "2025-03-01",
            "province": "guangdong",
            "doc_class": "grid_connection",
            "asset": "solar"
        }
    
    def test_valid_citation_validation(self, valid_citation_data):
        """Test validation of valid citation."""
        result = validate_citation_metadata(valid_citation_data)
        
        assert result["title"] == "广东省分布式光伏并网管理办法"
        assert result["province"] == Province.GUANGDONG
        assert result["doc_class"] == DocumentClass.GRID_CONNECTION
        assert result["asset"] == AssetType.SOLAR
        assert isinstance(result["effective_date"], date)
    
    def test_date_string_conversion(self, valid_citation_data):
        """Test date string to date object conversion."""
        result = validate_citation_metadata(valid_citation_data)
        assert isinstance(result["effective_date"], date)
        assert result["effective_date"] == date(2025, 3, 1)
    
    def test_optional_asset_field(self, valid_citation_data):
        """Test optional asset field handling."""
        # With asset
        result = validate_citation_metadata(valid_citation_data)
        assert result["asset"] == AssetType.SOLAR
        
        # Without asset
        data_without_asset = valid_citation_data.copy()
        del data_without_asset["asset"]
        result = validate_citation_metadata(data_without_asset)
        assert result["asset"] is None


class TestValidationError:
    """Test ValidationError exception."""
    
    def test_validation_error_creation(self):
        """Test ValidationError creation."""
        error = ValidationError("Test error", field="test_field", code="test_code")
        
        assert error.message == "Test error"
        assert error.field == "test_field"
        assert error.code == "test_code"
        assert str(error) == "Test error"
    
    def test_validation_error_to_dict(self):
        """Test ValidationError dictionary conversion."""
        error = ValidationError("Test error", field="test_field", code="test_code")
        error_dict = error.to_dict()
        
        assert error_dict["message"] == "Test error"
        assert error_dict["field"] == "test_field"
        assert error_dict["code"] == "test_code"


class TestSafeValidate:
    """Test safe validation wrapper."""
    
    def test_successful_validation(self):
        """Test successful validation."""
        def dummy_validator(value):
            return value.upper()
        
        result = safe_validate(dummy_validator, "test", "test_field")
        assert result == "TEST"
    
    def test_validation_error_handling(self):
        """Test validation error handling."""
        def failing_validator(value):
            raise ValueError("Validation failed")
        
        with pytest.raises(ValidationError) as exc_info:
            safe_validate(failing_validator, "test", "test_field")
        
        assert exc_info.value.message == "Validation failed"
        assert exc_info.value.field == "test_field"
        assert exc_info.value.code == "validation_error"
    
    def test_unexpected_error_handling(self):
        """Test unexpected error handling."""
        def error_validator(value):
            raise RuntimeError("Unexpected error")
        
        with pytest.raises(ValidationError) as exc_info:
            safe_validate(error_validator, "test", "test_field")
        
        assert "Unexpected validation error" in exc_info.value.message
        assert exc_info.value.field == "test_field"
        assert exc_info.value.code == "internal_error"


if __name__ == "__main__":
    pytest.main([__file__])