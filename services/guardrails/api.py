"""Guardrails service API for Task 12."""

import logging
from typing import List, Dict, Any
from datetime import datetime

from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel, Field

from .policy_engine import get_guardrails_engine, GuardrailsEngine, RefusalException

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Geo-Adaptive Energy Assistant - Guardrails Service",
    description="Policy-as-code guardrails for safe AI responses",
    version="1.0.0"
)


class GuardrailsRequest(BaseModel):
    """Guardrails check request model."""
    
    answer: str = Field(..., description="Generated answer text")
    citations: List[Dict[str, Any]] = Field(..., description="Citations used in answer")
    query: Dict[str, Any] = Field(..., description="Original query parameters")


class GuardrailsResponse(BaseModel):
    """Guardrails check response model."""
    
    status: str = Field(..., description="Check status: 'passed' or 'refused'")
    passed: bool = Field(..., description="Whether all policies passed")
    policies_checked: int = Field(..., description="Number of policies checked")
    processing_time_ms: int = Field(..., description="Processing time in milliseconds")
    timestamp: str = Field(..., description="Check timestamp")


class RefusalResponse(BaseModel):
    """Refusal response model."""
    
    status: str = Field(default="refused", description="Always 'refused'")
    reason: str = Field(..., description="Refusal reason code")
    message: str = Field(..., description="Human-readable refusal message")
    policy: str = Field(..., description="Policy that was violated")
    timestamp: str = Field(..., description="Refusal timestamp")


@app.post("/check", response_model=GuardrailsResponse)
async def check_guardrails(
    request: GuardrailsRequest,
    engine: GuardrailsEngine = Depends(get_guardrails_engine)
) -> GuardrailsResponse:
    """
    Check answer against all guardrails policies.
    
    Returns 200 if all policies pass, 422 if refused.
    Target: ≥99% refusal accuracy for policy violations.
    """
    import time
    start_time = time.time()
    
    try:
        # Perform guardrails check
        engine.check_all_policies(
            answer=request.answer,
            citations=request.citations,
            query=request.query
        )
        
        processing_time_ms = int((time.time() - start_time) * 1000)
        
        return GuardrailsResponse(
            status="passed",
            passed=True,
            policies_checked=len(engine.policies),
            processing_time_ms=processing_time_ms,
            timestamp=datetime.utcnow().isoformat()
        )
        
    except RefusalException as e:
        processing_time_ms = int((time.time() - start_time) * 1000)
        
        logger.info(f"Guardrails refusal: {e.reason.value} in {processing_time_ms}ms")
        
        # Return 422 Unprocessable Entity for policy violations
        refusal_response = RefusalResponse(
            reason=e.reason.value,
            message=e.message,
            policy=e.policy,
            timestamp=datetime.utcnow().isoformat()
        )
        
        raise HTTPException(
            status_code=422,
            detail=refusal_response.dict()
        )
        
    except Exception as e:
        logger.error(f"Guardrails check failed: {e}")
        raise HTTPException(
            status_code=500,
            detail="Internal guardrails error"
        )


@app.get("/health")
async def health_check(
    engine: GuardrailsEngine = Depends(get_guardrails_engine)
) -> Dict[str, Any]:
    """Check guardrails service health."""
    return engine.health_check()


@app.get("/stats")
async def get_statistics(
    engine: GuardrailsEngine = Depends(get_guardrails_engine)
) -> Dict[str, Any]:
    """Get guardrails service statistics."""
    return {
        "service": "guardrails",
        "stats": engine.get_statistics(),
        "timestamp": datetime.utcnow().isoformat()
    }


@app.get("/policies")
async def get_policies(
    engine: GuardrailsEngine = Depends(get_guardrails_engine)
) -> Dict[str, Any]:
    """Get information about all policies."""
    return {
        "policies": engine.get_policy_info(),
        "total_policies": len(engine.policies),
        "timestamp": datetime.utcnow().isoformat()
    }


@app.get("/")
async def root():
    """Root endpoint with service information."""
    return {
        "service": "geo-adaptive-energy-assistant-guardrails",
        "version": "1.0.0",
        "description": "Policy-as-code guardrails for safe AI responses",
        "endpoints": {
            "check": "POST /check - Check answer against policies",
            "health": "GET /health - Health check",
            "stats": "GET /stats - Service statistics",
            "policies": "GET /policies - Policy information"
        },
        "policies": [
            "citations_required - Must have first-party citations",
            "zh_first - Answer must be Chinese unless lang=en",
            "unsafe_scope - Province/domain/date validation"
        ],
        "targets": {
            "refusal_accuracy": "≥99%",
            "response_codes": "200 (passed) / 422 (refused) / 500 (error)"
        }
    }


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "services.guardrails.api:app",
        host="0.0.0.0",
        port=8002,
        log_level="info",
        reload=True
    )