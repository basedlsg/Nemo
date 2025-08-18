# Design Document

**Owners:** [PC, EC2]

**Lay Overview:** Cloud-agnostic RAG architecture using NeMo microservices on GKE with citation-required guardrails. Discovery via Perplexity → verification via Google CSE → immutable storage → OCR → normalization → vector search. Chinese-first UI with refusal-by-default policy.

## Overview

The geo-adaptive energy assistant implements a citation-required RAG (Retrieval-Augmented Generation) system that provides compliance guidance for Chinese provincial energy regulations. The system enforces a strict policy of only answering questions when verified first-party official citations exist, otherwise refusing with clear explanations.

The architecture is designed to be cloud-agnostic and portable, using Kubernetes orchestration with standard interfaces (S3-compatible storage, Postgres-compatible databases) to enable migration between cloud providers without vendor lock-in.

## Architecture

### Architecture Decision Records (ADRs)

**ADR-001:** RAG core via NeMo (Retriever, Guardrails, Evaluator) on GKE; portable to any K8s cluster
**ADR-002:** Storage - GCS (WORM) for snapshots; AlloyDB+pgvector for citations/embeddings; BigQuery for analytics
**ADR-003:** Discovery→Verification - Perplexity (allowlisted) → Google CSE JSON (deterministic) → ingest
**ADR-004:** Refusal-by-default - answers require verified first-party citation; otherwise 422 response
**ADR-005:** Cloud-agnostic - K8s, Postgres-compatible, S3-compatible abstractions; no vendor-specific logic

### System Architecture Diagram

```
[Explorer UI] ─┐            ┌─> [NeMo Retriever svc]
[Radar UI] ────┼─> [API GW] ├─> [NeMo Guardrails svc]
               │            └─> [Evaluator queue -> Evaluator jobs]
               │
               └─> [Research Orchestrator]
                    ├─> Perplexity (discovery, allowlist)
                    ├─> Google CSE (verify, allowlist)  
                    └─> Ingest svc -> GCS (WORM) -> Document AI OCR -> Normalize -> AlloyDB+pgvector
```

### Core Services

1. **API Gateway (FastAPI)** - Request routing, authentication, rate limiting
2. **NeMo Retriever** - Geo-sharded vector search with BM25+vector reranking
3. **NeMo Guardrails** - Policy enforcement (citations_required, zh_first, unsafe_scope)
4. **NeMo Evaluator** - Offline quality scoring and metrics
5. **Research Orchestrator** - Discovery and verification pipeline coordination
6. **Ingest Service** - Document fetching, OCR, normalization, embedding generation
7. **Explorer UI** - Chinese-first compliance query interface
8. **Radar UI** - Market signals and opportunity tracking dashboard

## Components and Interfaces

### NeMo Integration

#### Retriever Service
- **Purpose:** Geo-sharded vector search with citation filtering
- **Sharding:** By province (shandong, guangdong, inner_mongolia)
- **Ranking:** BM25 + vector similarity reranking
- **Output:** Passages with citation_id, confidence scores
- **SLA:** p95 < 600ms

#### Guardrails Service  
- **Purpose:** Policy enforcement before answer generation
- **Policies:**
  - `citations_required`: Hard fail if zero citations or missing snapshot metadata
  - `zh_first`: Block if answer not in zh-CN when language unspecified
  - `unsafe_scope`: Block if province mismatch or domain not in registry
- **Response:** Pass/fail with policy violation details

#### Evaluator Service
- **Purpose:** Offline quality assessment and metrics
- **Metrics:** Groundedness, citation precision, latency, refusal accuracy
- **Schedule:** Nightly batch jobs on held-out test sets
- **Thresholds:** Province enabled only if all metrics pass

### Research Pipeline

#### Discovery Phase (Perplexity Integration)
```python
import os, requests

API_KEY = os.environ["PPLX_API_KEY"]
resp = requests.post(
  "https://api.perplexity.ai/chat/completions",
  headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
  json={
    "model":"sonar-deep-research",
    "messages":[{"role":"user","content":"Find official 广东电力交易中心 交易规则 更新。只返回 *.gov.cn 或 gzpec.cn"}],
    "search_domain_filter":[".gov.cn","gzpec.cn"],
    "return_related_questions": False
  },
  timeout=60
)
```

#### Verification Phase (Google CSE Integration)
```python
import os, requests

KEY, CSE = os.environ["GOOGLE_API_KEY"], os.environ["GOOGLE_CSE_ID"]
r = requests.get(
  "https://www.googleapis.com/customsearch/v1",
  params={"key": KEY, "cx": CSE, "q": "site:gzpec.cn 交易 规则 公告", "num": 10, "lr": "lang_zh-CN"},
  timeout=30
)
```

#### Ingestion and Processing
1. **Fetch & Snapshot:** Store to GCS with SHA256 checksum and metadata
2. **OCR Processing:** Google Document AI for Chinese text and table extraction
3. **Normalization:** Map to energy ontology (jurisdiction → market/code → asset → lifecycle → requirement → parameter → citation)
4. **Embedding Generation:** Generate vectors using Google Cloud Vertex AI
5. **Storage:** Persist to AlloyDB with pgvector extension

### API Interfaces

#### Explorer Query API
```yaml
POST /api/v1/query:
  requestBody:
    required: true
    content:
      application/json:
        schema:
          type: object
          required: [province, asset, doc_class, question]
          properties:
            province: {type: string, enum: [shandong, guangdong, inner_mongolia]}
            asset: {type: string, enum: [wind, solar, bess, coal_flex]}
            doc_class: {type: string, enum: [market_rules, grid_connection, dispatch_ops]}
            question: {type: string}
  responses:
    "200":
      content:
        application/json:
          schema:
            type: object
            properties:
              answer_zh: {type: string}
              citations:
                type: array
                items:
                  type: object
                  required: [citation_id, url, checksum, effective_date, title]
    "422":
      content:
        application/json:
          schema:
            type: object
            required: [status, reason, policy]
            properties:
              status: {type: string, enum: [refused]}
              reason: {type: string, enum: [no_first_party_citation, stale_citation, province_mismatch, unsupported_doc_class]}
              policy: {type: string, enum: [first_party_citation_required]}
```

#### Research Orchestrator APIs
- **POST /api/v1/discover** - Trigger Perplexity discovery with allowlisted domains
- **POST /api/v1/verify** - Verify candidates using Google CSE JSON API  
- **POST /api/v1/ingest** - Process verified documents through OCR and normalization

## Data Models

### Citations Table (AlloyDB + pgvector)
```sql
CREATE TABLE citations (
  citation_id UUID PRIMARY KEY,
  province TEXT NOT NULL,
  doc_class TEXT NOT NULL,        -- market_rules | grid_connection | dispatch_ops
  asset TEXT,                     -- wind | solar | bess | coal_flex | ...
  title TEXT NOT NULL,
  url TEXT NOT NULL,
  effective_date DATE NOT NULL,
  checksum TEXT NOT NULL,
  content TEXT NOT NULL,          -- normalized atomic clauses
  embedding VECTOR(1536),
  superseded_by UUID,
  chunk_id TEXT,                  -- for traceability
  parent_citation_id UUID         -- chunk parent reference
);

CREATE INDEX cit_idx ON citations (province, doc_class, asset);
CREATE INDEX cit_effective_idx ON citations (province, doc_class, effective_date DESC);
```

### Packs Table (Generated Compliance Outputs)
```sql
CREATE TABLE packs (
  pack_id UUID PRIMARY KEY,
  created_at TIMESTAMP DEFAULT now(),
  province TEXT, asset TEXT, doc_class TEXT,
  query_fingerprint TEXT NOT NULL,
  citation_ids UUID[] NOT NULL
);

CREATE INDEX pack_qf_idx ON packs (query_fingerprint);
```

### Sources Registry
```sql
CREATE TABLE sources (
  domain TEXT PRIMARY KEY,
  province TEXT, label TEXT,
  cadence TEXT, robots TEXT,
  last_crawled_at TIMESTAMP, owner TEXT
);
```

### Source Registry Configuration (YAML → DB)
```yaml
- province: guangdong
  domain: gzpec.cn
  label: 广东电力交易中心
  doc_classes: [market_rules, dispatch_ops]
  cadence: "R/2025-01-01T00:00:00Z/P1D"  # daily
  robots: allow
  fetch_method: html|pdf
  selectors:
    index: "a[href*='公告'], a[href*='规则']"
  effective_date_locator: "meta[name='pubDate'] || regex"
  owner: CC
```

## Error Handling

### Refusal Policy Implementation
```python
from fastapi import FastAPI
from fastapi.responses import JSONResponse

app = FastAPI()

class RefusalException(Exception):
    def __init__(self, reason: str): 
        self.reason = reason

@app.exception_handler(RefusalException)
async def refusal_handler(_, exc: RefusalException):
    return JSONResponse(status_code=422, content={
        "status":"refused",
        "reason": exc.reason,
        "policy":"first_party_citation_required"
    })

def require_citation(citations):
    if not citations:
        raise RefusalException("no_first_party_citation")
```

### Guardrails Policy Configuration
```json
{
  "policies": {
    "citations_required": {
      "rule": "answer.citations.length > 0 && all(c in citations where c.snapshot && c.checksum && c.effective_date)"
    },
    "zh_first": { "rule": "answer.lang == 'zh-CN'" },
    "unsafe_scope": {
      "rule": "query.province in registry.provinces && all(c.domain in registry.allowlist for c in citations)"
    }
  },
  "on_fail": "refuse"
}
```

### Effective Date Conflict Resolution
**Rule:** Prefer the latest document whose effective_date <= now(); mark older documents as superseded_by the newer version. Refuse answers that only reference superseded citations.

### Chunking and Traceability
- Split normalized text by clause with max 800 tokens per chunk and 100 token overlap
- Persist chunk_id and parent_citation_id for complete answer traceability
- Enable debugging of which specific document sections contributed to each answer

## Testing Strategy

### Quality Assurance Framework

#### Evaluator Gold Sets
- Require 10 seed Q/As per province × doc_class combination before enabling
- Nightly evaluation jobs compute metrics on held-out test sets
- Province enabled only after passing all thresholds + committee approvals

#### RAG Evaluation Metrics
- **Groundedness:** Exact-span match in cited text ≥ 90%
- **Citation Precision:** No extra/irrelevant citations ≥ 95%  
- **Refusal Accuracy:** Correct refusal when no eligible citation ≥ 99%
- **Latency:** End-to-end p95 < 1000ms, Retriever p95 < 600ms

#### Red-Team Testing
- **Prompt Injection:** Attempt to force answers without citations
- **Cross-Province Leakage:** Verify province isolation in responses
- **Open-Web Contamination:** Ensure only allowlisted sources used
- **Stale Citation Detection:** Test superseded document handling

#### Load and Chaos Testing
- **Performance:** k6 scripts targeting SLO thresholds at pilot QPS
- **Resilience:** Pod kill, network jitter, verify retries and circuit breakers
- **Degradation:** External API failures should queue for manual processing

### Observability and Monitoring

#### Required Metrics
- `retriever_latency_ms{p50,p95}`
- `answer_latency_ms{p50,p95}`
- `groundedness_score` (0-1)
- `citation_precision` (0-1)
- `refusal_rate`
- `ingestion_doc_freshness_hours`
- `crawl_failures_total`
- `pack_gen_duration_ms`

#### Structured Logging (JSON)
Required fields: service, trace_id, user, province, doc_class, asset, event, citation_ids, latency_ms, verdict

#### Dashboards and Alerts
- Real-time SLO monitoring with p95 latency alerts
- Ingestion pipeline health and freshness tracking
- Citation quality and refusal rate trends
- Committee-specific KPI dashboards for governance