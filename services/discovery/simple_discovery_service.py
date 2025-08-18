"""Simplified discovery service for Task 5 foundation quartet."""

import asyncio
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from uuid import uuid4

from .simple_perplexity_client import SimplePerplexityClient
from services.registry.simple_loader import SimpleRegistryLoader
from services.registry.robots_checker import get_foundation_allowlist

logger = logging.getLogger(__name__)


class SimpleDiscoveryService:
    """Simplified discovery service focused on foundation quartet requirements."""
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize discovery service."""
        self.perplexity_client = SimplePerplexityClient(api_key)
        self.registry_loader = SimpleRegistryLoader()
        self.discovery_stats = {
            "total_discoveries": 0,
            "successful_discoveries": 0,
            "failed_discoveries": 0,
            "total_candidates": 0,
            "last_discovery": None
        }
    
    async def discover_for_province(
        self, 
        province: str,
        max_results: int = 20
    ) -> Dict[str, Any]:
        """
        Discover documents for a specific province.
        
        Args:
            province: Province name (guangdong, shandong, inner_mongolia)
            max_results: Maximum candidates to return
            
        Returns:
            Discovery result with candidates and metadata
        """
        discovery_id = str(uuid4())
        start_time = datetime.utcnow()
        
        try:
            logger.info(f"Starting discovery for {province} (ID: {discovery_id})")
            
            # Get allowlist from registry
            allowlist = await self._get_province_allowlist(province)
            
            # Discover using Perplexity
            candidates = await self.perplexity_client.discover_official(
                province, allowlist, max_results
            )
            
            # Process and validate candidates
            processed_candidates = await self._process_candidates(candidates, province)
            
            # Update stats
            self.discovery_stats["total_discoveries"] += 1
            self.discovery_stats["successful_discoveries"] += 1
            self.discovery_stats["total_candidates"] += len(processed_candidates)
            self.discovery_stats["last_discovery"] = datetime.utcnow().isoformat()
            
            processing_time = (datetime.utcnow() - start_time).total_seconds()
            
            result = {
                "discovery_id": discovery_id,
                "province": province,
                "status": "completed",
                "candidates": processed_candidates,
                "total_found": len(processed_candidates),
                "allowlist": allowlist,
                "processing_time_seconds": processing_time,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            logger.info(f"Discovery completed for {province}: {len(processed_candidates)} candidates")
            return result
            
        except Exception as e:
            logger.error(f"Discovery failed for {province}: {e}")
            
            self.discovery_stats["total_discoveries"] += 1
            self.discovery_stats["failed_discoveries"] += 1
            
            return {
                "discovery_id": discovery_id,
                "province": province,
                "status": "failed",
                "error": str(e),
                "candidates": [],
                "total_found": 0,
                "processing_time_seconds": (datetime.utcnow() - start_time).total_seconds(),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    async def discover_all_provinces(self) -> List[Dict[str, Any]]:
        """
        Discover documents for all foundation quartet provinces.
        
        Returns:
            List of discovery results for each province
        """
        provinces = ["guangdong", "shandong", "inner_mongolia"]
        results = []
        
        for province in provinces:
            try:
                result = await self.discover_for_province(province)
                results.append(result)
                
                # Add delay between provinces to respect rate limits
                await asyncio.sleep(2)
                
            except Exception as e:
                logger.error(f"Failed to discover for {province}: {e}")
                results.append({
                    "province": province,
                    "status": "failed",
                    "error": str(e),
                    "candidates": [],
                    "total_found": 0
                })
        
        return results
    
    async def emit_candidates_for_verification(
        self, 
        candidates: List[Dict[str, Any]], 
        province: str
    ) -> List[Dict[str, Any]]:
        """
        Emit candidates for verification (Task 6).
        
        Args:
            candidates: List of discovered candidates
            province: Province name
            
        Returns:
            List of verification jobs created
        """
        verification_jobs = []
        
        for candidate in candidates:
            try:
                # Create verification job payload
                verification_job = {
                    "job_id": str(uuid4()),
                    "job_type": "verification",
                    "province": province,
                    "candidate_url": candidate["url"],
                    "candidate_title": candidate.get("title", ""),
                    "candidate_domain": candidate.get("domain", ""),
                    "discovery_source": "perplexity",
                    "created_at": datetime.utcnow().isoformat(),
                    "status": "pending"
                }
                
                verification_jobs.append(verification_job)
                
                # In a real implementation, this would emit to Pub/Sub
                logger.debug(f"Emitted verification job: {verification_job['job_id']}")
                
            except Exception as e:
                logger.error(f"Failed to emit verification job for {candidate.get('url', 'unknown')}: {e}")
        
        logger.info(f"Emitted {len(verification_jobs)} verification jobs for {province}")
        return verification_jobs
    
    async def get_discovery_stats(self) -> Dict[str, Any]:
        """Get discovery service statistics."""
        # Add Perplexity health check
        perplexity_health = await self.perplexity_client.health_check()
        
        return {
            "service": "discovery",
            "stats": self.discovery_stats,
            "perplexity_health": perplexity_health,
            "foundation_allowlist": get_foundation_allowlist(),
            "supported_provinces": ["guangdong", "shandong", "inner_mongolia"],
            "timestamp": datetime.utcnow().isoformat()
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform comprehensive health check."""
        try:
            # Check Perplexity API
            perplexity_health = await self.perplexity_client.health_check()
            
            # Check registry loader
            registry_validation = self.registry_loader.validate_registry_file()
            
            # Determine overall status
            overall_status = "healthy"
            if perplexity_health["status"] != "healthy":
                overall_status = "degraded"
            if not registry_validation["file_valid"]:
                overall_status = "unhealthy"
            
            return {
                "service": "discovery",
                "status": overall_status,
                "components": {
                    "perplexity": perplexity_health,
                    "registry": {
                        "status": "healthy" if registry_validation["file_valid"] else "unhealthy",
                        "total_sources": registry_validation["total_sources"],
                        "enabled_sources": registry_validation["enabled_sources"]
                    }
                },
                "stats": self.discovery_stats,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                "service": "discovery",
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    async def close(self):
        """Close discovery service and cleanup resources."""
        try:
            await self.perplexity_client.close()
            logger.info("Discovery service closed")
        except Exception as e:
            logger.error(f"Error closing discovery service: {e}")
    
    async def _get_province_allowlist(self, province: str) -> List[str]:
        """Get domain allowlist for province from registry."""
        try:
            # Get sources from registry
            sources = self.registry_loader.get_sources_for_province(province)
            
            # Extract domains
            registry_domains = [source.get("domain") for source in sources if source.get("domain")]
            
            # Get foundation allowlist
            foundation_domains = list(get_foundation_allowlist())
            
            # Combine and deduplicate
            all_domains = list(set(registry_domains + foundation_domains))
            
            logger.debug(f"Allowlist for {province}: {all_domains}")
            return all_domains
            
        except Exception as e:
            logger.error(f"Failed to get allowlist for {province}: {e}")
            # Fallback to foundation allowlist
            return list(get_foundation_allowlist())
    
    async def _process_candidates(
        self, 
        candidates: List[Dict[str, Any]], 
        province: str
    ) -> List[Dict[str, Any]]:
        """Process and enrich discovered candidates."""
        processed_candidates = []
        
        for candidate in candidates:
            try:
                # Extract domain from URL
                from urllib.parse import urlparse
                parsed_url = urlparse(candidate["url"])
                domain = parsed_url.netloc.lower()
                
                # Enrich candidate with metadata
                enriched_candidate = {
                    "url": candidate["url"],
                    "title": candidate.get("title", "").strip(),
                    "domain": domain,
                    "province": province,
                    "source": candidate.get("source", "perplexity"),
                    "discovered_at": datetime.utcnow().isoformat(),
                    "confidence_score": self._calculate_confidence_score(candidate, province)
                }
                
                processed_candidates.append(enriched_candidate)
                
            except Exception as e:
                logger.error(f"Failed to process candidate {candidate.get('url', 'unknown')}: {e}")
        
        # Sort by confidence score
        processed_candidates.sort(key=lambda c: c["confidence_score"], reverse=True)
        
        return processed_candidates
    
    def _calculate_confidence_score(self, candidate: Dict[str, Any], province: str) -> float:
        """Calculate confidence score for candidate."""
        score = 0.5  # Base score
        
        try:
            title = candidate.get("title", "").lower()
            url = candidate.get("url", "").lower()
            domain = candidate.get("domain", "").lower()
            
            # Higher score for structured results with titles
            if title:
                score += 0.2
            
            # Higher score for official domains
            foundation_domains = get_foundation_allowlist()
            if any(allowed_domain in domain for allowed_domain in foundation_domains):
                score += 0.2
            
            # Higher score for relevant keywords in title/URL
            relevant_keywords = [
                "规则", "办法", "管理", "规定", "通知", "公告",
                "电力", "能源", "交易", "并网", "调度", "市场"
            ]
            
            content = f"{title} {url}"
            keyword_matches = sum(1 for keyword in relevant_keywords if keyword in content)
            score += min(keyword_matches * 0.05, 0.2)  # Max 0.2 bonus
            
            # Province-specific bonus
            province_keywords = {
                "guangdong": ["广东", "粤"],
                "shandong": ["山东", "鲁"],
                "inner_mongolia": ["内蒙古", "蒙"]
            }
            
            if province in province_keywords:
                for keyword in province_keywords[province]:
                    if keyword in content:
                        score += 0.1
                        break
            
            # Ensure score is between 0 and 1
            score = max(0.0, min(1.0, score))
            
        except Exception as e:
            logger.debug(f"Failed to calculate confidence score: {e}")
            score = 0.5  # Default score
        
        return score


async def run_foundation_discovery() -> Dict[str, Any]:
    """
    Convenience function to run discovery for all foundation provinces.
    
    Returns:
        Complete discovery results
    """
    service = SimpleDiscoveryService()
    
    try:
        # Run discovery for all provinces
        results = await service.discover_all_provinces()
        
        # Get service stats
        stats = await service.get_discovery_stats()
        
        return {
            "discovery_results": results,
            "service_stats": stats,
            "summary": {
                "total_provinces": len(results),
                "successful_provinces": len([r for r in results if r.get("status") == "completed"]),
                "total_candidates": sum(r.get("total_found", 0) for r in results),
                "timestamp": datetime.utcnow().isoformat()
            }
        }
        
    finally:
        await service.close()


if __name__ == "__main__":
    # Quick test of discovery service
    import json
    
    async def test_discovery():
        print("=== Foundation Quartet Discovery Test ===")
        
        service = SimpleDiscoveryService()
        
        try:
            # Test health check
            print("\n--- Health Check ---")
            health = await service.health_check()
            print(f"Status: {health['status']}")
            
            # Test single province discovery
            print("\n--- Single Province Discovery ---")
            result = await service.discover_for_province("guangdong", max_results=5)
            print(f"Province: {result['province']}")
            print(f"Status: {result['status']}")
            print(f"Candidates found: {result['total_found']}")
            
            if result.get("candidates"):
                print("\nTop candidates:")
                for i, candidate in enumerate(result["candidates"][:3], 1):
                    print(f"{i}. {candidate.get('title', 'No title')}")
                    print(f"   URL: {candidate['url']}")
                    print(f"   Confidence: {candidate['confidence_score']:.2f}")
            
            # Test verification job emission
            if result.get("candidates"):
                print("\n--- Verification Job Emission ---")
                verification_jobs = await service.emit_candidates_for_verification(
                    result["candidates"], result["province"]
                )
                print(f"Verification jobs created: {len(verification_jobs)}")
            
        finally:
            await service.close()
    
    asyncio.run(test_discovery())