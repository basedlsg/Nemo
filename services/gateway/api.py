from fastapi import FastAPI
from services.online.query_online import router as online_router

app = FastAPI()
app.include_router(online_router)  # exposes /api/v1/query

# (Optionally keep health aliases matching the frontend)
import os
@app.get("/_health")
def health_root():
    return {"ok": True, "mode": os.getenv("QUERY_MODE", "")}

@app.get("/api/v1/health")
def health_v1():
    return {"ok": True, "mode": os.getenv("QUERY_MODE", "")}
