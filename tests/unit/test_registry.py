"""Unit tests for source registry management."""

import pytest
import tempfile
import os
from datetime import datetime
from unittest.mock import AsyncMock, patch, MagicMock

import yaml

from services.registry.models import (
    RegistryConfig, SourceConfig, GlobalConfig, AssetMapping,
    Priority, FetchMethod, RobotsPolicy, SourceSelectors
)
from services.registry.loader import SourceRegistryLoader, RegistryFileWatcher
from services.registry.validator import SourceRegistryValidator, ValidationResult
from services.registry.manager import SourceRegistryManager, RegistryCache
from services.core.models import Province, DocumentClass


class TestSourceConfig:
    """Test SourceConfig model."""
    
    @pytest.fixture
    def valid_source_data(self):
        """Valid source configuration data."""
        return {
            "domain": "gzpec.cn",
            "label": "广东电力交易中心",
            "label_en": "Guangdong Power Exchange Center",
            "doc_classes": ["market_rules", "dispatch_ops"],
            "cadence": "R/2025-01-01T00:00:00Z/P1D",
            "robots": "allow",
            "fetch_method": "html",
            "selectors": {
                "index": "a[href*='公告']",
                "content": ".content"
            },
            "effective_date_locator": "meta[name='pubDate']",
            "owner": "CC",
            "priority": "high",
            "enabled": True
        }
    
    def test_valid_source_creation(self, valid_source_data):
        """Test creating valid source configuration."""
        source = SourceConfig(**valid_source_data)
        
        assert source.domain == "gzpec.cn"
        assert source.label == "广东电力交易中心"
        assert DocumentClass.MARKET_RULES in source.doc_classes
        assert source.priority == Priority.HIGH
        assert source.enabled is True
    
    def test_cadence_validation(self, valid_source_data):
        """Test cadence format validation."""
        # Valid cadence
        source = SourceConfig(**valid_source_data)
        assert source.cadence == "R/2025-01-01T00:00:00Z/P1D"
        
        # Invalid cadence format
        with pytest.raises(ValueError, match="ISO8601 interval format"):
            invalid_data = valid_source_data.copy()
            invalid_data["cadence"] = "invalid-format"
            SourceConfig(**invalid_data)
    
    def test_effective_date_locator_validation(self, valid_source_data):
        """Test effective date locator validation."""
        # Valid CSS selector
        source = SourceConfig(**valid_source_data)
        assert source.effective_date_locator == "meta[name='pubDate']"
        
        # Valid regex pattern
        regex_data = valid_source_data.copy()
        regex_data["effective_date_locator"] = "regex:(\\d{4})-(\\d{1,2})-(\\d{1,2})"
        source = SourceConfig(**regex_data)
        assert source.effective_date_locator.startswith("regex:")
        
        # Invalid regex pattern
        with pytest.raises(ValueError, match="Invalid regex pattern"):
            invalid_data = valid_source_data.copy()
            invalid_data["effective_date_locator"] = "regex:[invalid"
            SourceConfig(**invalid_data)
    
    def test_get_crawl_interval_hours(self, valid_source_data):
        """Test crawl interval calculation."""
        # Daily interval
        source = SourceConfig(**valid_source_data)
        assert source.get_crawl_interval_hours() == 24
        
        # Weekly interval
        weekly_data = valid_source_data.copy()
        weekly_data["cadence"] = "R/2025-01-01T00:00:00Z/P7D"
        source = SourceConfig(**weekly_data)
        assert source.get_crawl_interval_hours() == 168  # 7 * 24
        
        # Hourly interval
        hourly_data = valid_source_data.copy()
        hourly_data["cadence"] = "R/2025-01-01T00:00:00Z/PT6H"
        source = SourceConfig(**hourly_data)
        assert source.get_crawl_interval_hours() == 6
    
    def test_is_stale(self, valid_source_data):
        """Test stale source detection."""
        source = SourceConfig(**valid_source_data)
        
        # No last crawled time - should be stale
        assert source.is_stale(None) is True
        
        # Recent crawl - should not be stale
        from datetime import timedelta
        recent_time = datetime.utcnow() - timedelta(hours=12)
        assert source.is_stale(recent_time) is False
        
        # Old crawl - should be stale
        old_time = datetime.utcnow() - timedelta(hours=48)
        assert source.is_stale(old_time) is True


class TestRegistryConfig:
    """Test RegistryConfig model."""
    
    @pytest.fixture
    def valid_registry_data(self):
        """Valid registry configuration data."""
        return {
            "version": "1.0",
            "last_updated": "2025-01-14",
            "maintainer": "CC",
            "guangdong": [
                {
                    "domain": "gzpec.cn",
                    "label": "广东电力交易中心",
                    "doc_classes": ["market_rules"],
                    "cadence": "R/2025-01-01T00:00:00Z/P1D",
                    "selectors": {"index": "a[href*='公告']"},
                    "effective_date_locator": "meta[name='pubDate']",
                    "owner": "CC",
                    "enabled": True
                }
            ],
            "shandong": [],
            "inner_mongolia": [],
            "sichuan": [],
            "global_config": {
                "default_cadence": "R/2025-01-01T00:00:00Z/P1D"
            },
            "asset_mappings": {}
        }
    
    def test_valid_registry_creation(self, valid_registry_data):
        """Test creating valid registry configuration."""
        registry = RegistryConfig(**valid_registry_data)
        
        assert registry.version == "1.0"
        assert registry.maintainer == "CC"
        assert len(registry.guangdong) == 1
        assert registry.guangdong[0].domain == "gzpec.cn"
    
    def test_get_sources_by_province(self, valid_registry_data):
        """Test getting sources by province."""
        registry = RegistryConfig(**valid_registry_data)
        
        guangdong_sources = registry.get_sources_by_province(Province.GUANGDONG)
        assert len(guangdong_sources) == 1
        assert guangdong_sources[0].domain == "gzpec.cn"
        
        shandong_sources = registry.get_sources_by_province(Province.SHANDONG)
        assert len(shandong_sources) == 0
    
    def test_get_enabled_sources_by_province(self, valid_registry_data):
        """Test getting enabled sources by province."""
        # Add disabled source
        disabled_source = valid_registry_data["guangdong"][0].copy()
        disabled_source["domain"] = "disabled.cn"
        disabled_source["enabled"] = False
        valid_registry_data["guangdong"].append(disabled_source)
        
        registry = RegistryConfig(**valid_registry_data)
        
        enabled_sources = registry.get_enabled_sources_by_province(Province.GUANGDONG)
        assert len(enabled_sources) == 1
        assert enabled_sources[0].domain == "gzpec.cn"
    
    def test_get_sources_by_doc_class(self, valid_registry_data):
        """Test getting sources by document class."""
        registry = RegistryConfig(**valid_registry_data)
        
        market_sources = registry.get_sources_by_doc_class(
            Province.GUANGDONG, DocumentClass.MARKET_RULES
        )
        assert len(market_sources) == 1
        
        grid_sources = registry.get_sources_by_doc_class(
            Province.GUANGDONG, DocumentClass.GRID_CONNECTION
        )
        assert len(grid_sources) == 0
    
    def test_validate_source_coverage(self, valid_registry_data):
        """Test source coverage validation."""
        registry = RegistryConfig(**valid_registry_data)
        coverage_report = registry.validate_source_coverage()
        
        assert "guangdong" in coverage_report
        guangdong_report = coverage_report["guangdong"]
        assert guangdong_report["total_sources"] == 1
        assert guangdong_report["enabled_sources"] == 1
        assert "market_rules" in guangdong_report["covered_doc_classes"]
        assert "grid_connection" in guangdong_report["missing_doc_classes"]
        assert guangdong_report["coverage_complete"] is False


class TestSourceRegistryLoader:
    """Test SourceRegistryLoader functionality."""
    
    @pytest.fixture
    def temp_registry_file(self):
        """Create temporary registry file for testing."""
        registry_data = {
            "version": "1.0",
            "last_updated": "2025-01-14",
            "maintainer": "CC",
            "guangdong": [
                {
                    "domain": "gzpec.cn",
                    "label": "广东电力交易中心",
                    "doc_classes": ["market_rules"],
                    "cadence": "R/2025-01-01T00:00:00Z/P1D",
                    "selectors": {"index": "a[href*='公告']"},
                    "effective_date_locator": "meta[name='pubDate']",
                    "owner": "CC",
                    "enabled": True
                }
            ],
            "shandong": [],
            "inner_mongolia": [],
            "sichuan": [],
            "global_config": {},
            "asset_mappings": {}
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(registry_data, f, default_flow_style=False, allow_unicode=True)
            temp_path = f.name
        
        yield temp_path
        
        # Cleanup
        os.unlink(temp_path)
    
    def test_load_registry_success(self, temp_registry_file):
        """Test successful registry loading."""
        loader = SourceRegistryLoader(temp_registry_file)
        registry = loader.load_registry()
        
        assert isinstance(registry, RegistryConfig)
        assert registry.version == "1.0"
        assert len(registry.guangdong) == 1
    
    def test_load_registry_file_not_found(self):
        """Test loading non-existent registry file."""
        loader = SourceRegistryLoader("non_existent_file.yaml")
        
        with pytest.raises(FileNotFoundError):
            loader.load_registry()
    
    def test_load_province_sources(self, temp_registry_file):
        """Test loading sources for specific province."""
        loader = SourceRegistryLoader(temp_registry_file)
        guangdong_sources = loader.load_province_sources("guangdong")
        
        assert "gzpec.cn" in guangdong_sources
        assert isinstance(guangdong_sources["gzpec.cn"], SourceConfig)
    
    def test_validate_registry_file(self, temp_registry_file):
        """Test registry file validation."""
        loader = SourceRegistryLoader(temp_registry_file)
        validation_report = loader.validate_registry_file()
        
        assert validation_report["valid"] is True
        assert validation_report["source_count"] == 1
        assert "coverage_report" in validation_report
    
    def test_get_registry_stats(self, temp_registry_file):
        """Test registry statistics generation."""
        loader = SourceRegistryLoader(temp_registry_file)
        stats = loader.get_registry_stats()
        
        assert stats["version"] == "1.0"
        assert stats["total_sources"] == 1
        assert stats["enabled_sources"] == 1
        assert "provinces" in stats
        assert "doc_class_coverage" in stats


class TestSourceRegistryValidator:
    """Test SourceRegistryValidator functionality."""
    
    @pytest.fixture
    def validator(self):
        """Create validator instance."""
        return SourceRegistryValidator(check_connectivity=False)
    
    @pytest.fixture
    def valid_source(self):
        """Valid source configuration."""
        return SourceConfig(
            domain="gzpec.cn",
            label="Test Source",
            doc_classes=[DocumentClass.MARKET_RULES],
            cadence="R/2025-01-01T00:00:00Z/P1D",
            selectors=SourceSelectors(index="a[href*='test']"),
            effective_date_locator="meta[name='pubDate']",
            owner="CC",
            enabled=True
        )
    
    def test_validate_source_config_valid(self, validator, valid_source):
        """Test validation of valid source configuration."""
        result = validator.validate_source_config(valid_source)
        
        assert result.is_valid is True
        assert len(result.errors) == 0
    
    def test_validate_source_config_invalid_domain(self, validator, valid_source):
        """Test validation of invalid domain."""
        valid_source.domain = "invalid-domain"
        result = validator.validate_source_config(valid_source)
        
        assert result.is_valid is False
        assert any("Invalid domain format" in error for error in result.errors)
    
    def test_validate_source_config_invalid_regex(self, validator, valid_source):
        """Test validation of invalid regex in date locator."""
        valid_source.effective_date_locator = "regex:[invalid"
        result = validator.validate_source_config(valid_source)
        
        assert result.is_valid is False
        assert any("Invalid regex" in error for error in result.errors)
    
    def test_validate_registry_structure(self, validator):
        """Test registry structure validation."""
        # Create minimal valid registry
        registry = RegistryConfig(
            version="1.0",
            last_updated="2025-01-14",
            maintainer="CC",
            guangdong=[],
            shandong=[],
            inner_mongolia=[],
            sichuan=[]
        )
        
        result = validator.validate_registry(registry)
        
        # Should have warning about no sources
        assert any("must contain at least one source" in error for error in result.errors)
    
    @patch('requests.get')
    def test_validate_domain_accessibility(self, mock_get, validator):
        """Test domain accessibility validation."""
        # Mock successful response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response
        
        result = validator.validate_domain_accessibility("gzpec.cn")
        
        assert result["domain"] == "gzpec.cn"
        assert result["accessible"] is True
        assert result["response_time_ms"] is not None


class TestSourceRegistryManager:
    """Test SourceRegistryManager functionality."""
    
    @pytest.fixture
    def mock_session(self):
        """Mock database session."""
        return AsyncMock()
    
    @pytest.fixture
    def temp_registry_file(self):
        """Create temporary registry file."""
        registry_data = {
            "version": "1.0",
            "last_updated": "2025-01-14",
            "maintainer": "CC",
            "guangdong": [
                {
                    "domain": "gzpec.cn",
                    "label": "广东电力交易中心",
                    "doc_classes": ["market_rules"],
                    "cadence": "R/2025-01-01T00:00:00Z/P1D",
                    "selectors": {"index": "a[href*='公告']"},
                    "effective_date_locator": "meta[name='pubDate']",
                    "owner": "CC",
                    "enabled": True
                }
            ],
            "shandong": [],
            "inner_mongolia": [],
            "sichuan": [],
            "global_config": {},
            "asset_mappings": {}
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(registry_data, f, default_flow_style=False, allow_unicode=True)
            temp_path = f.name
        
        yield temp_path
        os.unlink(temp_path)
    
    @pytest.mark.asyncio
    async def test_initialize(self, temp_registry_file):
        """Test registry manager initialization."""
        manager = SourceRegistryManager(temp_registry_file)
        await manager.initialize()
        
        assert manager._current_registry is not None
        assert manager._current_registry.version == "1.0"
    
    @pytest.mark.asyncio
    async def test_get_sources_for_province(self, temp_registry_file):
        """Test getting sources for province."""
        manager = SourceRegistryManager(temp_registry_file)
        await manager.initialize()
        
        sources = await manager.get_sources_for_province(Province.GUANGDONG)
        assert len(sources) == 1
        assert sources[0].domain == "gzpec.cn"
        
        # Test with document class filter
        market_sources = await manager.get_sources_for_province(
            Province.GUANGDONG, DocumentClass.MARKET_RULES
        )
        assert len(market_sources) == 1
        
        grid_sources = await manager.get_sources_for_province(
            Province.GUANGDONG, DocumentClass.GRID_CONNECTION
        )
        assert len(grid_sources) == 0
    
    @pytest.mark.asyncio
    async def test_sync_to_database(self, temp_registry_file, mock_session):
        """Test syncing registry to database."""
        manager = SourceRegistryManager(temp_registry_file)
        await manager.initialize()
        
        # Mock database operations
        with patch('services.registry.manager.SourceCRUD') as mock_crud:
            mock_crud.get_by_domain.return_value = None  # No existing source
            mock_crud.create.return_value = MagicMock()
            
            result = await manager.sync_to_database(mock_session)
            
            assert result["synced_sources"] == 1
            assert result["new_sources"] == 1
            assert len(result["errors"]) == 0
    
    @pytest.mark.asyncio
    async def test_update_source_crawl_time(self, temp_registry_file, mock_session):
        """Test updating source crawl time."""
        manager = SourceRegistryManager(temp_registry_file)
        
        with patch('services.registry.manager.SourceCRUD') as mock_crud:
            mock_crud.update_crawl_time.return_value = True
            
            success = await manager.update_source_crawl_time(mock_session, "gzpec.cn")
            assert success is True
    
    @pytest.mark.asyncio
    async def test_get_registry_health(self, temp_registry_file):
        """Test getting registry health status."""
        manager = SourceRegistryManager(temp_registry_file)
        await manager.initialize()
        
        health = await manager.get_registry_health()
        
        assert "overall_status" in health
        assert "checks" in health
        assert "summary" in health


class TestRegistryCache:
    """Test RegistryCache functionality."""
    
    def test_cache_set_get(self):
        """Test basic cache set and get operations."""
        cache = RegistryCache(ttl_seconds=60)
        
        # Set and get value
        cache.set("test_key", "test_value")
        assert cache.get("test_key") == "test_value"
        
        # Get non-existent key
        assert cache.get("non_existent") is None
    
    def test_cache_expiration(self):
        """Test cache expiration."""
        cache = RegistryCache(ttl_seconds=1)
        
        cache.set("test_key", "test_value")
        assert cache.get("test_key") == "test_value"
        
        # Mock time passage
        import time
        with patch('services.registry.manager.datetime') as mock_datetime:
            # Simulate time passage beyond TTL
            mock_datetime.utcnow.return_value = datetime.utcnow() + timedelta(seconds=2)
            assert cache.get("test_key") is None
    
    def test_cache_clear(self):
        """Test cache clearing."""
        cache = RegistryCache()
        
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        
        assert cache.get("key1") == "value1"
        assert cache.get("key2") == "value2"
        
        cache.clear()
        
        assert cache.get("key1") is None
        assert cache.get("key2") is None
    
    def test_cache_stats(self):
        """Test cache statistics."""
        cache = RegistryCache()
        
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        
        stats = cache.get_stats()
        
        assert stats["total_keys"] == 2
        assert stats["ttl_seconds"] == 3600  # Default TTL


class TestRegistryFileWatcher:
    """Test RegistryFileWatcher functionality."""
    
    @pytest.fixture
    def temp_registry_file(self):
        """Create temporary registry file."""
        registry_data = {
            "version": "1.0",
            "last_updated": "2025-01-14",
            "maintainer": "CC",
            "guangdong": [],
            "shandong": [],
            "inner_mongolia": [],
            "sichuan": [],
            "global_config": {},
            "asset_mappings": {}
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(registry_data, f, default_flow_style=False, allow_unicode=True)
            temp_path = f.name
        
        yield temp_path
        os.unlink(temp_path)
    
    def test_file_watcher_initialization(self, temp_registry_file):
        """Test file watcher initialization."""
        callback = MagicMock()
        watcher = RegistryFileWatcher(temp_registry_file, callback)
        
        assert watcher.registry_path == temp_registry_file
        assert watcher.callback == callback
    
    def test_check_for_updates_initial_load(self, temp_registry_file):
        """Test initial registry load."""
        watcher = RegistryFileWatcher(temp_registry_file)
        registry = watcher.check_for_updates()
        
        assert registry is not None
        assert registry.version == "1.0"
    
    def test_get_current_registry(self, temp_registry_file):
        """Test getting current registry."""
        watcher = RegistryFileWatcher(temp_registry_file)
        
        # Should load on first call
        registry = watcher.get_current_registry()
        assert registry is not None
        assert registry.version == "1.0"
        
        # Should return cached version on second call
        cached_registry = watcher.get_current_registry()
        assert cached_registry is registry  # Same object


if __name__ == "__main__":
    pytest.main([__file__])