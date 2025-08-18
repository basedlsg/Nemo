"""Document fetcher with robots.txt compliance and metadata extraction."""

import asyncio
import hashlib
import logging
import time
from datetime import datetime
from typing import List, Dict, Any, Optional, Set
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import httpx
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings

from .models import DocumentSnapshot, FetchResult, FetchStatus, DocumentFormat
from services.core.utils import extract_effective_date, normalize_text

logger = logging.getLogger(__name__)


class FetchConfig(BaseSettings):
    """Configuration for document fetcher."""
    
    timeout: int = Field(default=30, env="FETCH_TIMEOUT")
    max_retries: int = Field(default=3, env="FETCH_MAX_RETRIES")
    retry_delay: int = Field(default=1, env="FETCH_RETRY_DELAY")
    max_redirects: int = Field(default=10, env="FETCH_MAX_REDIRECTS")
    max_content_size: int = Field(default=50 * 1024 * 1024, env="FETCH_MAX_CONTENT_SIZE")  # 50MB
    
    # Rate limiting
    requests_per_domain_per_minute: int = Field(default=30, env="FETCH_RATE_LIMIT_RPM")
    concurrent_requests: int = Field(default=10, env="FETCH_CONCURRENT_REQUESTS")
    
    # User agent
    user_agent: str = Field(
        default="Geo-Adaptive-Energy-Assistant/1.0 (+https://github.com/energy-assistant)",
        env="FETCH_USER_AGENT"
    )
    
    # Robots.txt compliance
    respect_robots_txt: bool = Field(default=True, env="FETCH_RESPECT_ROBOTS")
    robots_cache_ttl: int = Field(default=3600, env="FETCH_ROBOTS_CACHE_TTL")  # 1 hour
    
    # Content filtering
    allowed_content_types: List[str] = Field(
        default=[
            "text/html",
            "application/pdf", 
            "application/xml",
            "text/xml",
            "application/json",
            "text/plain"
        ],
        env="FETCH_ALLOWED_CONTENT_TYPES"
    )
    
    class Config:
        env_file = ".env"


class RobotsTxtCache:
    """Cache for robots.txt files with TTL."""
    
    def __init__(self, ttl_seconds: int = 3600):
        self.ttl_seconds = ttl_seconds
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._lock = asyncio.Lock()
    
    async def get_robots_parser(self, domain: str, user_agent: str) -> Optional[RobotFileParser]:
        """Get robots.txt parser for domain."""
        async with self._lock:
            cache_key = domain
            now = time.time()
            
            # Check cache
            if cache_key in self._cache:
                cached_data = self._cache[cache_key]
                if now - cached_data["timestamp"] < self.ttl_seconds:
                    return cached_data["parser"]
            
            # Fetch robots.txt
            try:
                robots_url = f"https://{domain}/robots.txt"
                
                async with httpx.AsyncClient(timeout=10) as client:
                    response = await client.get(robots_url)
                    
                    if response.status_code == 200:
                        parser = RobotFileParser()
                        parser.set_url(robots_url)
                        parser.read_from_string(response.text)
                    else:
                        # No robots.txt or error - allow all
                        parser = None
                
                # Cache result
                self._cache[cache_key] = {
                    "parser": parser,
                    "timestamp": now
                }
                
                return parser
                
            except Exception as e:
                logger.debug(f"Failed to fetch robots.txt for {domain}: {e}")
                # Cache failure as "allow all"
                self._cache[cache_key] = {
                    "parser": None,
                    "timestamp": now
                }
                return None
    
    def clear_cache(self) -> None:
        """Clear robots.txt cache."""
        self._cache.clear()


class DomainRateLimiter:
    """Per-domain rate limiter."""
    
    def __init__(self, requests_per_minute: int):
        self.requests_per_minute = requests_per_minute
        self._domain_requests: Dict[str, List[float]] = {}
        self._lock = asyncio.Lock()
    
    async def acquire(self, domain: str) -> bool:
        """Acquire rate limit slot for domain."""
        async with self._lock:
            now = time.time()
            
            # Initialize domain tracking
            if domain not in self._domain_requests:
                self._domain_requests[domain] = []
            
            # Clean old requests
            cutoff = now - 60  # 1 minute ago
            self._domain_requests[domain] = [
                req_time for req_time in self._domain_requests[domain] 
                if req_time > cutoff
            ]
            
            # Check limit
            if len(self._domain_requests[domain]) >= self.requests_per_minute:
                return False
            
            # Add request
            self._domain_requests[domain].append(now)
            return True
    
    def get_domain_stats(self) -> Dict[str, int]:
        """Get current request counts per domain."""
        now = time.time()
        cutoff = now - 60
        
        stats = {}
        for domain, requests in self._domain_requests.items():
            recent_requests = [req for req in requests if req > cutoff]
            stats[domain] = len(recent_requests)
        
        return stats


class DocumentFetcher:
    """Fetches documents with robots.txt compliance and metadata extraction."""
    
    def __init__(self, config: Optional[FetchConfig] = None):
        """Initialize document fetcher."""
        self.config = config or FetchConfig()
        self.robots_cache = RobotsTxtCache(self.config.robots_cache_ttl)
        self.rate_limiter = DomainRateLimiter(self.config.requests_per_domain_per_minute)
        
        # HTTP client with custom configuration
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(self.config.timeout),
            follow_redirects=True,
            max_redirects=self.config.max_redirects,
            headers={
                "User-Agent": self.config.user_agent,
                "Accept": "text/html,application/pdf,application/xml,text/xml,application/json,text/plain,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Accept-Encoding": "gzip, deflate",
                "DNT": "1",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1"
            }
        )
        
        # Semaphore for concurrent request limiting
        self._semaphore = asyncio.Semaphore(self.config.concurrent_requests)
    
    async def fetch_document(self, url: str, trace_id: Optional[str] = None) -> FetchResult:
        """Fetch a single document with full metadata extraction."""
        start_time = time.time()
        
        try:
            logger.info(f"Fetching document: {url}")
            
            # Parse URL and extract domain
            parsed_url = urlparse(url)
            domain = parsed_url.netloc.lower()
            
            # Check robots.txt compliance
            if self.config.respect_robots_txt:
                robots_allowed = await self._check_robots_txt(url, domain)
                if not robots_allowed:
                    return FetchResult(
                        url=url,
                        status=FetchStatus.ROBOTS_BLOCKED,
                        error_message="Blocked by robots.txt",
                        robots_txt_allowed=False,
                        user_agent_used=self.config.user_agent
                    )
            
            # Check rate limit
            if not await self.rate_limiter.acquire(domain):
                return FetchResult(
                    url=url,
                    status=FetchStatus.RATE_LIMITED,
                    error_message=f"Rate limit exceeded for domain {domain}"
                )
            
            # Fetch document with semaphore
            async with self._semaphore:
                result = await self._fetch_with_retries(url, trace_id)
                result.fetch_time_ms = int((time.time() - start_time) * 1000)
                return result
        
        except Exception as e:
            logger.error(f"Document fetch failed for {url}: {e}")
            return FetchResult(
                url=url,
                status=FetchStatus.FAILED,
                error_message=str(e),
                fetch_time_ms=int((time.time() - start_time) * 1000)
            )
    
    async def fetch_documents_batch(
        self,
        urls: List[str],
        batch_delay: float = 1.0,
        trace_id: Optional[str] = None
    ) -> List[FetchResult]:
        """Fetch multiple documents with rate limiting."""
        results = []
        
        # Group URLs by domain for better rate limiting
        domain_groups = {}
        for url in urls:
            domain = urlparse(url).netloc.lower()
            if domain not in domain_groups:
                domain_groups[domain] = []
            domain_groups[domain].append(url)
        
        # Process each domain group
        for domain, domain_urls in domain_groups.items():
            logger.info(f"Fetching {len(domain_urls)} documents from {domain}")
            
            for i, url in enumerate(domain_urls):
                result = await self.fetch_document(url, trace_id)
                results.append(result)
                
                # Add delay between requests to same domain
                if i < len(domain_urls) - 1:
                    await asyncio.sleep(batch_delay)
            
            # Add delay between domains
            await asyncio.sleep(batch_delay * 0.5)
        
        return results
    
    async def health_check(self) -> Dict[str, Any]:
        """Check fetcher health and connectivity."""
        try:
            # Test with a simple request
            test_url = "https://httpbin.org/status/200"
            start_time = time.time()
            
            response = await self.client.get(test_url, timeout=10)
            latency_ms = int((time.time() - start_time) * 1000)
            
            # Get rate limiter stats
            domain_stats = self.rate_limiter.get_domain_stats()
            
            return {
                "status": "healthy" if response.status_code == 200 else "degraded",
                "latency_ms": latency_ms,
                "concurrent_limit": self.config.concurrent_requests,
                "rate_limit_rpm": self.config.requests_per_domain_per_minute,
                "active_domains": len(domain_stats),
                "domain_request_counts": domain_stats,
                "robots_cache_size": len(self.robots_cache._cache),
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    async def close(self):
        """Close HTTP client and cleanup resources."""
        await self.client.aclose()
        self.robots_cache.clear_cache()
    
    async def _check_robots_txt(self, url: str, domain: str) -> bool:
        """Check if URL is allowed by robots.txt."""
        try:
            parser = await self.robots_cache.get_robots_parser(domain, self.config.user_agent)
            
            if parser is None:
                # No robots.txt or failed to fetch - allow by default
                return True
            
            return parser.can_fetch(self.config.user_agent, url)
            
        except Exception as e:
            logger.debug(f"Robots.txt check failed for {url}: {e}")
            # On error, allow by default
            return True
    
    async def _fetch_with_retries(self, url: str, trace_id: Optional[str] = None) -> FetchResult:
        """Fetch document with retry logic."""
        last_exception = None
        redirect_chain = []
        
        for attempt in range(self.config.max_retries):
            try:
                # Add trace ID to headers if provided
                headers = {}
                if trace_id:
                    headers["X-Trace-ID"] = trace_id
                
                # Make request
                response = await self.client.get(url, headers=headers)
                
                # Track redirects
                if hasattr(response, 'history') and response.history:
                    redirect_chain = [str(r.url) for r in response.history]
                
                # Check content type
                content_type = response.headers.get("content-type", "").lower()
                if not self._is_content_type_allowed(content_type):
                    return FetchResult(
                        url=url,
                        status=FetchStatus.FAILED,
                        error_message=f"Content type not allowed: {content_type}",
                        redirect_count=len(redirect_chain)
                    )
                
                # Check content size
                content_length = response.headers.get("content-length")
                if content_length and int(content_length) > self.config.max_content_size:
                    return FetchResult(
                        url=url,
                        status=FetchStatus.FAILED,
                        error_message=f"Content too large: {content_length} bytes",
                        redirect_count=len(redirect_chain)
                    )
                
                # Read content with size limit
                content = b""
                async for chunk in response.aiter_bytes(chunk_size=8192):
                    content += chunk
                    if len(content) > self.config.max_content_size:
                        return FetchResult(
                            url=url,
                            status=FetchStatus.FAILED,
                            error_message=f"Content too large: {len(content)} bytes",
                            redirect_count=len(redirect_chain)
                        )
                
                # Create document snapshot
                snapshot = await self._create_document_snapshot(
                    url, response, content, redirect_chain
                )
                
                return FetchResult(
                    url=url,
                    status=FetchStatus.SUCCESS,
                    snapshot=snapshot,
                    redirect_count=len(redirect_chain),
                    robots_txt_allowed=True,
                    user_agent_used=self.config.user_agent
                )
                
            except httpx.TimeoutException:
                last_exception = Exception("Request timeout")
                if attempt == self.config.max_retries - 1:
                    return FetchResult(
                        url=url,
                        status=FetchStatus.TIMEOUT,
                        error_message="Request timeout"
                    )
                
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    return FetchResult(
                        url=url,
                        status=FetchStatus.NOT_FOUND,
                        error_message=f"HTTP {e.response.status_code}: Not Found"
                    )
                
                last_exception = e
                # Don't retry on client errors (4xx)
                if 400 <= e.response.status_code < 500:
                    break
                
            except Exception as e:
                last_exception = e
            
            # Wait before retry
            if attempt < self.config.max_retries - 1:
                delay = self.config.retry_delay * (2 ** attempt)
                await asyncio.sleep(delay)
        
        # All retries failed
        return FetchResult(
            url=url,
            status=FetchStatus.FAILED,
            error_message=str(last_exception) if last_exception else "Unknown error"
        )
    
    async def _create_document_snapshot(
        self,
        original_url: str,
        response: httpx.Response,
        content: bytes,
        redirect_chain: List[str]
    ) -> DocumentSnapshot:
        """Create document snapshot with metadata extraction."""
        # Calculate checksums
        sha256_hash = hashlib.sha256(content).hexdigest()
        md5_hash = hashlib.md5(content).hexdigest()
        
        # Extract domain
        domain = urlparse(original_url).netloc.lower()
        canonical_url = str(response.url) if str(response.url) != original_url else None
        
        # Extract metadata from headers
        content_type = response.headers.get("content-type", "application/octet-stream")
        content_encoding = response.headers.get("content-encoding")
        
        # Parse last-modified header
        last_modified = None
        last_modified_str = response.headers.get("last-modified")
        if last_modified_str:
            try:
                from email.utils import parsedate_to_datetime
                last_modified = parsedate_to_datetime(last_modified_str)
            except Exception:
                pass
        
        # Extract title and effective date from content
        title = None
        effective_date = None
        language = None
        
        try:
            if "text/html" in content_type.lower():
                # Extract from HTML
                text_content = content.decode('utf-8', errors='ignore')
                title, language = self._extract_html_metadata(text_content)
                effective_date = extract_effective_date(text_content, original_url)
            elif "text/" in content_type.lower():
                # Extract from plain text
                text_content = content.decode('utf-8', errors='ignore')
                effective_date = extract_effective_date(text_content, original_url)
                
                # Simple title extraction from first line
                lines = text_content.split('\n')
                for line in lines:
                    line = line.strip()
                    if line and len(line) > 10:
                        title = line[:200]  # First meaningful line as title
                        break
        except Exception as e:
            logger.debug(f"Metadata extraction failed for {original_url}: {e}")
        
        # Create snapshot
        snapshot = DocumentSnapshot(
            original_url=original_url,
            canonical_url=canonical_url,
            domain=domain,
            content=content,
            content_type=content_type,
            content_length=len(content),
            content_encoding=content_encoding,
            sha256_checksum=sha256_hash,
            md5_checksum=md5_hash,
            title=title,
            language=language,
            effective_date=effective_date,
            last_modified=last_modified,
            http_status_code=response.status_code,
            http_headers=dict(response.headers),
            redirect_chain=redirect_chain,
            storage_path="",  # Will be set by storage service
            storage_bucket=""  # Will be set by storage service
        )
        
        return snapshot
    
    def _is_content_type_allowed(self, content_type: str) -> bool:
        """Check if content type is allowed."""
        content_type_lower = content_type.lower().split(';')[0].strip()
        return any(allowed in content_type_lower for allowed in self.config.allowed_content_types)
    
    def _extract_html_metadata(self, html_content: str) -> tuple[Optional[str], Optional[str]]:
        """Extract title and language from HTML content."""
        title = None
        language = None
        
        try:
            import re
            
            # Extract title
            title_match = re.search(r'<title[^>]*>(.*?)</title>', html_content, re.IGNORECASE | re.DOTALL)
            if title_match:
                title = normalize_text(title_match.group(1))
                title = title[:200] if title else None
            
            # Extract language
            lang_match = re.search(r'<html[^>]*lang=["\']([^"\']+)["\']', html_content, re.IGNORECASE)
            if lang_match:
                language = lang_match.group(1)
            else:
                # Try meta tag
                meta_lang_match = re.search(r'<meta[^>]*http-equiv=["\']content-language["\'][^>]*content=["\']([^"\']+)["\']', html_content, re.IGNORECASE)
                if meta_lang_match:
                    language = meta_lang_match.group(1)
        
        except Exception as e:
            logger.debug(f"HTML metadata extraction failed: {e}")
        
        return title, language


class DocumentFetcherMock:
    """Mock document fetcher for testing."""
    
    def __init__(self, mock_responses: Optional[Dict[str, Any]] = None):
        """Initialize mock fetcher."""
        self.mock_responses = mock_responses or {}
        self.fetch_count = 0
    
    async def fetch_document(self, url: str, trace_id: Optional[str] = None) -> FetchResult:
        """Mock document fetch."""
        self.fetch_count += 1
        
        # Simulate processing time
        await asyncio.sleep(0.1)
        
        # Check for mock response
        if url in self.mock_responses:
            response_data = self.mock_responses[url]
            
            if response_data.get("status") == "success":
                # Create mock snapshot
                content = response_data.get("content", b"Mock document content")
                if isinstance(content, str):
                    content = content.encode('utf-8')
                
                snapshot = DocumentSnapshot(
                    original_url=url,
                    domain=urlparse(url).netloc.lower(),
                    content=content,
                    content_type=response_data.get("content_type", "text/html"),
                    content_length=len(content),
                    sha256_checksum=hashlib.sha256(content).hexdigest(),
                    title=response_data.get("title", "Mock Document"),
                    http_status_code=200,
                    http_headers={"content-type": response_data.get("content_type", "text/html")},
                    storage_path="mock/path",
                    storage_bucket="mock-bucket"
                )
                
                return FetchResult(
                    url=url,
                    status=FetchStatus.SUCCESS,
                    snapshot=snapshot,
                    fetch_time_ms=100,
                    robots_txt_allowed=True
                )
            else:
                return FetchResult(
                    url=url,
                    status=FetchStatus.FAILED,
                    error_message=response_data.get("error", "Mock error")
                )
        
        # Default mock response for official domains
        domain = urlparse(url).netloc.lower()
        if any(official in domain for official in ["gov.cn", "gzpec.cn", "sgcc.com.cn"]):
            content = f"Mock content for {url}".encode('utf-8')
            snapshot = DocumentSnapshot(
                original_url=url,
                domain=domain,
                content=content,
                content_type="text/html",
                content_length=len(content),
                sha256_checksum=hashlib.sha256(content).hexdigest(),
                title=f"Mock Document from {domain}",
                http_status_code=200,
                http_headers={"content-type": "text/html"},
                storage_path="mock/path",
                storage_bucket="mock-bucket"
            )
            
            return FetchResult(
                url=url,
                status=FetchStatus.SUCCESS,
                snapshot=snapshot,
                fetch_time_ms=100,
                robots_txt_allowed=True
            )
        else:
            return FetchResult(
                url=url,
                status=FetchStatus.FAILED,
                error_message="Mock: Domain not allowed"
            )
    
    async def fetch_documents_batch(
        self,
        urls: List[str],
        batch_delay: float = 0.1,
        trace_id: Optional[str] = None
    ) -> List[FetchResult]:
        """Mock batch fetch."""
        results = []
        for url in urls:
            result = await self.fetch_document(url, trace_id)
            results.append(result)
            await asyncio.sleep(batch_delay)
        return results
    
    async def health_check(self) -> Dict[str, Any]:
        """Mock health check."""
        return {
            "status": "healthy",
            "latency_ms": 50,
            "fetch_count": self.fetch_count,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    async def close(self):
        """Mock close."""
        pass