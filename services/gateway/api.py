import os
import logging
from typing import List
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from services.online.query_online import router as online_router

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=LOG_LEVEL,
    format='{"level":"%(levelname)s","ts":"%(asctime)s","msg":"%(message)s"}',
)
logger = logging.getLogger("gaea-gateway")

app = FastAPI(
    title="Gaea Gateway",
    description="Public gateway for Chinese energy docs QA (online-only).",
    version="0.1.0",
)

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

app.include_router(online_router, prefix="/api/v1")

@app.on_event("startup")
async def on_startup():
    logger.info("Gateway starting")
    logger.info(f"Allowed Origins: {ALLOWED_ORIGINS}")
    for key in ["QUERY_MODE", "PPLX_API_KEY", "GOOGLE_API_KEY", "GOOGLE_CSE_ID", "ALLOWLIST_DOMAINS"]:
        logger.info(f"env {key} set: {bool(os.getenv(key))}")
    logger.info("Routers mounted: /_health, /api/v1/health, /api/v1/query")
