"""Tests for registry foundation components (Task 4)."""

import pytest
from unittest.mock import Mock, patch, mock_open
import yaml

from services.registry.simple_loader import SimpleRegistryLoader, load_and_validate_registry
from services.registry.robots_checker import (
    host_allowed, respects_robots, validate_domain_allowlist, 
    get_foundation_allowlist, validate_foundation_domains
)


class TestRobotsChecker:
    """Test robots.txt validation functionality."""
    
    def test_host_allowed_exact_match(self):
        """Test exact domain match in allowlist."""
        allowlist = {"gzpec.cn", "sdpxc.cn"}
        
        assert host_allowed("https://gzpec.cn/page", allowlist) is True
        assert host_allowed("https://sdpxc.cn/doc.pdf", allowlist) is True
        assert host_allowed("https://example.com/page", allowlist) is False
    
    def test_host_allowed_subdomain_match(self):
        """Test subdomain matching in allowlist."""
        allowlist = {"example.com"}
        
        assert host_allowed("https://www.example.com/page", allowlist) is True
        assert host_allowed("https://api.example.com/data", allowlist) is True
        assert host_allowed("https://notexample.com/page", allowlist) is False
    
    def test_host_allowed_invalid_url(self):
        """Test handling of invalid URLs."""
        allowlist = {"gzpec.cn"}
        
        assert host_allowed("not-a-url", allowlist) is False
        assert host_allowed("", allowlist) is False
    
    @patch('services.registry.robots_checker.requests.get')
    def test_respects_robots_allows_crawling(self, mock_get):
        """Test robots.txt that allows crawling."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "User-agent: *\nAllow: /"
        mock_get.return_value = mock_response
        
        result = respects_robots("gzpec.cn")
        
        assert result is True
        mock_get.assert_called_once_with("https://gzpec.cn/robots.txt", timeout=10)
    
    @patch('services.registry.robots_checker.requests.get')
    def test_respects_robots_disallows_crawling(self, mock_get):
        """Test robots.txt that disallows crawling."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "User-agent: *\nDisallow: /"
        mock_get.return_value = mock_response
        
        result = respects_robots("blocked-site.com")
        
        assert result is False
    
    @patch('services.registry.robots_checker.requests.get')
    def test_respects_robots_no_file(self, mock_get):
        """Test handling when robots.txt doesn't exist."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response
        
        result = respects_robots("no-robots.com")
        
        assert result is True  # Assume allowed if no robots.txt
    
    @patch('services.registry.robots_checker.requests.get')
    def test_respects_robots_request_error(self, mock_get):
        """Test handling of request errors."""
        mock_get.side_effect = Exception("Connection failed")
        
        result = respects_robots("unreachable.com")
        
        assert result is True  # Assume allowed on error
    
    def test_validate_domain_allowlist_valid_domains(self):
        """Test validation of valid domains."""
        domains = {"gzpec.cn", "sdpxc.cn", "impex.org.cn"}
        
        result = validate_domain_allowlist(domains)
        
        assert len(result["valid_domains"]) == 3
        assert len(result["invalid_domains"]) == 0
        assert len(result["validation_errors"]) == 0
    
    def test_validate_domain_allowlist_invalid_domains(self):
        """Test validation of invalid domains."""
        domains = {"invalid", "no-tld", "bad..domain.com", ""}
        
        result = validate_domain_allowlist(domains)
        
        assert len(result["valid_domains"]) == 0
        assert len(result["invalid_domains"]) == 4
        assert len(result["validation_errors"]) == 4
    
    def test_get_foundation_allowlist(self):
        """Test foundation allowlist contains expected domains."""
        allowlist = get_foundation_allowlist()
        
        expected_domains = {"gzpec.cn", "sdpxc.cn", "impex.org.cn"}
        assert allowlist == expected_domains
    
    @patch('services.registry.robots_checker.check_domain_accessibility')
    def test_validate_foundation_domains(self, mock_check):
        """Test validation of foundation domains."""
        # Mock accessibility results
        mock_check.side_effect = [
            {"accessible": True, "robots_allows": True, "status_code": 200, "response_time_ms": 500},
            {"accessible": True, "robots_allows": True, "status_code": 200, "response_time_ms": 300},
            {"accessible": False, "robots_allows": False, "error": "Connection failed"}
        ]
        
        result = validate_foundation_domains()
        
        assert result["total_domains"] == 3
        assert len(result["accessible_domains"]) == 2
        assert len(result["inaccessible_domains"]) == 1
        assert result["overall_status"] == "degraded"


class TestSimpleRegistryLoader:
    """Test simplified registry loader functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.sample_registry = {
            "version": "1.0",
            "last_updated": "2025-01-14",
            "maintainer": "CC",
            "guangdong": [
                {
                    "domain": "gzpec.cn",
                    "label": "广东电力交易中心",
                    "doc_classes": ["market_rules", "dispatch_ops"],
                    "cadence": "R/2025-01-01T00:00:00Z/P1D",
                    "robots": "respect",
                    "owner": "CC"
                }
            ],
            "shandong": [
                {
                    "domain": "sdpxc.cn",
                    "label": "山东电力交易中心",
                    "doc_classes": ["market_rules", "grid_connection"],
                    "cadence": "R/2025-01-01T00:00:00Z/P1D",
                    "robots": "respect",
                    "owner": "CC"
                }
            ],
            "inner_mongolia": [
                {
                    "domain": "impex.org.cn",
                    "label": "内蒙古电力交易中心",
                    "doc_classes": ["market_rules"],
                    "cadence": "R/2025-01-01T00:00:00Z/P2D",
                    "robots": "respect",
                    "owner": "CC"
                }
            ]
        }
        
        self.loader = SimpleRegistryLoader()
    
    @patch('builtins.open', new_callable=mock_open)
    @patch('yaml.safe_load')
    def test_load_sources_success(self, mock_yaml_load, mock_file):
        """Test successful source loading."""
        mock_yaml_load.return_value = self.sample_registry
        
        sources = self.loader.load_sources()
        
        assert "guangdong" in sources
        assert "shandong" in sources
        assert "inner_mongolia" in sources
        assert len(sources["guangdong"]) == 1
        assert sources["guangdong"][0]["domain"] == "gzpec.cn"
    
    @patch('os.path.exists')
    def test_load_sources_file_not_found(self, mock_exists):
        """Test handling of missing registry file."""
        mock_exists.return_value = False
        
        with pytest.raises(FileNotFoundError):
            self.loader.load_sources()
    
    @patch('builtins.open', new_callable=mock_open)
    @patch('yaml.safe_load')
    def test_load_sources_empty_file(self, mock_yaml_load, mock_file):
        """Test handling of empty registry file."""
        mock_yaml_load.return_value = None
        
        with pytest.raises(ValueError, match="Registry file is empty"):
            self.loader.load_sources()
    
    def test_validate_sources_valid_registry(self):
        """Test validation of valid registry."""
        sources = {
            "guangdong": [self.sample_registry["guangdong"][0]],
            "shandong": [self.sample_registry["shandong"][0]],
            "inner_mongolia": [self.sample_registry["inner_mongolia"][0]]
        }
        
        with patch('services.registry.simple_loader.respects_robots', return_value=True):
            result = self.loader.validate_sources(sources)
        
        assert result["valid"] is True
        assert len(result["errors"]) == 0
        assert result["allowlist_compliance"] is True
    
    def test_validate_sources_missing_required_fields(self):
        """Test validation with missing required fields."""
        sources = {
            "guangdong": [
                {
                    "domain": "gzpec.cn",
                    # Missing required fields
                }
            ]
        }
        
        result = self.loader.validate_sources(sources)
        
        assert result["valid"] is False
        assert len(result["errors"]) > 0
        assert any("Missing" in error for error in result["errors"])
    
    def test_validate_sources_invalid_cadence(self):
        """Test validation with invalid cadence format."""
        sources = {
            "guangdong": [
                {
                    "domain": "gzpec.cn",
                    "label": "Test",
                    "doc_classes": ["market_rules"],
                    "cadence": "invalid-format",
                    "robots": "respect",
                    "owner": "CC"
                }
            ]
        }
        
        result = self.loader.validate_sources(sources)
        
        assert result["valid"] is False
        assert any("Invalid cadence format" in error for error in result["errors"])
    
    def test_validate_sources_non_allowlist_domain(self):
        """Test validation with domain not in allowlist."""
        sources = {
            "guangdong": [
                {
                    "domain": "not-in-allowlist.com",
                    "label": "Test",
                    "doc_classes": ["market_rules"],
                    "cadence": "R/2025-01-01T00:00:00Z/P1D",
                    "robots": "respect",
                    "owner": "CC"
                }
            ]
        }
        
        with patch('services.registry.simple_loader.respects_robots', return_value=True):
            result = self.loader.validate_sources(sources)
        
        assert result["allowlist_compliance"] is False
        assert any("not in foundation allowlist" in warning for warning in result["warnings"])
    
    @patch('services.registry.simple_loader.SimpleRegistryLoader.load_sources')
    def test_get_sources_for_province(self, mock_load):
        """Test getting sources for specific province."""
        mock_load.return_value = self.sample_registry
        
        guangdong_sources = self.loader.get_sources_for_province("guangdong")
        
        assert len(guangdong_sources) == 1
        assert guangdong_sources[0]["domain"] == "gzpec.cn"
    
    @patch('services.registry.simple_loader.SimpleRegistryLoader.load_sources')
    def test_get_next_crawl_times(self, mock_load):
        """Test calculation of next crawl times."""
        mock_load.return_value = self.sample_registry
        
        next_crawl_times = self.loader.get_next_crawl_times()
        
        assert "gzpec.cn" in next_crawl_times
        assert "sdpxc.cn" in next_crawl_times
        assert "impex.org.cn" in next_crawl_times
        
        # Check that times are ISO format strings
        for domain, time_str in next_crawl_times.items():
            assert "T" in time_str  # ISO format contains 'T'
            assert ":" in time_str  # ISO format contains ':'
    
    @patch('services.registry.simple_loader.SimpleRegistryLoader.load_sources')
    @patch('services.registry.simple_loader.SimpleRegistryLoader.validate_sources')
    @patch('services.registry.simple_loader.validate_foundation_domains')
    def test_validate_registry_file(self, mock_validate_domains, mock_validate_sources, mock_load):
        """Test comprehensive registry file validation."""
        mock_load.return_value = self.sample_registry
        mock_validate_sources.return_value = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "allowlist_compliance": True,
            "robots_compliance": {"gzpec.cn": True, "sdpxc.cn": True, "impex.org.cn": True}
        }
        mock_validate_domains.return_value = {"overall_status": "healthy"}
        
        result = self.loader.validate_registry_file()
        
        assert result["file_valid"] is True
        assert result["total_sources"] == 3
        assert result["enabled_sources"] == 3
        assert result["allowlist_compliance"] is True
        assert "next_crawl_times" in result
    
    @patch('services.registry.simple_loader.get_pool')
    @patch('services.registry.simple_loader.SourceCRUD')
    @patch('services.registry.simple_loader.SimpleRegistryLoader.load_sources')
    @patch('services.registry.simple_loader.SimpleRegistryLoader.validate_sources')
    def test_sync_to_database_success(self, mock_validate, mock_load, mock_crud_class, mock_get_pool):
        """Test successful database synchronization."""
        # Setup mocks
        mock_load.return_value = self.sample_registry
        mock_validate.return_value = {"valid": True, "errors": [], "warnings": []}
        
        mock_pool = Mock()
        mock_conn = Mock()
        mock_pool.connection.return_value.__enter__.return_value = mock_conn
        mock_get_pool.return_value = mock_pool
        
        mock_crud = Mock()
        mock_crud.get_source_by_domain.return_value = None  # No existing sources
        mock_crud.create_source.return_value = "source-id"
        mock_crud_class.return_value = mock_crud
        
        result = self.loader.sync_to_database()
        
        assert result["success"] is True
        assert result["sources_processed"] == 3
        assert result["sources_created"] == 3
        assert result["sources_updated"] == 0
        assert len(result["errors"]) == 0
    
    @patch('services.registry.simple_loader.SimpleRegistryLoader.load_sources')
    def test_sync_to_database_validation_failure(self, mock_load):
        """Test database sync with validation failure."""
        mock_load.return_value = {}  # Empty registry
        
        result = self.loader.sync_to_database()
        
        assert result["success"] is False
        assert result["sources_processed"] == 0


class TestRegistryIntegration:
    """Test registry integration functions."""
    
    @patch('services.registry.simple_loader.SimpleRegistryLoader.validate_registry_file')
    def test_load_and_validate_registry(self, mock_validate):
        """Test convenience function for loading and validating registry."""
        expected_result = {"file_valid": True, "total_sources": 3}
        mock_validate.return_value = expected_result
        
        result = load_and_validate_registry()
        
        assert result == expected_result
        mock_validate.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__])