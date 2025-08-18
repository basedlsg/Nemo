"""Snapshot storage with WORM (Write Once Read Many) compliance."""

import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from uuid import UUID

from google.cloud import storage
from google.cloud.exceptions import NotFound, Conflict
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings

from .models import DocumentSnapshot, StorageResult, StorageStatus

logger = logging.getLogger(__name__)


class StorageConfig(BaseSettings):
    """Configuration for snapshot storage."""
    
    # Google Cloud Storage settings
    bucket_name: str = Field(..., env="GCS_BUCKET_NAME")
    project_id: Optional[str] = Field(None, env="GOOGLE_CLOUD_PROJECT")
    
    # WORM settings
    retention_period_days: int = Field(default=2555, env="STORAGE_RETENTION_DAYS")  # ~7 years
    enable_versioning: bool = Field(default=True, env="STORAGE_ENABLE_VERSIONING")
    
    # Performance settings
    chunk_size: int = Field(default=8192, env="STORAGE_CHUNK_SIZE")
    timeout: int = Field(default=300, env="STORAGE_TIMEOUT")  # 5 minutes
    max_retries: int = Field(default=3, env="STORAGE_MAX_RETRIES")
    
    # Metadata settings
    include_custom_metadata: bool = Field(default=True, env="STORAGE_INCLUDE_METADATA")
    compress_content: bool = Field(default=False, env="STORAGE_COMPRESS_CONTENT")
    
    class Config:
        env_file = ".env"


class SnapshotMetadata(BaseModel):
    """Metadata for stored snapshots."""
    
    snapshot_id: str
    original_url: str
    domain: str
    content_type: str
    content_length: int
    sha256_checksum: str
    stored_at: str
    effective_date: Optional[str] = None
    title: Optional[str] = None
    province: Optional[str] = None
    doc_class: Optional[str] = None
    
    # Storage metadata
    storage_class: str = "STANDARD"
    retention_expiry: Optional[str] = None
    
    def to_gcs_metadata(self) -> Dict[str, str]:
        """Convert to GCS metadata format."""
        metadata = {
            "snapshot-id": self.snapshot_id,
            "original-url": self.original_url,
            "domain": self.domain,
            "content-type": self.content_type,
            "content-length": str(self.content_length),
            "sha256-checksum": self.sha256_checksum,
            "stored-at": self.stored_at,
            "storage-class": self.storage_class
        }
        
        # Add optional fields
        if self.effective_date:
            metadata["effective-date"] = self.effective_date
        if self.title:
            metadata["title"] = self.title[:500]  # Limit metadata size
        if self.province:
            metadata["province"] = self.province
        if self.doc_class:
            metadata["doc-class"] = self.doc_class
        if self.retention_expiry:
            metadata["retention-expiry"] = self.retention_expiry
        
        return metadata


class SnapshotStorage:
    """Handles immutable storage of document snapshots with WORM compliance."""
    
    def __init__(self, config: Optional[StorageConfig] = None):
        """Initialize snapshot storage."""
        self.config = config or StorageConfig()
        self._client: Optional[storage.Client] = None
        self._bucket: Optional[storage.Bucket] = None
        self._duplicate_cache: Dict[str, UUID] = {}  # checksum -> snapshot_id
        self._lock = asyncio.Lock()
    
    async def initialize(self) -> None:
        """Initialize storage client and bucket."""
        try:
            logger.info("Initializing snapshot storage")
            
            # Initialize GCS client
            if self.config.project_id:
                self._client = storage.Client(project=self.config.project_id)
            else:
                self._client = storage.Client()
            
            # Get or create bucket
            self._bucket = self._client.bucket(self.config.bucket_name)
            
            # Verify bucket exists and is accessible
            if not self._bucket.exists():
                raise ValueError(f"Storage bucket does not exist: {self.config.bucket_name}")
            
            # Configure bucket for WORM if needed
            await self._configure_bucket_worm()
            
            logger.info(f"Snapshot storage initialized with bucket: {self.config.bucket_name}")
            
        except Exception as e:
            logger.error(f"Failed to initialize snapshot storage: {e}")
            raise
    
    async def store_snapshot(self, snapshot: DocumentSnapshot) -> StorageResult:
        """Store document snapshot with WORM compliance."""
        start_time = time.time()
        
        try:
            logger.info(f"Storing snapshot: {snapshot.snapshot_id}")
            
            # Check for duplicates
            async with self._lock:
                if snapshot.sha256_checksum in self._duplicate_cache:
                    duplicate_id = self._duplicate_cache[snapshot.sha256_checksum]
                    return StorageResult(
                        snapshot_id=snapshot.snapshot_id,
                        status=StorageStatus.DUPLICATE,
                        duplicate_of=duplicate_id,
                        storage_time_ms=int((time.time() - start_time) * 1000)
                    )
            
            # Generate storage path and metadata
            storage_key = snapshot.get_storage_key()
            metadata = self._create_snapshot_metadata(snapshot)
            
            # Store with retries
            result = await self._store_with_retries(snapshot, storage_key, metadata)
            
            # Update duplicate cache on success
            if result.status == StorageStatus.STORED:
                async with self._lock:
                    self._duplicate_cache[snapshot.sha256_checksum] = snapshot.snapshot_id
                
                # Update snapshot with storage info
                snapshot.storage_path = storage_key
                snapshot.storage_bucket = self.config.bucket_name
            
            result.storage_time_ms = int((time.time() - start_time) * 1000)
            return result
            
        except Exception as e:
            logger.error(f"Failed to store snapshot {snapshot.snapshot_id}: {e}")
            return StorageResult(
                snapshot_id=snapshot.snapshot_id,
                status=StorageStatus.FAILED,
                error_message=str(e),
                storage_time_ms=int((time.time() - start_time) * 1000)
            )
    
    async def store_snapshots_batch(self, snapshots: List[DocumentSnapshot]) -> List[StorageResult]:
        """Store multiple snapshots efficiently."""
        results = []
        
        # Process in parallel with limited concurrency
        semaphore = asyncio.Semaphore(5)  # Limit concurrent uploads
        
        async def store_single(snapshot):
            async with semaphore:
                return await self.store_snapshot(snapshot)
        
        # Execute all storage operations
        tasks = [store_single(snapshot) for snapshot in snapshots]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Handle exceptions
        final_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                final_results.append(StorageResult(
                    snapshot_id=snapshots[i].snapshot_id,
                    status=StorageStatus.FAILED,
                    error_message=str(result)
                ))
            else:
                final_results.append(result)
        
        return final_results
    
    async def retrieve_snapshot(self, snapshot_id: UUID) -> Optional[DocumentSnapshot]:
        """Retrieve stored snapshot by ID."""
        try:
            # Search for snapshot by metadata
            blobs = self._bucket.list_blobs(prefix="", metadata={"snapshot-id": str(snapshot_id)})
            
            for blob in blobs:
                if blob.metadata and blob.metadata.get("snapshot-id") == str(snapshot_id):
                    # Download content
                    content = blob.download_as_bytes()
                    
                    # Reconstruct snapshot from metadata
                    snapshot = self._reconstruct_snapshot_from_blob(blob, content)
                    return snapshot
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to retrieve snapshot {snapshot_id}: {e}")
            return None
    
    async def check_duplicate(self, checksum: str) -> Optional[UUID]:
        """Check if document with checksum already exists."""
        async with self._lock:
            return self._duplicate_cache.get(checksum)
    
    async def get_storage_stats(self) -> Dict[str, Any]:
        """Get storage statistics."""
        try:
            # Get bucket info
            bucket_info = {
                "name": self._bucket.name,
                "location": self._bucket.location,
                "storage_class": self._bucket.storage_class,
                "versioning_enabled": self._bucket.versioning_enabled,
                "retention_policy": None
            }
            
            # Get retention policy if exists
            if self._bucket.retention_policy:
                bucket_info["retention_policy"] = {
                    "retention_period": self._bucket.retention_policy.retention_period,
                    "effective_time": self._bucket.retention_policy.effective_time.isoformat() if self._bucket.retention_policy.effective_time else None
                }
            
            # Count objects and calculate size
            total_objects = 0
            total_size = 0
            
            # Sample recent objects for stats (limit to avoid timeout)
            for blob in self._bucket.list_blobs(max_results=1000):
                total_objects += 1
                total_size += blob.size or 0
            
            return {
                "bucket_info": bucket_info,
                "total_objects": total_objects,
                "total_size_bytes": total_size,
                "total_size_mb": total_size / (1024 * 1024),
                "duplicate_cache_size": len(self._duplicate_cache),
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to get storage stats: {e}")
            return {
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    async def health_check(self) -> Dict[str, Any]:
        """Check storage health and connectivity."""
        try:
            # Test bucket access
            start_time = time.time()
            bucket_exists = self._bucket.exists()
            latency_ms = int((time.time() - start_time) * 1000)
            
            if not bucket_exists:
                return {
                    "status": "unhealthy",
                    "error": f"Bucket {self.config.bucket_name} not accessible",
                    "timestamp": datetime.utcnow().isoformat()
                }
            
            # Test write permissions with a small test object
            test_blob_name = f"health-check/{datetime.utcnow().isoformat()}"
            test_blob = self._bucket.blob(test_blob_name)
            
            try:
                test_blob.upload_from_string("health check", content_type="text/plain")
                test_blob.delete()  # Clean up
                write_access = True
            except Exception:
                write_access = False
            
            return {
                "status": "healthy" if write_access else "degraded",
                "bucket_accessible": bucket_exists,
                "write_access": write_access,
                "latency_ms": latency_ms,
                "bucket_name": self.config.bucket_name,
                "versioning_enabled": self._bucket.versioning_enabled,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    async def cleanup_old_snapshots(self, days_old: int = 30) -> Dict[str, Any]:
        """Clean up old snapshots (for development/testing only)."""
        if self.config.retention_period_days <= days_old:
            return {
                "error": "Cannot cleanup snapshots newer than retention period",
                "retention_period_days": self.config.retention_period_days
            }
        
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days_old)
            deleted_count = 0
            
            # List and delete old blobs
            for blob in self._bucket.list_blobs():
                if blob.time_created and blob.time_created.replace(tzinfo=None) < cutoff_date:
                    blob.delete()
                    deleted_count += 1
            
            return {
                "deleted_count": deleted_count,
                "cutoff_date": cutoff_date.isoformat(),
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            return {
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    async def _configure_bucket_worm(self) -> None:
        """Configure bucket for WORM compliance."""
        try:
            # Enable versioning if not already enabled
            if self.config.enable_versioning and not self._bucket.versioning_enabled:
                self._bucket.versioning_enabled = True
                self._bucket.patch()
                logger.info("Enabled versioning on storage bucket")
            
            # Set retention policy if not already set
            if not self._bucket.retention_policy and self.config.retention_period_days > 0:
                retention_seconds = self.config.retention_period_days * 24 * 60 * 60
                self._bucket.retention_period = retention_seconds
                self._bucket.patch()
                logger.info(f"Set retention policy: {self.config.retention_period_days} days")
            
        except Exception as e:
            logger.warning(f"Failed to configure WORM settings: {e}")
    
    def _create_snapshot_metadata(self, snapshot: DocumentSnapshot) -> SnapshotMetadata:
        """Create metadata for snapshot storage."""
        # Calculate retention expiry
        retention_expiry = None
        if self.config.retention_period_days > 0:
            expiry_date = snapshot.stored_at + timedelta(days=self.config.retention_period_days)
            retention_expiry = expiry_date.isoformat()
        
        return SnapshotMetadata(
            snapshot_id=str(snapshot.snapshot_id),
            original_url=snapshot.original_url,
            domain=snapshot.domain,
            content_type=snapshot.content_type,
            content_length=snapshot.content_length,
            sha256_checksum=snapshot.sha256_checksum,
            stored_at=snapshot.stored_at.isoformat(),
            effective_date=snapshot.effective_date.isoformat() if snapshot.effective_date else None,
            title=snapshot.title,
            province=snapshot.province.value if snapshot.province else None,
            doc_class=snapshot.doc_class.value if snapshot.doc_class else None,
            retention_expiry=retention_expiry
        )
    
    async def _store_with_retries(
        self,
        snapshot: DocumentSnapshot,
        storage_key: str,
        metadata: SnapshotMetadata
    ) -> StorageResult:
        """Store snapshot with retry logic."""
        last_exception = None
        
        for attempt in range(self.config.max_retries):
            try:
                # Create blob
                blob = self._bucket.blob(storage_key)
                
                # Check if already exists (WORM compliance)
                if blob.exists():
                    return StorageResult(
                        snapshot_id=snapshot.snapshot_id,
                        status=StorageStatus.DUPLICATE,
                        error_message="Object already exists (WORM compliance)"
                    )
                
                # Set metadata
                if self.config.include_custom_metadata:
                    blob.metadata = metadata.to_gcs_metadata()
                
                # Set content type
                blob.content_type = snapshot.content_type
                
                # Upload content
                if self.config.compress_content and snapshot.get_document_format().value in ["html", "text", "xml", "json"]:
                    import gzip
                    compressed_content = gzip.compress(snapshot.content)
                    blob.content_encoding = "gzip"
                    blob.upload_from_string(compressed_content, timeout=self.config.timeout)
                else:
                    blob.upload_from_string(snapshot.content, timeout=self.config.timeout)
                
                # Verify upload
                if not blob.exists():
                    raise Exception("Upload verification failed")
                
                return StorageResult(
                    snapshot_id=snapshot.snapshot_id,
                    status=StorageStatus.STORED,
                    storage_path=storage_key,
                    storage_bucket=self.config.bucket_name
                )
                
            except Conflict:
                # Object already exists - this is expected with WORM
                return StorageResult(
                    snapshot_id=snapshot.snapshot_id,
                    status=StorageStatus.DUPLICATE,
                    error_message="Object already exists"
                )
                
            except Exception as e:
                last_exception = e
                
                if attempt < self.config.max_retries - 1:
                    delay = 2 ** attempt  # Exponential backoff
                    logger.warning(f"Storage attempt {attempt + 1} failed, retrying in {delay}s: {e}")
                    await asyncio.sleep(delay)
        
        # All retries failed
        return StorageResult(
            snapshot_id=snapshot.snapshot_id,
            status=StorageStatus.FAILED,
            error_message=str(last_exception) if last_exception else "Unknown error"
        )
    
    def _reconstruct_snapshot_from_blob(self, blob: storage.Blob, content: bytes) -> DocumentSnapshot:
        """Reconstruct DocumentSnapshot from stored blob."""
        metadata = blob.metadata or {}
        
        # Parse dates
        stored_at = datetime.fromisoformat(metadata.get("stored-at", datetime.utcnow().isoformat()))
        effective_date = None
        if metadata.get("effective-date"):
            effective_date = datetime.fromisoformat(metadata["effective-date"])
        
        return DocumentSnapshot(
            snapshot_id=UUID(metadata["snapshot-id"]),
            original_url=metadata["original-url"],
            canonical_url=metadata.get("canonical-url"),
            domain=metadata["domain"],
            content=content,
            content_type=metadata["content-type"],
            content_length=int(metadata["content-length"]),
            sha256_checksum=metadata["sha256-checksum"],
            title=metadata.get("title"),
            effective_date=effective_date,
            http_status_code=200,  # Assume success for stored documents
            storage_path=blob.name,
            storage_bucket=blob.bucket.name,
            stored_at=stored_at,
            province=Province(metadata["province"]) if metadata.get("province") else None,
            doc_class=DocumentClass(metadata["doc-class"]) if metadata.get("doc-class") else None
        )


class SnapshotStorageMock:
    """Mock snapshot storage for testing."""
    
    def __init__(self):
        """Initialize mock storage."""
        self._stored_snapshots: Dict[UUID, DocumentSnapshot] = {}
        self._checksum_index: Dict[str, UUID] = {}
        self.store_count = 0
    
    async def initialize(self) -> None:
        """Mock initialization."""
        pass
    
    async def store_snapshot(self, snapshot: DocumentSnapshot) -> StorageResult:
        """Mock snapshot storage."""
        self.store_count += 1
        
        # Simulate processing time
        await asyncio.sleep(0.05)
        
        # Check for duplicates
        if snapshot.sha256_checksum in self._checksum_index:
            duplicate_id = self._checksum_index[snapshot.sha256_checksum]
            return StorageResult(
                snapshot_id=snapshot.snapshot_id,
                status=StorageStatus.DUPLICATE,
                duplicate_of=duplicate_id,
                storage_time_ms=50
            )
        
        # Store snapshot
        snapshot.storage_path = f"mock/{snapshot.get_storage_key()}"
        snapshot.storage_bucket = "mock-bucket"
        
        self._stored_snapshots[snapshot.snapshot_id] = snapshot
        self._checksum_index[snapshot.sha256_checksum] = snapshot.snapshot_id
        
        return StorageResult(
            snapshot_id=snapshot.snapshot_id,
            status=StorageStatus.STORED,
            storage_path=snapshot.storage_path,
            storage_bucket=snapshot.storage_bucket,
            storage_time_ms=50
        )
    
    async def store_snapshots_batch(self, snapshots: List[DocumentSnapshot]) -> List[StorageResult]:
        """Mock batch storage."""
        results = []
        for snapshot in snapshots:
            result = await self.store_snapshot(snapshot)
            results.append(result)
        return results
    
    async def retrieve_snapshot(self, snapshot_id: UUID) -> Optional[DocumentSnapshot]:
        """Mock snapshot retrieval."""
        return self._stored_snapshots.get(snapshot_id)
    
    async def check_duplicate(self, checksum: str) -> Optional[UUID]:
        """Mock duplicate check."""
        return self._checksum_index.get(checksum)
    
    async def get_storage_stats(self) -> Dict[str, Any]:
        """Mock storage stats."""
        total_size = sum(len(s.content) for s in self._stored_snapshots.values())
        
        return {
            "bucket_info": {"name": "mock-bucket", "location": "mock"},
            "total_objects": len(self._stored_snapshots),
            "total_size_bytes": total_size,
            "total_size_mb": total_size / (1024 * 1024),
            "duplicate_cache_size": len(self._checksum_index),
            "timestamp": datetime.utcnow().isoformat()
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """Mock health check."""
        return {
            "status": "healthy",
            "bucket_accessible": True,
            "write_access": True,
            "latency_ms": 10,
            "bucket_name": "mock-bucket",
            "store_count": self.store_count,
            "timestamp": datetime.utcnow().isoformat()
        }