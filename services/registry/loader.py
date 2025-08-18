"""YAML source registry loader with validation."""

import os
import logging
from pathlib import Path
from typing import Dict, Any, Optional

import yaml
from pydantic import ValidationError

from .models import RegistryConfig, SourceConfig
from .validator import SourceRegistryValidator

logger = logging.getLogger(__name__)


class SourceRegistryLoader:
    """Loads and validates source registry from YAML files."""
    
    def __init__(self, registry_path: Optional[str] = None):
        """Initialize loader with registry path."""
        self.registry_path = registry_path or "data/registry/sources.yaml"
        self.validator = SourceRegistryValidator()
    
    def load_registry(self) -> RegistryConfig:
        """Load and validate complete registry configuration."""
        try:
            # Check if file exists
            if not os.path.exists(self.registry_path):
                raise FileNotFoundError(f"Registry file not found: {self.registry_path}")
            
            # Load YAML content
            with open(self.registry_path, 'r', encoding='utf-8') as file:
                raw_data = yaml.safe_load(file)
            
            if not raw_data:
                raise ValueError("Registry file is empty or invalid")
            
            # Validate and parse configuration
            registry_config = RegistryConfig(**raw_data)
            
            # Run additional validation
            validation_result = self.validator.validate_registry(registry_config)
            if not validation_result.is_valid:
                logger.warning(f"Registry validation warnings: {validation_result.warnings}")
                if validation_result.errors:
                    raise ValueError(f"Registry validation errors: {validation_result.errors}")
            
            logger.info(f"Successfully loaded registry with {self._count_sources(registry_config)} sources")
            return registry_config
            
        except yaml.YAMLError as e:
            logger.error(f"YAML parsing error: {e}")
            raise ValueError(f"Invalid YAML format: {e}")
        except ValidationError as e:
            logger.error(f"Registry validation error: {e}")
            raise ValueError(f"Registry validation failed: {e}")
        except Exception as e:
            logger.error(f"Failed to load registry: {e}")
            raise
    
    def load_province_sources(self, province: str) -> Dict[str, SourceConfig]:
        """Load sources for a specific province."""
        registry = self.load_registry()
        
        province_sources = getattr(registry, province, [])
        if not province_sources:
            logger.warning(f"No sources found for province: {province}")
            return {}
        
        # Convert to domain-keyed dictionary
        sources_dict = {}
        for source in province_sources:
            sources_dict[source.domain] = source
        
        logger.info(f"Loaded {len(sources_dict)} sources for province: {province}")
        return sources_dict
    
    def reload_registry(self) -> RegistryConfig:
        """Reload registry configuration (useful for hot reloading)."""
        logger.info("Reloading source registry configuration")
        return self.load_registry()
    
    def validate_registry_file(self) -> Dict[str, Any]:
        """Validate registry file and return detailed report."""
        try:
            registry = self.load_registry()
            validation_result = self.validator.validate_registry(registry)
            
            return {
                "valid": validation_result.is_valid,
                "errors": validation_result.errors,
                "warnings": validation_result.warnings,
                "source_count": self._count_sources(registry),
                "coverage_report": registry.validate_source_coverage(),
                "last_updated": registry.last_updated,
                "version": registry.version
            }
        except Exception as e:
            return {
                "valid": False,
                "errors": [str(e)],
                "warnings": [],
                "source_count": 0,
                "coverage_report": {},
                "last_updated": None,
                "version": None
            }
    
    def get_registry_stats(self) -> Dict[str, Any]:
        """Get registry statistics and health information."""
        try:
            registry = self.load_registry()
            
            stats = {
                "version": registry.version,
                "last_updated": registry.last_updated,
                "maintainer": registry.maintainer,
                "total_sources": self._count_sources(registry),
                "enabled_sources": self._count_enabled_sources(registry),
                "provinces": {
                    "guangdong": len(registry.guangdong),
                    "shandong": len(registry.shandong),
                    "inner_mongolia": len(registry.inner_mongolia),
                    "sichuan": len(registry.sichuan)
                },
                "doc_class_coverage": self._analyze_doc_class_coverage(registry),
                "priority_distribution": self._analyze_priority_distribution(registry),
                "fetch_method_distribution": self._analyze_fetch_methods(registry)
            }
            
            return stats
        except Exception as e:
            logger.error(f"Failed to get registry stats: {e}")
            return {"error": str(e)}
    
    def export_registry_summary(self, output_path: Optional[str] = None) -> str:
        """Export registry summary to markdown format."""
        try:
            registry = self.load_registry()
            stats = self.get_registry_stats()
            
            summary = self._generate_markdown_summary(registry, stats)
            
            if output_path:
                with open(output_path, 'w', encoding='utf-8') as file:
                    file.write(summary)
                logger.info(f"Registry summary exported to: {output_path}")
            
            return summary
        except Exception as e:
            logger.error(f"Failed to export registry summary: {e}")
            raise
    
    def _count_sources(self, registry: RegistryConfig) -> int:
        """Count total sources in registry."""
        return (
            len(registry.guangdong) + len(registry.shandong) + 
            len(registry.inner_mongolia) + len(registry.sichuan)
        )
    
    def _count_enabled_sources(self, registry: RegistryConfig) -> int:
        """Count enabled sources in registry."""
        all_sources = (
            registry.guangdong + registry.shandong + 
            registry.inner_mongolia + registry.sichuan
        )
        return len([s for s in all_sources if s.enabled])
    
    def _analyze_doc_class_coverage(self, registry: RegistryConfig) -> Dict[str, int]:
        """Analyze document class coverage across all sources."""
        from collections import Counter
        
        all_sources = (
            registry.guangdong + registry.shandong + 
            registry.inner_mongolia + registry.sichuan
        )
        
        doc_class_counts = Counter()
        for source in all_sources:
            if source.enabled:
                for doc_class in source.doc_classes:
                    doc_class_counts[doc_class.value] += 1
        
        return dict(doc_class_counts)
    
    def _analyze_priority_distribution(self, registry: RegistryConfig) -> Dict[str, int]:
        """Analyze priority distribution of sources."""
        from collections import Counter
        
        all_sources = (
            registry.guangdong + registry.shandong + 
            registry.inner_mongolia + registry.sichuan
        )
        
        priority_counts = Counter()
        for source in all_sources:
            if source.enabled:
                priority_counts[source.priority.value] += 1
        
        return dict(priority_counts)
    
    def _analyze_fetch_methods(self, registry: RegistryConfig) -> Dict[str, int]:
        """Analyze fetch method distribution."""
        from collections import Counter
        
        all_sources = (
            registry.guangdong + registry.shandong + 
            registry.inner_mongolia + registry.sichuan
        )
        
        method_counts = Counter()
        for source in all_sources:
            if source.enabled:
                method_counts[source.fetch_method.value] += 1
        
        return dict(method_counts)
    
    def _generate_markdown_summary(self, registry: RegistryConfig, stats: Dict[str, Any]) -> str:
        """Generate markdown summary of registry."""
        summary = f"""# Source Registry Summary

**Version:** {registry.version}  
**Last Updated:** {registry.last_updated}  
**Maintainer:** {registry.maintainer}

## Overview

- **Total Sources:** {stats['total_sources']}
- **Enabled Sources:** {stats['enabled_sources']}
- **Provinces Covered:** {len([p for p, count in stats['provinces'].items() if count > 0])}

## Province Coverage

| Province | Sources | Status |
|----------|---------|--------|
| Guangdong | {stats['provinces']['guangdong']} | {'✅ Active' if stats['provinces']['guangdong'] > 0 else '❌ No Sources'} |
| Shandong | {stats['provinces']['shandong']} | {'✅ Active' if stats['provinces']['shandong'] > 0 else '❌ No Sources'} |
| Inner Mongolia | {stats['provinces']['inner_mongolia']} | {'✅ Active' if stats['provinces']['inner_mongolia'] > 0 else '❌ No Sources'} |
| Sichuan | {stats['provinces']['sichuan']} | {'🚧 Queued' if stats['provinces']['sichuan'] > 0 else '❌ No Sources'} |

## Document Class Coverage

| Document Class | Sources |
|----------------|---------|
"""
        
        for doc_class, count in stats['doc_class_coverage'].items():
            summary += f"| {doc_class.replace('_', ' ').title()} | {count} |\n"
        
        summary += f"""
## Priority Distribution

| Priority | Sources |
|----------|---------|
"""
        
        for priority, count in stats['priority_distribution'].items():
            summary += f"| {priority.title()} | {count} |\n"
        
        summary += f"""
## Fetch Methods

| Method | Sources |
|--------|---------|
"""
        
        for method, count in stats['fetch_method_distribution'].items():
            summary += f"| {method.upper()} | {count} |\n"
        
        # Add coverage report
        coverage_report = registry.validate_source_coverage()
        summary += "\n## Province Coverage Details\n\n"
        
        for province, details in coverage_report.items():
            status = "✅ Complete" if details['coverage_complete'] else "⚠️ Incomplete"
            summary += f"### {province.title()}\n\n"
            summary += f"- **Status:** {status}\n"
            summary += f"- **Total Sources:** {details['total_sources']}\n"
            summary += f"- **Enabled Sources:** {details['enabled_sources']}\n"
            summary += f"- **High Priority Sources:** {details['high_priority_sources']}\n"
            summary += f"- **Covered Document Classes:** {', '.join(details['covered_doc_classes'])}\n"
            
            if details['missing_doc_classes']:
                summary += f"- **Missing Document Classes:** {', '.join(details['missing_doc_classes'])}\n"
            
            summary += "\n"
        
        return summary


class RegistryFileWatcher:
    """Watch registry file for changes and reload automatically."""
    
    def __init__(self, registry_path: str, callback=None):
        """Initialize file watcher."""
        self.registry_path = registry_path
        self.callback = callback
        self.loader = SourceRegistryLoader(registry_path)
        self._last_modified = None
        self._current_registry = None
    
    def check_for_updates(self) -> Optional[RegistryConfig]:
        """Check if registry file has been updated and reload if necessary."""
        try:
            current_modified = os.path.getmtime(self.registry_path)
            
            if self._last_modified is None or current_modified > self._last_modified:
                logger.info("Registry file updated, reloading...")
                new_registry = self.loader.load_registry()
                
                self._last_modified = current_modified
                self._current_registry = new_registry
                
                if self.callback:
                    self.callback(new_registry)
                
                return new_registry
            
            return self._current_registry
        except Exception as e:
            logger.error(f"Failed to check for registry updates: {e}")
            return self._current_registry
    
    def get_current_registry(self) -> Optional[RegistryConfig]:
        """Get current registry, loading if necessary."""
        if self._current_registry is None:
            return self.check_for_updates()
        return self._current_registry