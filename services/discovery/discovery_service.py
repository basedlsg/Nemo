"""Document discovery service with Perplexity integration."""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from .perplexity_client import PerplexityClient, PerplexityConfig
from .models import (
    DiscoveryQuery, DiscoveryResult, DiscoveryStatus, 
    DocumentCandidate, DiscoveryMetrics
)
from services.core.models import Province, DocumentClass, AssetType
from services.registry.manager import SourceRegistryManager
from services.database.crud import IngestionJobCRUD

logger = logging.getLogger(__name__)


class DiscoveryRequest:
    """Request for document discovery."""
    
    def __init__(
        self,
        province: Province,
        doc_class: DocumentClass,
        asset: Optional[AssetType] = None,
        keywords: Optional[List[str]] = None,
        max_results: int = 20,
        date_range: Optional[Dict[str, str]] = None
    ):
        self.province = province
        self.doc_class = doc_class
        self.asset = asset
        self.keywords = keywords or []
        self.max_results = max_results
        self.date_range = date_range
        self.request_id = uuid4()
        self.created_at = datetime.utcnow()


class DiscoveryService:
    """Service for discovering energy regulation documents."""
    
    def __init__(
        self,
        perplexity_client: Optional[PerplexityClient] = None,
        registry_manager: Optional[SourceRegistryManager] = None
    ):
        """Initialize discovery service."""
        self.perplexity_client = perplexity_client or PerplexityClient()
        self.registry_manager = registry_manager or SourceRegistryManager()
        self.metrics = DiscoveryMetrics()
        self._active_queries: Dict[UUID, DiscoveryQuery] = {}
    
    async def initialize(self) -> None:
        """Initialize discovery service."""
        try:
            logger.info("Initializing discovery service")
            
            # Initialize registry manager
            await self.registry_manager.initialize()
            
            # Test Perplexity connectivity
            health = await self.perplexity_client.health_check()
            if health["status"] != "healthy":
                logger.warning(f"Perplexity API health check failed: {health}")
            else:
                logger.info("Perplexity API connectivity verified")
            
            logger.info("Discovery service initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize discovery service: {e}")
            raise
    
    async def discover_documents(
        self,
        request: DiscoveryRequest,
        session: Optional[AsyncSession] = None
    ) -> DiscoveryResult:
        """Discover documents based on request parameters."""
        try:
            logger.info(f"Starting document discovery for {request.province.value} {request.doc_class.value}")
            
            # Create discovery query
            query = DiscoveryQuery(
                query_id=request.request_id,
                province=request.province,
                doc_class=request.doc_class,
                asset=request.asset,
                keywords=request.keywords,
                date_range=request.date_range,
                max_results=request.max_results
            )
            
            # Get domain allowlist from registry
            domain_allowlist = await self._get_domain_allowlist(query)
            query.domain_filter = domain_allowlist
            
            # Track active query
            self._active_queries[query.query_id] = query
            
            try:
                # Generate search query
                search_query = query.generate_search_query()
                logger.debug(f"Generated search query: {search_query}")
                
                # Perform discovery using Perplexity
                result = await self.perplexity_client.search_documents(
                    query=search_query,
                    domain_filter=domain_allowlist,
                    max_results=request.max_results
                )
                
                # Set query ID in result
                result.query_id = query.query_id
                
                # Filter and validate candidates
                result = await self._process_discovery_result(result, query)
                
                # Update metrics
                self.metrics.update_with_result(result)
                
                # Create ingestion jobs for valid candidates
                if session and result.status == DiscoveryStatus.COMPLETED:
                    await self._create_ingestion_jobs(session, result)
                
                logger.info(f"Discovery completed: {len(result.candidates)} candidates found")
                return result
                
            finally:
                # Remove from active queries
                self._active_queries.pop(query.query_id, None)
                
        except Exception as e:
            logger.error(f"Document discovery failed: {e}")
            return DiscoveryResult(
                query_id=request.request_id,
                status=DiscoveryStatus.FAILED,
                error_message=str(e)
            )
    
    async def discover_for_province_and_asset(
        self,
        province: Province,
        asset: AssetType,
        session: Optional[AsyncSession] = None
    ) -> List[DiscoveryResult]:
        """Discover documents for all document classes of a province/asset combination."""
        results = []
        
        # Get relevant document classes for this asset
        relevant_doc_classes = await self._get_relevant_doc_classes(province, asset)
        
        for doc_class in relevant_doc_classes:
            request = DiscoveryRequest(
                province=province,
                doc_class=doc_class,
                asset=asset,
                max_results=10  # Smaller batch for comprehensive discovery
            )
            
            result = await self.discover_documents(request, session)
            results.append(result)
            
            # Add delay between requests to respect rate limits
            await asyncio.sleep(1)
        
        return results
    
    async def get_discovery_status(self, query_id: UUID) -> Optional[Dict[str, Any]]:
        """Get status of active discovery query."""
        query = self._active_queries.get(query_id)
        if not query:
            return None
        
        return {
            "query_id": str(query_id),
            "province": query.province.value,
            "doc_class": query.doc_class.value,
            "asset": query.asset.value if query.asset else None,
            "status": "running",
            "created_at": query.created_at.isoformat(),
            "elapsed_seconds": (datetime.utcnow() - query.created_at).total_seconds()
        }
    
    async def get_discovery_metrics(self) -> Dict[str, Any]:
        """Get discovery service metrics."""
        return {
            "total_queries": self.metrics.total_queries,
            "successful_queries": self.metrics.successful_queries,
            "failed_queries": self.metrics.failed_queries,
            "rate_limited_queries": self.metrics.rate_limited_queries,
            "success_rate": self.metrics.get_success_rate(),
            "avg_processing_time_ms": self.metrics.avg_processing_time_ms,
            "total_candidates_found": self.metrics.total_candidates_found,
            "official_candidates_found": self.metrics.official_candidates_found,
            "official_candidate_ratio": self.metrics.get_official_candidate_ratio(),
            "active_queries": len(self._active_queries),
            "last_updated": self.metrics.last_updated.isoformat()
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check of discovery service."""
        health_status = {
            "service": "discovery",
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "components": {}
        }
        
        try:
            # Check Perplexity API
            perplexity_health = await self.perplexity_client.health_check()
            health_status["components"]["perplexity"] = perplexity_health
            
            # Check registry manager
            registry_health = await self.registry_manager.get_registry_health()
            health_status["components"]["registry"] = {
                "status": registry_health["overall_status"],
                "sources_count": registry_health["summary"].get("total_sources", 0)
            }
            
            # Check overall status
            component_statuses = [
                perplexity_health["status"],
                registry_health["overall_status"]
            ]
            
            if "unhealthy" in component_statuses:
                health_status["status"] = "unhealthy"
            elif "degraded" in component_statuses:
                health_status["status"] = "degraded"
            
            # Add metrics
            health_status["metrics"] = await self.get_discovery_metrics()
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            health_status["status"] = "unhealthy"
            health_status["error"] = str(e)
        
        return health_status
    
    async def close(self):
        """Close discovery service and cleanup resources."""
        try:
            await self.perplexity_client.close()
            logger.info("Discovery service closed")
        except Exception as e:
            logger.error(f"Error closing discovery service: {e}")
    
    async def _get_domain_allowlist(self, query: DiscoveryQuery) -> List[str]:
        """Get domain allowlist for discovery query."""
        try:
            # Get sources from registry for this province/doc_class
            sources = await self.registry_manager.get_sources_for_province(
                query.province, query.doc_class
            )
            
            # Extract domains from sources
            source_domains = [source.domain for source in sources]
            
            # Add base allowlist
            base_allowlist = query.get_domain_allowlist()
            
            # Combine and deduplicate
            all_domains = list(set(source_domains + base_allowlist))
            
            logger.debug(f"Domain allowlist for {query.province.value}: {all_domains}")
            return all_domains
            
        except Exception as e:
            logger.error(f"Failed to get domain allowlist: {e}")
            # Fallback to base allowlist
            return query.get_domain_allowlist()
    
    async def _process_discovery_result(
        self,
        result: DiscoveryResult,
        query: DiscoveryQuery
    ) -> DiscoveryResult:
        """Process and validate discovery result."""
        if result.status != DiscoveryStatus.COMPLETED:
            return result
        
        processed_candidates = []
        filtered_count = 0
        
        for candidate in result.candidates:
            # Validate candidate
            if await self._validate_candidate(candidate, query):
                processed_candidates.append(candidate)
            else:
                filtered_count += 1
        
        # Update result
        result.candidates = processed_candidates
        result.filtered_count = filtered_count
        
        # Sort by confidence score
        result.candidates = result.sort_by_confidence()
        
        return result
    
    async def _validate_candidate(
        self,
        candidate: DocumentCandidate,
        query: DiscoveryQuery
    ) -> bool:
        """Validate document candidate."""
        try:
            # Check if domain is in allowlist
            if not any(domain in candidate.domain for domain in query.domain_filter):
                logger.debug(f"Candidate filtered: domain {candidate.domain} not in allowlist")
                return False
            
            # Check if URL is accessible (basic validation)
            if not candidate.url.startswith(("http://", "https://")):
                logger.debug(f"Candidate filtered: invalid URL {candidate.url}")
                return False
            
            # Check for minimum confidence score
            if candidate.confidence_score < 0.3:
                logger.debug(f"Candidate filtered: low confidence {candidate.confidence_score}")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Candidate validation failed: {e}")
            return False
    
    async def _create_ingestion_jobs(
        self,
        session: AsyncSession,
        result: DiscoveryResult
    ) -> None:
        """Create ingestion jobs for discovered candidates."""
        try:
            for candidate in result.get_official_candidates():
                # Create ingestion job
                await IngestionJobCRUD.create(
                    session,
                    source_domain=candidate.domain,
                    url=candidate.url,
                    job_type="discovery"
                )
            
            logger.info(f"Created {len(result.get_official_candidates())} ingestion jobs")
            
        except Exception as e:
            logger.error(f"Failed to create ingestion jobs: {e}")
    
    async def _get_relevant_doc_classes(
        self,
        province: Province,
        asset: AssetType
    ) -> List[DocumentClass]:
        """Get relevant document classes for province/asset combination."""
        try:
            # Get asset-specific priorities from registry
            priority_sources = await self.registry_manager.get_priority_sources_for_asset(
                province, asset.value
            )
            
            # Extract document classes from priority sources
            doc_classes = set()
            for source in priority_sources:
                doc_classes.update(source.doc_classes)
            
            # If no specific priorities, use all document classes
            if not doc_classes:
                doc_classes = set(DocumentClass)
            
            return list(doc_classes)
            
        except Exception as e:
            logger.error(f"Failed to get relevant doc classes: {e}")
            # Fallback to all document classes
            return list(DocumentClass)


class DiscoveryScheduler:
    """Scheduler for automated document discovery."""
    
    def __init__(self, discovery_service: DiscoveryService):
        """Initialize discovery scheduler."""
        self.discovery_service = discovery_service
        self.scheduled_tasks: Dict[str, asyncio.Task] = {}
        self.running = False
    
    async def start_scheduled_discovery(self) -> None:
        """Start scheduled discovery for all enabled provinces."""
        if self.running:
            logger.warning("Discovery scheduler already running")
            return
        
        self.running = True
        logger.info("Starting scheduled discovery")
        
        try:
            # Schedule discovery for each enabled province
            enabled_provinces = Province.enabled_provinces()
            
            for province in enabled_provinces:
                task_name = f"discovery_{province.value}"
                task = asyncio.create_task(
                    self._run_province_discovery(Province(province))
                )
                self.scheduled_tasks[task_name] = task
            
            # Wait for all tasks to complete
            await asyncio.gather(*self.scheduled_tasks.values(), return_exceptions=True)
            
        except Exception as e:
            logger.error(f"Scheduled discovery failed: {e}")
        finally:
            self.running = False
            self.scheduled_tasks.clear()
    
    async def stop_scheduled_discovery(self) -> None:
        """Stop all scheduled discovery tasks."""
        logger.info("Stopping scheduled discovery")
        
        for task_name, task in self.scheduled_tasks.items():
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    logger.info(f"Cancelled discovery task: {task_name}")
        
        self.scheduled_tasks.clear()
        self.running = False
    
    async def _run_province_discovery(self, province: Province) -> None:
        """Run discovery for a specific province."""
        try:
            logger.info(f"Starting scheduled discovery for {province.value}")
            
            # Discover for each asset type
            for asset in AssetType:
                results = await self.discovery_service.discover_for_province_and_asset(
                    province, asset
                )
                
                successful_results = [r for r in results if r.status == DiscoveryStatus.COMPLETED]
                total_candidates = sum(len(r.candidates) for r in successful_results)
                
                logger.info(f"Province {province.value}, Asset {asset.value}: {total_candidates} candidates found")
                
                # Add delay between asset types
                await asyncio.sleep(5)
            
            logger.info(f"Completed scheduled discovery for {province.value}")
            
        except Exception as e:
            logger.error(f"Province discovery failed for {province.value}: {e}")