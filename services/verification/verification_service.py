"""Document verification service with Google CSE integration."""

import asyncio
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from .google_cse_client import GoogleCSEClient, GoogleCSEConfig
from .models import (
    VerificationCandidate, VerificationResult, VerificationStatus,
    VerificationMetrics, VerificationMethod
)
from services.discovery.models import DocumentCandidate
from services.core.models import Province, DocumentClass
from services.registry.manager import SourceRegistryManager
from services.database.crud import IngestionJobCRUD

logger = logging.getLogger(__name__)


class VerificationRequest:
    """Request for document verification."""
    
    def __init__(
        self,
        candidates: List[DocumentCandidate],
        province: Optional[Province] = None,
        doc_class: Optional[DocumentClass] = None,
        domain_allowlist: Optional[List[str]] = None,
        batch_size: int = 5,
        batch_delay: float = 1.0
    ):
        self.candidates = candidates
        self.province = province
        self.doc_class = doc_class
        self.domain_allowlist = domain_allowlist or []
        self.batch_size = batch_size
        self.batch_delay = batch_delay
        self.request_id = uuid4()
        self.created_at = datetime.utcnow()


class VerificationService:
    """Service for verifying discovered energy regulation documents."""
    
    def __init__(
        self,
        google_cse_client: Optional[GoogleCSEClient] = None,
        registry_manager: Optional[SourceRegistryManager] = None
    ):
        """Initialize verification service."""
        self.google_cse_client = google_cse_client or GoogleCSEClient()
        self.registry_manager = registry_manager or SourceRegistryManager()
        self.metrics = VerificationMetrics()
        self._active_requests: Dict[UUID, VerificationRequest] = {}
    
    async def initialize(self) -> None:
        """Initialize verification service."""
        try:
            logger.info("Initializing verification service")
            
            # Initialize registry manager
            await self.registry_manager.initialize()
            
            # Test Google CSE connectivity
            health = await self.google_cse_client.health_check()
            if health["status"] not in ["healthy", "rate_limited"]:
                logger.warning(f"Google CSE health check failed: {health}")
            else:
                logger.info("Google CSE connectivity verified")
            
            logger.info("Verification service initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize verification service: {e}")
            raise
    
    async def verify_documents(
        self,
        request: VerificationRequest,
        session: Optional[AsyncSession] = None
    ) -> VerificationResult:
        """Verify discovered documents using Google CSE."""
        try:
            logger.info(f"Starting document verification for {len(request.candidates)} candidates")
            
            # Track active request
            self._active_requests[request.request_id] = request
            
            try:
                # Get domain allowlist if not provided
                if not request.domain_allowlist and request.province:
                    request.domain_allowlist = await self._get_domain_allowlist(
                        request.province, request.doc_class
                    )
                
                # Convert candidates to verification format
                candidate_data = [
                    {
                        "url": candidate.url,
                        "title": candidate.title,
                        "confidence_score": candidate.confidence_score
                    }
                    for candidate in request.candidates
                ]
                
                # Perform verification in batches
                verified_candidates = await self._verify_candidates_in_batches(
                    candidate_data, request.domain_allowlist, request.batch_size, request.batch_delay
                )
                
                # Create result
                result = VerificationResult(
                    request_id=request.request_id,
                    status=VerificationStatus.VERIFIED,
                    candidates=verified_candidates,
                    total_candidates=len(verified_candidates),
                    verified_candidates=len([c for c in verified_candidates if c.is_verified()]),
                    not_found_candidates=len([c for c in verified_candidates if c.verification_status == VerificationStatus.NOT_FOUND]),
                    failed_candidates=len([c for c in verified_candidates if c.verification_status == VerificationStatus.FAILED]),
                    completed_at=datetime.utcnow()
                )
                
                # Update metrics
                self.metrics.update_with_result(result)
                
                # Create ingestion jobs for verified candidates
                if session:
                    await self._create_ingestion_jobs(session, result)
                
                logger.info(f"Verification completed: {result.verified_candidates}/{result.total_candidates} verified")
                return result
                
            finally:
                # Remove from active requests
                self._active_requests.pop(request.request_id, None)
                
        except Exception as e:
            logger.error(f"Document verification failed: {e}")
            return VerificationResult(
                request_id=request.request_id,
                status=VerificationStatus.FAILED,
                error_message=str(e)
            )
    
    async def verify_single_document(
        self,
        url: str,
        title: Optional[str] = None,
        domain_allowlist: Optional[List[str]] = None
    ) -> VerificationCandidate:
        """Verify a single document."""
        try:
            # Use default allowlist if not provided
            if not domain_allowlist:
                domain_allowlist = [".gov.cn", "gzpec.cn", "sgcc.com.cn"]
            
            # Verify using Google CSE
            candidate = await self.google_cse_client.verify_document(
                url, domain_allowlist, title
            )
            
            # Update method metrics
            if candidate.verification_method:
                self.metrics.update_method_count(candidate.verification_method)
            
            return candidate
            
        except Exception as e:
            logger.error(f"Single document verification failed for {url}: {e}")
            return VerificationCandidate(
                original_url=url,
                domain=self._extract_domain(url),
                verification_status=VerificationStatus.FAILED,
                error_message=str(e)
            )
    
    async def search_and_verify(
        self,
        query: str,
        domain_allowlist: List[str],
        max_results: int = 10
    ) -> List[VerificationCandidate]:
        """Search for documents and return pre-verified candidates."""
        try:
            # Search using Google CSE
            search_results = await self.google_cse_client.search_documents(
                query, domain_allowlist, max_results
            )
            
            # Convert search results to verification candidates
            candidates = []
            for result in search_results:
                candidate = VerificationCandidate(
                    original_url=result.link,
                    domain=result.extract_domain(),
                    verification_status=VerificationStatus.VERIFIED,
                    verification_method=VerificationMethod.GOOGLE_CSE,
                    canonical_url=result.link,
                    verified_title=result.title,
                    verified_snippet=result.snippet,
                    verification_confidence=0.8,  # High confidence from direct search
                    verified_at=datetime.utcnow()
                )
                candidates.append(candidate)
            
            logger.info(f"Search and verify completed: {len(candidates)} candidates found")
            return candidates
            
        except Exception as e:
            logger.error(f"Search and verify failed: {e}")
            return []
    
    async def get_verification_status(self, request_id: UUID) -> Optional[Dict[str, Any]]:
        """Get status of active verification request."""
        request = self._active_requests.get(request_id)
        if not request:
            return None
        
        return {
            "request_id": str(request_id),
            "candidates_count": len(request.candidates),
            "province": request.province.value if request.province else None,
            "doc_class": request.doc_class.value if request.doc_class else None,
            "status": "running",
            "created_at": request.created_at.isoformat(),
            "elapsed_seconds": (datetime.utcnow() - request.created_at).total_seconds()
        }
    
    async def get_verification_metrics(self) -> Dict[str, Any]:
        """Get verification service metrics."""
        return {
            "total_requests": self.metrics.total_requests,
            "successful_requests": self.metrics.successful_requests,
            "failed_requests": self.metrics.failed_requests,
            "rate_limited_requests": self.metrics.rate_limited_requests,
            "success_rate": self.metrics.get_success_rate(),
            
            "total_candidates_processed": self.metrics.total_candidates_processed,
            "verified_candidates": self.metrics.verified_candidates,
            "not_found_candidates": self.metrics.not_found_candidates,
            "failed_candidates": self.metrics.failed_candidates,
            "overall_verification_rate": self.metrics.get_overall_verification_rate(),
            
            "avg_processing_time_ms": self.metrics.avg_processing_time_ms,
            "avg_verification_rate": self.metrics.avg_verification_rate,
            
            "method_distribution": self.metrics.get_method_distribution(),
            "active_requests": len(self._active_requests),
            "last_updated": self.metrics.last_updated.isoformat()
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check of verification service."""
        health_status = {
            "service": "verification",
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "components": {}
        }
        
        try:
            # Check Google CSE API
            cse_health = await self.google_cse_client.health_check()
            health_status["components"]["google_cse"] = cse_health
            
            # Check registry manager
            registry_health = await self.registry_manager.get_registry_health()
            health_status["components"]["registry"] = {
                "status": registry_health["overall_status"],
                "sources_count": registry_health["summary"].get("total_sources", 0)
            }
            
            # Check overall status
            component_statuses = [
                cse_health["status"],
                registry_health["overall_status"]
            ]
            
            if "unhealthy" in component_statuses:
                health_status["status"] = "unhealthy"
            elif "degraded" in component_statuses or "rate_limited" in component_statuses:
                health_status["status"] = "degraded"
            
            # Add metrics
            health_status["metrics"] = await self.get_verification_metrics()
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            health_status["status"] = "unhealthy"
            health_status["error"] = str(e)
        
        return health_status
    
    async def close(self):
        """Close verification service and cleanup resources."""
        try:
            await self.google_cse_client.close()
            logger.info("Verification service closed")
        except Exception as e:
            logger.error(f"Error closing verification service: {e}")
    
    async def _get_domain_allowlist(
        self,
        province: Province,
        doc_class: Optional[DocumentClass] = None
    ) -> List[str]:
        """Get domain allowlist for verification."""
        try:
            # Get sources from registry
            sources = await self.registry_manager.get_sources_for_province(
                province, doc_class
            )
            
            # Extract domains from sources
            source_domains = [source.domain for source in sources]
            
            # Add base allowlist
            base_allowlist = [".gov.cn"]
            
            # Add province-specific domains
            province_domains = {
                Province.GUANGDONG: ["gzpec.cn", "gdpec.com.cn", "csg.cn"],
                Province.SHANDONG: ["shandong-electric.com.cn", "sgcc.com.cn"],
                Province.INNER_MONGOLIA: ["nmgdl.cn", "nmg.sgcc.com.cn"],
                Province.SICHUAN: ["sc.sgcc.com.cn", "scpec.com.cn"]
            }
            
            if province in province_domains:
                base_allowlist.extend(province_domains[province])
            
            # Combine and deduplicate
            all_domains = list(set(source_domains + base_allowlist))
            
            logger.debug(f"Domain allowlist for {province.value}: {all_domains}")
            return all_domains
            
        except Exception as e:
            logger.error(f"Failed to get domain allowlist: {e}")
            # Fallback to base allowlist
            return [".gov.cn"]
    
    async def _verify_candidates_in_batches(
        self,
        candidate_data: List[Dict[str, Any]],
        domain_allowlist: List[str],
        batch_size: int,
        batch_delay: float
    ) -> List[VerificationCandidate]:
        """Verify candidates in batches to respect rate limits."""
        all_verified = []
        
        # Process in batches
        for i in range(0, len(candidate_data), batch_size):
            batch = candidate_data[i:i + batch_size]
            
            logger.debug(f"Verifying batch {i//batch_size + 1}: {len(batch)} candidates")
            
            # Verify batch
            batch_verified = await self.google_cse_client.verify_documents_batch(
                batch, domain_allowlist, batch_delay
            )
            
            all_verified.extend(batch_verified)
            
            # Update method metrics
            for candidate in batch_verified:
                if candidate.verification_method:
                    self.metrics.update_method_count(candidate.verification_method)
            
            # Add delay between batches (except for last batch)
            if i + batch_size < len(candidate_data):
                await asyncio.sleep(batch_delay * 2)  # Longer delay between batches
        
        return all_verified
    
    async def _create_ingestion_jobs(
        self,
        session: AsyncSession,
        result: VerificationResult
    ) -> None:
        """Create ingestion jobs for verified candidates."""
        try:
            verified_candidates = result.get_verified_candidates()
            
            for candidate in verified_candidates:
                # Create ingestion job
                await IngestionJobCRUD.create(
                    session,
                    source_domain=candidate.domain,
                    url=candidate.get_final_url(),
                    job_type="verification"
                )
            
            logger.info(f"Created {len(verified_candidates)} ingestion jobs from verification")
            
        except Exception as e:
            logger.error(f"Failed to create ingestion jobs: {e}")
    
    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL."""
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            return parsed.netloc.lower()
        except Exception:
            return ""


class VerificationPipeline:
    """Pipeline that combines discovery and verification."""
    
    def __init__(
        self,
        verification_service: VerificationService,
        discovery_service=None  # Import would be circular, so we accept it as parameter
    ):
        """Initialize verification pipeline."""
        self.verification_service = verification_service
        self.discovery_service = discovery_service
    
    async def discover_and_verify(
        self,
        province: Province,
        doc_class: DocumentClass,
        asset: Optional[str] = None,
        max_candidates: int = 20,
        session: Optional[AsyncSession] = None
    ) -> Dict[str, Any]:
        """Complete pipeline: discover documents then verify them."""
        try:
            logger.info(f"Starting discover and verify pipeline for {province.value} {doc_class.value}")
            
            # Step 1: Discovery
            if not self.discovery_service:
                raise ValueError("Discovery service not provided to pipeline")
            
            from services.discovery.discovery_service import DiscoveryRequest
            
            discovery_request = DiscoveryRequest(
                province=province,
                doc_class=doc_class,
                asset=asset,
                max_results=max_candidates
            )
            
            discovery_result = await self.discovery_service.discover_documents(
                discovery_request, session
            )
            
            if discovery_result.status != "completed":
                return {
                    "status": "failed",
                    "stage": "discovery",
                    "error": discovery_result.error_message,
                    "discovery_result": discovery_result.dict()
                }
            
            # Step 2: Verification
            verification_request = VerificationRequest(
                candidates=discovery_result.candidates,
                province=province,
                doc_class=doc_class
            )
            
            verification_result = await self.verification_service.verify_documents(
                verification_request, session
            )
            
            # Step 3: Results
            verified_candidates = verification_result.get_verified_candidates()
            high_confidence = verification_result.get_high_confidence_candidates()
            
            return {
                "status": "completed",
                "discovery_result": {
                    "total_discovered": len(discovery_result.candidates),
                    "official_discovered": len(discovery_result.get_official_candidates())
                },
                "verification_result": {
                    "total_verified": len(verified_candidates),
                    "high_confidence": len(high_confidence),
                    "verification_rate": verification_result.get_verification_rate()
                },
                "final_candidates": [c.dict() for c in high_confidence],
                "processing_summary": {
                    "discovery_time_ms": discovery_result.processing_time_ms,
                    "verification_time_ms": verification_result.processing_time_ms,
                    "total_time_ms": (discovery_result.processing_time_ms or 0) + (verification_result.processing_time_ms or 0)
                }
            }
            
        except Exception as e:
            logger.error(f"Discover and verify pipeline failed: {e}")
            return {
                "status": "failed",
                "stage": "pipeline",
                "error": str(e)
            }