import os, time, re, urllib.parse
import logging
from typing import List, Dict, Any, Optional
import requests
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---- config -----------------------------------------------------------------
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GOOGLE_CSE_ID = os.getenv("GOOGLE_CSE_ID")
ALLOW = set(filter(None, os.getenv("ALLOWLIST_DOMAINS", "").lower().split(",")))

# ---- models -----------------------------------------------------------------
class Query(BaseModel):
    province: str
    doc_class: str
    asset: Optional[str] = None
    question: str
    lang: str = Field(default="zh-CN")

    @field_validator("lang")
    @classmethod
    def _lang_ok(cls, v):
        if v not in ("zh-CN", "en"):
            raise ValueError("lang must be 'zh-CN' or 'en'")
        return v

class Citation(BaseModel):
    title: str
    url: str
    snippet: str
    effective_date: Optional[str] = None

class QueryResponse(BaseModel):
    mode: str
    elapsed_ms: int
    answer_zh: str
    citations: List[Citation]

# ---- helpers ----------------------------------------------------------------
_UA = {"User-Agent": "Mozilla/5.0 (GAEA-online)"}

def _domain(url: str) -> str:
    try:
        d = urllib.parse.urlparse(url).netloc.lower()
        for p in ("www.", "m.", "wap."):
            if d.startswith(p):
                d = d[len(p):]
        return d
    except Exception:
        return ""

def _allowed(url: str) -> bool:
    d = _domain(url)
    return any(d == a or d.endswith("." + a) for a in ALLOW)

def _http_get(url: str, timeout: int = 20) -> bytes:
    r = requests.get(url, timeout=timeout, headers=_UA, allow_redirects=True)
    r.raise_for_status()
    return r.content

_WS = re.compile(r"\s+")
def _to_text(html_bytes: bytes) -> str:
    text = html_bytes.decode("utf-8", errors="ignore")
    text = re.sub(r"(?is)<script[^>]*>.*?</script>", " ", text)
    text = re.sub(r"(?is)<style[^>]*>.*?</style>", " ", text)
    text = re.sub(r"(?is)<[^>]+>", " ", text)
    text = _WS.sub(" ", text)
    return text.strip()

def _extract_date(text: str) -> Optional[str]:
    m = re.search(r"(\d{4}-\d{1,2}-\d{1,2})", text)
    if m:
        return m.group(1)
    m = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日", text)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    return None

def _zh_snippet(text: str, query: str, max_len: int = 120) -> str:
    keys = [k for k in re.split(r"[，。；、\s]", query) if k]
    for k in keys:
        i = text.find(k)
        if i != -1:
            start = max(0, i - 40)
            end = min(len(text), i + 80)
            return text[start:end].strip()
    return text[:max_len].strip()

def _google_cse_search(q: str) -> List[Dict[str, Any]]:
    if not GOOGLE_API_KEY or not GOOGLE_CSE_ID:
        logger.warning("GOOGLE_API_KEY/GOOGLE_CSE_ID missing")
        return []
    url = "https://www.googleapis.com/customsearch/v1?" + urllib.parse.urlencode({
        "key": GOOGLE_API_KEY,
        "cx": GOOGLE_CSE_ID,
        "q": q,
        "lr": "lang_zh",
        "safe": "off",
        "fields": "items(title,link,snippet)"
    })
    r = requests.get(url, headers=_UA, timeout=30)
    r.raise_for_status()
    return r.json().get("items", []) or []

def _build_query_text(payload: Query) -> str:
    parts = [payload.province, payload.doc_class]
    if payload.asset:
        parts.append(payload.asset)
    parts.append(payload.question)
    return " ".join([p for p in parts if p])

# ---- router -----------------------------------------------------------------
router = APIRouter()

@router.post("/query", response_model=QueryResponse)
def query_online(payload: Query) -> QueryResponse:
    t0 = time.time()
    if not ALLOW:
        raise HTTPException(status_code=400, detail="ALLOWLIST_DOMAINS not set")

    qtext = _build_query_text(payload)

    items = _google_cse_search(qtext)
    citations: List[Citation] = []
    for it in items:
        url = (it.get("link") or "").strip()
        title = (it.get("title") or "").strip()
        if not url or not _allowed(url):
            continue
        try:
            raw = _http_get(url, timeout=25)
            text = _to_text(raw)
            if not text:
                continue
            citations.append(Citation(
                title=title,
                url=url,
                snippet=_zh_snippet(text, payload.question),
                effective_date=_extract_date(text)
            ))
        except Exception as e:
            logger.warning(f"fetch failed for {url}: {e}")
        if len(citations) >= 5:
            break

    if citations:
        bullets = [f"• “{c.snippet}” — {c.title}" for c in citations[:5]]
        answer_zh = "\n".join(bullets)
    else:
        answer_zh = "未从许可来源中检索到可用答案，请调整问题或放宽条件。"

    return QueryResponse(
        mode="web_only",
        elapsed_ms=int((time.time() - t0) * 1000),
        answer_zh=answer_zh,
        citations=citations,
    )
import os, time, re, json, urllib.parse
import logging
from typing import List, Dict, Any
import requests
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---- config -----------------------------------------------------------------
PPLX_API_KEY   = os.getenv("PPLX_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GOOGLE_CSE_ID  = os.getenv("GOOGLE_CSE_ID")
ALLOW = set(filter(None, os.getenv("ALLOWLIST_DOMAINS","").lower().split(",")))

# ---- optional OCR (use your in-repo client if available) --------------------
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

def _sanitize_text_for_ui(text: str) -> str:
    if not text: return ""
    text = text.replace("\x00", "")
    text = re.sub(r"[\x00-\x1F\x7F]", " ", text)  # control chars
    text = re.sub(r"\s{2,}", " ", text)
    return text.strip()

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

router = APIRouter()

@router.post("/query")
def query_online(q: Query):
    """
    Online-only path:
      User Q → Perplexity URL candidates → Google CSE verified allowlisted docs → fetch → OCR/extract → score → top-N citations
    """
    logger.info(f"Received query: {q.dict()}")
    if not ALLOW:
        logger.error("ALLOWLIST_DOMAINS not set")
        raise HTTPException(status_code=400, detail="ALLOWLIST_DOMAINS not set")

    t0 = time.perf_counter()
    # Build a strong zh query for CSE
    terms = [q.province, q.doc_class, q.asset or "", q.question]
    hint  = " 规定 文件 通知 办法 指南 接入 并网"
    full_query = " ".join([t for t in terms if t]).strip() + hint

    # 1) Perplexity
    logger.info("Getting URLs from Perplexity...")
    try:
        perpl = perplexity_urls(full_query, max_urls=10)
        logger.info(f"Perplexity returned {len(perpl)} URLs.")
    except Exception as e:
        logger.error(f"Error calling Perplexity: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error calling Perplexity")

    # 2) Verify/augment with CSE (allowlist enforced here)
    logger.info("Verifying URLs with Google CSE...")
    try:
        candidates = verify_or_search(perpl, full_query)
        logger.info(f"Found {len(candidates)} candidates after CSE verification.")
    except Exception as e:
        logger.error(f"Error during CSE verification: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error during CSE verification")

    if not candidates:
        logger.warning("No first-party citations found.")
        raise HTTPException(status_code=422, detail="no_first_party_citation")

    # 3) Fetch + OCR/extract + score
    logger.info("Fetching, extracting, and scoring documents...")
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
        except Exception as e:
            logger.warning(f"Failed to fetch or process {url}: {e}")
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
        logger.error("All fetches or OCR failed.")
        raise HTTPException(status_code=422, detail="fetch_or_ocr_failed")

    logger.info(f"Successfully scored {len(scored)} documents.")
    scored.sort(key=lambda x: x["score"], reverse=True)
    top = scored[:3]

    elapsed_ms = int((time.perf_counter()-t0)*1000)
    
    # Sanitize outputs
    answer_zh = "；".join([_sanitize_text_for_ui(t["quote"]) for t in top if t.get("quote")]) or "（见引用条款）"
    sanitized_citations = [
        {
            "title": _sanitize_text_for_ui(t.get("title", "")),
            "url": t["url"],
            "snippet": _sanitize_text_for_ui(t.get("snippet", "")),
        }
        for t in top
    ]

    return {
        "mode": "online_only",
        "elapsed_ms": elapsed_ms,
        "answer_zh": _sanitize_text_for_ui(answer_zh),
        "citations": sanitized_citations,
    }
