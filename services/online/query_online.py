import os, re, time, json, urllib.parse
from typing import List, Dict, Any, Optional

import requests
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator

router = APIRouter()

# --- ENV / CONFIG ------------------------------------------------------------

PPLX_API_KEY   = os.getenv("PPLX_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GOOGLE_CSE_ID  = os.getenv("GOOGLE_CSE_ID")

# IMPORTANT: put tuned allowlist in env (see section C below)
_ALLOWLIST = os.getenv("ALLOWLIST_DOMAINS", "")
ALLOW = set([d.strip().lower() for d in _ALLOWLIST.split(",") if d.strip()])


# --- MODELS ------------------------------------------------------------------

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


# --- UTILITIES ---------------------------------------------------------------

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

def _http_get(url: str, timeout: float = 25.0) -> bytes:
    # Keep UA modest but non-empty
    headers = {"User-Agent": "GAEA/online (requests)"}
    r = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
    r.raise_for_status()
    return r.content

def _basic_text_from_html(html: bytes) -> str:
    # Super-light tag stripper, fine for relevance
    txt = re.sub(br"<script.*?</script>|<style.*?</style>", b" ", html, flags=re.S | re.I)
    txt = re.sub(br"<[^>]+>", b" ", txt)
    try:
        return txt.decode("utf-8", "ignore")
    except Exception:
        return txt.decode("gb18030", "ignore")

def _maybe_pdf_text(raw: bytes) -> Optional[str]:
    """
    Minimal PDF text path:
    - If pdfminer.six is installed: extract text
    - Else: return None (we'll fallback to HTML stripper or skip)
    """
    try:
        if not (raw[:4] == b"%PDF"):
            return None
        from io import BytesIO
        from pdfminer.high_level import extract_text
        return extract_text(BytesIO(raw)) or ""
    except Exception:
        return None

# Optional external OCR hook:
# If you later add a real OCR client, expose: services.ocr.client.ocr_extract(raw: bytes)->str
try:
    from services.ocr.client import ocr_extract as _external_ocr_extract  # type: ignore
    HAS_EXTERNAL_OCR = True
except Exception:
    HAS_EXTERNAL_OCR = False
    _external_ocr_extract = None  # type: ignore

def _maybe_docx_text(raw: bytes) -> Optional[str]:
    try:
        if not raw[:2] == b"PK":  # DOCX is a zip
            return None
        import zipfile, io, xml.etree.ElementTree as ET
        z = zipfile.ZipFile(io.BytesIO(raw))
        xml = z.read('word/document.xml')
        # strip tags
        text = re.sub(br"<[^>]+>", b" ", xml)
        return text.decode("utf-8", "ignore")
    except Exception:
        return None

def extract_text_any(raw: bytes, src_url: str) -> str:
    # 1) If PDF: prefer OCR hook or pdfminer
    is_pdf = raw[:4] == b"%PDF" or src_url.lower().endswith(".pdf")
    if is_pdf:
        if HAS_EXTERNAL_OCR:
            try:
                t = _external_ocr_extract(raw)
                if isinstance(t, (bytes, bytearray)):
                    t = t.decode("utf-8", "ignore")
                if t:
                    return t
            except Exception:
                pass
        pdf_txt = _maybe_pdf_text(raw)
        if pdf_txt:
            return pdf_txt
        # If we can’t parse PDF at all, return empty (we’ll still keep the URL as a citation)
        return ""

    # DOCX quick path
    if src_url.lower().endswith(".docx") or raw[:2] == b"PK":
        t = _maybe_docx_text(raw)
        if t: return t

    return _basic_text_from_html(raw)

STOP_WORDS = ("登录", "首页", "平台", "门户网站", "政务服务", "无障碍", "网站地图")

def _sanitize_text_for_ui(text: str) -> str:
    if "%PDF-" in text or "PK\u0003\u0004" in text or "Content_Types" in text:
        return ""
    text = re.sub(r"\s+", " ", text).strip()
    for sw in STOP_WORDS:
        # drop very short quotes that are clearly nav labels
        if text.startswith(sw) and len(text) < 30:
            return ""
    return text[:400]

def quote_first(text: str) -> str:
    cand = [l.strip() for l in re.split(r"[。\n.!?]", text) if l.strip()]
    for c in cand:
        c = _sanitize_text_for_ui(c)
        if c and len(c) >= 12:
            return c
    return ""

PROVINCE_SITES = {
    "广东": ["gd.gov.cn", "gz.gov.cn", "zhaoqing.gov.cn", "shenzhen.gov.cn", "foshan.gov.cn", "zhuhai.gov.cn"],
    "guangdong": ["gd.gov.cn","gz.gov.cn","shenzhen.gov.cn","foshan.gov.cn","zhuhai.gov.cn"],
    # add more as you go; these are hints, allowlist still enforces 1st-party
}

def _province_query_boost(q: Query) -> str:
    # turn province into site: filters
    doms = PROVINCE_SITES.get(q.province.lower(), []) or PROVINCE_SITES.get(q.province, [])
    site_clause = " OR ".join([f"site:{d}" for d in doms]) if doms else ""
    # strong regulatory keywords (Chinese, even if the user typed English)
    core = "并网 接入 申请 材料 资料 清单 光伏 发电 管理 办法 规定 通知 指南"
    # assemble
    pieces = [q.province, q.doc_class, q.asset or "", q.question, core, site_clause]
    return " ".join([p for p in pieces if p]).strip()

def score(text: str, q: Query) -> float:
    # Simple scoring: term frequency on question + province + doc_class + asset
    hay = text.lower()
    keys = [q.question, q.doc_class, q.province] + ([q.asset] if q.asset else [])
    s = 0.0
    for k in keys:
        if not k: continue
        k = str(k).lower()
        s += 2.0 * hay.count(k)
    for k in ("办法", "规定", "通知", "意见", "细则", "指南", "并网", "接入", "审批", "许可", "招标", "公告"):
        s += 0.5 * hay.count(k)
    return s


# --- PERPLEXITY --------------------------------------------------------------

def perplexity_urls(query: str, max_urls: int = 10) -> List[str]:
    if not PPLX_API_KEY:
        return []
    try:
        # Minimal schema; adjust model to your plan
        r = requests.post(
            "https://api.perplexity.ai/chat/completions",
            headers={"Authorization": f"Bearer {PPLX_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": "sonar-pro",
                "messages": [
                    {"role": "system", "content": "仅返回URL，不要解释。只列出与中国官方（一手）文档相关的链接。"},
                    {"role": "user",   "content": query}
                ],
                "temperature": 0.2,
                "max_tokens": 600,
            },
            timeout=30
        )
        if r.status_code == 401:
            raise HTTPException(status_code=503, detail="perplexity_unauthorized")
        if r.status_code == 429:
            raise HTTPException(status_code=503, detail="perplexity_rate_limited")
        r.raise_for_status()
        text = r.json().get("choices", [{}])[0].get("message", {}).get("content", "")
        urls = re.findall(r'https?://[^\s\)\]"}>]+', text)
        out, seen = [], set()
        for u in urls:
            u = u.strip().rstrip('.,);]\'"')
            if u not in seen:
                out.append(u); seen.add(u)
        return out[:max_urls]
    except HTTPException:
        raise
    except Exception as e:
        # Fail soft; we’ll rely on CSE
        return []


# --- GOOGLE CSE --------------------------------------------------------------

REQUIRED_TOKENS = ["并网", "接入", "申请", "材料", "资料", "清单", "光伏", "许可", "报审", "办理"]

def _passes_policy(text: str) -> bool:
    hay = text
    hits = sum(1 for t in REQUIRED_TOKENS if t in hay)
    return hits >= 2  # require at least two policy terms

def cse_items(query: str, num: int = 10) -> List[Dict[str, Any]]:
    if not GOOGLE_API_KEY or not GOOGLE_CSE_ID:
        raise HTTPException(status_code=503, detail="cse_key_or_id_missing")
    params = {
        "key": GOOGLE_API_KEY,
        "cx": GOOGLE_CSE_ID,
        "q": query,
        "num": min(num, 10),
        "lr": "lang_zh",
        "safe": "off",
        "fields": "items(title,link,snippet)"
    }
    r = requests.get("https://www.googleapis.com/customsearch/v1", params=params, timeout=20)
    if r.status_code == 403:
        raise HTTPException(status_code=503, detail="cse_quota_or_key_invalid")
    if r.status_code == 429:
        raise HTTPException(status_code=503, detail="cse_rate_limited")
    r.raise_for_status()
    return r.json().get("items", []) or []


def verify_or_search(perpl_urls: List[str], query: str, q: Query) -> List[Dict[str, Any]]:
    # Prefer Perplexity URLs that pass allowlist
    prefer = [{"title": "", "link": u, "snippet": ""} for u in perpl_urls if _allowed(u)]
    # Augment with CSE (filter by allowlist)
    full_query = _province_query_boost(q)
    items = cse_items(full_query, num=10)
    hits, seen = [], set()
    for it in prefer + items:
        link = it.get("link") or it.get("url") or ""
        if not link: continue
        if not _allowed(link): continue
        if link in seen: continue
        seen.add(link)
        hits.append({"title": it.get("title",""), "url": link, "snippet": it.get("snippet","")})
    return hits


def _title_from_html(html: bytes) -> str:
    try:
        m = re.search(br"<title[^>]*>(.*?)</title>", html, flags=re.I|re.S)
        if not m: return ""
        return m.group(1).decode("utf-8","ignore").strip()
    except Exception:
        return ""

# --- ROUTE -------------------------------------------------------------------
from fastapi import Body

@router.post("/api/v1/query_force")
def query_force(q: Query, urls: List[str] = Body(..., embed=True)):
    t0 = time.perf_counter()
    scored = []
    for u in urls:
        if not _allowed(u): 
            continue
        try:
            raw = _http_get(u, timeout=25)
            text = extract_text_any(raw, u)
            s    = score(text, q)
            quote = _sanitize_text_for_ui(quote_first(text))
            title = _title_from_html(raw) or "（无标题）"
            scored.append({"title": title, "url": u, "snippet": "", "quote": quote, "score": s})
        except Exception:
            continue
    if not scored:
        raise HTTPException(status_code=422, detail="force_fetch_failed")
    scored.sort(key=lambda x: x["score"], reverse=True)
    top = scored[:3]
    return {
        "mode": "online_only_forced",
        "elapsed_ms": int((time.perf_counter()-t0)*1000),
        "answer_zh": "；".join([t["quote"] for t in top if t["quote"]]) or "（见引用条款）",
        "citations": top
    }

@router.post("/api/v1/query")
def query_online(q: Query):
    """
    Online-only route:
      Q → Perplexity candidates → CSE verify (allowlist) → fetch → OCR/parse → score → top-N JSON
    """
    if not ALLOW:
        raise HTTPException(status_code=400, detail="ALLOWLIST_DOMAINS not set")

    t0 = time.perf_counter()

    # Strong zh query for CSE
    terms = [q.province, q.doc_class, q.asset or "", q.question]
    hint  = " 规定 文件 通知 办法 指南 接入 并网 审批"
    full_query = " ".join([t for t in terms if t]).strip() + " " + hint

    # 1) Perplexity → candidate URLs (soft failure)
    perpl = perplexity_urls(full_query, max_urls=10)

    # 2) Google CSE + allowlist (hard requirement)
    candidates = verify_or_search(perpl, full_query, q)
    if not candidates:
        raise HTTPException(
            status_code=422,
            detail={
                "code":"no_first_party_citation",
                "hint":"扩大检索范围或调整地区/资产类型；检查 allowlist 是否包含目标机构域名。",
                "allowlist": list(ALLOW)
            }
        )

    # 3) Fetch + parse + score
    scored: List[Dict[str, Any]] = []
    for c in candidates[:8]:  # cap fetches for latency
        url = c["url"]
        try:
            raw = _http_get(url, timeout=25)
            text = extract_text_any(raw, url)
            if not _passes_policy(text):
                continue
            title = c.get("title") or _title_from_html(raw) or "（无标题）"
        except Exception:
            continue
        sc    = score(text, q)
        quote = quote_first(text)
        quote = _sanitize_text_for_ui(quote)
        scored.append({
            "title": title,
            "url": url,
            "snippet": c.get("snippet",""),
            "quote": quote,
            "score": sc,
            "effective_date": None  # TODO: parse later; keep schema stable now
        })

    if not scored:
        raise HTTPException(status_code=422, detail="fetch_or_ocr_failed")

    scored.sort(key=lambda x: x["score"], reverse=True)
    top = scored[:3]

    elapsed_ms = int((time.perf_counter() - t0) * 1000)
    # Quote-first verbatim-ish bullets; minimal glue
    answer_zh = "；".join([t["quote"] for t in top if t["quote"]]) or "（见引用条款）"

    return {
        "mode": "online_only",
        "elapsed_ms": elapsed_ms,
        "answer_zh": _sanitize_text_for_ui(answer_zh),
        "citations": [
            {
              "title": t["title"],
              "url": t["url"],
              "snippet": t["snippet"],
              "quote": t["quote"],
              "effective_date": t.get("effective_date")
            } for t in top
        ]
    }
