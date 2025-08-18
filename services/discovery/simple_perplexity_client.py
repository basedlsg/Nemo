"""Simplified Perplexity client for Task 5 foundation quartet."""

import asyncio
import logging
import time
from datetime import datetime
from typing import List, Dict, Any, Optional, Set
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)


class SimplePerplexityClient:
    """Simplified Perplexity client focused on foundation quartet requirements."""
    
    def __init__(self, api_key: Optional[str] = None, timeout: int = 30):
        """Initialize Perplexity client."""
        import os
        self.api_key = api_key or os.getenv("PERPLEXITY_API_KEY")
        
        # Check if real APIs are enabled
        self.enable_real_apis = os.getenv("ENABLE_REAL_APIS", "false").lower() == "true"
        self.enable_perplexity = os.getenv("ENABLE_PERPLEXITY", "false").lower() == "true"
        
        # Only require API key if real APIs are enabled
        if self.enable_real_apis and self.enable_perplexity:
            if not self.api_key or self.api_key.startswith("demo"):
                logger.warning("Real Perplexity API enabled but no valid API key found. Using mock responses.")
                self.use_real_api = False
            else:
                self.use_real_api = True
                logger.info("Using real Perplexity API")
        else:
            self.use_real_api = False
            logger.info("Using mock Perplexity responses")
        
        self.timeout = timeout
        self.base_url = "https://api.perplexity.ai"
        
        # Only create HTTP client if using real API
        if self.use_real_api:
            self.client = httpx.AsyncClient(
                timeout=httpx.Timeout(timeout),
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                }
            )
        else:
            self.client = None
        
        # Rate limiting (150 calls/day per unblocker plan)
        self.daily_limit = 150
        self.request_count = 0
        self.last_reset = datetime.utcnow().date()
    
    async def discover_official(
        self, 
        province: str, 
        allowlist: List[str],
        max_results: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Discover official documents using Chinese-first prompts.
        
        Args:
            province: Province name (guangdong, shandong, inner_mongolia)
            allowlist: List of allowed domains
            max_results: Maximum results to return
            
        Returns:
            List of discovered documents with title and URL
        """
        try:
            if self.use_real_api:
                return await self._discover_with_real_api(province, allowlist, max_results)
            else:
                return await self._discover_with_mock_api(province, allowlist, max_results)
                
        except Exception as e:
            logger.error(f"Discovery failed for {province}: {e}")
            # Fallback to mock on error
            return await self._discover_with_mock_api(province, allowlist, max_results)
    
    async def _discover_with_real_api(
        self, 
        province: str, 
        allowlist: List[str],
        max_results: int = 20
    ) -> List[Dict[str, Any]]:
        """Discover using real Perplexity API."""
        # Check daily rate limit
        if not self._check_rate_limit():
            logger.warning("Daily rate limit exceeded for Perplexity API")
            return []
        
        # Generate Chinese-first prompt
        prompt = self._build_chinese_prompt(province, allowlist)
        
        # Make API request
        response_data = await self._make_api_request(prompt, allowlist)
        
        # Parse and filter results
        candidates = self._parse_response(response_data, allowlist)
        
        # Deduplicate and limit results
        unique_candidates = self._deduplicate_candidates(candidates)
        
        self.request_count += 1
        logger.info(f"Discovered {len(unique_candidates)} candidates for {province} using real API")
        
        return unique_candidates[:max_results]
    
    async def _discover_with_mock_api(
        self, 
        province: str, 
        allowlist: List[str],
        max_results: int = 20
    ) -> List[Dict[str, Any]]:
        """Discover using mock responses for testing."""
        await asyncio.sleep(1)  # Simulate API delay
        
        # Mock data based on province
        mock_data = {
            "guangdong": [
                {
                    "title": "广东省分布式光伏发电项目管理暂行办法",
                    "url": "https://drc.gd.gov.cn/gkmlpt/content/3/3297/post_3297749.html",
                    "source": "mock_api"
                },
                {
                    "title": "广东电力市场交易规则（2024年版）",
                    "url": "https://drc.gd.gov.cn/gkmlpt/content/3/3298/post_3298123.html",
                    "source": "mock_api"
                }
            ],
            "shandong": [
                {
                    "title": "山东省风电项目并网管理实施细则",
                    "url": "https://nyj.shandong.gov.cn/art/2023/5/15/art_100476_123456.html",
                    "source": "mock_api"
                },
                {
                    "title": "山东省分布式光伏发电市场化交易实施方案",
                    "url": "https://nyj.shandong.gov.cn/art/2023/8/20/art_100477_234567.html",
                    "source": "mock_api"
                }
            ],
            "inner_mongolia": [
                {
                    "title": "内蒙古自治区风电场并网运行管理办法",
                    "url": "https://nyj.nmg.gov.cn/art/2023/3/10/art_200123_345678.html",
                    "source": "mock_api"
                },
                {
                    "title": "内蒙古电力市场煤电机组灵活性改造激励机制",
                    "url": "https://nyj.nmg.gov.cn/art/2023/6/25/art_200124_456789.html",
                    "source": "mock_api"
                }
            ]
        }
        
        candidates = mock_data.get(province, [])
        
        # Filter by allowlist
        filtered_candidates = []
        for candidate in candidates:
            url = candidate.get("url", "")
            if self._is_url_allowed(url, allowlist):
                filtered_candidates.append(candidate)
        
        logger.info(f"Discovered {len(filtered_candidates)} candidates for {province} using mock API")
        return filtered_candidates[:max_results]
    
    async def health_check(self) -> Dict[str, Any]:
        """Check Perplexity API health and rate limit status."""
        try:
            # Simple test request
            test_prompt = "测试"
            
            start_time = time.time()
            response = await self.client.post(
                f"{self.base_url}/chat/completions",
                json={
                    "model": "sonar-small-online",
                    "messages": [{"role": "user", "content": test_prompt}],
                    "max_tokens": 1
                }
            )
            response.raise_for_status()
            latency_ms = int((time.time() - start_time) * 1000)
            
            return {
                "status": "healthy",
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
    
    def _build_chinese_prompt(self, province: str, allowlist: List[str]) -> str:
        """
        Build Chinese-first prompt template per unblocker plan.
        
        Template: "查找 {province_label} 的官方电力交易中心/能源部门 规则或公告页面。
        只返回以下域名：{allowlist}. 输出JSON列表：[{title, url}]，不要返回非官方站点。"
        """
        # Province labels in Chinese
        province_labels = {
            "guangdong": "广东省",
            "shandong": "山东省", 
            "inner_mongolia": "内蒙古自治区"
        }
        
        province_label = province_labels.get(province, province)
        allowlist_str = ", ".join(allowlist)
        
        prompt = f"""查找 {province_label} 的官方电力交易中心/能源部门 规则或公告页面。只返回以下域名：{allowlist_str}。输出JSON列表：[{{"title": "标题", "url": "网址"}}]，不要返回非官方站点。

请找到最新的电力市场规则、并网管理办法、调度运行规定等官方文件。重点关注：
- 电力交易规则
- 并网接入管理
- 调度运行管理
- 市场准入规定

只返回JSON格式，不要其他解释。"""
        
        return prompt
    
    async def _make_api_request(self, prompt: str, allowlist: List[str]) -> Dict[str, Any]:
        """Make API request with domain filtering and backoff."""
        request_data = {
            "model": "sonar-small-online",
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "search_domain_filter": allowlist,
            "return_related_questions": False,
            "return_images": False,
            "search_recency_filter": "month",
            "max_tokens": 2000
        }
        
        # Retry with exponential backoff
        max_retries = 3
        base_delay = 1
        
        for attempt in range(max_retries):
            try:
                response = await self.client.post(
                    f"{self.base_url}/chat/completions",
                    json=request_data
                )
                response.raise_for_status()
                return response.json()
                
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429:  # Rate limited
                    if attempt < max_retries - 1:
                        delay = base_delay * (2 ** attempt)
                        logger.warning(f"Rate limited, retrying in {delay}s")
                        await asyncio.sleep(delay)
                        continue
                raise
            except httpx.TimeoutException:
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    logger.warning(f"Request timeout, retrying in {delay}s")
                    await asyncio.sleep(delay)
                    continue
                raise
        
        raise Exception("Max retries exceeded")
    
    def _parse_response(self, response_data: Dict[str, Any], allowlist: List[str]) -> List[Dict[str, Any]]:
        """Parse Perplexity response and extract candidates."""
        candidates = []
        
        try:
            choices = response_data.get("choices", [])
            if not choices:
                return candidates
            
            content = choices[0].get("message", {}).get("content", "")
            if not content:
                return candidates
            
            # Try to parse JSON response first
            json_candidates = self._extract_json_candidates(content)
            if json_candidates:
                candidates.extend(json_candidates)
            
            # Fallback: extract URLs and titles from text
            text_candidates = self._extract_text_candidates(content, allowlist)
            candidates.extend(text_candidates)
            
            # Filter by allowlist
            filtered_candidates = []
            for candidate in candidates:
                url = candidate.get("url", "")
                if self._is_url_allowed(url, allowlist):
                    filtered_candidates.append(candidate)
            
            return filtered_candidates
            
        except Exception as e:
            logger.error(f"Failed to parse Perplexity response: {e}")
            return []
    
    def _extract_json_candidates(self, content: str) -> List[Dict[str, Any]]:
        """Extract candidates from JSON format in response."""
        import json
        import re
        
        candidates = []
        
        try:
            # Look for JSON arrays in the content
            json_pattern = r'\[[\s\S]*?\]'
            json_matches = re.findall(json_pattern, content)
            
            for json_str in json_matches:
                try:
                    parsed = json.loads(json_str)
                    if isinstance(parsed, list):
                        for item in parsed:
                            if isinstance(item, dict) and "url" in item:
                                candidates.append({
                                    "title": item.get("title", ""),
                                    "url": item["url"],
                                    "source": "perplexity_json"
                                })
                except json.JSONDecodeError:
                    continue
        
        except Exception as e:
            logger.debug(f"JSON extraction failed: {e}")
        
        return candidates
    
    def _extract_text_candidates(self, content: str, allowlist: List[str]) -> List[Dict[str, Any]]:
        """Extract candidates from text format in response."""
        import re
        
        candidates = []
        
        try:
            # Look for URLs in the content
            url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+[^\s<>"{}|\\^`\[\].,;:!?]'
            urls = re.findall(url_pattern, content)
            
            # Look for title: URL patterns
            title_url_pattern = r'(?:^|\n)(?:\d+\.?\s*)?(.+?)[:：]\s*(https?://[^\s<>"{}|\\^`\[\]]+)'
            title_url_matches = re.findall(title_url_pattern, content, re.MULTILINE)
            
            # Process title-URL pairs
            for title, url in title_url_matches:
                title = title.strip()
                url = url.strip()
                
                if self._is_url_allowed(url, allowlist):
                    candidates.append({
                        "title": title,
                        "url": url,
                        "source": "perplexity_text"
                    })
            
            # Process standalone URLs
            processed_urls = {url for _, url in title_url_matches}
            for url in urls:
                if url not in processed_urls and self._is_url_allowed(url, allowlist):
                    candidates.append({
                        "title": "",
                        "url": url,
                        "source": "perplexity_text"
                    })
        
        except Exception as e:
            logger.debug(f"Text extraction failed: {e}")
        
        return candidates
    
    def _is_url_allowed(self, url: str, allowlist: List[str]) -> bool:
        """Check if URL domain is in allowlist."""
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            
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
    
    def _deduplicate_candidates(self, candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove duplicate candidates based on URL."""
        seen_urls = set()
        unique_candidates = []
        
        for candidate in candidates:
            url = candidate.get("url", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                unique_candidates.append(candidate)
        
        return unique_candidates


def discover_official_documents(
    province: str, 
    allowlist: List[str],
    api_key: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Convenience function for synchronous document discovery.
    
    Args:
        province: Province name
        allowlist: List of allowed domains
        api_key: Perplexity API key (optional, uses env var)
        
    Returns:
        List of discovered documents
    """
    async def _discover():
        client = SimplePerplexityClient(api_key)
        try:
            return await client.discover_official(province, allowlist)
        finally:
            await client.close()
    
    return asyncio.run(_discover())


if __name__ == "__main__":
    # Quick test with foundation quartet domains
    import json
    
    foundation_allowlist = ["gzpec.cn", "sdpxc.cn", "impex.org.cn"]
    
    print("=== Testing Perplexity Discovery ===")
    
    for province in ["guangdong", "shandong", "inner_mongolia"]:
        print(f"\n--- {province.title()} ---")
        
        try:
            results = discover_official_documents(province, foundation_allowlist)
            print(f"Found {len(results)} candidates:")
            
            for i, result in enumerate(results[:3], 1):  # Show first 3
                print(f"{i}. {result.get('title', 'No title')}")
                print(f"   URL: {result['url']}")
                print(f"   Source: {result.get('source', 'unknown')}")
        
        except Exception as e:
            print(f"Error: {e}")
    
    print("\n=== Health Check ===")
    
    async def test_health():
        client = SimplePerplexityClient()
        try:
            health = await client.health_check()
            print(json.dumps(health, indent=2))
        finally:
            await client.close()
    
    asyncio.run(test_health())