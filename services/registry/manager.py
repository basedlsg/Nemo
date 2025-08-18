"""Source registry manager with database integration."""

import logging
from datetime import datetime
from typing import List, Dict, Optional, Any

from sqlalchemy.ext.asyncio import AsyncSession

from .loader import SourceRegistryLoader, RegistryFileWatcher
from .validator import SourceRegistryValidator, RegistryHealthChecker
from .models import RegistryConfig, SourceConfig
from services.database.crud import SourceCRUD
from services.database.models import Source as DBSource
from services.core.models import Province, DocumentClass

logger = logging.getLogger(__name__)


class SourceRegistryManager:
    """Manages source registry with database synchronization."""
    
    def __init__(self, registry_path: Optional[str] = None):
        """Initialize registry manager."""
        self.loader = SourceRegistryLoader(registry_path)
        self.validator = SourceRegistryValidator()
        self.file_watcher = RegistryFileWatcher(
            registry_path or "data/registry/sources.yaml",
            callback=self._on_registry_updated
        )
        self._current_registry: Optional[RegistryConfig] = None
        self._last_sync_time: Optional[datetime] = None
    
    async def initialize(self) -> None:
        """Initialize registry manager and load configuration."""
        try:
            logger.info("Initializing source registry manager")
            
            # Load initial registry
            self._current_registry = self.loader.load_registry()
            
            # Validate registry
            validation_result = self.validator.validate_registry(self._current_registry)
            if not validation_result.is_valid:
                logger.error(f"Registry validation failed: {validation_result.errors}")
                raise ValueError(f"Invalid registry configuration: {validation_result.errors}")
            
            if validation_result.warnings:
                logger.warning(f"Registry validation warnings: {validation_result.warnings}")
            
            logger.info(f"Registry initialized with {self._count_sources()} sources")
            
        except Exception as e:
            logger.error(f"Failed to initialize registry manager: {e}")
            raise
    
    async def sync_to_database(self, session: AsyncSession) -> Dict[str, Any]:
        """Synchronize registry configuration to database."""
        if not self._current_registry:
            await self.initialize()
        
        sync_result = {
            "synced_sources": 0,
            "updated_sources": 0,
            "new_sources": 0,
            "disabled_sources": 0,
            "errors": []
        }
        
        try:
            all_sources = self._get_all_sources()
            
            for source_config in all_sources:
                try:
                    # Check if source exists in database
                    existing_source = await SourceCRUD.get_by_domain(session, source_config.domain)
                    
                    if existing_source:
                        # Update existing source
                        updated = await self._update_database_source(session, existing_source, source_config)
                        if updated:
                            sync_result["updated_sources"] += 1
                    else:
                        # Create new source
                        await self._create_database_source(session, source_config)
                        sync_result["new_sources"] += 1
                    
                    sync_result["synced_sources"] += 1
                    
                except Exception as e:
                    error_msg = f"Failed to sync source {source_config.domain}: {e}"
                    logger.error(error_msg)
                    sync_result["errors"].append(error_msg)
            
            # Disable sources not in registry
            await self._disable_orphaned_sources(session, all_sources)
            
            self._last_sync_time = datetime.utcnow()
            logger.info(f"Registry sync completed: {sync_result}")
            
        except Exception as e:
            error_msg = f"Registry sync failed: {e}"
            logger.error(error_msg)
            sync_result["errors"].append(error_msg)
        
        return sync_result
    
    async def get_sources_for_province(
        self, 
        province: Province, 
        doc_class: Optional[DocumentClass] = None,
        enabled_only: bool = True
    ) -> List[SourceConfig]:
        """Get sources for specific province and document class."""
        if not self._current_registry:
            await self.initialize()
        
        if enabled_only:
            sources = self._current_registry.get_enabled_sources_by_province(province)
        else:
            sources = self._current_registry.get_sources_by_province(province)
        
        if doc_class:
            sources = [s for s in sources if doc_class in s.doc_classes]
        
        return sources
    
    async def get_priority_sources_for_asset(
        self, 
        province: Province, 
        asset: str
    ) -> List[SourceConfig]:
        """Get priority sources for specific asset type."""
        if not self._current_registry:
            await self.initialize()
        
        return self._current_registry.get_priority_sources_for_asset(province, asset)
    
    async def get_stale_sources(self, threshold_hours: Optional[int] = None) -> List[SourceConfig]:
        """Get sources that need crawling."""
        if not self._current_registry:
            await self.initialize()
        
        return self._current_registry.get_stale_sources(threshold_hours)
    
    async def update_source_crawl_time(
        self, 
        session: AsyncSession, 
        domain: str, 
        crawl_time: Optional[datetime] = None
    ) -> bool:
        """Update last crawled time for a source."""
        try:
            success = await SourceCRUD.update_crawl_time(session, domain, crawl_time)
            if success:
                logger.debug(f"Updated crawl time for {domain}")
            return success
        except Exception as e:
            logger.error(f"Failed to update crawl time for {domain}: {e}")
            return False
    
    async def get_registry_health(self) -> Dict[str, Any]:
        """Get comprehensive registry health status."""
        if not self._current_registry:
            await self.initialize()
        
        health_checker = RegistryHealthChecker(self._current_registry)
        return health_checker.check_registry_health()
    
    async def reload_registry(self) -> bool:
        """Reload registry from file."""
        try:
            logger.info("Reloading source registry")
            new_registry = self.loader.reload_registry()
            
            # Validate new registry
            validation_result = self.validator.validate_registry(new_registry)
            if not validation_result.is_valid:
                logger.error(f"New registry validation failed: {validation_result.errors}")
                return False
            
            self._current_registry = new_registry
            logger.info("Registry reloaded successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to reload registry: {e}")
            return False
    
    def check_for_updates(self) -> Optional[RegistryConfig]:
        """Check for registry file updates."""
        return self.file_watcher.check_for_updates()
    
    def get_registry_stats(self) -> Dict[str, Any]:
        """Get registry statistics."""
        return self.loader.get_registry_stats()
    
    def export_registry_summary(self, output_path: Optional[str] = None) -> str:
        """Export registry summary."""
        return self.loader.export_registry_summary(output_path)
    
    async def validate_source_accessibility(self, domain: str) -> Dict[str, Any]:
        """Validate source domain accessibility."""
        return self.validator.validate_domain_accessibility(domain)
    
    def _on_registry_updated(self, new_registry: RegistryConfig) -> None:
        """Callback for registry file updates."""
        logger.info("Registry file updated, configuration reloaded")
        self._current_registry = new_registry
    
    def _get_all_sources(self) -> List[SourceConfig]:
        """Get all sources from current registry."""
        if not self._current_registry:
            return []
        
        return (
            self._current_registry.guangdong + self._current_registry.shandong + 
            self._current_registry.inner_mongolia + self._current_registry.sichuan
        )
    
    def _count_sources(self) -> int:
        """Count total sources in registry."""
        return len(self._get_all_sources())
    
    async def _create_database_source(
        self, 
        session: AsyncSession, 
        source_config: SourceConfig
    ) -> DBSource:
        """Create new database source from config."""
        from services.database.models import SourceCreate
        
        # Determine province from registry structure
        province = self._get_province_for_source(source_config.domain)
        
        source_data = SourceCreate(
            domain=source_config.domain,
            province=province.value if province else None,
            label=source_config.label,
            cadence=source_config.cadence,
            robots=source_config.robots.value,
            owner=source_config.owner,
            doc_classes=[dc.value for dc in source_config.doc_classes],
            fetch_method=source_config.fetch_method.value,
            enabled=source_config.enabled
        )
        
        return await SourceCRUD.create(session, source_data)
    
    async def _update_database_source(
        self, 
        session: AsyncSession, 
        db_source: DBSource, 
        source_config: SourceConfig
    ) -> bool:
        """Update existing database source with new config."""
        # Check if update is needed
        needs_update = (
            db_source.label != source_config.label or
            db_source.cadence != source_config.cadence or
            db_source.robots != source_config.robots.value or
            db_source.owner != source_config.owner or
            set(db_source.doc_classes or []) != set(dc.value for dc in source_config.doc_classes) or
            db_source.fetch_method != source_config.fetch_method.value or
            db_source.enabled != source_config.enabled
        )
        
        if needs_update:
            # Update source fields
            db_source.label = source_config.label
            db_source.cadence = source_config.cadence
            db_source.robots = source_config.robots.value
            db_source.owner = source_config.owner
            db_source.doc_classes = [dc.value for dc in source_config.doc_classes]
            db_source.fetch_method = source_config.fetch_method.value
            db_source.enabled = source_config.enabled
            db_source.updated_at = datetime.utcnow()
            
            await session.commit()
            return True
        
        return False
    
    async def _disable_orphaned_sources(
        self, 
        session: AsyncSession, 
        current_sources: List[SourceConfig]
    ) -> None:
        """Disable sources in database that are not in current registry."""
        current_domains = {source.domain for source in current_sources}
        
        # This would require a method to get all database sources
        # For now, we'll skip this step as it requires additional CRUD methods
        pass
    
    def _get_province_for_source(self, domain: str) -> Optional[Province]:
        """Determine which province a source belongs to."""
        if not self._current_registry:
            return None
        
        for province_name, sources in [
            ("guangdong", self._current_registry.guangdong),
            ("shandong", self._current_registry.shandong),
            ("inner_mongolia", self._current_registry.inner_mongolia),
            ("sichuan", self._current_registry.sichuan),
        ]:
            if any(source.domain == domain for source in sources):
                return Province(province_name)
        
        return None


class RegistryCache:
    """In-memory cache for registry data."""
    
    def __init__(self, ttl_seconds: int = 3600):
        """Initialize cache with TTL."""
        self.ttl_seconds = ttl_seconds
        self._cache: Dict[str, Any] = {}
        self._timestamps: Dict[str, datetime] = {}
    
    def get(self, key: str) -> Optional[Any]:
        """Get cached value if not expired."""
        if key not in self._cache:
            return None
        
        timestamp = self._timestamps.get(key)
        if not timestamp:
            return None
        
        # Check if expired
        if (datetime.utcnow() - timestamp).total_seconds() > self.ttl_seconds:
            self._cache.pop(key, None)
            self._timestamps.pop(key, None)
            return None
        
        return self._cache[key]
    
    def set(self, key: str, value: Any) -> None:
        """Set cached value with timestamp."""
        self._cache[key] = value
        self._timestamps[key] = datetime.utcnow()
    
    def clear(self) -> None:
        """Clear all cached values."""
        self._cache.clear()
        self._timestamps.clear()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return {
            "total_keys": len(self._cache),
            "expired_keys": len([
                key for key, timestamp in self._timestamps.items()
                if (datetime.utcnow() - timestamp).total_seconds() > self.ttl_seconds
            ]),
            "ttl_seconds": self.ttl_seconds
        }