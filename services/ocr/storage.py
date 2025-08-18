"""GCS storage utilities for OCR service."""

import json
import logging
from typing import Dict, Any, List, Optional
from google.cloud import storage
from google.cloud.exceptions import NotFound, GoogleCloudError

logger = logging.getLogger(__name__)


class GCSStorageClient:
    """Google Cloud Storage client for OCR artifacts."""
    
    def __init__(self, project_id: Optional[str] = None):
        """Initialize GCS client."""
        self.client = storage.Client(project=project_id)
        logger.info("Initialized GCS storage client")
    
    def write_gcs_json(self, gcs_uri: str, obj: Dict[str, Any]) -> bool:
        """
        Write JSON object to GCS.
        
        Args:
            gcs_uri: GCS URI (gs://bucket/path)
            obj: Dictionary to write as JSON
            
        Returns:
            True if successful, False otherwise
        """
        try:
            bucket_name, blob_name = self._parse_gcs_uri(gcs_uri)
            bucket = self.client.bucket(bucket_name)
            blob = bucket.blob(blob_name)
            
            # Serialize with proper Chinese character handling
            json_data = json.dumps(obj, ensure_ascii=False, indent=2)
            
            blob.upload_from_string(
                json_data,
                content_type="application/json; charset=utf-8"
            )
            
            logger.info(f"Successfully wrote JSON to {gcs_uri}")
            return True
            
        except Exception as e:
            logger.error(f"Error writing JSON to {gcs_uri}: {e}")
            return False
    
    def write_gcs_jsonl(self, gcs_uri: str, rows: List[Dict[str, Any]]) -> bool:
        """
        Write list of objects as JSONL to GCS.
        
        Args:
            gcs_uri: GCS URI (gs://bucket/path)
            rows: List of dictionaries to write as JSONL
            
        Returns:
            True if successful, False otherwise
        """
        try:
            bucket_name, blob_name = self._parse_gcs_uri(gcs_uri)
            bucket = self.client.bucket(bucket_name)
            blob = bucket.blob(blob_name)
            
            # Create JSONL content
            jsonl_lines = []
            for row in rows:
                line = json.dumps(row, ensure_ascii=False)
                jsonl_lines.append(line)
            
            jsonl_data = '\n'.join(jsonl_lines)
            
            blob.upload_from_string(
                jsonl_data,
                content_type="application/jsonl; charset=utf-8"
            )
            
            logger.info(f"Successfully wrote JSONL ({len(rows)} rows) to {gcs_uri}")
            return True
            
        except Exception as e:
            logger.error(f"Error writing JSONL to {gcs_uri}: {e}")
            return False
    
    def read_gcs_json(self, gcs_uri: str) -> Optional[Dict[str, Any]]:
        """
        Read JSON object from GCS.
        
        Args:
            gcs_uri: GCS URI (gs://bucket/path)
            
        Returns:
            Dictionary if successful, None otherwise
        """
        try:
            bucket_name, blob_name = self._parse_gcs_uri(gcs_uri)
            bucket = self.client.bucket(bucket_name)
            blob = bucket.blob(blob_name)
            
            if not blob.exists():
                logger.warning(f"Blob does not exist: {gcs_uri}")
                return None
            
            content = blob.download_as_text(encoding='utf-8')
            obj = json.loads(content)
            
            logger.info(f"Successfully read JSON from {gcs_uri}")
            return obj
            
        except Exception as e:
            logger.error(f"Error reading JSON from {gcs_uri}: {e}")
            return None
    
    def read_gcs_bytes(self, gcs_uri: str) -> Optional[bytes]:
        """
        Read raw bytes from GCS.
        
        Args:
            gcs_uri: GCS URI (gs://bucket/path)
            
        Returns:
            Bytes if successful, None otherwise
        """
        try:
            bucket_name, blob_name = self._parse_gcs_uri(gcs_uri)
            bucket = self.client.bucket(bucket_name)
            blob = bucket.blob(blob_name)
            
            if not blob.exists():
                logger.warning(f"Blob does not exist: {gcs_uri}")
                return None
            
            content = blob.download_as_bytes()
            
            logger.info(f"Successfully read {len(content)} bytes from {gcs_uri}")
            return content
            
        except Exception as e:
            logger.error(f"Error reading bytes from {gcs_uri}: {e}")
            return None
    
    def blob_exists(self, gcs_uri: str) -> bool:
        """
        Check if a blob exists in GCS.
        
        Args:
            gcs_uri: GCS URI (gs://bucket/path)
            
        Returns:
            True if blob exists, False otherwise
        """
        try:
            bucket_name, blob_name = self._parse_gcs_uri(gcs_uri)
            bucket = self.client.bucket(bucket_name)
            blob = bucket.blob(blob_name)
            
            return blob.exists()
            
        except Exception as e:
            logger.error(f"Error checking blob existence {gcs_uri}: {e}")
            return False
    
    def get_blob_metadata(self, gcs_uri: str) -> Optional[Dict[str, Any]]:
        """
        Get blob metadata from GCS.
        
        Args:
            gcs_uri: GCS URI (gs://bucket/path)
            
        Returns:
            Metadata dictionary if successful, None otherwise
        """
        try:
            bucket_name, blob_name = self._parse_gcs_uri(gcs_uri)
            bucket = self.client.bucket(bucket_name)
            blob = bucket.blob(blob_name)
            
            if not blob.exists():
                return None
            
            # Reload to get fresh metadata
            blob.reload()
            
            metadata = {
                "name": blob.name,
                "bucket": blob.bucket.name,
                "size": blob.size,
                "content_type": blob.content_type,
                "created": blob.time_created.isoformat() if blob.time_created else None,
                "updated": blob.updated.isoformat() if blob.updated else None,
                "etag": blob.etag,
                "md5_hash": blob.md5_hash,
                "crc32c": blob.crc32c,
                "custom_metadata": blob.metadata or {}
            }
            
            return metadata
            
        except Exception as e:
            logger.error(f"Error getting blob metadata {gcs_uri}: {e}")
            return None
    
    def list_blobs(self, bucket_name: str, prefix: str = "", max_results: int = 1000) -> List[str]:
        """
        List blobs in a bucket with optional prefix.
        
        Args:
            bucket_name: GCS bucket name
            prefix: Blob name prefix filter
            max_results: Maximum number of results
            
        Returns:
            List of blob names
        """
        try:
            bucket = self.client.bucket(bucket_name)
            blobs = bucket.list_blobs(prefix=prefix, max_results=max_results)
            
            blob_names = [blob.name for blob in blobs]
            
            logger.info(f"Listed {len(blob_names)} blobs from gs://{bucket_name}/{prefix}")
            return blob_names
            
        except Exception as e:
            logger.error(f"Error listing blobs from gs://{bucket_name}/{prefix}: {e}")
            return []
    
    def delete_blob(self, gcs_uri: str) -> bool:
        """
        Delete a blob from GCS.
        
        Args:
            gcs_uri: GCS URI (gs://bucket/path)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            bucket_name, blob_name = self._parse_gcs_uri(gcs_uri)
            bucket = self.client.bucket(bucket_name)
            blob = bucket.blob(blob_name)
            
            if blob.exists():
                blob.delete()
                logger.info(f"Successfully deleted {gcs_uri}")
                return True
            else:
                logger.warning(f"Blob does not exist for deletion: {gcs_uri}")
                return False
                
        except Exception as e:
            logger.error(f"Error deleting blob {gcs_uri}: {e}")
            return False
    
    def copy_blob(self, source_gcs_uri: str, dest_gcs_uri: str) -> bool:
        """
        Copy a blob within GCS.
        
        Args:
            source_gcs_uri: Source GCS URI
            dest_gcs_uri: Destination GCS URI
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Parse source
            source_bucket_name, source_blob_name = self._parse_gcs_uri(source_gcs_uri)
            source_bucket = self.client.bucket(source_bucket_name)
            source_blob = source_bucket.blob(source_blob_name)
            
            # Parse destination
            dest_bucket_name, dest_blob_name = self._parse_gcs_uri(dest_gcs_uri)
            dest_bucket = self.client.bucket(dest_bucket_name)
            
            # Copy blob
            dest_blob = source_bucket.copy_blob(source_blob, dest_bucket, dest_blob_name)
            
            logger.info(f"Successfully copied {source_gcs_uri} to {dest_gcs_uri}")
            return True
            
        except Exception as e:
            logger.error(f"Error copying blob from {source_gcs_uri} to {dest_gcs_uri}: {e}")
            return False
    
    def _parse_gcs_uri(self, gcs_uri: str) -> tuple[str, str]:
        """
        Parse GCS URI into bucket and blob name.
        
        Args:
            gcs_uri: GCS URI (gs://bucket/path)
            
        Returns:
            Tuple of (bucket_name, blob_name)
        """
        if not gcs_uri.startswith('gs://'):
            raise ValueError(f"Invalid GCS URI format: {gcs_uri}")
        
        path = gcs_uri[5:]  # Remove 'gs://'
        parts = path.split('/', 1)
        
        if len(parts) != 2:
            raise ValueError(f"Invalid GCS URI format: {gcs_uri}")
        
        return parts[0], parts[1]


def generate_parsed_path(snapshot_gcs_uri: str) -> str:
    """Generate parsed JSON path from snapshot URI."""
    # Convert: gs://bucket/snapshots/domain/2025/03/abc123/doc.pdf
    # To:      gs://bucket/parsed/domain/2025/03/abc123/doc.json
    
    if "/snapshots/" in snapshot_gcs_uri:
        parsed_uri = snapshot_gcs_uri.replace("/snapshots/", "/parsed/")
        # Change extension to .json
        if '.' in parsed_uri:
            parsed_uri = parsed_uri.rsplit('.', 1)[0] + '.json'
        else:
            parsed_uri += '.json'
        return parsed_uri
    else:
        # Fallback: add parsed prefix
        return snapshot_gcs_uri.replace('gs://', 'gs://').replace('/', '/parsed/', 1) + '.json'


def generate_normalized_path(snapshot_gcs_uri: str) -> str:
    """Generate normalized JSONL path from snapshot URI."""
    # Convert: gs://bucket/snapshots/domain/2025/03/abc123/doc.pdf
    # To:      gs://bucket/normalized/domain/2025/03/abc123/doc.jsonl
    
    if "/snapshots/" in snapshot_gcs_uri:
        normalized_uri = snapshot_gcs_uri.replace("/snapshots/", "/normalized/")
        # Change extension to .jsonl
        if '.' in normalized_uri:
            normalized_uri = normalized_uri.rsplit('.', 1)[0] + '.jsonl'
        else:
            normalized_uri += '.jsonl'
        return normalized_uri
    else:
        # Fallback: add normalized prefix
        return snapshot_gcs_uri.replace('gs://', 'gs://').replace('/', '/normalized/', 1) + '.jsonl'


class GCSStorageClientMock:
    """Mock GCS storage client for testing."""
    
    def __init__(self):
        """Initialize mock client."""
        self._storage: Dict[str, Any] = {}
        self.operation_count = 0
    
    def write_gcs_json(self, gcs_uri: str, obj: Dict[str, Any]) -> bool:
        """Mock JSON write."""
        self.operation_count += 1
        self._storage[gcs_uri] = {
            "type": "json",
            "content": obj,
            "size": len(json.dumps(obj))
        }
        return True
    
    def write_gcs_jsonl(self, gcs_uri: str, rows: List[Dict[str, Any]]) -> bool:
        """Mock JSONL write."""
        self.operation_count += 1
        self._storage[gcs_uri] = {
            "type": "jsonl",
            "content": rows,
            "size": sum(len(json.dumps(row)) for row in rows)
        }
        return True
    
    def read_gcs_json(self, gcs_uri: str) -> Optional[Dict[str, Any]]:
        """Mock JSON read."""
        self.operation_count += 1
        stored = self._storage.get(gcs_uri)
        if stored and stored["type"] == "json":
            return stored["content"]
        return None
    
    def read_gcs_bytes(self, gcs_uri: str) -> Optional[bytes]:
        """Mock bytes read."""
        self.operation_count += 1
        stored = self._storage.get(gcs_uri)
        if stored:
            content = stored["content"]
            if isinstance(content, dict):
                return json.dumps(content).encode('utf-8')
            elif isinstance(content, list):
                return '\n'.join(json.dumps(row) for row in content).encode('utf-8')
        return None
    
    def blob_exists(self, gcs_uri: str) -> bool:
        """Mock blob existence check."""
        return gcs_uri in self._storage
    
    def get_blob_metadata(self, gcs_uri: str) -> Optional[Dict[str, Any]]:
        """Mock metadata retrieval."""
        if gcs_uri in self._storage:
            stored = self._storage[gcs_uri]
            return {
                "name": gcs_uri.split('/')[-1],
                "bucket": "mock-bucket",
                "size": stored["size"],
                "content_type": "application/json",
                "created": "2025-01-01T00:00:00Z",
                "updated": "2025-01-01T00:00:00Z"
            }
        return None
    
    def list_blobs(self, bucket_name: str, prefix: str = "", max_results: int = 1000) -> List[str]:
        """Mock blob listing."""
        matching_keys = [
            key for key in self._storage.keys()
            if key.startswith(f"gs://{bucket_name}/{prefix}")
        ]
        return matching_keys[:max_results]
    
    def delete_blob(self, gcs_uri: str) -> bool:
        """Mock blob deletion."""
        if gcs_uri in self._storage:
            del self._storage[gcs_uri]
            return True
        return False