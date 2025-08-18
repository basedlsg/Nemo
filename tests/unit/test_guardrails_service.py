"""Tests for guardrails service (Task 12)."""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime

from services.guardrails.policy_engine import (
    GuardrailsEngine, RefusalException, RefusalReason,
    CitationsRequiredPolicy, ChineseFirstPolicy, UnsafeScopePolicy,
    guardrails_check, get_guardrails_engine
)


class TestRefusalException:
    """Test refusal exception functionality."""
    
    def test_refusal_exception_creation(self):
        """Test refusal exception creation."""
        exception = RefusalException(
            RefusalReason.NO_FIRST_PARTY_CITATION,
            "No citations available",
            "first_party_citation_required"
        )
        
        assert exception.reason == RefusalReason.NO_FIRST_PARTY_CITATION
        assert exception.message == "No citations available"
        assert exception.policy == "first_party_citation_required"
    
    def test_refusal_exception_to_dict(self):
        """Test refusal exception dictionary conversion."""
        exception = RefusalException(
            RefusalReason.STALE_CITATION,
            "Citation is stale",
            "current_citation_required"
        )
        
        result = exception.to_dict()
        
        assert result["status"] == "refused"
        assert result["reason"] == "stale_citation"
        assert result["message"] == "Citation is stale"
        assert result["policy"] == "current_citation_required"
        assert "timestamp" in result


class TestCitationsRequiredPolicy:
    """Test citations required policy."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.policy = CitationsRequiredPolicy()
        self.valid_citations = [
            {
                "citation_id": "cite-1",
                "checksum": "abc123",
                "effective_date": "2025-01-01",
                "title": "Test Citation"
            }
        ]
    
    def test_policy_name_and_description(self):
        """Test policy metadata."""
        assert self.policy.name == "citations_required"
        assert "first-party citation" in self.policy.description
    
    def test_check_valid_citations(self):
        """Test policy with valid citations."""
        result = self.policy.check("answer", self.valid_citations, {})
        assert result is True
    
    def test_check_no_citations(self):
        """Test policy with no citations."""
        with pytest.raises(RefusalException) as exc_info:
            self.policy.check("answer", [], {})
        
        assert exc_info.value.reason == RefusalReason.NO_FIRST_PARTY_CITATION
        assert exc_info.value.policy == "first_party_citation_required"
    
    def test_check_missing_checksum(self):
        """Test policy with citation missing checksum."""
        invalid_citations = [
            {
                "citation_id": "cite-1",
                "effective_date": "2025-01-01",
                "title": "Test Citation"
                # Missing checksum
            }
        ]
        
        with pytest.raises(RefusalException) as exc_info:
            self.policy.check("answer", invalid_citations, {})
        
        assert exc_info.value.reason == RefusalReason.STALE_CITATION
        assert exc_info.value.policy == "citation_integrity_required"
    
    def test_check_missing_effective_date(self):
        """Test policy with citation missing effective date."""
        invalid_citations = [
            {
                "citation_id": "cite-1",
                "checksum": "abc123",
                "title": "Test Citation"
                # Missing effective_date
            }
        ]
        
        with pytest.raises(RefusalException) as exc_info:
            self.policy.check("answer", invalid_citations, {})
        
        assert exc_info.value.reason == RefusalReason.MISSING_EFFECTIVE_DATE
        assert exc_info.value.policy == "effective_date_required"


class TestChineseFirstPolicy:
    """Test Chinese-first policy."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.policy = ChineseFirstPolicy()
    
    def test_policy_name_and_description(self):
        """Test policy metadata."""
        assert self.policy.name == "zh_first"
        assert "Chinese" in self.policy.description
    
    def test_contains_chinese_with_chinese_text(self):
        """Test Chinese character detection with Chinese text."""
        assert self.policy._contains_chinese("这是中文") is True
        assert self.policy._contains_chinese("Hello 世界") is True
    
    def test_contains_chinese_with_english_text(self):
        """Test Chinese character detection with English text."""
        assert self.policy._contains_chinese("Hello World") is False
        assert self.policy._contains_chinese("123 ABC") is False
    
    def test_contains_chinese_with_empty_text(self):
        """Test Chinese character detection with empty text."""
        assert self.policy._contains_chinese("") is False
        assert self.policy._contains_chinese(None) is False
    
    def test_check_chinese_answer_zh_request(self):
        """Test policy with Chinese answer and Chinese request."""
        result = self.policy.check("这是中文回答", [], {"lang": "zh"})
        assert result is True
    
    def test_check_english_answer_zh_request(self):
        """Test policy with English answer and Chinese request (warning only)."""
        # This should pass but log a warning (not a hard refusal for MVP)
        result = self.policy.check("This is English", [], {"lang": "zh"})
        assert result is True
    
    def test_check_english_answer_en_request(self):
        """Test policy with English answer and English request."""
        result = self.policy.check("This is English", [], {"lang": "en"})
        assert result is True
    
    def test_check_default_language(self):
        """Test policy with default language (should be Chinese)."""
        result = self.policy.check("这是中文回答", [], {})
        assert result is True


class TestUnsafeScopePolicy:
    """Test unsafe scope policy."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.policy = UnsafeScopePolicy()
        self.valid_query = {
            "province": "guangdong",
            "doc_class": "grid_connection"
        }
        self.valid_citations = [
            {
                "citation_id": "cite-1",
                "url": "https://gzpec.cn/rules",
                "title": "Test Citation"
            }
        ]
    
    def test_policy_name_and_description(self):
        """Test policy metadata."""
        assert self.policy.name == "unsafe_scope"
        assert "safe" in self.policy.description
    
    def test_extract_domain_from_url(self):
        """Test domain extraction from URLs."""
        assert self.policy._extract_domain_from_url("https://gzpec.cn/rules") == "gzpec.cn"
        assert self.policy._extract_domain_from_url("https://www.gzpec.cn/path") == "www.gzpec.cn"
        assert self.policy._extract_domain_from_url("invalid-url") == ""
    
    def test_is_domain_allowed_foundation_domains(self):
        """Test domain allowlist checking with foundation domains."""
        assert self.policy._is_domain_allowed("gzpec.cn") is True
        assert self.policy._is_domain_allowed("sdpxc.cn") is True
        assert self.policy._is_domain_allowed("impex.org.cn") is True
        assert self.policy._is_domain_allowed("example.com") is False
    
    def test_is_domain_allowed_subdomains(self):
        """Test domain allowlist checking with subdomains."""
        assert self.policy._is_domain_allowed("www.gzpec.cn") is True
        assert self.policy._is_domain_allowed("api.gzpec.cn") is True
    
    def test_check_valid_province(self):
        """Test policy with valid province."""
        result = self.policy.check("answer", self.valid_citations, self.valid_query)
        assert result is True
    
    def test_check_invalid_province(self):
        """Test policy with invalid province."""
        invalid_query = {"province": "invalid_province", "doc_class": "grid_connection"}
        
        with pytest.raises(RefusalException) as exc_info:
            self.policy.check("answer", self.valid_citations, invalid_query)
        
        assert exc_info.value.reason == RefusalReason.PROVINCE_MISMATCH
        assert exc_info.value.policy == "supported_province_required"
    
    def test_check_invalid_doc_class(self):
        """Test policy with invalid doc_class."""
        invalid_query = {"province": "guangdong", "doc_class": "invalid_class"}
        
        with pytest.raises(RefusalException) as exc_info:
            self.policy.check("answer", self.valid_citations, invalid_query)
        
        assert exc_info.value.reason == RefusalReason.DOC_CLASS_MISMATCH
        assert exc_info.value.policy == "supported_doc_class_required"
    
    def test_check_unauthorized_domain(self):
        """Test policy with citation from unauthorized domain."""
        unauthorized_citations = [
            {
                "citation_id": "cite-1",
                "url": "https://unauthorized.com/rules",
                "title": "Unauthorized Citation"
            }
        ]
        
        with pytest.raises(RefusalException) as exc_info:
            self.policy.check("answer", unauthorized_citations, self.valid_query)
        
        assert exc_info.value.reason == RefusalReason.DOMAIN_NOT_ALLOWED
        assert exc_info.value.policy == "authorized_domain_required"
    
    def test_check_superseded_citation(self):
        """Test policy with superseded citation."""
        superseded_citations = [
            {
                "citation_id": "cite-1",
                "url": "https://gzpec.cn/rules",
                "title": "Superseded Citation",
                "superseded_by": "cite-2"
            }
        ]
        
        with pytest.raises(RefusalException) as exc_info:
            self.policy.check("answer", superseded_citations, self.valid_query)
        
        assert exc_info.value.reason == RefusalReason.SUPERSEDED_CITATION
        assert exc_info.value.policy == "current_regulation_required"


class TestGuardrailsEngine:
    """Test guardrails engine functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.engine = GuardrailsEngine()
        self.valid_answer = "根据广东省光伏并网管理办法，需要提交以下资料..."
        self.valid_citations = [
            {
                "citation_id": "cite-1",
                "url": "https://gzpec.cn/solar-rules",
                "title": "广东省光伏并网管理办法",
                "effective_date": "2025-01-01",
                "checksum": "abc123"
            }
        ]
        self.valid_query = {
            "province": "guangdong",
            "doc_class": "grid_connection",
            "question": "光伏并网需要什么资料？"
        }
    
    def test_engine_initialization(self):
        """Test engine initialization."""
        assert len(self.engine.policies) == 3
        assert self.engine.stats["total_checks"] == 0
        assert self.engine.stats["passed_checks"] == 0
        assert self.engine.stats["refused_checks"] == 0
    
    def test_check_all_policies_success(self):
        """Test successful policy check."""
        result = self.engine.check_all_policies(
            self.valid_answer, self.valid_citations, self.valid_query
        )
        
        assert result is True
        assert self.engine.stats["total_checks"] == 1
        assert self.engine.stats["passed_checks"] == 1
        assert self.engine.stats["refused_checks"] == 0
    
    def test_check_all_policies_refusal(self):
        """Test policy check with refusal."""
        # Test with no citations (should trigger CitationsRequiredPolicy)
        with pytest.raises(RefusalException) as exc_info:
            self.engine.check_all_policies(self.valid_answer, [], self.valid_query)
        
        assert exc_info.value.reason == RefusalReason.NO_FIRST_PARTY_CITATION
        assert self.engine.stats["total_checks"] == 1
        assert self.engine.stats["passed_checks"] == 0
        assert self.engine.stats["refused_checks"] == 1
        assert self.engine.stats["refusal_reasons"]["no_first_party_citation"] == 1
    
    def test_get_policy_info(self):
        """Test policy information retrieval."""
        policy_info = self.engine.get_policy_info()
        
        assert len(policy_info) == 3
        assert all("name" in policy and "description" in policy for policy in policy_info)
        
        policy_names = [policy["name"] for policy in policy_info]
        assert "citations_required" in policy_names
        assert "zh_first" in policy_names
        assert "unsafe_scope" in policy_names
    
    def test_get_statistics(self):
        """Test statistics retrieval."""
        # Run a successful check first
        self.engine.check_all_policies(
            self.valid_answer, self.valid_citations, self.valid_query
        )
        
        stats = self.engine.get_statistics()
        
        assert stats["total_checks"] == 1
        assert stats["passed_checks"] == 1
        assert stats["refused_checks"] == 0
        assert stats["pass_rate"] == 1.0
        assert stats["refusal_rate"] == 0.0
        assert stats["refusal_accuracy"] == 0.0
        assert "policies" in stats
        assert "last_check" in stats
    
    @patch('services.guardrails.policy_engine.SimpleRegistryLoader')
    @patch('services.guardrails.policy_engine.get_foundation_allowlist')
    def test_health_check_healthy(self, mock_allowlist, mock_loader_class):
        """Test healthy engine health check."""
        mock_allowlist.return_value = {"gzpec.cn", "sdpxc.cn", "impex.org.cn"}
        
        mock_loader = Mock()
        mock_loader.validate_registry_file.return_value = {"file_valid": True}
        mock_loader_class.return_value = mock_loader
        
        health = self.engine.health_check()
        
        assert health["status"] == "healthy"
        assert health["policy_count"] == 3
        assert health["registry_status"] == "healthy"
        assert health["foundation_allowlist_size"] == 3
        assert "statistics" in health
    
    @patch('services.guardrails.policy_engine.SimpleRegistryLoader')
    def test_health_check_unhealthy(self, mock_loader_class):
        """Test unhealthy engine health check."""
        mock_loader_class.side_effect = Exception("Registry error")
        
        health = self.engine.health_check()
        
        assert health["status"] == "unhealthy"
        assert "error" in health


class TestGuardrailsGlobal:
    """Test global guardrails functions."""
    
    def test_get_guardrails_engine_singleton(self):
        """Test that get_guardrails_engine returns singleton instance."""
        # Clear any existing instance
        import services.guardrails.policy_engine
        services.guardrails.policy_engine._guardrails_engine = None
        
        engine1 = get_guardrails_engine()
        engine2 = get_guardrails_engine()
        
        assert engine1 is engine2
        assert isinstance(engine1, GuardrailsEngine)
    
    def test_guardrails_check_convenience_function(self):
        """Test convenience function for guardrails checking."""
        valid_answer = "根据广东省光伏并网管理办法..."
        valid_citations = [
            {
                "citation_id": "cite-1",
                "url": "https://gzpec.cn/rules",
                "effective_date": "2025-01-01",
                "checksum": "abc123"
            }
        ]
        valid_query = {
            "province": "guangdong",
            "doc_class": "grid_connection"
        }
        
        result = guardrails_check(valid_answer, valid_citations, valid_query)
        assert result is True


if __name__ == "__main__":
    pytest.main([__file__])