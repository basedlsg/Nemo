"""Google Document AI client wrapper for Chinese document processing."""

import logging
import time
from typing import Dict, Any, Optional, List

from google.cloud import documentai
from google.cloud.documentai_v1 import Document, ProcessRequest, RawDocument
from google.api_core import exceptions as gcp_exceptions

from .schemas import DocumentFormat, OcrConfig

logger = logging.getLogger(__name__)


class DocAIClient:
    """Google Document AI client for processing Chinese energy documents."""
    
    def __init__(self, config: Optional[OcrConfig] = None):
        """Initialize Document AI client."""
        self.config = config or OcrConfig()
        self.client = documentai.DocumentProcessorServiceClient()
        self.processor_name = self.client.processor_path(
            self.config.project_id,
            self.config.processor_location,
            self.config.processor_id
        )
        
        logger.info(f"Initialized DocAI client with processor: {self.processor_name}")
    
    def process_gcs_document(self, gcs_uri: str, mime_type: Optional[str] = None) -> Dict[str, Any]:
        """Process a document stored in Google Cloud Storage."""
        start_time = time.time()
        
        try:
            logger.info(f"Processing document from GCS: {gcs_uri}")
            
            # Determine MIME type if not provided
            if not mime_type:
                mime_type = self._detect_mime_type(gcs_uri)
            
            # Create process request
            request = ProcessRequest(
                name=self.processor_name,
                raw_document=RawDocument(
                    content=None,  # Using GCS URI instead of content
                    mime_type=mime_type
                ),
                gcs_input_uri=gcs_uri
            )
            
            # Process document
            result = self.client.process_document(request=request)
            
            processing_time = int((time.time() - start_time) * 1000)
            logger.info(f"Document processed successfully in {processing_time}ms")
            
            # Convert to dictionary for easier handling
            doc_dict = Document.to_dict(result.document)
            
            # Add processing metadata
            doc_dict["_processing_metadata"] = {
                "processing_time_ms": processing_time,
                "processor_name": self.processor_name,
                "gcs_uri": gcs_uri,
                "mime_type": mime_type
            }
            
            return doc_dict
            
        except gcp_exceptions.GoogleAPIError as e:
            logger.error(f"Google API error processing {gcs_uri}: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error processing {gcs_uri}: {e}")
            raise
    
    def process_raw_content(self, content: bytes, mime_type: str) -> Dict[str, Any]:
        """Process raw document content."""
        start_time = time.time()
        
        try:
            logger.info(f"Processing raw content ({len(content)} bytes, {mime_type})")
            
            # Create process request
            request = ProcessRequest(
                name=self.processor_name,
                raw_document=RawDocument(
                    content=content,
                    mime_type=mime_type
                )
            )
            
            # Process document
            result = self.client.process_document(request=request)
            
            processing_time = int((time.time() - start_time) * 1000)
            logger.info(f"Raw content processed successfully in {processing_time}ms")
            
            # Convert to dictionary
            doc_dict = Document.to_dict(result.document)
            
            # Add processing metadata
            doc_dict["_processing_metadata"] = {
                "processing_time_ms": processing_time,
                "processor_name": self.processor_name,
                "content_size": len(content),
                "mime_type": mime_type
            }
            
            return doc_dict
            
        except gcp_exceptions.GoogleAPIError as e:
            logger.error(f"Google API error processing raw content: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error processing raw content: {e}")
            raise
    
    def batch_process_documents(
        self,
        gcs_uris: List[str],
        output_gcs_prefix: str,
        mime_type: Optional[str] = None
    ) -> str:
        """Process multiple documents in batch (for high-volume processing)."""
        try:
            logger.info(f"Starting batch processing of {len(gcs_uris)} documents")
            
            # Determine MIME type if not provided
            if not mime_type:
                mime_type = self._detect_mime_type(gcs_uris[0])
            
            # Create batch process request
            from google.cloud.documentai_v1 import BatchProcessRequest, BatchDocumentsInputConfig, DocumentOutputConfig, GcsOutputConfig, GcsDocuments, GcsDocument
            
            input_config = BatchDocumentsInputConfig(
                gcs_documents=GcsDocuments(
                    documents=[
                        GcsDocument(gcs_uri=uri, mime_type=mime_type)
                        for uri in gcs_uris
                    ]
                )
            )
            
            output_config = DocumentOutputConfig(
                gcs_output_config=GcsOutputConfig(
                    gcs_uri=output_gcs_prefix
                )
            )
            
            request = BatchProcessRequest(
                name=self.processor_name,
                input_documents=input_config,
                document_output_config=output_config
            )
            
            # Start batch operation
            operation = self.client.batch_process_documents(request=request)
            logger.info(f"Batch operation started: {operation.operation.name}")
            
            return operation.operation.name
            
        except Exception as e:
            logger.error(f"Error starting batch processing: {e}")
            raise
    
    def get_batch_operation_status(self, operation_name: str) -> Dict[str, Any]:
        """Get status of batch processing operation."""
        try:
            from google.cloud import documentai
            
            # Get operation status
            operation = self.client.transport.operations_client.get_operation(
                name=operation_name
            )
            
            status = {
                "name": operation.name,
                "done": operation.done,
                "error": None,
                "metadata": None
            }
            
            if operation.error:
                status["error"] = {
                    "code": operation.error.code,
                    "message": operation.error.message
                }
            
            if operation.metadata:
                # Parse metadata if available
                try:
                    from google.cloud.documentai_v1 import BatchProcessMetadata
                    metadata = BatchProcessMetadata.deserialize(operation.metadata.value)
                    status["metadata"] = {
                        "state": metadata.state.name if metadata.state else "UNKNOWN",
                        "create_time": metadata.create_time.isoformat() if metadata.create_time else None,
                        "update_time": metadata.update_time.isoformat() if metadata.update_time else None
                    }
                except Exception as e:
                    logger.debug(f"Could not parse batch metadata: {e}")
            
            return status
            
        except Exception as e:
            logger.error(f"Error getting batch operation status: {e}")
            raise
    
    def health_check(self) -> Dict[str, Any]:
        """Check Document AI service health and connectivity."""
        try:
            start_time = time.time()
            
            # Test with a minimal document
            test_content = b"Health check test document"
            test_doc = self.process_raw_content(test_content, "text/plain")
            
            latency_ms = int((time.time() - start_time) * 1000)
            
            return {
                "status": "healthy",
                "processor_name": self.processor_name,
                "latency_ms": latency_ms,
                "test_pages": len(test_doc.get("pages", [])),
                "timestamp": time.time()
            }
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "processor_name": self.processor_name,
                "error": str(e),
                "timestamp": time.time()
            }
    
    def _detect_mime_type(self, gcs_uri: str) -> str:
        """Detect MIME type from file extension."""
        uri_lower = gcs_uri.lower()
        
        if uri_lower.endswith('.pdf'):
            return "application/pdf"
        elif uri_lower.endswith(('.html', '.htm')):
            return "text/html"
        elif uri_lower.endswith('.xml'):
            return "application/xml"
        elif uri_lower.endswith('.json'):
            return "application/json"
        elif uri_lower.endswith('.txt'):
            return "text/plain"
        elif uri_lower.endswith(('.jpg', '.jpeg')):
            return "image/jpeg"
        elif uri_lower.endswith('.png'):
            return "image/png"
        elif uri_lower.endswith('.tiff'):
            return "image/tiff"
        else:
            # Default to PDF for unknown extensions
            logger.warning(f"Unknown file extension for {gcs_uri}, defaulting to PDF")
            return "application/pdf"
    
    def extract_document_info(self, doc_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Extract key information from processed document."""
        info = {
            "page_count": len(doc_dict.get("pages", [])),
            "text_length": len(doc_dict.get("text", "")),
            "has_tables": False,
            "table_count": 0,
            "has_entities": False,
            "entity_count": 0,
            "confidence_scores": []
        }
        
        # Count tables across all pages
        for page in doc_dict.get("pages", []):
            tables = page.get("tables", [])
            info["table_count"] += len(tables)
            if tables:
                info["has_tables"] = True
        
        # Count entities
        entities = doc_dict.get("entities", [])
        info["entity_count"] = len(entities)
        if entities:
            info["has_entities"] = True
        
        # Extract confidence scores
        for page in doc_dict.get("pages", []):
            for block in page.get("blocks", []):
                layout = block.get("layout", {})
                if "confidence" in layout:
                    info["confidence_scores"].append(layout["confidence"])
        
        # Calculate average confidence
        if info["confidence_scores"]:
            info["avg_confidence"] = sum(info["confidence_scores"]) / len(info["confidence_scores"])
        else:
            info["avg_confidence"] = 0.0
        
        return info


class DocAIClientMock:
    """Mock Document AI client for testing."""
    
    def __init__(self, mock_responses: Optional[Dict[str, Any]] = None):
        """Initialize mock client."""
        self.mock_responses = mock_responses or {}
        self.process_count = 0
    
    def process_gcs_document(self, gcs_uri: str, mime_type: Optional[str] = None) -> Dict[str, Any]:
        """Mock GCS document processing."""
        self.process_count += 1
        
        # Simulate processing time
        import time
        time.sleep(0.1)
        
        # Check for mock response
        if gcs_uri in self.mock_responses:
            return self.mock_responses[gcs_uri]
        
        # Default mock response
        return {
            "text": "这是一个测试文档。\n\n第一条：测试条款内容。\n第二条：更多测试内容。",
            "pages": [
                {
                    "page_number": 1,
                    "blocks": [
                        {
                            "layout": {
                                "text_anchor": {
                                    "text_segments": [{"start_index": 0, "end_index": 50}]
                                },
                                "confidence": 0.95
                            }
                        }
                    ],
                    "tables": [
                        {
                            "header_rows": [
                                {
                                    "cells": [
                                        {"layout": {"text_anchor": {"text_segments": [{"start_index": 0, "end_index": 4}]}}},
                                        {"layout": {"text_anchor": {"text_segments": [{"start_index": 5, "end_index": 9}]}}}
                                    ]
                                }
                            ],
                            "body_rows": [
                                {
                                    "cells": [
                                        {"layout": {"text_anchor": {"text_segments": [{"start_index": 10, "end_index": 14}]}}},
                                        {"layout": {"text_anchor": {"text_segments": [{"start_index": 15, "end_index": 19}]}}}
                                    ]
                                }
                            ]
                        }
                    ]
                }
            ],
            "entities": [
                {
                    "type": "DATE",
                    "mention_text": "2025年3月1日",
                    "confidence": 0.9
                }
            ],
            "_processing_metadata": {
                "processing_time_ms": 100,
                "processor_name": "mock-processor",
                "gcs_uri": gcs_uri,
                "mime_type": mime_type or "application/pdf"
            }
        }
    
    def process_raw_content(self, content: bytes, mime_type: str) -> Dict[str, Any]:
        """Mock raw content processing."""
        return self.process_gcs_document(f"mock://{len(content)}", mime_type)
    
    def health_check(self) -> Dict[str, Any]:
        """Mock health check."""
        return {
            "status": "healthy",
            "processor_name": "mock-processor",
            "latency_ms": 50,
            "test_pages": 1,
            "process_count": self.process_count,
            "timestamp": time.time()
        }
    
    def extract_document_info(self, doc_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Mock document info extraction."""
        return {
            "page_count": len(doc_dict.get("pages", [])),
            "text_length": len(doc_dict.get("text", "")),
            "has_tables": True,
            "table_count": 1,
            "has_entities": True,
            "entity_count": 1,
            "avg_confidence": 0.95
        }