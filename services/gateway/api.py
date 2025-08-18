from fastapi import FastAPI
app = FastAPI()

@app.get("/api/v1/health")
def api_health():
    return {"ok": True, "status": "ok"}

@app.get("/_health")  # optional fallback
def root_health():
    return {"ok": True, "status": "ok"}
