import os
import logging
import time
import json
from typing import List
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from services.online.query_online import router as online_router
from services.gateway.feature_flags import is_feature_enabled

# ---- logging ------------------------------------------------------------------
def _get_json_log_handler() -> logging.Handler:
    
    class JsonLogFormatter(logging.Formatter):
        def format(self, record: logging.LogRecord) -> str:
            log_obj = {
                "timestamp": self.formatTime(record, self.datefmt),
                "level": record.levelname,
                "message": record.getMessage(),
                "context": {
                    "service": "gateway",
                    "filename": record.filename,
                    "lineno": record.lineno,
                }
            }
            # Add extra fields if they exist
            if hasattr(record, 'extra_context'):
                log_obj['context'].update(record.extra_context)
            return json.dumps(log_obj)

    handler = logging.StreamHandler()
    handler.setFormatter(JsonLogFormatter())
    return handler

logger = logging.getLogger("gaea-gateway")
logger.setLevel(os.getenv("LOG_LEVEL", "INFO").upper())
logger.addHandler(_get_json_log_handler())
logger.propagate = False


# ---- app ----------------------------------------------------------------------
app = FastAPI(
    title="Gaea Gateway",
    description="Public gateway for Chinese energy docs QA (online-only).",
    version="0.1.0",
)

@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    
    # Log request
    request_details = {
        "method": request.method,
        "path": request.url.path,
        "client_ip": request.client.host,
    }
    logger.info("Incoming request", extra={'extra_context': request_details})
    
    response = await call_next(request)
    
    # Log response
    process_time = (time.time() - start_time) * 1000
    response_details = {
        "status_code": response.status_code,
        "response_time_ms": f"{process_time:.2f}",
    }
    logger.info("Outgoing response", extra={'extra_context': response_details})
    
    return response

_default_origins = "http://localhost:3000,http://localhost:8080,file://,*"
origins_env = os.getenv("ALLOWED_ORIGINS", _default_origins)
ALLOWED_ORIGINS: List[str] = [o.strip() for o in origins_env.split(",") if o.strip()]

# For production, allow all origins to handle dynamic Vercel domains
if os.getenv("NODE_ENV") == "production" or any("vercel.app" in origin for origin in ALLOWED_ORIGINS):
    ALLOWED_ORIGINS = ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/_health")
def health_root():
    return {"ok": True}

@app.get("/api/v1/health")
def health_v1():
    return {"ok": True}

@app.get("/")
def root():
    return {
        "service": "Gaea Gateway",
        "description": "Chinese energy compliance assistant API",
        "endpoints": {
            "health": "/_health",
            "api_health": "/api/v1/health", 
            "query": "/api/v1/query (POST)"
        },
        "status": "running"
    }

if is_feature_enabled("ONLINE_QUERY"):
    app.include_router(online_router, prefix="/api/v1")

@app.on_event("startup")
async def on_startup():
    logger.info("Gateway starting up...")
    
    # Log configuration details
    config_details = {
        "allowed_origins": ALLOWED_ORIGINS,
        "log_level": logger.level,
        "query_mode_set": bool(os.getenv("QUERY_MODE")),
        "pplx_api_key_set": bool(os.getenv("PPLX_API_KEY")),
        "google_api_key_set": bool(os.getenv("GOOGLE_API_KEY")),
        "google_cse_id_set": bool(os.getenv("GOOGLE_CSE_ID")),
        "allowlist_domains_set": bool(os.getenv("ALLOWLIST_DOMAINS")),
    }
    logger.info("Application configuration", extra={'extra_context': config_details})
    
    logger.info("Routers mounted", extra={'extra_context': {"routers": ["/_health", "/api/v1/health", "/api/v1/query"]}})