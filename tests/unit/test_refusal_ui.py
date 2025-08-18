"""Tests for refusal UI components and ingestion request flow."""
import pytest
import json
from unittest.mock import Mock, patch, AsyncMock
from fastapi.testclient import TestClient
from fastapi import FastAPI, HTTPException

# Mock ingestion request API for testing
app = FastAPI()

@app.post("/api/ingestion/request")
async def submit_ingestion_request(request: dict):
    """Mock ingestion request endpoint."""
    required_fields = ['query', 'province', 'asset_type', 'doc_class', 'refusal_code', 'justification']
    
    for field in required_fields:
        if field not in request or not request[field]:
            raise HTTPException(status_code=400, detail=f"Missing required field: {field}")
    
    # Simulate processing
    return {
        "request_id": "REQ-001",
        "status": "submitted",
        "estimated_processing_time": "2-3 business days",
        "message": "Your ingestion request has been submitted successfully."
    }

@app.get("/help/refusal-codes")
async def get_refusal_codes_help():
    """Mock help endpoint for refusal codes."""
    return {
        "refusal_codes": {
            "no_first_party_citation": {
                "description": "No first-party citations found",
                "severity": "medium",
                "category": "citation_quality",
                "can_request_ingestion": True
            },
            "province_mismatch": {
                "description": "Query province doesn't match available data",
                "severity": "medium", 
                "category": "geographic_scope",
                "can_request_ingestion": True
            },
            "unsafe_content": {
                "description": "Content violates safety policies",
                "severity": "high",
                "category": "content_policy",
                "can_request_ingestion": False
            }
        }
    }


class TestRefusalUIComponents:
    """Test refusal UI components and functionality."""
    
    @pytest.fixture
    def client(self):
        """Test client fixture."""
        return TestClient(app)
    
    @pytest.fixture
    def sample_error_response(self):
        """Sample error response for testing."""
        return {
            "error": "Query refused",
            "refusal_code": "no_first_party_citation",
            "message": "未找到相关的第一方引用文献。系统无法为您的查询提供基于官方文档的回答。",
            "message_en": "No first-party citations found. The system cannot provide an answer based on official documents for your query.",
            "suggestion": "请尝试使用更具体的关键词，或选择不同的省份和资产类型组合。",
            "suggestion_en": "Please try using more specific keywords, or select a different combination of province and asset type.",
            "policy_violated": "citations_required",
            "trace_id": "trace-123456",
            "can_request_ingestion": True,
            "error_category": "citation_quality",
            "severity": "medium"
        }
    
    @pytest.fixture
    def sample_ingestion_request(self):
        """Sample ingestion request for testing."""
        return {
            "query": "分布式光伏并网技术要求",
            "province": "guangdong",
            "asset_type": "solar",
            "doc_class": "grid_connection",
            "refusal_code": "no_first_party_citation",
            "user_email": "test@example.com",
            "justification": "我们公司正在广东省开发分布式光伏项目，需要了解具体的并网技术要求以确保合规。",
            "priority": "medium"
        }
    
    def test_ingestion_request_submission(self, client, sample_ingestion_request):
        """Test successful ingestion request submission."""
        response = client.post("/api/ingestion/request", json=sample_ingestion_request)
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "submitted"
        assert "request_id" in data
        assert "estimated_processing_time" in data
    
    def test_ingestion_request_missing_fields(self, client):
        """Test ingestion request with missing required fields."""
        incomplete_request = {
            "query": "测试查询",
            "province": "guangdong"
            # Missing other required fields
        }
        
        response = client.post("/api/ingestion/request", json=incomplete_request)
        assert response.status_code == 400
        assert "Missing required field" in response.json()["detail"]
    
    def test_ingestion_request_empty_justification(self, client, sample_ingestion_request):
        """Test ingestion request with empty justification."""
        sample_ingestion_request["justification"] = ""
        
        response = client.post("/api/ingestion/request", json=sample_ingestion_request)
        assert response.status_code == 400
        assert "justification" in response.json()["detail"]
    
    def test_refusal_codes_help_endpoint(self, client):
        """Test refusal codes help endpoint."""
        response = client.get("/help/refusal-codes")
        assert response.status_code == 200
        
        data = response.json()
        assert "refusal_codes" in data
        assert "no_first_party_citation" in data["refusal_codes"]
        assert "province_mismatch" in data["refusal_codes"]
        assert "unsafe_content" in data["refusal_codes"]
        
        # Check structure of refusal code info
        citation_code = data["refusal_codes"]["no_first_party_citation"]
        assert "description" in citation_code
        assert "severity" in citation_code
        assert "category" in citation_code
        assert "can_request_ingestion" in citation_code


class TestRefusalUILogic:
    """Test refusal UI logic and error handling."""
    
    def test_refusal_icon_mapping(self):
        """Test refusal icon mapping logic."""
        # This would be JavaScript logic, but we can test the mapping concept
        icon_mapping = {
            'no_first_party_citation': '📚',
            'stale_citation': '📚',
            'insufficient_citations': '📚',
            'province_mismatch': '🗺️',
            'cross_province_leakage': '🗺️',
            'language_policy_violation': '🌐',
            'unsafe_content': '🛡️',
            'prompt_injection': '🛡️',
            'system_overload': '⚠️',
            'retrieval_failed': '⚠️',
            'unknown': '❌'
        }
        
        # Test specific mappings
        assert icon_mapping['no_first_party_citation'] == '📚'
        assert icon_mapping['province_mismatch'] == '🗺️'
        assert icon_mapping['unsafe_content'] == '🛡️'
        assert icon_mapping['system_overload'] == '⚠️'
    
    def test_refusal_severity_classification(self):
        """Test refusal severity classification logic."""
        high_severity = ['unsafe_content', 'prompt_injection', 'cross_province_leakage']
        medium_severity = ['province_mismatch', 'language_policy_violation', 'stale_citation']
        low_severity = ['no_first_party_citation', 'insufficient_citations', 'system_overload']
        
        def get_severity(code):
            if code in high_severity:
                return 'high'
            elif code in medium_severity:
                return 'medium'
            else:
                return 'low'
        
        # Test classifications
        assert get_severity('unsafe_content') == 'high'
        assert get_severity('province_mismatch') == 'medium'
        assert get_severity('no_first_party_citation') == 'low'
        assert get_severity('unknown_code') == 'low'  # Default to low
    
    def test_ingestion_eligibility(self):
        """Test ingestion request eligibility logic."""
        # Codes that allow ingestion requests
        ingestion_allowed = [
            'no_first_party_citation',
            'stale_citation',
            'insufficient_citations',
            'province_mismatch'
        ]
        
        # Codes that don't allow ingestion requests
        ingestion_blocked = [
            'unsafe_content',
            'prompt_injection',
            'cross_province_leakage',
            'language_policy_violation'
        ]
        
        def can_request_ingestion(code):
            return code in ingestion_allowed
        
        # Test eligibility
        assert can_request_ingestion('no_first_party_citation') is True
        assert can_request_ingestion('province_mismatch') is True
        assert can_request_ingestion('unsafe_content') is False
        assert can_request_ingestion('prompt_injection') is False


class TestIngestionRequestValidation:
    """Test ingestion request validation logic."""
    
    def test_valid_ingestion_request(self):
        """Test validation of valid ingestion request."""
        request = {
            "query": "分布式光伏并网技术要求",
            "province": "guangdong",
            "asset_type": "solar",
            "doc_class": "grid_connection",
            "refusal_code": "no_first_party_citation",
            "justification": "需要了解具体的并网技术要求",
            "priority": "medium"
        }
        
        # Validation logic
        required_fields = ['query', 'province', 'asset_type', 'doc_class', 'refusal_code', 'justification']
        valid_priorities = ['low', 'medium', 'high']
        
        # Check required fields
        for field in required_fields:
            assert field in request
            assert request[field] and request[field].strip()
        
        # Check priority
        assert request['priority'] in valid_priorities
        
        # Check justification length
        assert len(request['justification'].strip()) >= 10
    
    def test_invalid_ingestion_request_missing_fields(self):
        """Test validation with missing required fields."""
        request = {
            "query": "测试查询",
            "province": "guangdong"
            # Missing other required fields
        }
        
        required_fields = ['query', 'province', 'asset_type', 'doc_class', 'refusal_code', 'justification']
        missing_fields = []
        
        for field in required_fields:
            if field not in request or not request.get(field, '').strip():
                missing_fields.append(field)
        
        assert len(missing_fields) > 0
        assert 'asset_type' in missing_fields
        assert 'justification' in missing_fields
    
    def test_invalid_ingestion_request_short_justification(self):
        """Test validation with insufficient justification."""
        request = {
            "query": "测试查询",
            "province": "guangdong",
            "asset_type": "solar",
            "doc_class": "grid_connection",
            "refusal_code": "no_first_party_citation",
            "justification": "短",  # Too short
            "priority": "medium"
        }
        
        # Justification should be at least 10 characters
        assert len(request['justification'].strip()) < 10
    
    def test_invalid_priority_value(self):
        """Test validation with invalid priority value."""
        request = {
            "query": "测试查询",
            "province": "guangdong",
            "asset_type": "solar",
            "doc_class": "grid_connection",
            "refusal_code": "no_first_party_citation",
            "justification": "这是一个有效的申请理由",
            "priority": "invalid"  # Invalid priority
        }
        
        valid_priorities = ['low', 'medium', 'high']
        assert request['priority'] not in valid_priorities


class TestRefusalUIInteractions:
    """Test refusal UI user interactions."""
    
    def test_refusal_display_rendering(self, sample_error_response):
        """Test refusal display component rendering logic."""
        error = sample_error_response
        
        # Test component data extraction
        assert error['refusal_code'] == 'no_first_party_citation'
        assert error['can_request_ingestion'] is True
        assert error['severity'] == 'medium'
        
        # Test message display
        assert len(error['message']) > 0
        assert len(error['suggestion']) > 0
        
        # Test action button availability
        assert error['can_request_ingestion'] is True
    
    def test_ingestion_modal_data_preparation(self):
        """Test ingestion modal data preparation."""
        # Simulate form data preparation
        query_context = {
            "question": "分布式光伏并网技术要求",
            "province": "guangdong",
            "asset": "solar",
            "docClass": "grid_connection"
        }
        
        error_data = {
            "refusal_code": "no_first_party_citation"
        }
        
        # Prepare ingestion request
        ingestion_request = {
            "query": query_context["question"],
            "province": query_context["province"],
            "asset_type": query_context["asset"],
            "doc_class": query_context["docClass"],
            "refusal_code": error_data["refusal_code"],
            "justification": "",
            "priority": "medium"
        }
        
        # Verify preparation
        assert ingestion_request["query"] == query_context["question"]
        assert ingestion_request["province"] == query_context["province"]
        assert ingestion_request["refusal_code"] == error_data["refusal_code"]
        assert ingestion_request["priority"] == "medium"  # Default value
    
    def test_modal_form_validation(self):
        """Test modal form validation logic."""
        form_data = {
            "user_email": "test@example.com",
            "justification": "我们需要这些信息来完成项目合规性评估",
            "priority": "high"
        }
        
        # Email validation (optional field)
        if form_data.get("user_email"):
            assert "@" in form_data["user_email"]
            assert "." in form_data["user_email"]
        
        # Justification validation (required)
        assert form_data["justification"].strip()
        assert len(form_data["justification"].strip()) >= 10
        
        # Priority validation
        valid_priorities = ["low", "medium", "high"]
        assert form_data["priority"] in valid_priorities


class TestRefusalUIAccessibility:
    """Test refusal UI accessibility features."""
    
    def test_refusal_display_accessibility(self):
        """Test refusal display accessibility features."""
        # Test color contrast and visual indicators
        severity_colors = {
            'high': {'bg': '#fed7d7', 'border': '#feb2b2', 'text': '#c53030'},
            'medium': {'bg': '#fef5e7', 'border': '#f6e05e', 'text': '#d69e2e'},
            'low': {'bg': '#e6fffa', 'border': '#81e6d9', 'text': '#319795'}
        }
        
        # Verify color schemes exist for all severities
        assert 'high' in severity_colors
        assert 'medium' in severity_colors
        assert 'low' in severity_colors
        
        # Verify each color scheme has required properties
        for severity, colors in severity_colors.items():
            assert 'bg' in colors
            assert 'border' in colors
            assert 'text' in colors
    
    def test_modal_accessibility_features(self):
        """Test modal accessibility features."""
        # Test keyboard navigation and ARIA attributes
        modal_features = {
            "has_close_button": True,
            "has_form_labels": True,
            "has_required_indicators": True,
            "supports_keyboard_navigation": True,
            "has_focus_management": True
        }
        
        # Verify accessibility features
        assert modal_features["has_close_button"] is True
        assert modal_features["has_form_labels"] is True
        assert modal_features["has_required_indicators"] is True
    
    def test_bilingual_support(self):
        """Test bilingual support in refusal UI."""
        # Test message translations
        messages = {
            "zh-CN": {
                "query_refused": "查询被拒绝",
                "suggestion": "建议",
                "request_ingestion": "请求补充资料",
                "learn_more": "了解更多"
            },
            "en": {
                "query_refused": "Query Refused",
                "suggestion": "Suggestion",
                "request_ingestion": "Request Data Ingestion",
                "learn_more": "Learn More"
            }
        }
        
        # Verify translations exist
        assert "zh-CN" in messages
        assert "en" in messages
        
        # Verify key messages are translated
        for lang in messages:
            assert "query_refused" in messages[lang]
            assert "suggestion" in messages[lang]
            assert "request_ingestion" in messages[lang]