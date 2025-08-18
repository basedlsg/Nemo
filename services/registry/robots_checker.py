"""Robots.txt validation utilities for Task 4."""

import logging
from typing import Dict, Any, Set
from urllib.parse import urlparse

import requests

logger = logging.getLogger(__name__)


def host_allowed(url: str, allowlist: Set[str]) -> bool:
    """
    Check if URL host is in allowlist.
    
    Args:
        url: URL to check
        allowlist: Set of allowed domains
        
    Returns:
        True if host is allowed
    """
    try:
        host = urlparse(url).netloc
        return any(host == d or host.endswith(f".{d}") for d in allowlist)
    except Exception as e:
        logger.error(f"Failed to parse URL {url}: {e}")
        return False


def respects_robots(base: str) -> bool:
    """
    Check if domain respects robots.txt (allows crawling).
    
    Args:
        base: Base domain (e.g., "gzpec.cn")
        
    Returns:
        True if crawling is allowed
    """
    try:
        robots_url = f"https://{base}/robots.txt"
        response = requests.get(robots_url, timeout=10)
        
        if response.status_code != 200:
            # No robots.txt found, assume allowed
            logger.debug(f"No robots.txt found for {base}, assuming allowed")
            return True
        
        robots_content = response.text.lower()
        
        # Simple check: if "disallow: /" is present, crawling is not allowed
        if "disallow: /" in robots_content:
            logger.warning(f"Robots.txt disallows crawling for {base}")
            return False
        
        logger.debug(f"Robots.txt allows crawling for {base}")
        return True
        
    except requests.RequestException as e:
        logger.warning(f"Failed to check robots.txt for {base}: {e}")
        # If we can't check robots.txt, assume allowed to avoid blocking
        return True
    except Exception as e:
        logger.error(f"Unexpected error checking robots.txt for {base}: {e}")
        return True


def validate_domain_allowlist(domains: Set[str]) -> Dict[str, Any]:
    """
    Validate that all domains in allowlist are properly formatted.
    
    Args:
        domains: Set of domain names to validate
        
    Returns:
        Validation result with details
    """
    result = {
        "valid_domains": [],
        "invalid_domains": [],
        "total_domains": len(domains),
        "validation_errors": []
    }
    
    for domain in domains:
        try:
            # Basic domain format validation
            if not domain or "." not in domain:
                result["invalid_domains"].append(domain)
                result["validation_errors"].append(f"Invalid domain format: {domain}")
                continue
            
            # Check for valid characters
            if not all(c.isalnum() or c in ".-" for c in domain):
                result["invalid_domains"].append(domain)
                result["validation_errors"].append(f"Invalid characters in domain: {domain}")
                continue
            
            # Check for proper TLD
            parts = domain.split(".")
            if len(parts) < 2 or len(parts[-1]) < 2:
                result["invalid_domains"].append(domain)
                result["validation_errors"].append(f"Invalid TLD in domain: {domain}")
                continue
            
            result["valid_domains"].append(domain)
            
        except Exception as e:
            result["invalid_domains"].append(domain)
            result["validation_errors"].append(f"Error validating {domain}: {e}")
    
    return result


def check_domain_accessibility(domain: str, timeout: int = 10) -> Dict[str, Any]:
    """
    Check if domain is accessible and get basic info.
    
    Args:
        domain: Domain to check
        timeout: Request timeout in seconds
        
    Returns:
        Accessibility result with details
    """
    result = {
        "domain": domain,
        "accessible": False,
        "status_code": None,
        "response_time_ms": None,
        "robots_allows": False,
        "error": None
    }
    
    try:
        import time
        
        # Check main domain
        start_time = time.time()
        response = requests.get(f"https://{domain}", timeout=timeout, allow_redirects=True)
        end_time = time.time()
        
        result["accessible"] = response.status_code == 200
        result["status_code"] = response.status_code
        result["response_time_ms"] = int((end_time - start_time) * 1000)
        
        # Check robots.txt
        result["robots_allows"] = respects_robots(domain)
        
    except requests.RequestException as e:
        result["error"] = f"Request failed: {str(e)}"
    except Exception as e:
        result["error"] = f"Unexpected error: {str(e)}"
    
    return result


def get_foundation_allowlist() -> Set[str]:
    """
    Get the foundation quartet allowlist domains.
    
    Returns:
        Set of allowed domains for foundation implementation
    """
    return {
        "gzpec.cn",      # Guangdong Power Exchange Center
        "sdpxc.cn",      # Shandong Power Exchange Center  
        "impex.org.cn"   # Inner Mongolia Power Exchange Center
    }


def validate_foundation_domains() -> Dict[str, Any]:
    """
    Validate all foundation quartet domains.
    
    Returns:
        Comprehensive validation report
    """
    allowlist = get_foundation_allowlist()
    
    validation_report = {
        "allowlist": list(allowlist),
        "total_domains": len(allowlist),
        "accessible_domains": [],
        "inaccessible_domains": [],
        "robots_compliant": [],
        "robots_blocked": [],
        "validation_timestamp": "2025-01-14T00:00:00Z",  # Would use datetime.utcnow().isoformat()
        "overall_status": "unknown"
    }
    
    accessible_count = 0
    robots_compliant_count = 0
    
    for domain in allowlist:
        logger.info(f"Validating domain: {domain}")
        
        accessibility = check_domain_accessibility(domain)
        
        if accessibility["accessible"]:
            validation_report["accessible_domains"].append({
                "domain": domain,
                "status_code": accessibility["status_code"],
                "response_time_ms": accessibility["response_time_ms"]
            })
            accessible_count += 1
        else:
            validation_report["inaccessible_domains"].append({
                "domain": domain,
                "error": accessibility["error"]
            })
        
        if accessibility["robots_allows"]:
            validation_report["robots_compliant"].append(domain)
            robots_compliant_count += 1
        else:
            validation_report["robots_blocked"].append(domain)
    
    # Determine overall status
    if accessible_count == len(allowlist) and robots_compliant_count == len(allowlist):
        validation_report["overall_status"] = "healthy"
    elif accessible_count > 0:
        validation_report["overall_status"] = "degraded"
    else:
        validation_report["overall_status"] = "unhealthy"
    
    validation_report["summary"] = {
        "accessible_count": accessible_count,
        "robots_compliant_count": robots_compliant_count,
        "success_rate": accessible_count / len(allowlist) if allowlist else 0,
        "robots_compliance_rate": robots_compliant_count / len(allowlist) if allowlist else 0
    }
    
    return validation_report


if __name__ == "__main__":
    # Quick validation script
    import json
    
    print("=== Foundation Quartet Domain Validation ===")
    report = validate_foundation_domains()
    print(json.dumps(report, indent=2, ensure_ascii=False))
    
    print(f"\n=== Summary ===")
    print(f"Total domains: {report['total_domains']}")
    print(f"Accessible: {report['summary']['accessible_count']}")
    print(f"Robots compliant: {report['summary']['robots_compliant_count']}")
    print(f"Overall status: {report['overall_status']}")