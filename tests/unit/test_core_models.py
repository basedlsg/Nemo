"""Unit tests for core domain models."""

import pytest
from datetime import datetime, date, timedelta
from uuid import uuid4, UUID

from pydantic import ValidationError

from services.core.models import (
    Province,
    DocumentClass,
    AssetType,
    RefusalReason,
    CitationMetadata,
    QueryRequest,
    QueryResponse,
    RefusalResponse,
    CompliancePack,
    IngestionRequest,
    EvaluationResult,
    SourceRegistry,
)


class TestProvince:
    """Test Province enum functionality."""
    
    def test_enabled_provinces(self):
        """Test enabled provinces list."""
        enabled = Province.enabled_provinces()
        assert Province.SHANDONG in enabled
        assert Province.GUANGDONG in enabled
        assert Province.INNER_MONGOLIA in enabled
        assert Province.SICHUAN not in enabled  # Queued but not enabled
    
    def test_is_enabled(self):
        """Test province enablement check."""
        assert Province.is_enabled(Province.SHANDONG) is True
        assert Province.is_enabled(Province.GUANGDONG) is True
        assert Province.is_enabled(Province.INNER_MONGOLIA) is True
        assert Province.is_enabled(Province.SICHUAN) is False
    
    def test_display_name_zh(self):
        """Test Chinese display names."""
        assert Province.SHANDONG.display_name_zh() == "山东"
        assert Province.GUANGDONG.display_name_zh() == "广东"
        assert Province.INNER_MONGOLIA.display_name_zh() == "内蒙古"
        assert Province.SICHUAN.display_name_zh() == "四川"


class TestDocumentClass:
    """Test DocumentClass enum functionality."""
    
    def test_display_name_zh(self):
        """Test Chinese display names."""
        assert DocumentClass.MARKET_RULES.display_name_zh() == "市场规则"
        assert DocumentClass.GRID_CONNECTION.display_name_zh() == "并网接入"
        assert DocumentClass.DISPATCH_OPS.display_name_zh() == "调度运行"


class TestAssetType:
    """Test AssetType enum functionality."""
    
    def test_display_name_zh(self):
        """Test Chinese display names."""
        assert AssetType.WIND.display_name_zh() == "风电"
        assert AssetType.SOLAR.display_name_zh() == "光伏"
        assert AssetType.BESS.display_name_zh() == "储能"
        assert AssetType.COAL_FLEX.display_name_zh() == "煤电灵活性"


class TestRefusalReason:
    """Test RefusalReason enum functionality."""
    
    def test_message_zh(self):
        """Test Chinese refusal messages."""
        assert RefusalReason.NO_FIRST_PARTY_CITATION.message_zh() == "未找到官方一手引用文件"
        assert RefusalReason.STALE_CITATION.message_zh() == "仅找到已过期的引用文件"
        assert RefusalReason.PROVINCE_MISMATCH.message_zh() == "查询省份不在支持范围内"
        assert RefusalReason.UNSUPPORTED_DOC_CLASS.message_zh() == "该省份不支持此文档类别"


class TestCitationMetadata:
    """Test CitationMetadata model."""
    
    @pytest.fixture
    def valid_citation_data(self):
        """Valid citation data for testing."""
        return {
            "citation_id": uuid4(),
            "title": "广东省分布式光伏并网管理办法",
            "url": "https://gzpec.cn/rules/solar-grid-connection",
            "checksum": "a" * 64,  # Valid SHA256 length
            "effective_date": date(2025, 3, 1),
            "province": Province.GUANGDONG,
            "doc_class": DocumentClass.GRID_CONNECTION,
            "asset": AssetType.SOLAR
        }
    
    def test_valid_citation_creation(self, valid_citation_data):
        """Test creating valid citation metadata."""
        citation = CitationMetadata(**valid_citation_data)
        
        assert citation.province == Province.GUANGDONG
        assert citation.doc_class == DocumentClass.GRID_CONNECTION
        assert citation.asset == AssetType.SOLAR
        assert citation.title == "广东省分布式光伏并网管理办法"
        assert len(citation.checksum) == 64
    
    def test_checksum_validation(self, valid_citation_data):
        """Test checksum format validation."""
        # Valid checksum
        citation = CitationMetadata(**valid_citation_data)
        assert citation.checksum == "a" * 64
        
        # Invalid checksum length
        with pytest.raises(ValidationError):
            invalid_data = valid_citation_data.copy()
            invalid_data["checksum"] = "abc123"
            CitationMetadata(**invalid_data)
        
        # Invalid checksum characters
        with pytest.raises(ValidationError):
            invalid_data = valid_citation_data.copy()
            invalid_data["checksum"] = "g" * 64  # 'g' is not hex
            CitationMetadata(**invalid_data)
    
    def test_effective_date_validation(self, valid_citation_data):
        """Test effective date validation."""
        # Future date should fail
        with pytest.raises(ValidationError):
            invalid_data = valid_citation_data.copy()
            invalid_data["effective_date"] = date.today() + timedelta(days=1)
            CitationMetadata(**invalid_data)
        
        # Past date should work
        valid_data = valid_citation_data.copy()
        valid_data["effective_date"] = date.today() - timedelta(days=30)
        citation = CitationMetadata(**valid_data)
        assert citation.effective_date < date.today()
    
    def test_optional_asset(self, valid_citation_data):
        """Test optional asset field."""
        # With asset
        citation = CitationMetadata(**valid_citation_data)
        assert citation.asset == AssetType.SOLAR
        
        # Without asset
        data_without_asset = valid_citation_data.copy()
        del data_without_asset["asset"]
        citation = CitationMetadata(**data_without_asset)
        assert citation.asset is None


class TestQueryRequest:
    """Test QueryRequest model."""
    
    @pytest.fixture
    def valid_query_data(self):
        """Valid query data for testing."""
        return {
            "province": Province.GUANGDONG,
            "asset": AssetType.SOLAR,
            "doc_class": DocumentClass.GRID_CONNECTION,
            "question": "并网验收需要哪些资料？",
            "user_id": "test_user",
            "trace_id": str(uuid4())
        }
    
    def test_valid_query_creation(self, valid_query_data):
        """Test creating valid query request."""
        query = QueryRequest(**valid_query_data)
        
        assert query.province == Province.GUANGDONG
        assert query.asset == AssetType.SOLAR
        assert query.doc_class == DocumentClass.GRID_CONNECTION
        assert query.question == "并网验收需要哪些资料？"
    
    def test_question_validation(self, valid_query_data):
        """Test question content validation."""
        # Valid question
        query = QueryRequest(**valid_query_data)
        assert len(query.question) > 3
        
        # Too short question
        with pytest.raises(ValidationError):
            invalid_data = valid_query_data.copy()
            invalid_data["question"] = "？"
            QueryRequest(**invalid_data)
        
        # Empty question
        with pytest.raises(ValidationError):
            invalid_data = valid_query_data.copy()
            invalid_data["question"] = ""
            QueryRequest(**invalid_data)
    
    def test_province_enabled_validation(self, valid_query_data):
        """Test province enablement validation."""
        # Enabled province should work
        query = QueryRequest(**valid_query_data)
        assert query.province in Province.enabled_provinces()
        
        # Disabled province should fail
        with pytest.raises(ValidationError):
            invalid_data = valid_query_data.copy()
            invalid_data["province"] = Province.SICHUAN  # Not enabled
            QueryRequest(**invalid_data)
    
    def test_generate_fingerprint(self, valid_query_data):
        """Test query fingerprint generation."""
        query = QueryRequest(**valid_query_data)
        fingerprint = query.generate_fingerprint()
        
        assert isinstance(fingerprint, str)
        assert len(fingerprint) == 64  # SHA256 hex length
        
        # Same query should generate same fingerprint
        query2 = QueryRequest(**valid_query_data)
        assert query.generate_fingerprint() == query2.generate_fingerprint()
        
        # Different question should generate different fingerprint
        different_data = valid_query_data.copy()
        different_data["question"] = "不同的问题"
        query3 = QueryRequest(**different_data)
        assert query.generate_fingerprint() != query3.generate_fingerprint()


class TestQueryResponse:
    """Test QueryResponse model."""
    
    @pytest.fixture
    def valid_response_data(self):
        """Valid response data for testing."""
        return {
            "answer_zh": "根据广东省相关规定，分布式光伏并网验收需要以下资料：1. 项目备案文件...",
            "citations": [
                CitationMetadata(
                    citation_id=uuid4(),
                    title="广东省分布式光伏并网管理办法",
                    url="https://gzpec.cn/rules/solar",
                    checksum="a" * 64,
                    effective_date=date(2025, 3, 1),
                    province=Province.GUANGDONG,
                    doc_class=DocumentClass.GRID_CONNECTION,
                    asset=AssetType.SOLAR
                )
            ],
            "pack_id": uuid4(),
            "latency_ms": 850
        }
    
    def test_valid_response_creation(self, valid_response_data):
        """Test creating valid query response."""
        response = QueryResponse(**valid_response_data)
        
        assert "根据广东省相关规定" in response.answer_zh
        assert len(response.citations) == 1
        assert response.latency_ms == 850
        assert isinstance(response.generated_at, datetime)
    
    def test_chinese_content_validation(self, valid_response_data):
        """Test Chinese content validation."""
        # Valid Chinese content
        response = QueryResponse(**valid_response_data)
        assert any('\u4e00' <= char <= '\u9fff' for char in response.answer_zh)
        
        # No Chinese content should fail
        with pytest.raises(ValidationError):
            invalid_data = valid_response_data.copy()
            invalid_data["answer_zh"] = "This is only English content"
            QueryResponse(**invalid_data)
    
    def test_citations_required(self, valid_response_data):
        """Test that citations are required."""
        # Valid with citations
        response = QueryResponse(**valid_response_data)
        assert len(response.citations) > 0
        
        # Empty citations should fail
        with pytest.raises(ValidationError):
            invalid_data = valid_response_data.copy()
            invalid_data["citations"] = []
            QueryResponse(**invalid_data)


class TestRefusalResponse:
    """Test RefusalResponse model."""
    
    def test_valid_refusal_creation(self):
        """Test creating valid refusal response."""
        refusal = RefusalResponse(
            reason=RefusalReason.NO_FIRST_PARTY_CITATION,
            ingestion_request_id=uuid4()
        )
        
        assert refusal.status == "refused"
        assert refusal.reason == RefusalReason.NO_FIRST_PARTY_CITATION
        assert refusal.policy == "first_party_citation_required"
        assert refusal.message_zh == "未找到官方一手引用文件"
        assert isinstance(refusal.generated_at, datetime)
    
    def test_chinese_message_auto_generation(self):
        """Test automatic Chinese message generation."""
        refusal = RefusalResponse(reason=RefusalReason.STALE_CITATION)
        assert refusal.message_zh == "仅找到已过期的引用文件"
        
        # Custom message should override
        custom_refusal = RefusalResponse(
            reason=RefusalReason.STALE_CITATION,
            message_zh="自定义拒答消息"
        )
        assert custom_refusal.message_zh == "自定义拒答消息"


class TestCompliancePack:
    """Test CompliancePack model."""
    
    @pytest.fixture
    def valid_pack_data(self):
        """Valid pack data for testing."""
        return {
            "province": Province.GUANGDONG,
            "asset": AssetType.SOLAR,
            "doc_class": DocumentClass.GRID_CONNECTION,
            "query_fingerprint": "a" * 64,
            "answer_zh": "根据相关规定...",
            "citations": [
                CitationMetadata(
                    citation_id=uuid4(),
                    title="测试文档",
                    url="https://gzpec.cn/test",
                    checksum="b" * 64,
                    effective_date=date.today(),
                    province=Province.GUANGDONG,
                    doc_class=DocumentClass.GRID_CONNECTION
                )
            ]
        }
    
    def test_valid_pack_creation(self, valid_pack_data):
        """Test creating valid compliance pack."""
        pack = CompliancePack(**valid_pack_data)
        
        assert pack.province == Province.GUANGDONG
        assert pack.asset == AssetType.SOLAR
        assert pack.pack_status == "generated"
        assert isinstance(pack.pack_id, UUID)
        assert pack.expires_at is not None
    
    def test_expiration_auto_set(self, valid_pack_data):
        """Test automatic expiration setting."""
        pack = CompliancePack(**valid_pack_data)
        
        # Should be set to 7 days from generation
        expected_expiry = pack.generated_at + timedelta(days=7)
        assert abs((pack.expires_at - expected_expiry).total_seconds()) < 60  # Within 1 minute
    
    def test_is_expired(self, valid_pack_data):
        """Test expiration checking."""
        # Fresh pack should not be expired
        pack = CompliancePack(**valid_pack_data)
        assert pack.is_expired() is False
        
        # Manually set expired pack
        pack.expires_at = datetime.utcnow() - timedelta(hours=1)
        assert pack.is_expired() is True
    
    def test_pdf_metadata_generation(self, valid_pack_data):
        """Test PDF metadata generation."""
        pack = CompliancePack(**valid_pack_data)
        metadata = pack.to_pdf_metadata()
        
        assert "广东" in metadata["title"]
        assert "并网接入" in metadata["title"]
        assert "光伏" in metadata["subject"]
        assert metadata["author"] == "地域自适应能源助手"
        assert "合规" in metadata["keywords"]


class TestEvaluationResult:
    """Test EvaluationResult model."""
    
    @pytest.fixture
    def valid_evaluation_data(self):
        """Valid evaluation data for testing."""
        return {
            "province": Province.GUANGDONG,
            "doc_class": DocumentClass.GRID_CONNECTION,
            "groundedness_score": 0.92,
            "citation_precision": 0.96,
            "refusal_accuracy": 0.99,
            "avg_latency_ms": 850,
            "p95_latency_ms": 1200,
            "total_queries": 100,
            "passed_queries": 92,
            "refused_queries": 8
        }
    
    def test_valid_evaluation_creation(self, valid_evaluation_data):
        """Test creating valid evaluation result."""
        evaluation = EvaluationResult(**valid_evaluation_data)
        
        assert evaluation.province == Province.GUANGDONG
        assert evaluation.groundedness_score == 0.92
        assert evaluation.citation_precision == 0.96
        assert evaluation.refusal_accuracy == 0.99
    
    def test_score_validation(self, valid_evaluation_data):
        """Test score range validation."""
        # Valid scores (0.0 to 1.0)
        evaluation = EvaluationResult(**valid_evaluation_data)
        assert 0.0 <= evaluation.groundedness_score <= 1.0
        
        # Invalid score > 1.0
        with pytest.raises(ValidationError):
            invalid_data = valid_evaluation_data.copy()
            invalid_data["groundedness_score"] = 1.5
            EvaluationResult(**invalid_data)
        
        # Invalid score < 0.0
        with pytest.raises(ValidationError):
            invalid_data = valid_evaluation_data.copy()
            invalid_data["citation_precision"] = -0.1
            EvaluationResult(**invalid_data)
    
    def test_meets_quality_thresholds(self, valid_evaluation_data):
        """Test quality threshold checking."""
        # Meets default thresholds
        evaluation = EvaluationResult(**valid_evaluation_data)
        assert evaluation.meets_quality_thresholds() is True
        
        # Doesn't meet groundedness threshold
        low_groundedness_data = valid_evaluation_data.copy()
        low_groundedness_data["groundedness_score"] = 0.85
        evaluation = EvaluationResult(**low_groundedness_data)
        assert evaluation.meets_quality_thresholds() is False
        
        # Custom thresholds
        assert evaluation.meets_quality_thresholds(min_groundedness=0.8) is True
    
    def test_readiness_status(self, valid_evaluation_data):
        """Test readiness status determination."""
        # Ready status
        evaluation = EvaluationResult(**valid_evaluation_data)
        assert evaluation.get_readiness_status() == "ready"
        
        # Needs improvement
        low_score_data = valid_evaluation_data.copy()
        low_score_data["groundedness_score"] = 0.85
        evaluation = EvaluationResult(**low_score_data)
        assert evaluation.get_readiness_status() == "needs_improvement"
        
        # Not evaluated
        no_scores_data = {
            "province": Province.GUANGDONG,
            "doc_class": DocumentClass.GRID_CONNECTION,
            "total_queries": 0
        }
        evaluation = EvaluationResult(**no_scores_data)
        assert evaluation.get_readiness_status() == "not_evaluated"


if __name__ == "__main__":
    pytest.main([__file__])