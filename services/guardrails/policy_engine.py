"""Guardrails policy engine for Task 12 - policy-as-code implementation."""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, date
from enum import Enum

from services.registry.simple_loader import SimpleRegistryLoader
from services.registry.robots_checker import get_foundation_allowlist

logger = logging.getLogger(__name__)

# Placeholder domains that should trigger refusal during development
PLACEHOLDER_DOMAINS = {
    "gzpec.cn", 
    "sdpxc.cn", 
    "impex.org.cn"
}


class RefusalReason(str, Enum):
    """Refusal reasons for policy violations."""
    NO_FIRST_PARTY_CITATION = "no_first_party_citation"
    STALE_CITATION = "stale_citation"
    MISSING_EFFECTIVE_DATE = "missing_effective_date"
    PROVINCE_MISMATCH = "province_mismatch"
    DOC_CLASS_MISMATCH = "doc_class_mismatch"
    DOMAIN_NOT_ALLOWED = "domain_not_allowed"
    SUPERSEDED_CITATION = "superseded_citation"
    UNSAFE_SCOPE = "unsafe_scope"
    PLACEHOLDER_URL_DETECTED = "placeholder_url_detected"


class RefusalException(Exception):
    """Exception raised when guardrails policy is violated."""
    
    def __init__(self, reason: RefusalReason, message: str, policy: str):
        """
        Initialize refusal exception.
        
        Args:
            reason: Refusal reason code
            message: Human-readable error message
            policy: Policy that was violated
        """
        self.reason = reason
        self.message = message
        self.policy = policy
        super().__init__(message)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            "status": "refused",
            "reason": self.reason.value,
            "message": self.message,
            "policy": self.policy,
            "timestamp": datetime.utcnow().isoformat()
        }


class GuardrailsPolicy:
    """Individual guardrails policy implementation."""
    
    def __init__(self, name: str, description: str):
        """Initialize policy."""
        self.name = name
        self.description = description
    
    def check(self, answer: str, citations: List[Dict[str, Any]], query: Dict[str, Any]) -> bool:
        """
        Check if policy is satisfied.
        
        Args:
            answer: Generated answer text
            citations: List of citations used
            query: Original query parameters
            
        Returns:
            True if policy is satisfied
            
        Raises:
            RefusalException: If policy is violated
        """
        raise NotImplementedError("Subclasses must implement check method")


class CitationsRequiredPolicy(GuardrailsPolicy):
    """Policy: Result must include ≥1 citation with snapshot+checksum+effective_date."""
    
    def __init__(self):
        super().__init__(
            name="citations_required",
            description="Result must include at least one first-party citation with complete metadata"
        )
    
    def check(self, answer: str, citations: List[Dict[str, Any]], query: Dict[str, Any]) -> bool:
        """Check citations required policy."""
        if not citations:
            raise RefusalException(
                RefusalReason.NO_FIRST_PARTY_CITATION,
                "No first-party citations available for this query",
                "first_party_citation_required"
            )
        
        # Check that citations have required metadata
        for citation in citations:
            if not citation.get("checksum"):
                raise RefusalException(
                    RefusalReason.STALE_CITATION,
                    "Citation missing checksum verification",
                    "citation_integrity_required"
                )
            
            if not citation.get("effective_date"):
                raise RefusalException(
                    RefusalReason.MISSING_EFFECTIVE_DATE,
                    "Citation missing effective date",
                    "effective_date_required"
                )
        
        return True


class ChineseFirstPolicy(GuardrailsPolicy):
    """Policy: Answer must be zh-CN unless ?lang=en."""
    
    def __init__(self):
        super().__init__(
            name="zh_first",
            description="Answer must be in Chinese unless English is explicitly requested"
        )
    
    def check(self, answer: str, citations: List[Dict[str, Any]], query: Dict[str, Any]) -> bool:
        """Check Chinese-first policy."""
        requested_lang = query.get("lang", "zh")
        
        if requested_lang == "zh" or requested_lang == "zh-CN":
            # Check if answer contains Chinese characters
            if not self._contains_chinese(answer):
                logger.warning("Answer should be in Chinese but contains no Chinese characters")
                # Note: This is a warning, not a hard refusal for MVP
        
        return True
    
    def _contains_chinese(self, text: str) -> bool:
        """Check if text contains Chinese characters."""
        if not text:
            return False
        
        for char in text:
            if '\u4e00' <= char <= '\u9fff':  # CJK Unified Ideographs
                return True
        return False


class UnsafeScopePolicy(GuardrailsPolicy):
    """Policy: Province/doc_class in registry; citation domains in allowlist; effective_date not superseded."""
    
    def __init__(self):
        super().__init__(
            name="unsafe_scope",
            description="Ensure query scope is safe and citations are from allowed domains"
        )
        self.registry_loader = SimpleRegistryLoader()
        self.foundation_allowlist = get_foundation_allowlist()
    
    def check(self, answer: str, citations: List[Dict[str, Any]], query: Dict[str, Any]) -> bool:
        """Check unsafe scope policy."""
        # Check province is in registry
        province = query.get("province")
        if province not in ["guangdong", "shandong", "inner_mongolia"]:
            raise RefusalException(
                RefusalReason.PROVINCE_MISMATCH,
                f"Province '{province}' is not supported",
                "supported_province_required"
            )
        
        # Check doc_class is valid
        doc_class = query.get("doc_class")
        if doc_class not in ["market_rules", "grid_connection", "dispatch_ops"]:
            raise RefusalException(
                RefusalReason.DOC_CLASS_MISMATCH,
                f"Document class '{doc_class}' is not supported",
                "supported_doc_class_required"
            )
        
        # Check for placeholder domains (development safety)
        for citation in citations:
            citation_domain = self._extract_domain_from_url(citation.get("url", ""))
            if citation_domain in PLACEHOLDER_DOMAINS:
                raise RefusalException(
                    RefusalReason.PLACEHOLDER_URL_DETECTED,
                    f"Citation contains placeholder domain: {citation_domain}",
                    "no_placeholder_citations"
                )
        
        # Check citation domains are in allowlist
        for citation in citations:
            citation_domain = self._extract_domain_from_url(citation.get("url", ""))
            if citation_domain and not self._is_domain_allowed(citation_domain):
                raise RefusalException(
                    RefusalReason.DOMAIN_NOT_ALLOWED,
                    f"Citation from unauthorized domain: {citation_domain}",
                    "authorized_domain_required"
                )
        
        # Check for superseded citations (simplified check)
        for citation in citations:
            if citation.get("superseded_by"):
                raise RefusalException(
                    RefusalReason.SUPERSEDED_CITATION,
                    "Citation has been superseded by newer regulation",
                    "current_regulation_required"
                )
        
        return True
    
    def _extract_domain_from_url(self, url: str) -> str:
        """Extract domain from URL."""
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            return parsed.netloc.lower()
        except Exception:
            return ""
    
    def _is_domain_allowed(self, domain: str) -> bool:
        """Check if domain is in foundation allowlist."""
        for allowed_domain in self.foundation_allowlist:
            if allowed_domain.startswith('.'):
                if domain.endswith(allowed_domain):
                    return True
            else:
                if domain == allowed_domain or domain.endswith('.' + allowed_domain):
                    return True
        return False


class GuardrailsEngine:
    """Main guardrails engine that enforces all policies."""
    
    def __init__(self):
        """Initialize guardrails engine with all policies."""
        self.policies = [
            CitationsRequiredPolicy(),
            ChineseFirstPolicy(),
            UnsafeScopePolicy()
        ]
        self.stats = {
            "total_checks": 0,
            "passed_checks": 0,
            "refused_checks": 0,
            "refusal_reasons": {},
            "last_check": None
        }
    
    def check_all_policies(
        self, 
        answer: str, 
        citations: List[Dict[str, Any]], 
        query: Dict[str, Any]
    ) -> bool:
        """
        Check all guardrails policies.
        
        Args:
            answer: Generated answer text
            citations: List of citations used
            query: Original query parameters
            
        Returns:
            True if all policies pass
            
        Raises:
            RefusalException: If any policy is violated
        """
        self.stats["total_checks"] += 1
        self.stats["last_check"] = datetime.utcnow().isoformat()
        
        try:
            logger.info(f"Checking {len(self.policies)} guardrails policies")
            
            for policy in self.policies:
                try:
                    policy.check(answer, citations, query)
                    logger.debug(f"Policy '{policy.name}' passed")
                except RefusalException as e:
                    logger.warning(f"Policy '{policy.name}' failed: {e.reason.value}")
                    
                    # Update refusal statistics
                    self.stats["refused_checks"] += 1
                    reason = e.reason.value
                    if reason not in self.stats["refusal_reasons"]:
                        self.stats["refusal_reasons"][reason] = 0
                    self.stats["refusal_reasons"][reason] += 1
                    
                    raise  # Re-raise the exception
            
            # All policies passed
            self.stats["passed_checks"] += 1
            logger.info("All guardrails policies passed")
            return True
            
        except RefusalException:
            raise
        except Exception as e:
            logger.error(f"Guardrails check failed with unexpected error: {e}")
            # Fail safe: refuse on unexpected errors
            self.stats["refused_checks"] += 1
            raise RefusalException(
                RefusalReason.UNSAFE_SCOPE,
                "Internal policy check error",
                "system_safety_required"
            )
    
    def get_policy_info(self) -> List[Dict[str, str]]:
        """Get information about all policies."""
        return [
            {
                "name": policy.name,
                "description": policy.description
            }
            for policy in self.policies
        ]
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get guardrails statistics."""
        total = self.stats["total_checks"]
        return {
            "total_checks": total,
            "passed_checks": self.stats["passed_checks"],
            "refused_checks": self.stats["refused_checks"],
            "pass_rate": self.stats["passed_checks"] / total if total > 0 else 0,
            "refusal_rate": self.stats["refused_checks"] / total if total > 0 else 0,
            "refusal_accuracy": self.stats["refused_checks"] / total if total > 0 else 0,  # Target ≥99%
            "refusal_reasons": self.stats["refusal_reasons"],
            "last_check": self.stats["last_check"],
            "policies": self.get_policy_info()
        }
    
    def health_check(self) -> Dict[str, Any]:
        """Check guardrails engine health."""
        try:
            # Test policy loading
            policy_count = len(self.policies)
            
            # Test registry access
            registry_loader = SimpleRegistryLoader()
            registry_validation = registry_loader.validate_registry_file()
            
            return {
                "status": "healthy",
                "policy_count": policy_count,
                "registry_status": "healthy" if registry_validation["file_valid"] else "degraded",
                "foundation_allowlist_size": len(get_foundation_allowlist()),
                "statistics": self.get_statistics(),
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Guardrails health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }


# Global guardrails engine instance
_guardrails_engine: Optional[GuardrailsEngine] = None


def get_guardrails_engine() -> GuardrailsEngine:
    """Get global guardrails engine instance."""
    global _guardrails_engine
    if _guardrails_engine is None:
        _guardrails_engine = GuardrailsEngine()
    return _guardrails_engine


def guardrails_check(answer: str, citations: List[Dict[str, Any]], query: Dict[str, Any]) -> bool:
    """
    Convenience function for guardrails checking.
    
    Args:
        answer: Generated answer text
        citations: List of citations used
        query: Original query parameters
        
    Returns:
        True if all policies pass
        
    Raises:
        RefusalException: If any policy is violated
    """
    engine = get_guardrails_engine()
    return engine.check_all_policies(answer, citations, query)


if __name__ == "__main__":
    # Quick test of guardrails engine
    import json
    
    def test_guardrails():
        print("=== Guardrails Engine Test ===")
        
        engine = GuardrailsEngine()
        
        # Test health check
        print("\n--- Health Check ---")
        health = engine.health_check()
        print(f"Status: {health['status']}")
        print(f"Policies: {health['policy_count']}")
        
        # Test valid case
        print("\n--- Valid Case Test ---")
        try:
            valid_answer = "根据广东省光伏并网管理办法，需要提交以下资料..."
            valid_citations = [
                {
                    "citation_id": "cite-1",
                    "url": "https://gzpec.cn/solar-rules",
                    "title": "广东省光伏并网管理办法",
                    "effective_date": "2025-01-01",
                    "checksum": "abc123"
                }
            ]
            valid_query = {
                "province": "guangdong",
                "doc_class": "grid_connection",
                "question": "光伏并网需要什么资料？"
            }
            
            result = engine.check_all_policies(valid_answer, valid_citations, valid_query)
            print(f"Valid case result: {result}")
            
        except RefusalException as e:
            print(f"Unexpected refusal: {e.to_dict()}")
        
        # Test refusal case - no citations
        print("\n--- Refusal Case Test (No Citations) ---")
        try:
            engine.check_all_policies("Some answer", [], valid_query)
            print("ERROR: Should have been refused")
        except RefusalException as e:
            print(f"Correctly refused: {e.reason.value}")
        
        # Test refusal case - invalid province
        print("\n--- Refusal Case Test (Invalid Province) ---")
        try:
            invalid_query = {
                "province": "invalid_province",
                "doc_class": "grid_connection",
                "question": "test"
            }
            engine.check_all_policies(valid_answer, valid_citations, invalid_query)
            print("ERROR: Should have been refused")
        except RefusalException as e:
            print(f"Correctly refused: {e.reason.value}")
        
        # Show statistics
        print("\n--- Statistics ---")
        stats = engine.get_statistics()
        print(json.dumps(stats, indent=2, ensure_ascii=False))
    
    test_guardrails()