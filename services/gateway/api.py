import os, traceback, uuid
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse

# Online-only path (Perplexity + CSE + OCR + allowlist)
from services.online.query_online import Query as OnlineQuery, query_online

app = FastAPI()

@app.post("/query")
async def query_entry(request: Request):
    """
    In web_only mode, bypass all DB/retriever/orchestrator code.
    This endpoint must not use FastAPI Depends for anything.
    """
    mode = os.getenv("QUERY_MODE", "web_only").lower()
    body = await request.json()

    if mode == "web_only":
        q = OnlineQuery(**body)      # pydantic validation
        return query_online(q)       # pure web path (no DB)

    # If you later want hybrid back, import orchestrated flow here.
    raise HTTPException(status_code=503, detail="hybrid_mode_disabled_until_db_ready")


# Optional: health/diag endpoints (safe)
@app.get("/_health")
def health():
    return {"ok": True, "mode": os.getenv("QUERY_MODE", "")}

@app.exception_handler(Exception)
async def all_exceptions_handler(request: Request, exc: Exception):
    """
    Prevents opaque 500s and returns a stable JSON with a trace_id.
    """
    trace_id = f"gaea-{uuid.uuid4().hex[:12]}"
    tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    # Log the full traceback to stdout/stderr so you see it in the terminal
    print(f"[{trace_id}] UNHANDLED ERROR\n{tb}", flush=True)
    return JSONResponse(
        status_code=500,
        content={"detail": f"Internal error", "trace_id": trace_id}
    )
