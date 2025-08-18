"""Tests for API gateway service (Task 14)."""

import pytest
import json
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime
from fastapi.testclient import TestClient

from services.gateway.api import app
from services.gateway.models import QueryRequest, Province, DocClass, Asset, Language
from services.gateway.orchestrator import QueryOrchestrator


class TestGatewayAPI:
    """Test API gateway endpoints."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.client = TestClient(app)
        
        self.valid_query_request = {
            "question": "广东省光伏电站并网需要什么资料？",
            "province": "guangdong",
            "doc_class": "grid_connection",
            "asset": "solar",
            "lang": "zh-CN",
            "max_citations": 10
        }
        
        self.mock_successful_response = {
            "answer_zh": "**并网要点（广东 / 光伏）**\n- 相关规定：\n  • 光伏项目需要提交技术资料 〔《广东省光伏并网管理办法》，生效：2024-06-01〕",
            "citations": [
                {
                    "citation_id": "cite-guangdong-1",
                    "title": "广东省光伏并网管理办法",
                    "url": "https://example.com/guangdong/rules",
                    "effective_date": "2024-06-01",
                    "score": 0.92,
                    "passage": "光伏项目需要提交技术资料"
                }
            ],
            "sections": 1,
            "total_citations": 1,
            "processing_time_ms": 150,
            "composed_at": "2025-01-14T10:00:00Z",
            "query_context": {
                "province": "guangdong",
                "asset": "solar",
                "doc_class": "grid_connection"
            },
            "trace_id": "gaea-test123"
        }
        
        self.mock_refusal_response = {
            "error": "query_refused",
            "reason": "没有找到相关的官方资料",
            "policy_violated": "no_citations_found",
            "suggestion": "尝试使用更具体的关键词或选择不同的省份/资产类型",
            "trace_id": "gaea-test123",
            "timestamp": "2025-01-14T10:00:00Z"
        }
    
    def test_root_endpoint(self):
        """Test root endpoint returns service information."""
        response = self.client.get("/")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["service"] == "geo-adaptive-energy-assistant-gateway"
        assert data["version"] == "1.0.0"
        assert "endpoints" in data
        assert "features" in data
        assert "pipeline" in data
        assert data["default_language"] == "zh-CN"
    
    def test_health_endpoint(self):
        """Test health check endpoint."""
        response = self.client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "status" in data
        assert "services" in data
        assert "version" in data
        assert "timestamp" in data
        assert data["version"] == "1.0.0"
    
    def test_provinces_endpoint(self):
        """Test provinces endpoint returns supported provinces."""
        response = self.client.get("/provinces")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "provinces" in data
        assert data["total"] == 3
        
        provinces = data["provinces"]
        province_codes = [p["code"] for p in provinces]
        assert "guangdong" in province_codes
        assert "shandong" in province_codes
        assert "inner_mongolia" in province_codes
        
        # Check Chinese labels
        guangdong = next(p for p in provinces if p["code"] == "guangdong")
        assert guangdong["label"] == "广东省"
        assert guangdong["label_en"] == "Guangdong"
    
    def test_assets_endpoint(self):
        """Test assets endpoint returns supported asset types."""
        response = self.client.get("/assets")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "assets" in data
        assert data["total"] == 4
        
        assets = data["assets"]
        asset_codes = [a["code"] for a in assets]
        assert "wind" in asset_codes
        assert "solar" in asset_codes
        assert "bess" in asset_codes
        assert "coal_flex" in asset_codes
        
        # Check Chinese labels
        solar = next(a for a in assets if a["code"] == "solar")
        assert solar["label"] == "光伏"
        assert solar["label_en"] == "Solar Power"
    
    def test_doc_classes_endpoint(self):
        """Test doc_classes endpoint returns supported document classes."""
        response = self.client.get("/doc_classes")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "doc_classes" in data
        assert data["total"] == 3
        
        doc_classes = data["doc_classes"]
        doc_class_codes = [d["code"] for d in doc_classes]
        assert "market_rules" in doc_class_codes
        assert "grid_connection" in doc_class_codes
        assert "dispatch_ops" in doc_class_codes
        
        # Check Chinese labels
        grid_connection = next(d for d in doc_classes if d["code"] == "grid_connection")
        assert grid_connection["label"] == "并网规定"
        assert grid_connection["label_en"] == "Grid Connection"
    
    @patch('services.gateway.orchestrator.get_orchestrator')
    def test_query_endpoint_success(self, mock_get_orchestrator):
        """Test successful query processing."""
        # Mock orchestrator
        mock_orchestrator = Mock()
        mock_orchestrator.process_query = AsyncMock(return_value=self.mock_successful_response)
        mock_get_orchestrator.return_value = mock_orchestrator
        
        response = self.client.post("/query", json=self.valid_query_request)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["answer_zh"].startswith("**并网要点（广东 / 光伏）**")
        assert len(data["citations"]) == 1
        assert data["total_citations"] == 1
        assert data["sections"] == 1
        assert "processing_time_ms" in data
        assert "trace_id" in data
        
        # Verify orchestrator was called correctly
        mock_orchestrator.process_query.assert_called_once()
        call_args = mock_orchestrator.process_query.call_args
        request_arg = call_args[0][0]
        assert request_arg.question == self.valid_query_request["question"]
        assert request_arg.province.value == self.valid_query_request["province"]
    
    @patch('services.gateway.orchestrator.get_orchestrator')
    def test_query_endpoint_refusal(self, mock_get_orchestrator):
        """Test query refusal response."""
        # Mock orchestrator returning refusal
        mock_orchestrator = Mock()
        mock_orchestrator.process_query = AsyncMock(return_value=self.mock_refusal_response)
        mock_get_orchestrator.return_value = mock_orchestrator
        
        response = self.client.post("/query", json=self.valid_query_request)
        
        assert response.status_code == 422
        data = response.json()
        
        assert data["error"] == "query_refused"
        assert data["reason"] == "没有找到相关的官方资料"
        assert data["policy_violated"] == "no_citations_found"
        assert "suggestion" in data
        assert "trace_id" in data
    
    def test_query_endpoint_missing_required_fields(self):
        """Test query endpoint with missing required fields."""
        invalid_request = {
            "question": "测试问题"
            # Missing province and doc_class
        }
        
        response = self.client.post("/query", json=invalid_request)
        
        assert response.status_code == 400
        data = response.json()
        assert "Missing required field" in data["detail"]
    
    def test_query_endpoint_invalid_province(self):
        """Test query endpoint with invalid province."""
        invalid_request = {
            **self.valid_query_request,
            "province": "invalid_province"
        }
        
        response = self.client.post("/query", json=invalid_request)
        
        assert response.status_code == 400
        data = response.json()
        assert "Invalid province" in data["detail"]
        assert "guangdong" in data["detail"]  # Should show allowed values
    
    def test_query_endpoint_invalid_doc_class(self):
        """Test query endpoint with invalid doc_class."""
        invalid_request = {
            **self.valid_query_request,
            "doc_class": "invalid_doc_class"
        }
        
        response = self.client.post("/query", json=invalid_request)
        
        assert response.status_code == 400
        data = response.json()
        assert "Invalid doc_class" in data["detail"]
        assert "market_rules" in data["detail"]  # Should show allowed values
    
    def test_query_endpoint_invalid_asset(self):
        """Test query endpoint with invalid asset."""
        invalid_request = {
            **self.valid_query_request,
            "asset": "invalid_asset"
        }
        
        response = self.client.post("/query", json=invalid_request)
        
        assert response.status_code == 400
        data = response.json()
        assert "Invalid asset" in data["detail"]
        assert "solar" in data["detail"]  # Should show allowed values
    
    def test_query_endpoint_empty_question(self):
        """Test query endpoint with empty question."""
        invalid_request = {
            **self.valid_query_request,
            "question": ""
        }
        
        response = self.client.post("/query", json=invalid_request)
        
        assert response.status_code == 400
        data = response.json()
        assert "Question cannot be empty" in data["detail"]
    
    def test_query_endpoint_question_too_long(self):
        """Test query endpoint with question too long."""
        invalid_request = {
            **self.valid_query_request,
            "question": "很长的问题" * 100  # Over 500 characters
        }
        
        response = self.client.post("/query", json=invalid_request)
        
        assert response.status_code == 400
        data = response.json()
        assert "Question too long" in data["detail"]
    
    def test_query_endpoint_invalid_max_citations(self):
        """Test query endpoint with invalid max_citations."""
        invalid_request = {
            **self.valid_query_request,
            "max_citations": 25  # Over limit of 20
        }
        
        response = self.client.post("/query", json=invalid_request)
        
        assert response.status_code == 400
        data = response.json()
        assert "max_citations must be an integer between 1 and 20" in data["detail"]
    
    def test_query_endpoint_invalid_json(self):
        """Test query endpoint with invalid JSON."""
        response = self.client.post(
            "/query",
            data="invalid json",
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code == 400
        data = response.json()
        assert "Invalid JSON" in data["detail"]
    
    def test_query_endpoint_no_body(self):
        """Test query endpoint with no request body."""
        response = self.client.post("/query")
        
        assert response.status_code == 400
        data = response.json()
        assert "Request body is required" in data["detail"]
    
    @patch('services.gateway.orchestrator.get_orchestrator')
    def test_stats_endpoint(self, mock_get_orchestrator):
        """Test statistics endpoint."""
        # Mock orchestrator stats
        mock_stats = {
            "total_queries": 100,
            "successful_queries": 85,
            "refusal_rate": 0.15,
            "avg_processing_time_ms": 250.5,
            "province_distribution": {"guangdong": 50, "shandong": 30, "inner_mongolia": 20},
            "doc_class_distribution": {"grid_connection": 60, "market_rules": 25, "dispatch_ops": 15},
            "asset_distribution": {"solar": 40, "wind": 35, "bess": 15, "coal_flex": 10},
            "timestamp": "2025-01-14T10:00:00Z"
        }
        
        mock_orchestrator = Mock()
        mock_orchestrator.get_stats.return_value = mock_stats
        mock_get_orchestrator.return_value = mock_orchestrator
        
        response = self.client.get("/stats")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["total_queries"] == 100
        assert data["successful_queries"] == 85
        assert data["refusal_rate"] == 0.15
        assert data["avg_processing_time_ms"] == 250.5
        assert data["province_distribution"]["guangdong"] == 50
        assert data["doc_class_distribution"]["grid_connection"] == 60
        assert data["asset_distribution"]["solar"] == 40
    
    def test_request_headers_added(self):
        """Test that trace ID and processing time headers are added."""
        response = self.client.get("/health")
        
        assert response.status_code == 200
        assert "X-Trace-ID" in response.headers
        assert "X-Processing-Time-MS" in response.headers
        
        # Trace ID should follow format
        trace_id = response.headers["X-Trace-ID"]
        assert trace_id.startswith("gaea-")
        assert len(trace_id) == 17  # "gaea-" + 12 hex chars


class TestGatewayModels:
    """Test gateway request/response models."""
    
    def test_query_request_validation(self):
        """Test query request model validation."""
        # Valid request
        valid_data = {
            "question": "广东省光伏电站并网需要什么资料？",
            "province": "guangdong",
            "doc_class": "grid_connection",
            "asset": "solar",
            "lang": "zh-CN",
            "max_citations": 10
        }
        
        request = QueryRequest(**valid_data)
        assert request.question == valid_data["question"]
        assert request.province == Province.GUANGDONG
        assert request.doc_class == DocClass.GRID_CONNECTION
        assert request.asset == Asset.SOLAR
        assert request.lang == Language.CHINESE
        assert request.max_citations == 10
    
    def test_query_request_defaults(self):
        """Test query request model defaults."""
        minimal_data = {
            "question": "测试问题",
            "province": "shandong",
            "doc_class": "market_rules"
        }
        
        request = QueryRequest(**minimal_data)
        assert request.asset is None
        assert request.lang == Language.CHINESE
        assert request.max_citations == 10
    
    def test_query_request_validation_errors(self):
        """Test query request validation errors."""
        # Empty question
        with pytest.raises(ValueError, match="Question cannot be empty"):
            QueryRequest(
                question="",
                province="guangdong",
                doc_class="grid_connection"
            )
        
        # Whitespace-only question
        with pytest.raises(ValueError, match="Question cannot be empty"):
            QueryRequest(
                question="   ",
                province="guangdong",
                doc_class="grid_connection"
            )
    
    def test_province_enum(self):
        """Test Province enum values."""
        assert Province.GUANGDONG.value == "guangdong"
        assert Province.SHANDONG.value == "shandong"
        assert Province.INNER_MONGOLIA.value == "inner_mongolia"
        
        # Test enum creation from string
        assert Province("guangdong") == Province.GUANGDONG
        
        # Test invalid value
        with pytest.raises(ValueError):
            Province("invalid_province")
    
    def test_asset_enum(self):
        """Test Asset enum values."""
        assert Asset.WIND.value == "wind"
        assert Asset.SOLAR.value == "solar"
        assert Asset.BESS.value == "bess"
        assert Asset.COAL_FLEX.value == "coal_flex"
    
    def test_doc_class_enum(self):
        """Test DocClass enum values."""
        assert DocClass.MARKET_RULES.value == "market_rules"
        assert DocClass.GRID_CONNECTION.value == "grid_connection"
        assert DocClass.DISPATCH_OPS.value == "dispatch_ops"
    
    def test_language_enum(self):
        """Test Language enum values."""
        assert Language.CHINESE.value == "zh-CN"
        assert Language.ENGLISH.value == "en"


class TestGatewayMiddleware:
    """Test gateway middleware functionality."""
    
    def test_request_logging_middleware(self):
        """Test that requests are logged with structured format."""
        with patch('services.gateway.middleware.logger') as mock_logger:
            response = self.client.get("/health")
            
            assert response.status_code == 200
            
            # Check that request and response were logged
            assert mock_logger.info.call_count >= 2
            
            # Check log structure
            log_calls = mock_logger.info.call_args_list
            request_log = json.loads(log_calls[0][0][0])
            
            assert request_log["event"] == "request_received"
            assert "trace_id" in request_log
            assert request_log["method"] == "GET"
            assert request_log["path"] == "/health"
            assert "timestamp" in request_log
    
    def test_validation_middleware_skip_health(self):
        """Test that validation middleware skips health endpoints."""
        # Health endpoint should work without validation
        response = self.client.get("/health")
        assert response.status_code == 200
        
        # Docs endpoints should work without validation
        response = self.client.get("/docs")
        assert response.status_code == 200


if __name__ == "__main__":
    pytest.main([__file__])