"""Simplified Google CSE client for Task 6 foundation quartet."""

import asyncio
import logging
import time
from datetime import datetime
from typing import List, Dict, Any, Optional, Set
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode

import httpx

logger = logging.getLogger(__name__)


class SimpleCSEClient:
    """Simplified Google CSE client focused on foundation quartet requirements."""
    
    def __init__(self, api_key: Optional[str] = None, cse_id: Optional[str] = None, timeout: int = 30):
        """Initialize Google CSE client."""
        import os
        self.api_key = api_key or os.getenv("GOOGLE_CSE_API_KEY")
        self.cse_id = cse_id or os.getenv("GOOGLE_CSE_ENGINE_ID")
        
        # Check if real APIs are enabled
        self.enable_real_apis = os.getenv("ENABLE_REAL_APIS", "false").lower() == "true"
        self.enable_google_cse = os.getenv("ENABLE_GOOGLE_CSE", "false").lower() == "true"
        
        # Only require API keys if real APIs are enabled
        if self.enable_real_apis and self.enable_google_cse:
            if not self.api_key or self.api_key.startswith("demo"):
                logger.warning("Real Google CSE API enabled but no valid API key found. Using mock responses.")
                self.use_real_api = False
            elif not self.cse_id or self.cse_id.startswith("demo"):
                logger.warning("Real Google CSE API enabled but no valid engine ID found. Using mock responses.")
                self.use_real_api = False
            else:
                self.use_real_api = True
                logger.info("Using real Google CSE API")
        else:
            self.use_real_api = False
            logger.info("Using mock Google CSE responses")
        
        self.timeout = timeout
        self.base_url = "https://www.googleapis.com/customsearch/v1"
        
        # Only create HTTP client if using real API
        if self.use_real_api:
            self.client = httpx.AsyncClient(
                timeout=httpx.Timeout(timeout),
                headers={"User-Agent": "Geo-Adaptive-Energy-Assistant/1.0"}
            )
        else:
            self.client = None
        
        # Rate limiting (150 calls/day per unblocker plan)
        self.daily_limit = 150
        self.request_count = 0
        self.last_reset = datetime.utcnow().date()
    
    async def verify_urls(
        self, 
        query: str, 
        allowlist: Set[str],
        max_results: int = 10
    ) -> List[str]:
        """
        Verify URLs using Google CSE with canonicalization and allowlist filtering.
        
        Args:
            query: Search query
            allowlist: Set of allowed domains
            max_results: Maximum results to return
            
        Returns:
            List of canonical allowlisted URLs
        """
        try:
            # Check daily rate limit
            if not self._check_rate_limit():
                logger.warning("Daily rate limit exceeded for Google CSE API")
                return []
            
            # Perform search
            search_results = await self._search_with_retries(query, max_results)
            
            # Process and filter results
            verified_urls = []
            for result in search_results:
                url = result.get("link", "")
                if not url:
                    continue
                
                # Canonicalize URL
                canonical_url = self._canonicalize_url(url)
                
                # Check allowlist
                if self._is_url_allowed(canonical_url, allowlist):
                    verified_urls.append(canonical_url)
            
            # Remove duplicates while preserving order
            unique_urls = []
            seen = set()
            for url in verified_urls:
                if url not in seen:
                    unique_urls.append(url)
                    seen.add(url)
            
            self.request_count += 1
            logger.info(f"Verified {len(unique_urls)} URLs from {len(search_results)} search results")
            
            return unique_urls[:max_results]
            
        except Exception as e:
            logger.error(f"URL verification failed for query '{query}': {e}")
            return []
    
    async def verify_candidate_urls(
        self,
        candidates: List[Dict[str, Any]],
        allowlist: Set[str]
    ) -> List[Dict[str, Any]]:
        """
        Verify candidate URLs from discovery results.
        
        Args:
            candidates: List of candidate dictionaries with 'url' and 'title'
            allowlist: Set of allowed domains
            
        Returns:
            List of verified candidate dictionaries with canonical URLs
        """
        verified_candidates = []
        
        for candidate in candidates:
            original_url = candidate.get("url", "")
            title = candidate.get("title", "")
            
            if not original_url:
                continue
            
            try:
                # Canonicalize URL
                canonical_url = self._canonicalize_url(original_url)
                
                # Check allowlist
                if self._is_url_allowed(canonical_url, allowlist):
                    verified_candidate = {
                        "original_url": original_url,
                        "canonical_url": canonical_url,
                        "title": title,
                        "domain": self._extract_domain(canonical_url),
                        "verified_at": datetime.utcnow().isoformat(),
                        "verification_method": "canonicalization"
                    }
                    
                    # Copy other fields from original candidate
                    for key, value in candidate.items():
                        if key not in verified_candidate:
                            verified_candidate[key] = value
                    
                    verified_candidates.append(verified_candidate)
                else:
                    logger.debug(f"URL filtered by allowlist: {canonical_url}")
            
            except Exception as e:
                logger.error(f"Failed to verify candidate URL {original_url}: {e}")
        
        logger.info(f"Verified {len(verified_candidates)} candidates from {len(candidates)} inputs")
        return verified_candidates
    
    async def health_check(self) -> Dict[str, Any]:
        """Check Google CSE API health and rate limit status."""
        try:
            # Simple test search
            test_query = "site:gov.cn 能源"
            
            start_time = time.time()
            
            # Only test if we have quota
            if self.request_count < self.daily_limit:
                await self._search_with_retries(test_query, max_results=1)
                latency_ms = int((time.time() - start_time) * 1000)
                status = "healthy"
            else:
                latency_ms = None
                status = "rate_limited"
            
            return {
                "status": status,
                "latency_ms": latency_ms,
                "daily_requests_used": self.request_count,
                "daily_requests_remaining": self.daily_limit - self.request_count,
                "rate_limit_reset_date": self.last_reset.isoformat()
            }
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "daily_requests_used": self.request_count,
                "daily_requests_remaining": self.daily_limit - self.request_count
            }
    
    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()
    
    def _check_rate_limit(self) -> bool:
        """Check if we're within daily rate limit."""
        current_date = datetime.utcnow().date()
        
        # Reset counter if new day
        if current_date > self.last_reset:
            self.request_count = 0
            self.last_reset = current_date
        
        return self.request_count < self.daily_limit
    
    async def _search_with_retries(self, query: str, max_results: int = 10) -> List[Dict[str, Any]]:
        """Perform Google CSE search with retry logic."""
        max_retries = 3
        base_delay = 1
        
        for attempt in range(max_retries):
            try:
                # Build request parameters
                params = {
                    "key": self.api_key,
                    "cx": self.cse_id,
                    "q": query,
                    "num": min(max_results, 10),  # CSE max is 10 per request
                    "lr": "lang_zh-CN",  # Prefer Chinese results
                    "safe": "off",
                    "fields": "items(title,link,snippet,displayLink)"
                }
                
                # Make request
                response = await self.client.get(self.base_url, params=params)
                response.raise_for_status()
                
                data = response.json()
                return data.get("items", [])
                
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429:  # Rate limited
                    if attempt < max_retries - 1:
                        delay = base_delay * (2 ** attempt)
                        logger.warning(f"CSE rate limited, retrying in {delay}s")
                        await asyncio.sleep(delay)
                        continue
                raise
            except httpx.TimeoutException:
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    logger.warning(f"CSE request timeout, retrying in {delay}s")
                    await asyncio.sleep(delay)
                    continue
                raise
        
        raise Exception("Max retries exceeded")
    
    def _canonicalize_url(self, url: str) -> str:
        """
        Canonicalize URL: follow redirects, strip tracking params, force https.
        
        Note: This is a simplified version. In production, you'd want to:
        - Actually follow redirects with HTTP requests
        - Have a comprehensive list of tracking parameters
        - Handle more edge cases
        """
        try:
            parsed = urlparse(url)
            
            # Force HTTPS
            if parsed.scheme == "http":
                parsed = parsed._replace(scheme="https")
            
            # Strip common tracking parameters
            tracking_params = {
                "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
                "fbclid", "gclid", "msclkid", "ref", "source", "from", "spm"
            }
            
            if parsed.query:
                query_params = parse_qs(parsed.query, keep_blank_values=True)
                
                # Remove tracking parameters
                filtered_params = {
                    key: value for key, value in query_params.items()
                    if key.lower() not in tracking_params
                }
                
                # Rebuild query string
                if filtered_params:
                    new_query = urlencode(filtered_params, doseq=True)
                    parsed = parsed._replace(query=new_query)
                else:
                    parsed = parsed._replace(query="")
            
            # Remove fragment (anchor)
            parsed = parsed._replace(fragment="")
            
            # Normalize path (remove trailing slash for non-root paths)
            if parsed.path and parsed.path != "/" and parsed.path.endswith("/"):
                parsed = parsed._replace(path=parsed.path.rstrip("/"))
            
            return urlunparse(parsed)
            
        except Exception as e:
            logger.debug(f"URL canonicalization failed for {url}: {e}")
            return url  # Return original URL if canonicalization fails
    
    def _is_url_allowed(self, url: str, allowlist: Set[str]) -> bool:
        """Check if URL domain is in allowlist."""
        try:
            domain = self._extract_domain(url)
            
            for allowed_domain in allowlist:
                if allowed_domain.startswith('.'):
                    # Suffix match (e.g., .gov.cn)
                    if domain.endswith(allowed_domain):
                        return True
                else:
                    # Exact match or subdomain
                    if domain == allowed_domain or domain.endswith('.' + allowed_domain):
                        return True
            
            return False
            
        except Exception:
            return False
    
    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL."""
        try:
            parsed = urlparse(url)
            return parsed.netloc.lower()
        except Exception:
            return ""


def verify_urls_with_cse(
    query: str,
    allowlist: Set[str],
    api_key: Optional[str] = None,
    cse_id: Optional[str] = None
) -> List[str]:
    """
    Convenience function for synchronous URL verification.
    
    Args:
        query: Search query
        allowlist: Set of allowed domains
        api_key: Google CSE API key (optional, uses env var)
        cse_id: Google CSE engine ID (optional, uses env var)
        
    Returns:
        List of verified canonical URLs
    """
    async def _verify():
        client = SimpleCSEClient(api_key, cse_id)
        try:
            return await client.verify_urls(query, allowlist)
        finally:
            await client.close()
    
    return asyncio.run(_verify())


if __name__ == "__main__":
    # Quick test with foundation quartet domains
    import json
    
    foundation_allowlist = {"gzpec.cn", "sdpxc.cn", "impex.org.cn"}
    
    print("=== Testing Google CSE Verification ===")
    
    test_queries = [
        "site:gzpec.cn 电力市场规则",
        "site:sdpxc.cn 并网管理办法",
        "site:impex.org.cn 调度规定"
    ]
    
    for query in test_queries:
        print(f"\n--- Query: {query} ---")
        
        try:
            results = verify_urls_with_cse(query, foundation_allowlist)
            print(f"Found {len(results)} verified URLs:")
            
            for i, url in enumerate(results[:3], 1):  # Show first 3
                print(f"{i}. {url}")
        
        except Exception as e:
            print(f"Error: {e}")
    
    print("\n=== Health Check ===")
    
    async def test_health():
        client = SimpleCSEClient()
        try:
            health = await client.health_check()
            print(json.dumps(health, indent=2))
        finally:
            await client.close()
    
    asyncio.run(test_health())
    
    print("\n=== URL Canonicalization Test ===")
    
    test_urls = [
        "http://gzpec.cn/rules?utm_source=google&ref=search",
        "https://sdpxc.cn/documents/",
        "https://impex.org.cn/dispatch#section1"
    ]
    
    client = SimpleCSEClient()
    for url in test_urls:
        canonical = client._canonicalize_url(url)
        print(f"Original:  {url}")
        print(f"Canonical: {canonical}")
        print()