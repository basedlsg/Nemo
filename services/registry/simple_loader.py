"""Simplified YAML registry loader for Task 4 foundation quartet."""

import os
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta

import yaml

from .robots_checker import respects_robots, get_foundation_allowlist, validate_foundation_domains
from services.database.simple_crud import SourceCRUD
from services.database.pool import get_pool

logger = logging.getLogger(__name__)


class SimpleRegistryLoader:
    """Simplified registry loader focused on foundation quartet requirements."""
    
    def __init__(self, registry_path: str = "data/registry/sources.yaml"):
        """Initialize loader with registry path."""
        self.registry_path = registry_path
        self.allowlist = get_foundation_allowlist()
    
    def load_sources(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Load sources from YAML registry.
        
        Returns:
            Dictionary with province -> list of sources
        """
        try:
            if not os.path.exists(self.registry_path):
                raise FileNotFoundError(f"Registry file not found: {self.registry_path}")
            
            with open(self.registry_path, 'r', encoding='utf-8') as file:
                data = yaml.safe_load(file)
            
            if not data:
                raise ValueError("Registry file is empty")
            
            # Extract province sources
            sources = {}
            for province in ["guangdong", "shandong", "inner_mongolia"]:
                province_sources = data.get(province, [])
                sources[province] = province_sources
                logger.info(f"Loaded {len(province_sources)} sources for {province}")
            
            return sources
            
        except Exception as e:
            logger.error(f"Failed to load registry: {e}")
            raise
    
    def validate_sources(self, sources: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
        """
        Validate loaded sources against foundation requirements.
        
        Args:
            sources: Sources dictionary from load_sources()
            
        Returns:
            Validation report
        """
        validation_report = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "source_validation": {},
            "allowlist_compliance": True,
            "robots_compliance": {}
        }
        
        all_domains = set()
        
        # Validate each province's sources
        for province, province_sources in sources.items():
            for source in province_sources:
                domain = source.get("domain")
                if not domain:
                    validation_report["errors"].append(f"Missing domain in {province} source")
                    validation_report["valid"] = False
                    continue
                
                all_domains.add(domain)
                
                # Validate required fields
                required_fields = ["label", "doc_classes", "cadence", "robots", "owner"]
                for field in required_fields:
                    if not source.get(field):
                        validation_report["errors"].append(f"Missing {field} for {domain}")
                        validation_report["valid"] = False
                
                # Check allowlist compliance
                if domain not in self.allowlist:
                    validation_report["warnings"].append(f"Domain {domain} not in foundation allowlist")
                    validation_report["allowlist_compliance"] = False
                
                # Validate cadence format (basic check)
                cadence = source.get("cadence", "")
                if not cadence.startswith("R/") or "/P" not in cadence:
                    validation_report["errors"].append(f"Invalid cadence format for {domain}: {cadence}")
                    validation_report["valid"] = False
        
        # Check robots.txt compliance for all domains
        for domain in all_domains:
            try:
                robots_ok = respects_robots(domain)
                validation_report["robots_compliance"][domain] = robots_ok
                
                if not robots_ok:
                    validation_report["warnings"].append(f"Robots.txt may block crawling for {domain}")
            except Exception as e:
                validation_report["warnings"].append(f"Failed to check robots.txt for {domain}: {e}")
        
        return validation_report
    
    def sync_to_database(self) -> Dict[str, Any]:
        """
        Load registry and sync to database.
        
        Returns:
            Sync result report
        """
        sync_result = {
            "success": False,
            "sources_processed": 0,
            "sources_created": 0,
            "sources_updated": 0,
            "errors": []
        }
        
        try:
            # Load sources from YAML
            sources = self.load_sources()
            
            # Validate sources
            validation = self.validate_sources(sources)
            if not validation["valid"]:
                sync_result["errors"].extend(validation["errors"])
                return sync_result
            
            if validation["warnings"]:
                logger.warning(f"Registry validation warnings: {validation['warnings']}")
            
            # Sync to database
            pool = get_pool()
            source_crud = SourceCRUD()
            
            with pool.connection() as conn:
                for province, province_sources in sources.items():
                    for source_data in province_sources:
                        try:
                            # Prepare source data for database
                            db_source_data = {
                                "domain": source_data["domain"],
                                "province": province,
                                "label": source_data["label"],
                                "cadence": source_data["cadence"],
                                "robots": source_data["robots"],
                                "owner": source_data["owner"]
                            }
                            
                            # Check if source exists
                            existing = source_crud.get_source_by_domain(conn, source_data["domain"])
                            
                            if existing:
                                # Update existing source
                                success = source_crud.update_source(conn, source_data["domain"], db_source_data)
                                if success:
                                    sync_result["sources_updated"] += 1
                            else:
                                # Create new source
                                source_id = source_crud.create_source(conn, db_source_data)
                                if source_id:
                                    sync_result["sources_created"] += 1
                            
                            sync_result["sources_processed"] += 1
                            
                        except Exception as e:
                            error_msg = f"Failed to sync source {source_data.get('domain', 'unknown')}: {e}"
                            logger.error(error_msg)
                            sync_result["errors"].append(error_msg)
            
            sync_result["success"] = len(sync_result["errors"]) == 0
            logger.info(f"Registry sync completed: {sync_result}")
            
        except Exception as e:
            error_msg = f"Registry sync failed: {e}"
            logger.error(error_msg)
            sync_result["errors"].append(error_msg)
        
        return sync_result
    
    def get_sources_for_province(self, province: str) -> List[Dict[str, Any]]:
        """
        Get sources for specific province.
        
        Args:
            province: Province name (guangdong, shandong, inner_mongolia)
            
        Returns:
            List of source configurations
        """
        try:
            sources = self.load_sources()
            return sources.get(province, [])
        except Exception as e:
            logger.error(f"Failed to get sources for {province}: {e}")
            return []
    
    def get_next_crawl_times(self) -> Dict[str, str]:
        """
        Calculate next crawl times for all sources based on cadence.
        
        Returns:
            Dictionary of domain -> next crawl time
        """
        next_crawl_times = {}
        
        try:
            sources = self.load_sources()
            
            for province, province_sources in sources.items():
                for source in province_sources:
                    domain = source.get("domain")
                    cadence = source.get("cadence", "")
                    
                    if not domain or not cadence:
                        continue
                    
                    try:
                        # Parse ISO8601 interval (simplified)
                        # Format: R/2025-01-01T00:00:00Z/P1D
                        if cadence.startswith("R/") and "/P" in cadence:
                            parts = cadence.split("/")
                            if len(parts) >= 3:
                                start_time = parts[1]  # Start time
                                interval = parts[2]   # Interval (e.g., P1D)
                                
                                # Simple interval parsing
                                if interval == "P1D":
                                    hours = 24
                                elif interval == "P2D":
                                    hours = 48
                                elif interval == "P3D":
                                    hours = 72
                                else:
                                    hours = 24  # Default to daily
                                
                                # Calculate next crawl time (simplified)
                                next_crawl = datetime.utcnow() + timedelta(hours=hours)
                                next_crawl_times[domain] = next_crawl.isoformat()
                    
                    except Exception as e:
                        logger.warning(f"Failed to parse cadence for {domain}: {e}")
                        # Default to 24 hours from now
                        next_crawl = datetime.utcnow() + timedelta(hours=24)
                        next_crawl_times[domain] = next_crawl.isoformat()
        
        except Exception as e:
            logger.error(f"Failed to calculate next crawl times: {e}")
        
        return next_crawl_times
    
    def validate_registry_file(self) -> Dict[str, Any]:
        """
        Validate registry file and return comprehensive report.
        
        Returns:
            Validation report with details
        """
        try:
            # Load and validate sources
            sources = self.load_sources()
            validation = self.validate_sources(sources)
            
            # Get domain validation
            domain_validation = validate_foundation_domains()
            
            # Calculate statistics
            total_sources = sum(len(province_sources) for province_sources in sources.values())
            enabled_sources = sum(
                len([s for s in province_sources if s.get("enabled", True)])
                for province_sources in sources.values()
            )
            
            return {
                "file_valid": validation["valid"],
                "file_errors": validation["errors"],
                "file_warnings": validation["warnings"],
                "total_sources": total_sources,
                "enabled_sources": enabled_sources,
                "allowlist_compliance": validation["allowlist_compliance"],
                "robots_compliance": validation["robots_compliance"],
                "domain_accessibility": domain_validation,
                "next_crawl_times": self.get_next_crawl_times(),
                "validation_timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            return {
                "file_valid": False,
                "file_errors": [str(e)],
                "file_warnings": [],
                "total_sources": 0,
                "enabled_sources": 0,
                "allowlist_compliance": False,
                "robots_compliance": {},
                "domain_accessibility": {"overall_status": "error"},
                "next_crawl_times": {},
                "validation_timestamp": datetime.utcnow().isoformat()
            }


def load_and_validate_registry() -> Dict[str, Any]:
    """
    Convenience function to load and validate registry.
    
    Returns:
        Complete validation report
    """
    loader = SimpleRegistryLoader()
    return loader.validate_registry_file()


def sync_registry_to_database() -> Dict[str, Any]:
    """
    Convenience function to sync registry to database.
    
    Returns:
        Sync result report
    """
    loader = SimpleRegistryLoader()
    return loader.sync_to_database()


if __name__ == "__main__":
    # Quick validation and sync
    import json
    
    print("=== Registry Validation ===")
    validation_report = load_and_validate_registry()
    print(json.dumps(validation_report, indent=2, ensure_ascii=False))
    
    if validation_report["file_valid"]:
        print("\n=== Syncing to Database ===")
        sync_report = sync_registry_to_database()
        print(json.dumps(sync_report, indent=2, ensure_ascii=False))
    else:
        print("\n❌ Registry validation failed, skipping database sync")