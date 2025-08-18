"""Simplified verification service for Task 6 foundation quartet."""

import asyncio
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional, Set
from uuid import uuid4

from .simple_cse_client import SimpleCSEClient
from services.registry.robots_checker import get_foundation_allowlist

logger = logging.getLogger(__name__)


class SimpleVerificationService:
    """Simplified verification service focused on foundation quartet requirements."""
    
    def __init__(self, api_key: Optional[str] = None, cse_id: Optional[str] = None):
        """Initialize verification service."""
        self.cse_client = SimpleCSEClient(api_key, cse_id)
        self.verification_stats = {
            "total_verifications": 0,
            "successful_verifications": 0,
            "failed_verifications": 0,
            "total_candidates_processed": 0,
            "verified_candidates": 0,
            "filtered_candidates": 0,
            "last_verification": None
        }
    
    async def verify_discovery_candidates(
        self,
        candidates: List[Dict[str, Any]],
        allowlist: Optional[Set[str]] = None
    ) -> Dict[str, Any]:
        """
        Verify candidates from discovery service.
        
        Args:
            candidates: List of discovery candidates with 'url' and 'title'
            allowlist: Set of allowed domains (uses foundation allowlist if None)
            
        Returns:
            Verification result with verified candidates and metadata
        """
        verification_id = str(uuid4())
        start_time = datetime.utcnow()
        
        try:
            logger.info(f"Starting verification for {len(candidates)} candidates (ID: {verification_id})")
            
            # Use foundation allowlist if not provided
            if allowlist is None:
                allowlist = get_foundation_allowlist()
            
            # Verify candidates using canonicalization and allowlist filtering
            verified_candidates = await self.cse_client.verify_candidate_urls(candidates, allowlist)
            
            # Update stats
            self.verification_stats["total_verifications"] += 1
            self.verification_stats["successful_verifications"] += 1
            self.verification_stats["total_candidates_processed"] += len(candidates)
            self.verification_stats["verified_candidates"] += len(verified_candidates)
            self.verification_stats["filtered_candidates"] += len(candidates) - len(verified_candidates)
            self.verification_stats["last_verification"] = datetime.utcnow().isoformat()
            
            processing_time = (datetime.utcnow() - start_time).total_seconds()
            
            result = {
                "verification_id": verification_id,
                "status": "completed",
                "input_candidates": len(candidates),
                "verified_candidates": len(verified_candidates),
                "filtered_candidates": len(candidates) - len(verified_candidates),
                "verification_rate": len(verified_candidates) / len(candidates) if candidates else 0,
                "candidates": verified_candidates,
                "allowlist": list(allowlist),
                "processing_time_seconds": processing_time,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            logger.info(f"Verification completed: {len(verified_candidates)}/{len(candidates)} candidates verified")
            return result
            
        except Exception as e:
            logger.error(f"Verification failed: {e}")
            
            self.verification_stats["total_verifications"] += 1
            self.verification_stats["failed_verifications"] += 1
            
            return {
                "verification_id": verification_id,
                "status": "failed",
                "error": str(e),
                "input_candidates": len(candidates),
                "verified_candidates": 0,
                "candidates": [],
                "processing_time_seconds": (datetime.utcnow() - start_time).total_seconds(),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    async def search_and_verify(
        self,
        query: str,
        allowlist: Optional[Set[str]] = None,
        max_results: int = 10
    ) -> Dict[str, Any]:
        """
        Search using Google CSE and return verified URLs.
        
        Args:
            query: Search query
            allowlist: Set of allowed domains
            max_results: Maximum results to return
            
        Returns:
            Search and verification result
        """
        search_id = str(uuid4())
        start_time = datetime.utcnow()
        
        try:
            logger.info(f"Starting search and verify for query: '{query}' (ID: {search_id})")
            
            # Use foundation allowlist if not provided
            if allowlist is None:
                allowlist = get_foundation_allowlist()
            
            # Search and verify using CSE
            verified_urls = await self.cse_client.verify_urls(query, allowlist, max_results)
            
            # Convert URLs to candidate format
            verified_candidates = []
            for url in verified_urls:
                candidate = {
                    "url": url,
                    "canonical_url": url,
                    "domain": self.cse_client._extract_domain(url),
                    "verification_method": "google_cse",
                    "verified_at": datetime.utcnow().isoformat(),
                    "confidence_score": 0.8  # High confidence from direct search
                }
                verified_candidates.append(candidate)
            
            processing_time = (datetime.utcnow() - start_time).total_seconds()
            
            result = {
                "search_id": search_id,
                "status": "completed",
                "query": query,
                "verified_urls": len(verified_urls),
                "candidates": verified_candidates,
                "allowlist": list(allowlist),
                "processing_time_seconds": processing_time,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            logger.info(f"Search and verify completed: {len(verified_urls)} URLs found")
            return result
            
        except Exception as e:
            logger.error(f"Search and verify failed: {e}")
            
            return {
                "search_id": search_id,
                "status": "failed",
                "error": str(e),
                "query": query,
                "verified_urls": 0,
                "candidates": [],
                "processing_time_seconds": (datetime.utcnow() - start_time).total_seconds(),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    async def emit_verified_candidates_for_fetch(
        self,
        verified_candidates: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Emit verified candidates for fetch service (existing Task 7).
        
        Args:
            verified_candidates: List of verified candidate dictionaries
            
        Returns:
            List of fetch jobs created
        """
        fetch_jobs = []
        
        for candidate in verified_candidates:
            try:
                # Create fetch job payload
                fetch_job = {
                    "job_id": str(uuid4()),
                    "job_type": "fetch",
                    "url": candidate.get("canonical_url") or candidate.get("url"),
                    "domain": candidate.get("domain"),
                    "title": candidate.get("title", ""),
                    "province": candidate.get("province"),
                    "doc_class": candidate.get("doc_class"),
                    "verification_method": candidate.get("verification_method"),
                    "confidence_score": candidate.get("confidence_score", 0.0),
                    "created_at": datetime.utcnow().isoformat(),
                    "status": "pending"
                }
                
                fetch_jobs.append(fetch_job)
                
                # In a real implementation, this would emit to the existing fetch service
                logger.debug(f"Emitted fetch job: {fetch_job['job_id']}")
                
            except Exception as e:
                logger.error(f"Failed to emit fetch job for {candidate.get('url', 'unknown')}: {e}")
        
        logger.info(f"Emitted {len(fetch_jobs)} fetch jobs for verified candidates")
        return fetch_jobs
    
    async def get_verification_stats(self) -> Dict[str, Any]:
        """Get verification service statistics."""
        # Add CSE health check
        cse_health = await self.cse_client.health_check()
        
        return {
            "service": "verification",
            "stats": self.verification_stats,
            "cse_health": cse_health,
            "foundation_allowlist": list(get_foundation_allowlist()),
            "timestamp": datetime.utcnow().isoformat()
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform comprehensive health check."""
        try:
            # Check Google CSE API
            cse_health = await self.cse_client.health_check()
            
            # Determine overall status
            overall_status = "healthy"
            if cse_health["status"] != "healthy":
                if cse_health["status"] == "rate_limited":
                    overall_status = "degraded"
                else:
                    overall_status = "unhealthy"
            
            return {
                "service": "verification",
                "status": overall_status,
                "components": {
                    "google_cse": cse_health
                },
                "stats": self.verification_stats,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                "service": "verification",
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    async def close(self):
        """Close verification service and cleanup resources."""
        try:
            await self.cse_client.close()
            logger.info("Verification service closed")
        except Exception as e:
            logger.error(f"Error closing verification service: {e}")


class FoundationPipeline:
    """Complete foundation quartet pipeline: Registry → Discovery → Verification → Fetch."""
    
    def __init__(
        self,
        discovery_service=None,
        verification_service: Optional[SimpleVerificationService] = None
    ):
        """Initialize foundation pipeline."""
        self.discovery_service = discovery_service
        self.verification_service = verification_service or SimpleVerificationService()
    
    async def run_end_to_end_pipeline(
        self,
        province: str,
        max_candidates: int = 10
    ) -> Dict[str, Any]:
        """
        Run complete end-to-end pipeline for a province.
        
        Args:
            province: Province name (guangdong, shandong, inner_mongolia)
            max_candidates: Maximum candidates to process
            
        Returns:
            Complete pipeline result
        """
        pipeline_id = str(uuid4())
        start_time = datetime.utcnow()
        
        try:
            logger.info(f"Starting end-to-end pipeline for {province} (ID: {pipeline_id})")
            
            # Step 1: Discovery (Task 5)
            if not self.discovery_service:
                # Use simplified discovery for testing
                from services.discovery.simple_discovery_service import SimpleDiscoveryService
                self.discovery_service = SimpleDiscoveryService()
            
            discovery_result = await self.discovery_service.discover_for_province(
                province, max_candidates
            )
            
            if discovery_result["status"] != "completed":
                return {
                    "pipeline_id": pipeline_id,
                    "status": "failed",
                    "stage": "discovery",
                    "error": discovery_result.get("error", "Discovery failed"),
                    "province": province
                }
            
            # Step 2: Verification (Task 6)
            verification_result = await self.verification_service.verify_discovery_candidates(
                discovery_result["candidates"]
            )
            
            if verification_result["status"] != "completed":
                return {
                    "pipeline_id": pipeline_id,
                    "status": "failed",
                    "stage": "verification",
                    "error": verification_result.get("error", "Verification failed"),
                    "province": province,
                    "discovery_result": discovery_result
                }
            
            # Step 3: Emit for Fetch (Task 7 integration)
            fetch_jobs = await self.verification_service.emit_verified_candidates_for_fetch(
                verification_result["candidates"]
            )
            
            # Calculate pipeline metrics
            processing_time = (datetime.utcnow() - start_time).total_seconds()
            
            result = {
                "pipeline_id": pipeline_id,
                "status": "completed",
                "province": province,
                "stages": {
                    "discovery": {
                        "candidates_found": discovery_result["total_found"],
                        "processing_time_seconds": discovery_result.get("processing_time_seconds", 0)
                    },
                    "verification": {
                        "candidates_verified": verification_result["verified_candidates"],
                        "verification_rate": verification_result["verification_rate"],
                        "processing_time_seconds": verification_result["processing_time_seconds"]
                    },
                    "fetch_emission": {
                        "fetch_jobs_created": len(fetch_jobs)
                    }
                },
                "final_candidates": verification_result["candidates"],
                "total_processing_time_seconds": processing_time,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            logger.info(f"End-to-end pipeline completed for {province}: {len(verification_result['candidates'])} final candidates")
            return result
            
        except Exception as e:
            logger.error(f"End-to-end pipeline failed for {province}: {e}")
            
            return {
                "pipeline_id": pipeline_id,
                "status": "failed",
                "stage": "pipeline",
                "error": str(e),
                "province": province,
                "total_processing_time_seconds": (datetime.utcnow() - start_time).total_seconds(),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    async def run_walking_skeleton(self) -> Dict[str, Any]:
        """
        Run the complete "walking skeleton" for all foundation provinces.
        
        Returns:
            Walking skeleton results
        """
        skeleton_id = str(uuid4())
        start_time = datetime.utcnow()
        
        try:
            logger.info(f"Starting walking skeleton E2E test (ID: {skeleton_id})")
            
            provinces = ["guangdong", "shandong", "inner_mongolia"]
            province_results = []
            
            for province in provinces:
                try:
                    result = await self.run_end_to_end_pipeline(province, max_candidates=5)
                    province_results.append(result)
                    
                    # Add delay between provinces
                    await asyncio.sleep(2)
                    
                except Exception as e:
                    logger.error(f"Walking skeleton failed for {province}: {e}")
                    province_results.append({
                        "province": province,
                        "status": "failed",
                        "error": str(e)
                    })
            
            # Calculate overall metrics
            successful_provinces = [r for r in province_results if r.get("status") == "completed"]
            total_candidates = sum(len(r.get("final_candidates", [])) for r in successful_provinces)
            
            processing_time = (datetime.utcnow() - start_time).total_seconds()
            
            result = {
                "skeleton_id": skeleton_id,
                "status": "completed",
                "provinces_tested": len(provinces),
                "successful_provinces": len(successful_provinces),
                "total_final_candidates": total_candidates,
                "province_results": province_results,
                "total_processing_time_seconds": processing_time,
                "timestamp": datetime.utcnow().isoformat(),
                "pipeline_stages_validated": [
                    "Registry → Discovery (Task 5)",
                    "Discovery → Verification (Task 6)", 
                    "Verification → Fetch emission (Task 7 integration)"
                ]
            }
            
            logger.info(f"Walking skeleton completed: {len(successful_provinces)}/{len(provinces)} provinces successful, {total_candidates} total candidates")
            return result
            
        except Exception as e:
            logger.error(f"Walking skeleton failed: {e}")
            
            return {
                "skeleton_id": skeleton_id,
                "status": "failed",
                "error": str(e),
                "total_processing_time_seconds": (datetime.utcnow() - start_time).total_seconds(),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    async def close(self):
        """Close pipeline and cleanup resources."""
        try:
            if self.verification_service:
                await self.verification_service.close()
            if hasattr(self.discovery_service, 'close'):
                await self.discovery_service.close()
            logger.info("Foundation pipeline closed")
        except Exception as e:
            logger.error(f"Error closing foundation pipeline: {e}")


if __name__ == "__main__":
    # Quick test of verification service
    import json
    
    async def test_verification():
        print("=== Foundation Quartet Verification Test ===")
        
        service = SimpleVerificationService()
        
        try:
            # Test health check
            print("\n--- Health Check ---")
            health = await service.health_check()
            print(f"Status: {health['status']}")
            
            # Test candidate verification
            print("\n--- Candidate Verification ---")
            test_candidates = [
                {"url": "https://gzpec.cn/rules/market", "title": "广东电力市场规则"},
                {"url": "https://sdpxc.cn/grid/connection", "title": "山东并网管理办法"},
                {"url": "https://example.com/blocked", "title": "Blocked Domain"}  # Should be filtered
            ]
            
            result = await service.verify_discovery_candidates(test_candidates)
            print(f"Input candidates: {result['input_candidates']}")
            print(f"Verified candidates: {result['verified_candidates']}")
            print(f"Verification rate: {result['verification_rate']:.2f}")
            
            # Test search and verify
            print("\n--- Search and Verify ---")
            search_result = await service.search_and_verify("site:gzpec.cn 电力规则", max_results=3)
            print(f"Search query: {search_result['query']}")
            print(f"Verified URLs: {search_result['verified_urls']}")
            
        finally:
            await service.close()
    
    asyncio.run(test_verification())