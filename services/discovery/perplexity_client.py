"""Perplexity API client for document discovery."""

import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

import httpx
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings

from .models import DocumentCandidate, DiscoveryResult, DiscoveryStatus

logger = logging.getLogger(__name__)


class PerplexityConfig(BaseSettings):
    """Configuration for Perplexity API client."""
    
    api_key: str = Field(..., env="PPLX_API_KEY")
    base_url: str = Field(default="https://api.perplexity.ai", env="PPLX_BASE_URL")
    model: str = Field(default="sonar-deep-research", env="PPLX_MODEL")
    timeout: int = Field(default=60, env="PPLX_TIMEOUT")
    max_retries: int = Field(default=3, env="PPLX_MAX_RETRIES")
    retry_delay: int = Field(default=1, env="PPLX_RETRY_DELAY")
    rate_limit_requests_per_minute: int = Field(default=20, env="PPLX_RATE_LIMIT_RPM")
    
    class Config:
        env_file = ".env"


class RateLimiter:
    """Rate limiter for API requests."""
    
    def __init__(self, requests_per_minute: int):
        self.requests_per_minute = requests_per_minute
        self.requests = []
        self.lock = asyncio.Lock()
    
    async def acquire(self) -> bool:
        """Acquire rate limit slot."""
        async with self.lock:
            now = time.time()
            
            # Remove requests older than 1 minute
            self.requests = [req_time for req_time in self.requests if now - req_time < 60]
            
            # Check if we can make a request
            if len(self.requests) < self.requests_per_minute:
                self.requests.append(now)
                return True
            
            return False
    
    def get_reset_time(self) -> Optional[datetime]:
        """Get time when rate limit resets."""
        if not self.requests:
            return None
        
        oldest_request = min(self.requests)
        reset_time = datetime.fromtimestamp(oldest_request + 60)
        return reset_time


class PerplexityClient:
    """Client for Perplexity API with rate limiting and error handling."""
    
    def __init__(self, config: Optional[PerplexityConfig] = None):
        """Initialize Perplexity client."""
        self.config = config or PerplexityConfig()
        self.rate_limiter = RateLimiter(self.config.rate_limit_requests_per_minute)
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(self.config.timeout),
            headers={
                "Authorization": f"Bearer {self.config.api_key}",
                "Content-Type": "application/json"
            }
        )
    
    async def search_documents(
        self,
        query: str,
        domain_filter: List[str],
        max_results: int = 20
    ) -> DiscoveryResult:
        """Search for documents using Perplexity API."""
        start_time = time.time()
        
        try:
            # Check rate limit
            if not await self.rate_limiter.acquire():
                logger.warning("Rate limit exceeded for Perplexity API")
                return DiscoveryResult(
                    query_id=None,  # Will be set by caller
                    status=DiscoveryStatus.RATE_LIMITED,
                    rate_limit_reset_at=self.rate_limiter.get_reset_time()
                )
            
            # Prepare request
            request_data = {
                "model": self.config.model,
                "messages": [
                    {
                        "role": "user",
                        "content": self._build_search_prompt(query, domain_filter)
                    }
                ],
                "search_domain_filter": domain_filter,
                "return_related_questions": False,
                "return_images": False,
                "search_recency_filter": "month"  # Focus on recent documents
            }
            
            # Make API request with retries
            response_data = await self._make_request_with_retries(request_data)
            
            # Parse response and extract candidates
            candidates = self._parse_response(response_data, domain_filter)
            
            processing_time = int((time.time() - start_time) * 1000)
            
            return DiscoveryResult(
                query_id=None,  # Will be set by caller
                status=DiscoveryStatus.COMPLETED,
                candidates=candidates[:max_results],
                total_found=len(candidates),
                processing_time_ms=processing_time,
                completed_at=datetime.utcnow()
            )
            
        except httpx.TimeoutException:
            logger.error("Perplexity API request timed out")
            return DiscoveryResult(
                query_id=None,
                status=DiscoveryStatus.FAILED,
                error_message="Request timed out"
            )
        except httpx.HTTPStatusError as e:
            logger.error(f"Perplexity API HTTP error: {e.response.status_code}")
            return DiscoveryResult(
                query_id=None,
                status=DiscoveryStatus.FAILED,
                error_message=f"HTTP {e.response.status_code}: {e.response.text}"
            )
        except Exception as e:
            logger.error(f"Perplexity API request failed: {e}")
            return DiscoveryResult(
                query_id=None,
                status=DiscoveryStatus.FAILED,
                error_message=str(e)
            )
    
    async def health_check(self) -> Dict[str, Any]:
        """Check Perplexity API health and connectivity."""
        try:
            # Simple test request
            test_data = {
                "model": self.config.model,
                "messages": [{"role": "user", "content": "test"}],
                "max_tokens": 1
            }
            
            start_time = time.time()
            response = await self.client.post(
                f"{self.config.base_url}/chat/completions",
                json=test_data
            )
            response.raise_for_status()
            
            latency_ms = int((time.time() - start_time) * 1000)
            
            return {
                "status": "healthy",
                "latency_ms": latency_ms,
                "rate_limit_remaining": self.config.rate_limit_requests_per_minute - len(self.rate_limiter.requests),
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
    
    def _build_search_prompt(self, query: str, domain_filter: List[str]) -> str:
        """Build search prompt for Perplexity."""
        prompt = f"""Find official energy regulation documents related to: {query}

Requirements:
- Only return results from official government or power company domains
- Focus on recent regulatory documents, policies, and announcements
- Include document titles and URLs
- Prioritize documents from these domains: {', '.join(domain_filter)}

Please provide a list of relevant documents with their URLs and brief descriptions."""
        
        return prompt
    
    async def _make_request_with_retries(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Make API request with retry logic."""
        last_exception = None
        
        for attempt in range(self.config.max_retries):
            try:
                response = await self.client.post(
                    f"{self.config.base_url}/chat/completions",
                    json=request_data
                )
                response.raise_for_status()
                return response.json()
                
            except httpx.HTTPStatusError as e:
                last_exception = e
                
                # Don't retry on client errors (4xx)
                if 400 <= e.response.status_code < 500:
                    raise
                
                # Retry on server errors (5xx) with exponential backoff
                if attempt < self.config.max_retries - 1:
                    delay = self.config.retry_delay * (2 ** attempt)
                    logger.warning(f"Perplexity API error {e.response.status_code}, retrying in {delay}s")
                    await asyncio.sleep(delay)
                
            except Exception as e:
                last_exception = e
                
                if attempt < self.config.max_retries - 1:
                    delay = self.config.retry_delay * (2 ** attempt)
                    logger.warning(f"Perplexity API request failed, retrying in {delay}s: {e}")
                    await asyncio.sleep(delay)
        
        # All retries failed
        raise last_exception
    
    def _parse_response(self, response_data: Dict[str, Any], domain_filter: List[str]) -> List[DocumentCandidate]:
        """Parse Perplexity API response and extract document candidates."""
        candidates = []
        
        try:
            # Extract content from response
            choices = response_data.get("choices", [])
            if not choices:
                logger.warning("No choices in Perplexity response")
                return candidates
            
            content = choices[0].get("message", {}).get("content", "")
            if not content:
                logger.warning("No content in Perplexity response")
                return candidates
            
            # Extract URLs and information from content
            import re
            
            # Look for URLs in the content
            url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+[^\s<>"{}|\\^`\[\].,;:!?]'
            urls = re.findall(url_pattern, content)
            
            # Look for structured information (title: URL format)
            structured_pattern = r'(?:^|\n)(?:\d+\.?\s*)?(.+?):\s*(https?://[^\s<>"{}|\\^`\[\]]+)'
            structured_matches = re.findall(structured_pattern, content, re.MULTILINE)
            
            # Process structured matches first
            for title, url in structured_matches:
                title = title.strip()
                url = url.strip()
                
                domain = self._extract_domain(url)
                if domain and self._is_domain_allowed(domain, domain_filter):
                    candidate = DocumentCandidate(
                        url=url,
                        title=title,
                        domain=domain,
                        confidence_score=0.8,  # Higher confidence for structured results
                        source="perplexity"
                    )
                    candidates.append(candidate)
            
            # Process remaining URLs
            structured_urls = {url for _, url in structured_matches}
            for url in urls:
                if url in structured_urls:
                    continue  # Already processed
                
                domain = self._extract_domain(url)
                if domain and self._is_domain_allowed(domain, domain_filter):
                    candidate = DocumentCandidate(
                        url=url,
                        domain=domain,
                        confidence_score=0.6,  # Lower confidence for unstructured results
                        source="perplexity"
                    )
                    candidates.append(candidate)
            
            # Extract snippets from content for context
            self._add_snippets_to_candidates(candidates, content)
            
            logger.info(f"Extracted {len(candidates)} candidates from Perplexity response")
            
        except Exception as e:
            logger.error(f"Failed to parse Perplexity response: {e}")
        
        return candidates
    
    def _extract_domain(self, url: str) -> Optional[str]:
        """Extract domain from URL."""
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            return parsed.netloc.lower()
        except Exception:
            return None
    
    def _is_domain_allowed(self, domain: str, domain_filter: List[str]) -> bool:
        """Check if domain is in allowlist."""
        for allowed_domain in domain_filter:
            if allowed_domain.startswith('.'):
                # Suffix match (e.g., .gov.cn)
                if domain.endswith(allowed_domain):
                    return True
            else:
                # Exact match or subdomain
                if domain == allowed_domain or domain.endswith('.' + allowed_domain):
                    return True
        return False
    
    def _add_snippets_to_candidates(self, candidates: List[DocumentCandidate], content: str) -> None:
        """Add content snippets to candidates for context."""
        for candidate in candidates:
            # Find text around the URL in the content
            url_index = content.find(candidate.url)
            if url_index != -1:
                # Extract surrounding context (up to 200 characters before and after)
                start = max(0, url_index - 200)
                end = min(len(content), url_index + len(candidate.url) + 200)
                snippet = content[start:end].strip()
                
                # Clean up snippet
                snippet = re.sub(r'\s+', ' ', snippet)
                if len(snippet) > 300:
                    snippet = snippet[:300] + "..."
                
                candidate.snippet = snippet


class PerplexityMockClient:
    """Mock client for testing purposes."""
    
    def __init__(self, mock_responses: Optional[List[Dict[str, Any]]] = None):
        """Initialize mock client with predefined responses."""
        self.mock_responses = mock_responses or []
        self.request_count = 0
    
    async def search_documents(
        self,
        query: str,
        domain_filter: List[str],
        max_results: int = 20
    ) -> DiscoveryResult:
        """Mock search that returns predefined results."""
        self.request_count += 1
        
        # Simulate processing time
        await asyncio.sleep(0.1)
        
        # Return mock candidates
        mock_candidates = [
            DocumentCandidate(
                url="https://gzpec.cn/rules/solar-2025",
                title="广东省分布式光伏并网管理办法",
                domain="gzpec.cn",
                confidence_score=0.9,
                source="perplexity_mock"
            ),
            DocumentCandidate(
                url="https://shandong-electric.com.cn/wind-dispatch",
                title="山东省风电调度管理规定",
                domain="shandong-electric.com.cn",
                confidence_score=0.8,
                source="perplexity_mock"
            )
        ]
        
        # Filter by domain
        filtered_candidates = [
            c for c in mock_candidates 
            if any(domain in c.domain for domain in domain_filter)
        ]
        
        return DiscoveryResult(
            query_id=None,
            status=DiscoveryStatus.COMPLETED,
            candidates=filtered_candidates[:max_results],
            total_found=len(filtered_candidates),
            processing_time_ms=100
        )
    
    async def health_check(self) -> Dict[str, Any]:
        """Mock health check."""
        return {
            "status": "healthy",
            "latency_ms": 50,
            "rate_limit_remaining": 20,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    async def close(self):
        """Mock close method."""
        pass