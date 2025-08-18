"""Google Custom Search Engine (CSE) client for document verification."""

import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from urllib.parse import urlparse, quote

import httpx
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings

from .models import CSESearchResult, VerificationCandidate, VerificationStatus, VerificationMethod

logger = logging.getLogger(__name__)


class GoogleCSEConfig(BaseSettings):
    """Configuration for Google CSE client."""
    
    api_key: str = Field(..., env="GOOGLE_API_KEY")
    cse_id: str = Field(..., env="GOOGLE_CSE_ID")
    base_url: str = Field(default="https://www.googleapis.com/customsearch/v1", env="GOOGLE_CSE_BASE_URL")
    timeout: int = Field(default=30, env="GOOGLE_CSE_TIMEOUT")
    max_retries: int = Field(default=3, env="GOOGLE_CSE_MAX_RETRIES")
    retry_delay: int = Field(default=1, env="GOOGLE_CSE_RETRY_DELAY")
    requests_per_day: int = Field(default=100, env="GOOGLE_CSE_REQUESTS_PER_DAY")
    requests_per_100_seconds: int = Field(default=100, env="GOOGLE_CSE_REQUESTS_PER_100S")
    
    class Config:
        env_file = ".env"


class CSERateLimiter:
    """Rate limiter for Google CSE API with daily and per-100-seconds limits."""
    
    def __init__(self, requests_per_day: int, requests_per_100_seconds: int):
        self.requests_per_day = requests_per_day
        self.requests_per_100_seconds = requests_per_100_seconds
        
        # Track requests
        self.daily_requests = []
        self.recent_requests = []
        self.lock = asyncio.Lock()
    
    async def acquire(self) -> bool:
        """Acquire rate limit slot."""
        async with self.lock:
            now = time.time()
            
            # Clean up old requests
            self._cleanup_requests(now)
            
            # Check daily limit
            if len(self.daily_requests) >= self.requests_per_day:
                return False
            
            # Check 100-second limit
            if len(self.recent_requests) >= self.requests_per_100_seconds:
                return False
            
            # Add request to tracking
            self.daily_requests.append(now)
            self.recent_requests.append(now)
            
            return True
    
    def _cleanup_requests(self, now: float) -> None:
        """Remove old requests from tracking."""
        # Remove requests older than 24 hours
        day_ago = now - (24 * 60 * 60)
        self.daily_requests = [req_time for req_time in self.daily_requests if req_time > day_ago]
        
        # Remove requests older than 100 seconds
        hundred_seconds_ago = now - 100
        self.recent_requests = [req_time for req_time in self.recent_requests if req_time > hundred_seconds_ago]
    
    def get_reset_times(self) -> Dict[str, Optional[datetime]]:
        """Get reset times for rate limits."""
        now = time.time()
        
        daily_reset = None
        if self.daily_requests:
            oldest_daily = min(self.daily_requests)
            daily_reset = datetime.fromtimestamp(oldest_daily + (24 * 60 * 60))
        
        recent_reset = None
        if self.recent_requests:
            oldest_recent = min(self.recent_requests)
            recent_reset = datetime.fromtimestamp(oldest_recent + 100)
        
        return {
            "daily_reset": daily_reset,
            "recent_reset": recent_reset
        }
    
    def get_remaining_quota(self) -> Dict[str, int]:
        """Get remaining quota for both limits."""
        return {
            "daily_remaining": max(0, self.requests_per_day - len(self.daily_requests)),
            "recent_remaining": max(0, self.requests_per_100_seconds - len(self.recent_requests))
        }


class GoogleCSEClient:
    """Client for Google Custom Search Engine API."""
    
    def __init__(self, config: Optional[GoogleCSEConfig] = None):
        """Initialize Google CSE client."""
        self.config = config or GoogleCSEConfig()
        self.rate_limiter = CSERateLimiter(
            self.config.requests_per_day,
            self.config.requests_per_100_seconds
        )
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(self.config.timeout),
            headers={"User-Agent": "Geo-Adaptive-Energy-Assistant/1.0"}
        )
    
    async def verify_document(
        self,
        original_url: str,
        domain_allowlist: List[str],
        title_hint: Optional[str] = None
    ) -> VerificationCandidate:
        """Verify a single document using Google CSE."""
        start_time = time.time()
        
        try:
            # Check rate limit
            if not await self.rate_limiter.acquire():
                logger.warning("Rate limit exceeded for Google CSE API")
                return VerificationCandidate(
                    original_url=original_url,
                    domain=self._extract_domain(original_url),
                    verification_status=VerificationStatus.RATE_LIMITED,
                    error_message="Rate limit exceeded"
                )
            
            # Build search query
            search_query = self._build_verification_query(original_url, title_hint)
            
            # Perform search
            search_results = await self._search_with_retries(search_query, domain_allowlist)
            
            # Find best match
            best_match = self._find_best_match(search_results, original_url, title_hint)
            
            if best_match:
                # Create verified candidate
                candidate = VerificationCandidate(
                    original_url=original_url,
                    domain=self._extract_domain(original_url),
                    verification_status=VerificationStatus.VERIFIED,
                    verification_method=VerificationMethod.GOOGLE_CSE,
                    canonical_url=best_match.link,
                    verified_title=best_match.title,
                    verified_snippet=best_match.snippet,
                    verification_confidence=best_match.calculate_relevance_score(original_url, title_hint),
                    verified_at=datetime.utcnow()
                )
                
                # Try to get additional metadata
                await self._enrich_candidate_metadata(candidate)
                
                return candidate
            else:
                # Not found in search results
                return VerificationCandidate(
                    original_url=original_url,
                    domain=self._extract_domain(original_url),
                    verification_status=VerificationStatus.NOT_FOUND,
                    verification_method=VerificationMethod.GOOGLE_CSE,
                    error_message="Document not found in search results"
                )
        
        except Exception as e:
            logger.error(f"Document verification failed for {original_url}: {e}")
            return VerificationCandidate(
                original_url=original_url,
                domain=self._extract_domain(original_url),
                verification_status=VerificationStatus.FAILED,
                verification_method=VerificationMethod.GOOGLE_CSE,
                error_message=str(e)
            )
    
    async def verify_documents_batch(
        self,
        candidates: List[Dict[str, Any]],
        domain_allowlist: List[str],
        batch_delay: float = 1.0
    ) -> List[VerificationCandidate]:
        """Verify multiple documents with rate limiting."""
        verified_candidates = []
        
        for i, candidate_data in enumerate(candidates):
            original_url = candidate_data.get("url")
            title_hint = candidate_data.get("title")
            
            if not original_url:
                logger.warning("Skipping candidate without URL")
                continue
            
            # Verify document
            verified_candidate = await self.verify_document(
                original_url, domain_allowlist, title_hint
            )
            
            # Copy discovery confidence if available
            if "confidence_score" in candidate_data:
                verified_candidate.discovery_confidence = candidate_data["confidence_score"]
            
            verified_candidates.append(verified_candidate)
            
            # Add delay between requests (except for last request)
            if i < len(candidates) - 1:
                await asyncio.sleep(batch_delay)
        
        return verified_candidates
    
    async def search_documents(
        self,
        query: str,
        domain_allowlist: List[str],
        max_results: int = 10
    ) -> List[CSESearchResult]:
        """Search for documents using Google CSE."""
        try:
            # Check rate limit
            if not await self.rate_limiter.acquire():
                logger.warning("Rate limit exceeded for Google CSE search")
                return []
            
            # Perform search
            search_results = await self._search_with_retries(query, domain_allowlist, max_results)
            return search_results
            
        except Exception as e:
            logger.error(f"Document search failed: {e}")
            return []
    
    async def health_check(self) -> Dict[str, Any]:
        """Check Google CSE API health and quota."""
        try:
            # Get quota information
            quota = self.rate_limiter.get_remaining_quota()
            reset_times = self.rate_limiter.get_reset_times()
            
            # Try a simple search to test connectivity
            test_query = "site:gov.cn 能源"
            start_time = time.time()
            
            # Only test if we have quota
            if quota["daily_remaining"] > 0 and quota["recent_remaining"] > 0:
                await self._search_with_retries(test_query, [".gov.cn"], max_results=1)
                latency_ms = int((time.time() - start_time) * 1000)
                status = "healthy"
            else:
                latency_ms = None
                status = "rate_limited"
            
            return {
                "status": status,
                "latency_ms": latency_ms,
                "quota": quota,
                "reset_times": {
                    "daily_reset": reset_times["daily_reset"].isoformat() if reset_times["daily_reset"] else None,
                    "recent_reset": reset_times["recent_reset"].isoformat() if reset_times["recent_reset"] else None
                },
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()
    
    def _build_verification_query(self, url: str, title_hint: Optional[str] = None) -> str:
        """Build search query for document verification."""
        domain = self._extract_domain(url)
        
        # Start with site-specific search
        query_parts = [f"site:{domain}"]
        
        # Add URL path components
        try:
            parsed = urlparse(url)
            path_parts = [part for part in parsed.path.split('/') if part and len(part) > 2]
            query_parts.extend(path_parts[:3])  # Limit to first 3 path components
        except Exception:
            pass
        
        # Add title words if available
        if title_hint:
            # Extract key words from title (Chinese and English)
            title_words = []
            for word in title_hint.split():
                if len(word) > 1:  # Skip single characters
                    title_words.append(word)
            
            # Add most relevant title words
            query_parts.extend(title_words[:5])
        
        return " ".join(query_parts)
    
    async def _search_with_retries(
        self,
        query: str,
        domain_allowlist: List[str],
        max_results: int = 10
    ) -> List[CSESearchResult]:
        """Perform search with retry logic."""
        last_exception = None
        
        for attempt in range(self.config.max_retries):
            try:
                # Build request parameters
                params = {
                    "key": self.config.api_key,
                    "cx": self.config.cse_id,
                    "q": query,
                    "num": min(max_results, 10),  # CSE max is 10 per request
                    "lr": "lang_zh-CN",  # Prefer Chinese results
                    "safe": "off",
                    "fields": "items(title,link,snippet,displayLink,formattedUrl,htmlTitle,htmlSnippet,cacheId)"
                }
                
                # Make request
                response = await self.client.get(self.config.base_url, params=params)
                response.raise_for_status()
                
                data = response.json()
                
                # Parse results
                results = []
                items = data.get("items", [])
                
                for item in items:
                    # Check if result is from allowed domain
                    result_domain = self._extract_domain(item.get("link", ""))
                    if self._is_domain_allowed(result_domain, domain_allowlist):
                        results.append(CSESearchResult(**item))
                
                return results
                
            except httpx.HTTPStatusError as e:
                last_exception = e
                
                # Don't retry on client errors (4xx)
                if 400 <= e.response.status_code < 500:
                    if e.response.status_code == 429:  # Rate limited
                        logger.warning("Google CSE rate limit exceeded")
                    raise
                
                # Retry on server errors (5xx)
                if attempt < self.config.max_retries - 1:
                    delay = self.config.retry_delay * (2 ** attempt)
                    logger.warning(f"Google CSE error {e.response.status_code}, retrying in {delay}s")
                    await asyncio.sleep(delay)
                
            except Exception as e:
                last_exception = e
                
                if attempt < self.config.max_retries - 1:
                    delay = self.config.retry_delay * (2 ** attempt)
                    logger.warning(f"Google CSE request failed, retrying in {delay}s: {e}")
                    await asyncio.sleep(delay)
        
        # All retries failed
        raise last_exception
    
    def _find_best_match(
        self,
        search_results: List[CSESearchResult],
        original_url: str,
        title_hint: Optional[str] = None
    ) -> Optional[CSESearchResult]:
        """Find best matching result from search results."""
        if not search_results:
            return None
        
        # Calculate relevance scores for all results
        scored_results = []
        for result in search_results:
            score = result.calculate_relevance_score(original_url, title_hint)
            scored_results.append((result, score))
        
        # Sort by score (descending)
        scored_results.sort(key=lambda x: x[1], reverse=True)
        
        # Return best match if score is above threshold
        best_result, best_score = scored_results[0]
        if best_score >= 0.3:  # Minimum relevance threshold
            return best_result
        
        return None
    
    async def _enrich_candidate_metadata(self, candidate: VerificationCandidate) -> None:
        """Enrich candidate with additional metadata via HEAD request."""
        try:
            # Make HEAD request to get metadata
            response = await self.client.head(
                candidate.get_final_url(),
                follow_redirects=True,
                timeout=10
            )
            
            candidate.http_status_code = response.status_code
            candidate.content_type = response.headers.get("content-type")
            candidate.content_length = int(response.headers.get("content-length", 0)) or None
            
            # Parse last-modified header
            last_modified_str = response.headers.get("last-modified")
            if last_modified_str:
                try:
                    from email.utils import parsedate_to_datetime
                    candidate.last_modified = parsedate_to_datetime(last_modified_str)
                except Exception:
                    pass
            
        except Exception as e:
            logger.debug(f"Failed to enrich metadata for {candidate.get_final_url()}: {e}")
            # Don't fail verification if metadata enrichment fails
    
    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL."""
        try:
            parsed = urlparse(url)
            return parsed.netloc.lower()
        except Exception:
            return ""
    
    def _is_domain_allowed(self, domain: str, domain_allowlist: List[str]) -> bool:
        """Check if domain is in allowlist."""
        for allowed_domain in domain_allowlist:
            if allowed_domain.startswith('.'):
                # Suffix match (e.g., .gov.cn)
                if domain.endswith(allowed_domain):
                    return True
            else:
                # Exact match or subdomain
                if domain == allowed_domain or domain.endswith('.' + allowed_domain):
                    return True
        return False


class GoogleCSEMockClient:
    """Mock client for testing purposes."""
    
    def __init__(self, mock_responses: Optional[Dict[str, Any]] = None):
        """Initialize mock client with predefined responses."""
        self.mock_responses = mock_responses or {}
        self.request_count = 0
    
    async def verify_document(
        self,
        original_url: str,
        domain_allowlist: List[str],
        title_hint: Optional[str] = None
    ) -> VerificationCandidate:
        """Mock document verification."""
        self.request_count += 1
        
        # Simulate processing time
        await asyncio.sleep(0.1)
        
        domain = self._extract_domain(original_url)
        
        # Check if domain is allowed
        if not self._is_domain_allowed(domain, domain_allowlist):
            return VerificationCandidate(
                original_url=original_url,
                domain=domain,
                verification_status=VerificationStatus.NOT_FOUND,
                verification_method=VerificationMethod.GOOGLE_CSE,
                error_message="Domain not in allowlist"
            )
        
        # Mock successful verification for official domains
        if any(official in domain for official in ["gov.cn", "gzpec.cn", "sgcc.com.cn"]):
            return VerificationCandidate(
                original_url=original_url,
                domain=domain,
                verification_status=VerificationStatus.VERIFIED,
                verification_method=VerificationMethod.GOOGLE_CSE,
                canonical_url=original_url,
                verified_title=title_hint or "Mock Document Title",
                verified_snippet="Mock document snippet for testing",
                verification_confidence=0.85,
                http_status_code=200,
                content_type="text/html",
                verified_at=datetime.utcnow()
            )
        else:
            return VerificationCandidate(
                original_url=original_url,
                domain=domain,
                verification_status=VerificationStatus.NOT_FOUND,
                verification_method=VerificationMethod.GOOGLE_CSE,
                error_message="Document not found in mock search"
            )
    
    async def verify_documents_batch(
        self,
        candidates: List[Dict[str, Any]],
        domain_allowlist: List[str],
        batch_delay: float = 0.1
    ) -> List[VerificationCandidate]:
        """Mock batch verification."""
        results = []
        
        for candidate_data in candidates:
            result = await self.verify_document(
                candidate_data.get("url", ""),
                domain_allowlist,
                candidate_data.get("title")
            )
            
            if "confidence_score" in candidate_data:
                result.discovery_confidence = candidate_data["confidence_score"]
            
            results.append(result)
            await asyncio.sleep(batch_delay)
        
        return results
    
    async def search_documents(
        self,
        query: str,
        domain_allowlist: List[str],
        max_results: int = 10
    ) -> List[CSESearchResult]:
        """Mock document search."""
        # Return mock search results
        mock_results = [
            CSESearchResult(
                title="Mock Energy Document",
                link="https://gzpec.cn/mock-document",
                snippet="Mock snippet about energy regulations",
                display_link="gzpec.cn"
            )
        ]
        
        # Filter by domain allowlist
        filtered_results = []
        for result in mock_results:
            domain = self._extract_domain(result.link)
            if self._is_domain_allowed(domain, domain_allowlist):
                filtered_results.append(result)
        
        return filtered_results[:max_results]
    
    async def health_check(self) -> Dict[str, Any]:
        """Mock health check."""
        return {
            "status": "healthy",
            "latency_ms": 100,
            "quota": {
                "daily_remaining": 95,
                "recent_remaining": 95
            },
            "reset_times": {
                "daily_reset": None,
                "recent_reset": None
            },
            "timestamp": datetime.utcnow().isoformat()
        }
    
    async def close(self):
        """Mock close method."""
        pass
    
    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL."""
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            return parsed.netloc.lower()
        except Exception:
            return ""
    
    def _is_domain_allowed(self, domain: str, domain_allowlist: List[str]) -> bool:
        """Check if domain is in allowlist."""
        for allowed_domain in domain_allowlist:
            if allowed_domain.startswith('.'):
                if domain.endswith(allowed_domain):
                    return True
            else:
                if domain == allowed_domain or domain.endswith('.' + allowed_domain):
                    return True
        return False