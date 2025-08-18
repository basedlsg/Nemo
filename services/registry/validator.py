"""Source registry validation utilities."""

import re
import logging
from typing import List, Dict, Any, Optional, Set
from dataclasses import dataclass
from urllib.parse import urlparse

import requests
from pydantic import ValidationError

from .models import RegistryConfig, SourceConfig, Priority, DocumentClass
from services.core.models import Province

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of registry validation."""
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    source_issues: Dict[str, List[str]]


class SourceRegistryValidator:
    """Validates source registry configuration and connectivity."""
    
    def __init__(self, check_connectivity: bool = False):
        """Initialize validator."""
        self.check_connectivity = check_connectivity
        self.timeout = 10  # seconds
    
    def validate_registry(self, registry: RegistryConfig) -> ValidationResult:
        """Validate complete registry configuration."""
        errors = []
        warnings = []
        source_issues = {}
        
        try:
            # Validate basic structure
            structure_errors = self._validate_registry_structure(registry)
            errors.extend(structure_errors)
            
            # Validate individual sources
            all_sources = self._get_all_sources(registry)
            for source in all_sources:
                source_errors, source_warnings = self._validate_source(source)
                
                if source_errors or source_warnings:
                    source_issues[source.domain] = source_errors + source_warnings
                
                errors.extend(source_errors)
                warnings.extend(source_warnings)
            
            # Validate cross-source consistency
            consistency_errors, consistency_warnings = self._validate_cross_source_consistency(all_sources)
            errors.extend(consistency_errors)
            warnings.extend(consistency_warnings)
            
            # Validate coverage requirements
            coverage_errors, coverage_warnings = self._validate_coverage_requirements(registry)
            errors.extend(coverage_errors)
            warnings.extend(coverage_warnings)
            
            # Check connectivity if requested
            if self.check_connectivity:
                connectivity_warnings = self._check_source_connectivity(all_sources)
                warnings.extend(connectivity_warnings)
            
            is_valid = len(errors) == 0
            
            return ValidationResult(
                is_valid=is_valid,
                errors=errors,
                warnings=warnings,
                source_issues=source_issues
            )
            
        except Exception as e:
            logger.error(f"Registry validation failed: {e}")
            return ValidationResult(
                is_valid=False,
                errors=[f"Validation error: {str(e)}"],
                warnings=[],
                source_issues={}
            )
    
    def validate_source_config(self, source: SourceConfig) -> ValidationResult:
        """Validate individual source configuration."""
        errors, warnings = self._validate_source(source)
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            source_issues={source.domain: errors + warnings} if errors or warnings else {}
        )
    
    def validate_domain_accessibility(self, domain: str) -> Dict[str, Any]:
        """Validate domain accessibility and robots.txt compliance."""
        result = {
            "domain": domain,
            "accessible": False,
            "robots_txt_exists": False,
            "robots_allows_crawling": False,
            "response_time_ms": None,
            "error": None
        }
        
        try:
            import time
            
            # Check main domain accessibility
            start_time = time.time()
            response = requests.get(f"https://{domain}", timeout=self.timeout, allow_redirects=True)
            end_time = time.time()
            
            result["accessible"] = response.status_code == 200
            result["response_time_ms"] = int((end_time - start_time) * 1000)
            
            # Check robots.txt
            robots_response = requests.get(f"https://{domain}/robots.txt", timeout=self.timeout)
            if robots_response.status_code == 200:
                result["robots_txt_exists"] = True
                
                # Basic check for crawling permissions
                robots_content = robots_response.text.lower()
                if "disallow: /" not in robots_content or "allow: /" in robots_content:
                    result["robots_allows_crawling"] = True
            
        except requests.RequestException as e:
            result["error"] = str(e)
        except Exception as e:
            result["error"] = f"Unexpected error: {str(e)}"
        
        return result
    
    def _validate_registry_structure(self, registry: RegistryConfig) -> List[str]:
        """Validate basic registry structure."""
        errors = []
        
        # Check version format
        if not re.match(r'^\d+\.\d+$', registry.version):
            errors.append(f"Invalid version format: {registry.version}")
        
        # Check maintainer
        if not registry.maintainer:
            errors.append("Maintainer is required")
        
        # Check that at least one province has sources
        total_sources = (
            len(registry.guangdong) + len(registry.shandong) + 
            len(registry.inner_mongolia) + len(registry.sichuan)
        )
        if total_sources == 0:
            errors.append("Registry must contain at least one source")
        
        # Validate global config
        try:
            # Check rate limiting values
            if registry.global_config.requests_per_minute <= 0:
                errors.append("requests_per_minute must be positive")
            
            if registry.global_config.concurrent_requests <= 0:
                errors.append("concurrent_requests must be positive")
            
            # Check content validation settings
            if registry.global_config.min_content_length >= registry.global_config.max_content_length:
                errors.append("min_content_length must be less than max_content_length")
            
        except Exception as e:
            errors.append(f"Global config validation error: {e}")
        
        return errors
    
    def _validate_source(self, source: SourceConfig) -> tuple[List[str], List[str]]:
        """Validate individual source configuration."""
        errors = []
        warnings = []
        
        # Validate domain format
        if not self._is_valid_domain(source.domain):
            errors.append(f"Invalid domain format: {source.domain}")
        
        # Check if domain is in official allowlist
        if not self._is_official_domain(source.domain):
            warnings.append(f"Domain not in official allowlist: {source.domain}")
        
        # Validate selectors
        if not source.selectors.index:
            errors.append(f"Index selector is required for {source.domain}")
        
        # Validate effective date locator
        if source.effective_date_locator.startswith("regex:"):
            regex_pattern = source.effective_date_locator[6:]
            try:
                re.compile(regex_pattern)
            except re.error as e:
                errors.append(f"Invalid regex in effective_date_locator for {source.domain}: {e}")
        
        # Validate document classes
        if not source.doc_classes:
            errors.append(f"At least one document class is required for {source.domain}")
        
        # Check priority vs enabled consistency
        if source.priority == Priority.HIGH and not source.enabled:
            warnings.append(f"High priority source is disabled: {source.domain}")
        
        # Validate cadence interval
        try:
            interval_hours = source.get_crawl_interval_hours()
            if interval_hours < 1:
                warnings.append(f"Very frequent crawling interval for {source.domain}: {interval_hours}h")
            elif interval_hours > 168:  # 1 week
                warnings.append(f"Very infrequent crawling interval for {source.domain}: {interval_hours}h")
        except Exception as e:
            errors.append(f"Invalid cadence format for {source.domain}: {e}")
        
        return errors, warnings
    
    def _validate_cross_source_consistency(self, sources: List[SourceConfig]) -> tuple[List[str], List[str]]:
        """Validate consistency across sources."""
        errors = []
        warnings = []
        
        # Check for duplicate domains
        domains = [source.domain for source in sources]
        duplicate_domains = set([domain for domain in domains if domains.count(domain) > 1])
        
        if duplicate_domains:
            errors.extend([f"Duplicate domain found: {domain}" for domain in duplicate_domains])
        
        # Check for conflicting configurations for same domain
        domain_configs = {}
        for source in sources:
            if source.domain in domain_configs:
                existing = domain_configs[source.domain]
                
                # Check for conflicting robots policies
                if existing.robots != source.robots:
                    warnings.append(f"Conflicting robots policy for {source.domain}")
                
                # Check for conflicting fetch methods
                if existing.fetch_method != source.fetch_method:
                    warnings.append(f"Conflicting fetch method for {source.domain}")
            else:
                domain_configs[source.domain] = source
        
        return errors, warnings
    
    def _validate_coverage_requirements(self, registry: RegistryConfig) -> tuple[List[str], List[str]]:
        """Validate coverage requirements for enabled provinces."""
        errors = []
        warnings = []
        
        enabled_provinces = [Province.GUANGDONG, Province.SHANDONG, Province.INNER_MONGOLIA]
        required_doc_classes = set(DocumentClass)
        
        for province in enabled_provinces:
            sources = registry.get_enabled_sources_by_province(province)
            
            if not sources:
                errors.append(f"No enabled sources for province: {province.value}")
                continue
            
            # Check document class coverage
            covered_doc_classes = set()
            for source in sources:
                covered_doc_classes.update(source.doc_classes)
            
            missing_doc_classes = required_doc_classes - covered_doc_classes
            if missing_doc_classes:
                missing_names = [dc.value for dc in missing_doc_classes]
                warnings.append(f"Incomplete doc class coverage for {province.value}: missing {missing_names}")
            
            # Check for at least one high priority source
            high_priority_sources = [s for s in sources if s.priority == Priority.HIGH]
            if not high_priority_sources:
                warnings.append(f"No high priority sources for province: {province.value}")
        
        # Check Sichuan (should be configured but disabled)
        sichuan_sources = registry.get_sources_by_province(Province.SICHUAN)
        if not sichuan_sources:
            warnings.append("Sichuan province has no configured sources (should be queued)")
        else:
            enabled_sichuan = [s for s in sichuan_sources if s.enabled]
            if enabled_sichuan:
                warnings.append("Sichuan sources are enabled (should be queued/disabled)")
        
        return errors, warnings
    
    def _check_source_connectivity(self, sources: List[SourceConfig]) -> List[str]:
        """Check connectivity to source domains."""
        warnings = []
        
        for source in sources:
            if not source.enabled:
                continue
            
            try:
                accessibility = self.validate_domain_accessibility(source.domain)
                
                if not accessibility["accessible"]:
                    warnings.append(f"Domain not accessible: {source.domain} - {accessibility.get('error', 'Unknown error')}")
                
                if accessibility["response_time_ms"] and accessibility["response_time_ms"] > 5000:
                    warnings.append(f"Slow response from {source.domain}: {accessibility['response_time_ms']}ms")
                
                if source.robots == "allow" and not accessibility["robots_allows_crawling"]:
                    warnings.append(f"Robots.txt may disallow crawling for {source.domain}")
                
            except Exception as e:
                warnings.append(f"Failed to check connectivity for {source.domain}: {e}")
        
        return warnings
    
    def _get_all_sources(self, registry: RegistryConfig) -> List[SourceConfig]:
        """Get all sources from registry."""
        return (
            registry.guangdong + registry.shandong + 
            registry.inner_mongolia + registry.sichuan
        )
    
    def _is_valid_domain(self, domain: str) -> bool:
        """Check if domain format is valid."""
        domain_pattern = r'^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*\.[a-zA-Z]{2,}$'
        return bool(re.match(domain_pattern, domain))
    
    def _is_official_domain(self, domain: str) -> bool:
        """Check if domain is in official allowlist."""
        official_patterns = [
            r'.*\.gov\.cn$',
            r'^gzpec\.cn$',
            r'^gdpec\.com\.cn$',
            r'^csg\.cn$',
            r'^shandong-electric\.com\.cn$',
            r'^sgcc\.com\.cn$',
            r'.*\.sgcc\.com\.cn$',
            r'^nmgdl\.cn$',
            r'^scpec\.com\.cn$',
        ]
        
        return any(re.match(pattern, domain) for pattern in official_patterns)


class RegistryHealthChecker:
    """Health checker for source registry."""
    
    def __init__(self, registry: RegistryConfig):
        """Initialize health checker."""
        self.registry = registry
        self.validator = SourceRegistryValidator(check_connectivity=True)
    
    def check_registry_health(self) -> Dict[str, Any]:
        """Perform comprehensive registry health check."""
        health_report = {
            "overall_status": "healthy",
            "timestamp": "2025-01-14T00:00:00Z",  # Would use datetime.utcnow().isoformat()
            "checks": {},
            "summary": {}
        }
        
        try:
            # Validate registry structure
            validation_result = self.validator.validate_registry(self.registry)
            
            health_report["checks"]["validation"] = {
                "status": "healthy" if validation_result.is_valid else "unhealthy",
                "errors": validation_result.errors,
                "warnings": validation_result.warnings,
                "source_issues_count": len(validation_result.source_issues)
            }
            
            # Check source coverage
            coverage_report = self.registry.validate_source_coverage()
            incomplete_provinces = [
                province for province, details in coverage_report.items()
                if not details["coverage_complete"]
            ]
            
            health_report["checks"]["coverage"] = {
                "status": "healthy" if not incomplete_provinces else "degraded",
                "incomplete_provinces": incomplete_provinces,
                "total_provinces": len(coverage_report),
                "complete_provinces": len(coverage_report) - len(incomplete_provinces)
            }
            
            # Check stale sources
            stale_sources = self.registry.get_stale_sources()
            health_report["checks"]["freshness"] = {
                "status": "healthy" if len(stale_sources) < 5 else "degraded",
                "stale_sources_count": len(stale_sources),
                "stale_sources": [s.domain for s in stale_sources[:10]]  # Limit to 10
            }
            
            # Determine overall status
            check_statuses = [check["status"] for check in health_report["checks"].values()]
            if "unhealthy" in check_statuses:
                health_report["overall_status"] = "unhealthy"
            elif "degraded" in check_statuses:
                health_report["overall_status"] = "degraded"
            
            # Summary
            health_report["summary"] = {
                "total_sources": len(self._get_all_sources()),
                "enabled_sources": len([s for s in self._get_all_sources() if s.enabled]),
                "validation_errors": len(validation_result.errors),
                "validation_warnings": len(validation_result.warnings),
                "provinces_with_complete_coverage": len(coverage_report) - len(incomplete_provinces)
            }
            
        except Exception as e:
            health_report["overall_status"] = "unhealthy"
            health_report["checks"]["system"] = {
                "status": "unhealthy",
                "error": str(e)
            }
        
        return health_report
    
    def _get_all_sources(self) -> List[SourceConfig]:
        """Get all sources from registry."""
        return (
            self.registry.guangdong + self.registry.shandong + 
            self.registry.inner_mongolia + self.registry.sichuan
        )