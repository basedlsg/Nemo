"""Ingestion request handler service."""
import asyncio
import logging
import json
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, asdict
import uuid

from pydantic import BaseModel, Field, EmailStr, validator

logger = logging.getLogger(__name__)


class Priority(str, Enum):
    """Request priority levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class RequestStatus(str, Enum):
    """Request status values."""
    SUBMITTED = "submitted"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class IngestionRequest(BaseModel):
    """Ingestion request model."""
    query: str = Field(..., min_length=4, max_length=500)
    province: str = Field(..., min_length=1)
    asset_type: str = Field(..., min_length=1)
    doc_class: str = Field(..., min_length=1)
    refusal_code: str = Field(..., min_length=1)
    user_email: Optional[EmailStr] = None
    justification: str = Field(..., min_length=10, max_length=2000)
    priority: Priority = Priority.MEDIUM
    
    @validator('justification')
    def validate_justification(cls, v):
        """Validate justification content."""
        if not v.strip():
            raise ValueError('Justification cannot be empty')
        if len(v.strip()) < 10:
            raise ValueError('Justification must be at least 10 characters')
        return v.strip()


class IngestionRequestResponse(BaseModel):
    """Ingestion request response model."""
    request_id: str
    status: RequestStatus
    estimated_processing_time: str
    message: str
    message_zh: str
    created_at: str
    priority: Priority


@dataclass
class StoredIngestionRequest:
    """Stored ingestion request with metadata."""
    request_id: str
    query: str
    province: str
    asset_type: str
    doc_class: str
    refusal_code: str
    user_email: Optional[str]
    justification: str
    priority: str
    status: str
    created_at: str
    updated_at: str
    estimated_completion: str
    reviewer_notes: Optional[str] = None
    completion_notes: Optional[str] = None


class IngestionRequestHandler:
    """Handles ingestion requests and workflow."""
    
    def __init__(self):
        """Initialize request handler."""
        # In-memory storage for demo (would use database in production)
        self.requests: Dict[str, StoredIngestionRequest] = {}
        self.request_stats = {
            "total_requests": 0,
            "by_status": {status.value: 0 for status in RequestStatus},
            "by_priority": {priority.value: 0 for priority in Priority},
            "by_refusal_code": {}
        }
    
    async def submit_request(self, request: IngestionRequest) -> IngestionRequestResponse:
        """Submit new ingestion request."""
        try:
            # Generate request ID
            request_id = f"REQ-{datetime.utcnow().strftime('%Y%m%d')}-{str(uuid.uuid4())[:8].upper()}"
            
            # Calculate estimated processing time
            processing_time = self._calculate_processing_time(request.priority)
            estimated_completion = (datetime.utcnow() + processing_time).isoformat()
            
            # Create stored request
            stored_request = StoredIngestionRequest(
                request_id=request_id,
                query=request.query,
                province=request.province,
                asset_type=request.asset_type,
                doc_class=request.doc_class,
                refusal_code=request.refusal_code,
                user_email=request.user_email,
                justification=request.justification,
                priority=request.priority.value,
                status=RequestStatus.SUBMITTED.value,
                created_at=datetime.utcnow().isoformat(),
                updated_at=datetime.utcnow().isoformat(),
                estimated_completion=estimated_completion
            )
            
            # Store request
            self.requests[request_id] = stored_request
            
            # Update statistics
            self._update_stats(request)
            
            # Log request submission
            logger.info(f"Ingestion request submitted: {request_id} for {request.province}/{request.asset_type}")
            
            # Prepare response messages
            processing_time_str = self._format_processing_time(processing_time)
            message_en = f"Your ingestion request has been submitted successfully. Request ID: {request_id}"
            message_zh = f"您的补充资料申请已成功提交。申请编号：{request_id}"
            
            return IngestionRequestResponse(
                request_id=request_id,
                status=RequestStatus.SUBMITTED,
                estimated_processing_time=processing_time_str,
                message=message_en,
                message_zh=message_zh,
                created_at=stored_request.created_at,
                priority=request.priority
            )
            
        except Exception as e:
            logger.error(f"Failed to submit ingestion request: {e}")
            raise
    
    async def get_request(self, request_id: str) -> Optional[StoredIngestionRequest]:
        """Get ingestion request by ID."""
        return self.requests.get(request_id)
    
    async def update_request_status(
        self, 
        request_id: str, 
        status: RequestStatus,
        reviewer_notes: Optional[str] = None
    ) -> bool:
        """Update request status."""
        try:
            if request_id not in self.requests:
                return False
            
            request = self.requests[request_id]
            old_status = request.status
            
            # Update request
            request.status = status.value
            request.updated_at = datetime.utcnow().isoformat()
            if reviewer_notes:
                request.reviewer_notes = reviewer_notes
            
            # Update statistics
            self.request_stats["by_status"][old_status] -= 1
            self.request_stats["by_status"][status.value] += 1
            
            logger.info(f"Request {request_id} status updated: {old_status} -> {status.value}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update request status: {e}")
            return False
    
    async def list_requests(
        self, 
        status: Optional[RequestStatus] = None,
        priority: Optional[Priority] = None,
        limit: int = 50
    ) -> List[StoredIngestionRequest]:
        """List ingestion requests with optional filters."""
        try:
            requests = list(self.requests.values())
            
            # Apply filters
            if status:
                requests = [r for r in requests if r.status == status.value]
            if priority:
                requests = [r for r in requests if r.priority == priority.value]
            
            # Sort by creation date (newest first)
            requests.sort(key=lambda r: r.created_at, reverse=True)
            
            # Apply limit
            return requests[:limit]
            
        except Exception as e:
            logger.error(f"Failed to list requests: {e}")
            return []
    
    async def get_request_stats(self) -> Dict[str, Any]:
        """Get request statistics."""
        try:
            # Calculate additional stats
            total_requests = len(self.requests)
            
            # Status distribution
            status_counts = {}
            for request in self.requests.values():
                status_counts[request.status] = status_counts.get(request.status, 0) + 1
            
            # Priority distribution
            priority_counts = {}
            for request in self.requests.values():
                priority_counts[request.priority] = priority_counts.get(request.priority, 0) + 1
            
            # Refusal code distribution
            refusal_code_counts = {}
            for request in self.requests.values():
                code = request.refusal_code
                refusal_code_counts[code] = refusal_code_counts.get(code, 0) + 1
            
            # Average processing time by priority
            avg_processing_times = {
                "high": "1-2 business days",
                "medium": "2-3 business days", 
                "low": "3-5 business days"
            }
            
            return {
                "total_requests": total_requests,
                "status_distribution": status_counts,
                "priority_distribution": priority_counts,
                "refusal_code_distribution": refusal_code_counts,
                "average_processing_times": avg_processing_times,
                "last_updated": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to get request stats: {e}")
            return {}
    
    def _calculate_processing_time(self, priority: Priority) -> timedelta:
        """Calculate estimated processing time based on priority."""
        processing_times = {
            Priority.HIGH: timedelta(days=2),
            Priority.MEDIUM: timedelta(days=3),
            Priority.LOW: timedelta(days=5)
        }
        return processing_times.get(priority, timedelta(days=3))
    
    def _format_processing_time(self, processing_time: timedelta) -> str:
        """Format processing time as human-readable string."""
        days = processing_time.days
        if days == 1:
            return "1 business day"
        elif days <= 2:
            return "1-2 business days"
        elif days <= 3:
            return "2-3 business days"
        elif days <= 5:
            return "3-5 business days"
        else:
            return f"{days} business days"
    
    def _update_stats(self, request: IngestionRequest):
        """Update request statistics."""
        self.request_stats["total_requests"] += 1
        self.request_stats["by_status"][RequestStatus.SUBMITTED.value] += 1
        self.request_stats["by_priority"][request.priority.value] += 1
        
        code = request.refusal_code
        self.request_stats["by_refusal_code"][code] = self.request_stats["by_refusal_code"].get(code, 0) + 1
    
    async def validate_request_eligibility(self, refusal_code: str) -> Dict[str, Any]:
        """Validate if refusal code is eligible for ingestion request."""
        # Codes that allow ingestion requests
        eligible_codes = {
            'no_first_party_citation': {
                'eligible': True,
                'reason': 'Missing official documents can be requested',
                'priority_suggestion': 'medium'
            },
            'stale_citation': {
                'eligible': True,
                'reason': 'Updated documents can be requested',
                'priority_suggestion': 'high'
            },
            'insufficient_citations': {
                'eligible': True,
                'reason': 'Additional documents can be requested',
                'priority_suggestion': 'medium'
            },
            'province_mismatch': {
                'eligible': True,
                'reason': 'Province-specific documents can be requested',
                'priority_suggestion': 'medium'
            }
        }
        
        # Codes that don't allow ingestion requests
        ineligible_codes = {
            'unsafe_content': {
                'eligible': False,
                'reason': 'Content violates safety policies',
                'alternative': 'Please rephrase your query'
            },
            'prompt_injection': {
                'eligible': False,
                'reason': 'Query contains potential security risks',
                'alternative': 'Please use a standard query format'
            },
            'cross_province_leakage': {
                'eligible': False,
                'reason': 'Query violates geographic scope policies',
                'alternative': 'Please focus on a single province'
            },
            'language_policy_violation': {
                'eligible': False,
                'reason': 'Query violates language policies',
                'alternative': 'Please use Chinese for queries'
            }
        }
        
        # Check eligibility
        if refusal_code in eligible_codes:
            return eligible_codes[refusal_code]
        elif refusal_code in ineligible_codes:
            return ineligible_codes[refusal_code]
        else:
            # Unknown code - default to eligible with low priority
            return {
                'eligible': True,
                'reason': 'Unknown refusal code - manual review required',
                'priority_suggestion': 'low'
            }


# Global handler instance
_request_handler = None


async def get_request_handler() -> IngestionRequestHandler:
    """Get or create global request handler instance."""
    global _request_handler
    
    if _request_handler is None:
        _request_handler = IngestionRequestHandler()
    
    return _request_handler


async def submit_ingestion_request(request_data: Dict[str, Any]) -> Dict[str, Any]:
    """Submit ingestion request."""
    try:
        # Validate request
        request = IngestionRequest(**request_data)
        
        # Get handler
        handler = await get_request_handler()
        
        # Submit request
        response = await handler.submit_request(request)
        
        return response.dict()
        
    except Exception as e:
        logger.error(f"Failed to submit ingestion request: {e}")
        raise


async def get_ingestion_request_stats() -> Dict[str, Any]:
    """Get ingestion request statistics."""
    try:
        handler = await get_request_handler()
        return await handler.get_request_stats()
        
    except Exception as e:
        logger.error(f"Failed to get request stats: {e}")
        return {}