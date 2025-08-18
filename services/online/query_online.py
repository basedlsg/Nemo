import os, time, re, json, urllib.parse
from typing import List, Dict, Any
import requests
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator
from dotenv import load_dotenv

load_dotenv()

# ---- config -----------------------------------------------------------------
PPLX_API_KEY   = os.getenv("PPLX_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GOOGLE_CSE_ID  = os.getenv("GOOGLE_CSE_ID")
ALLOW = set(filter(None, os.getenv("ALLOWLIST_DOMAINS","").lower().split(",")))

# ---- optional OCR (use your in-repo client if available) --------------------
try:
    # assume your repo exposes this; otherwise we fallback below
    from services.ocr.client import ocr_extract  # def ocr_extract(bytes|url)->str
    HAS_OCR_CLIENT = True
except Exception:
    HAS_OCR_CLIENT = False

# ---- models -----------------------------------------------------------------
class Query(BaseModel):
    province: str
    doc_class: str
    asset: str | None = None
    question: str
    lang: str = Field(default="zh-CN")
    @field_validator("lang")
    @classmethod
    def _lang_ok(cls, v):
        if v not in ("zh-CN","en"):
            raise ValueError("lang must be 'zh-CN' or 'en'")
        return v

# ---- helpers ----------------------------------------------------------------
def _domain(url: str) -> str:
    try:
        d = urllib.parse.urlparse(url).netloc.lower()
        for p in ("www.","m.","wap."):
            if d.startswith(p): d = d[len(p):]
        return d
    except:
        return ""

def _allowed(url: str) -> bool:
    d = _domain(url)
    return any(d == a or d.endswith("."+a) for a in ALLOW)

def _http_get(url: str, timeout=20) -> bytes:
    r = requests.get(url, timeout=timeout, headers={"User-Agent":"Mozilla/5.0 (GAEA-online)"})
    r.raise_for_status()
    return r.content

def _basic_text_from_html(html: bytes) -> str:
    # ultra-light extractor: strip tags; good enough for quick scoring if OCR not available
    txt = re.sub(br"<script.*?</script>|<style.*?</style>", b" ", html, flags=re.S|re.I)
    txt = re.sub(br"<[^>]+>", b" ", txt)
    try:
        return txt.decode("utf-8","ignore")
    except:
        return txt.decode("gb18030","ignore")

# ---- Perplexity (simple URL discovery) --------------------------------------
def perplexity_urls(query: str, max_urls: int = 10) -> List[str]:
    if not PPLX_API_KEY:
        return []
    # Minimal public API pattern; replace with your exact endpoint if different
    # This call should return text with URLs; we extract URLs naively.
    try:
        resp = requests.post(
            "https://api.perplexity.ai/chat/completions",
            headers={"Authorization": f"Bearer {PPLX_API_KEY}", "Content-Type":"application/json"},
            json={
                "model": "sonar-pro",  # or what your plan supports
                "messages": [{"role":"user","content": f"列出与以下问题相关的中国官方（一手）文档URL，仅给出URL：{query}"}],
                "max_tokens": 500,
                "temperature": 0.2,
            },
            timeout=30
        )
        resp.raise_for_status()
        text = resp.json().get("choices",[{}])[0].get("message",{}).get("content","")
        # URL regex (simple)
        urls = re.findall(r'https?://[^\s\)]+', text)
        # normalize & dedupe
        out = []
        seen = set()
        for u in urls:
            u = u.strip().rstrip('.,);]\'"')
            if u not in seen:
                out.append(u); seen.add(u)
        return out[:max_urls]
    except Exception:
        return []

# ---- Google CSE verification -------------------------------------------------
def cse_items(query: str, num: int = 10) -> List[Dict[str,Any]]:
    if not GOOGLE_API_KEY or not GOOGLE_CSE_ID:
        raise RuntimeError("GOOGLE_API_KEY/GOOGLE_CSE_ID not set")
    params = {
        "key": GOOGLE_API_KEY,
        "cx": GOOGLE_CSE_ID,
        "q": query,
        "num": min(10, num),
        "lr": "lang_zh",
        "safe": "off",
        "fields": "items(title,link,snippet)"
    }
    r = requests.get("https://www.googleapis.com/customsearch/v1", params=params, timeout=20)
    r.raise_for_status()
    return r.json().get("items",[]) or []

def verify_or_search(perpl_urls: List[str], query: str) -> List[Dict[str,Any]]:
    # 1) Prefer Perplexity URLs that pass allowlist
    prefer = [{"title":"", "link":u, "snippet":""} for u in perpl_urls if _allowed(u)]
    # 2) Augment with Google CSE results and filter by allowlist
    items = cse_items(query, num=10)
    hits = []
    seen = set()
    for it in prefer + items:
        link = it.get("link","")
        if not link: continue
        if not _allowed(link): continue
        if link in seen: continue
        seen.add(link)
        hits.append({"title": it.get("title",""), "url": link, "snippet": it.get("snippet","")})
    return hits

# ---- scoring (quick & dirty, in-memory) -------------------------------------
def score(doc_text: str, q: Query) -> float:
    # very simple relevance: frequency of key terms + presence of province/doc_class/asset
    text = doc_text.lower()
    keys = [q.question, q.doc_class, q.province] + ([q.asset] if q.asset else [])
    s = 0.0
    for k in keys:
        if not k: continue
        k = str(k).lower()
        s += 2.0 * text.count(k)
    # bonus for regulatory cue words
    for k in ("办法","规定","通知","意见","细则","指南","并网","接入","审批","许可","招标","公告"):
        s += 0.5 * text.count(k)
    return s

def quote_first(text: str) -> str:
    # Return first 1-2 short clauses as “verbatim-ish” bullets
    lines = [l.strip() for l in re.split(r"[。\n]", text) if l.strip()]
    return "；".join(lines[:2])

# ---- FastAPI router ----------------------------------------------------------
router = APIRouter()

@router.get("/health_online")
def health_check():
    return {"status": "ok"}

@router.post("/query_online")
def query_online(q: Query):
    """
    Online-only path:
      User Q → Perplexity URL candidates → Google CSE verified allowlisted docs → fetch → OCR/extract → score → top-N citations
    """
    if not ALLOW:
        raise HTTPException(status_code=400, detail="ALLOWLIST_DOMAINS not set")

    t0 = time.perf_counter()
    # Build a strong zh query for CSE
    terms = [q.province, q.doc_class, q.asset or "", q.question]
    hint  = " 规定 文件 通知 办法 指南 接入 并网"
    full_query = " ".join([t for t in terms if t]).strip() + hint

    # 1) Perplexity
    perpl = perplexity_urls(full_query, max_urls=10)

    # 2) Verify/augment with CSE (allowlist enforced here)
    candidates = verify_or_search(perpl, full_query)
    if not candidates:
        raise HTTPException(status_code=422, detail="no_first_party_citation")

    # 3) Fetch + OCR/extract + score
    scored: List[Dict[str,Any]] = []
    for c in candidates[:8]:  # cap fetches for latency
        url = c["url"]
        try:
            raw = _http_get(url, timeout=25)
            if HAS_OCR_CLIENT and (url.lower().endswith(".pdf") or b"%PDF" in raw[:4]):
                # use your in-repo OCR if present
                try:
                    text = ocr_extract(raw)  # returns str
                except Exception:
                    text = _basic_text_from_html(raw)
            else:
                text = _basic_text_from_html(raw)
        except Exception:
            continue
        sc = score(text, q)
        quote = quote_first(text)
        scored.append({
            "title": c.get("title") or "",
            "url": url,
            "snippet": c.get("snippet") or quote[:140],
            "score": sc,
            "quote": quote[:220]
        })

    if not scored:
        raise HTTPException(status_code=422, detail="fetch_or_ocr_failed")

    scored.sort(key=lambda x: x["score"], reverse=True)
    top = scored[:3]

    elapsed_ms = int((time.perf_counter()-t0)*1000)
    # Quote-first, minimal glue, verbatim-ish clauses:
    answer_zh = "；".join([t["quote"] for t in top if t["quote"]])

    return {
        "mode": "online_only",
        "elapsed_ms": elapsed_ms,
        "answer_zh": answer_zh or "（见引用条款）",
        "citations": [{"title": t["title"], "url": t["url"], "snippet": t["snippet"]} for t in top]
    }
