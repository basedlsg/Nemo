import re
import urllib.parse
import requests

def _domain(url: str) -> str:
    try:
        d = urllib.parse.urlparse(url).netloc.lower()
        for p in ("www.", "m.", "wap."):
            if d.startswith(p):
                d = d[len(p):]
        return d
    except Exception:
        return ""

def _allowed(url: str, allowlist: set) -> bool:
    d = _domain(url)
    return any(d == a or d.endswith("." + a) for a in allowlist)

def _classify_government_domain(url: str) -> str:
    """
    Classify government domains by authority level and specialization
    """
    domain = _domain(url)
    
    # National authorities
    if domain in ["nea.gov.cn", "ndrc.gov.cn"]:
        return "national_energy"
    elif domain in ["miit.gov.cn", "mee.gov.cn"]:
        return "national_regulatory"
    elif domain == "gov.cn":
        return "national_general"
    
    # Provincial authorities
    elif domain in ["gd.gov.cn", "sh.gov.cn", "bj.gov.cn", "tj.gov.cn", "he.gov.cn", 
                   "sx.gov.cn", "nm.gov.cn", "ln.gov.cn", "jl.gov.cn", "hlj.gov.cn",
                   "js.gov.cn", "zj.gov.cn", "ah.gov.cn", "fj.gov.cn", "jx.gov.cn",
                   "sd.gov.cn", "ha.gov.cn", "hb.gov.cn", "hn.gov.cn", "sc.gov.cn",
                   "gz.gov.cn", "yn.gov.cn", "xz.gov.cn", "sn.gov.cn", "gs.gov.cn",
                   "qh.gov.cn", "nx.gov.cn", "xj.gov.cn"]:
        return "provincial"
    
    # Specialized agencies
    elif "customs.gov.cn" in domain:
        return "customs"
    elif "tax.gov.cn" in domain:
        return "tax"
    
    return "other_government"

def _http_get(url: str, timeout=20) -> bytes:
    r = requests.get(url, timeout=timeout, headers={"User-Agent": "Mozilla/5.0 (GAEA-online)"})
    r.raise_for_status()
    return r.content

def _basic_text_from_html(html: bytes) -> str:
    # ultra-light extractor: strip tags; good enough for quick scoring if OCR not available
    txt = re.sub(br"<script.*?</script>|<style.*?</style>", b" ", html, flags=re.S | re.I)
    txt = re.sub(br"<[^>]+>", b" ", txt)
    try:
        return txt.decode("utf-8", "ignore")
    except:
        return txt.decode("gb18030", "ignore")

def _sanitize_text_for_ui(text: str) -> str:
    if not text:
        return ""
    text = text.replace("\x00", "")
    text = re.sub(r"[\x00-\x1F\x7F]", " ", text)  # control chars
    text = re.sub(r"\s{2,}", " ", text)
    return text.strip()

def quote_first(text: str) -> str:
    # Return first 1-2 short clauses as "verbatim-ish" bullets
    lines = [l.strip() for l in re.split(r"[。\n]", text) if l.strip()]
    return "；".join(lines[:2])