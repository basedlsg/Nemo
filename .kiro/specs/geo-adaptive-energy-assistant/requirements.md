# Requirements Document

**Owners:** [EC, PC, EC2, CC, OC, IC]

**Lay Overview:** Build a geo-adaptive assistant that answers only with first-party official citations. Pilot provinces: Shandong, Guangdong, Inner Mongolia (Sichuan queued). Chinese-first output. Cloud-agnostic, portable. Refuse by default if citations missing.

## Introduction

The geo-adaptive energy assistant is a specialized system that normalizes provincial energy regulations across Chinese provinces and provides compliance guidance only when official first-party citations exist. The system covers market procedures, grid connection requirements, and dispatch codes for renewable energy assets (wind/solar), battery storage (BESS), and coal flexibility projects. The pilot focuses on Shandong, Guangdong, and Inner Mongolia provinces, with a strict policy of refusing to answer questions without verified official documentation.

## Non-Negotiables

1. **Citation Gate:** The system MUST refuse any answer that lacks a first-party citation (citation_id -> snapshot with URL, checksum, effective_date)
2. **Chinese-First:** UI responses default to zh-CN; English summary optional
3. **Cloud-Agnostic:** Kubernetes + Postgres-compatible DB + S3-compatible storage abstractions. No vendor-specific code paths
4. **Scope (Pilot):** Provinces = Shandong, Guangdong, Inner Mongolia; Sichuan queued (ingestion ready, feature flag off)

## Requirements

### Requirement 1: Citation-Required Query Processing

**Owners:** [PC, EC2, CC]

**User Story:** As an energy compliance professional, I want to query province-specific energy regulations with guaranteed official citations, so that I can ensure regulatory compliance with verifiable sources.

#### Acceptance Criteria

1. WHEN a user submits query {province:'guangdong', doc_class:'grid_connection', question:'并网验收需要哪些资料？'} THEN the system SHALL return a Chinese pack within 120 seconds AND every requirement line SHALL include at least one citation_id with valid snapshot (checksum + effective_date) OR the system SHALL refuse with reason no_first_party_citation
2. WHEN no verified first-party citation exists for an answer THEN the system SHALL return 422 refused with policy first_party_citation_required AND log verdict=refused with trace_id and query fingerprint
3. WHEN an answer is provided THEN the system SHALL include citation metadata (citation_id, title, URL, effective_date, checksum) for verification
4. WHEN the system processes a query THEN it SHALL apply guardrails: citations_required (block if zero citations), zh_first (block if not zh-CN), unsafe_scope (block if province mismatch or domain not in registry)

### Requirement 2: Source Registry and Ingestion Pipeline

**Owners:** [PC, EC2, CC]

**User Story:** As a system administrator, I want the research pipeline to discover and verify official energy documents automatically, so that the knowledge base stays current with authoritative sources only.

#### Acceptance Criteria

1. WHEN the discovery process runs THEN the system SHALL use Perplexity API with domain allowlists (\*.gov.cn, operator domains) only AND return candidate URLs
2. WHEN candidate documents are found THEN the system SHALL verify them using Google Programmable Search CSE JSON API scoped to the same allowlist AND retrieve canonical URLs
3. WHEN documents are verified THEN the system SHALL store immutable snapshots in object storage (versioned/WORM) with SHA256 checksums and effective dates
4. WHEN documents are processed THEN the system SHALL extract text using Document AI OCR AND normalize to ontology (jurisdiction → market/code → asset → lifecycle → requirement → parameter → citation) AND compute embeddings
5. WHEN enabling a source THEN robots.txt SHALL be honored AND fetch SHALL be logged with trace_id AND effective date SHALL be extracted or flagged "unknown" (blocked from answers) AND Mini-Evaluator baseline SHALL pass (≥80% groundedness on seed Q/As) AND CC SHALL spot-check ≥10% of new docs

### Requirement 3

**User Story:** As a compliance officer, I want the system to cover specific energy asset types and regulatory domains, so that I can get targeted guidance for my projects.

#### Acceptance Criteria

1. WHEN querying regulations THEN the system SHALL support wind, solar, BESS, and coal flexibility asset types
2. WHEN selecting regulatory domains THEN the system SHALL cover market rules, grid connection procedures, and dispatch operations
3. WHEN processing documents THEN the system SHALL map content to the ontology (jurisdiction → market/code → asset → lifecycle → requirement → parameter → citation)
4. WHEN generating responses THEN the system SHALL filter results by province, asset type, and document class

### Requirement 4: Quality Gates and Evaluation Metrics

**Owners:** [OC, CC]

**User Story:** As a quality assurance manager, I want strict citation requirements and evaluation metrics, so that the system maintains high accuracy and reliability standards.

#### Acceptance Criteria

1. WHEN Evaluator runs on held-out Q/As per province & doc-class THEN groundedness SHALL be ≥90% AND citation precision SHALL be ≥95% AND refusal accuracy SHALL be ≥99%
2. WHEN measuring response time THEN p95 latency SHALL be <1000ms end-to-end
3. WHEN enabling a province THEN the system SHALL pass Evaluator thresholds (groundedness ≥90%, citation precision ≥95%, refusal accuracy ≥99%) AND CC spot-check (10% sample) AND OC sign-off
4. WHEN conducting refusal red-team testing THEN the system SHALL resist answer-without-citation injection AND cross-province misrouting AND open-web leakage
5. WHEN policy-diff detection runs THEN the system SHALL mark superseded_by if newer doc detected AND refuse answers from stale citations

### Requirement 5

**User Story:** As a DevOps engineer, I want cloud-agnostic architecture with portable components, so that the system can migrate between cloud providers without vendor lock-in.

#### Acceptance Criteria

1. WHEN deploying infrastructure THEN the system SHALL use Kubernetes with portable Helm charts
2. WHEN accessing storage THEN the system SHALL use S3-compatible interfaces for object storage
3. WHEN accessing databases THEN the system SHALL use Postgres-compatible drivers
4. WHEN running NeMo services THEN they SHALL be containerized and deployable on any GPU-capable Kubernetes cluster
5. WHEN external APIs are unavailable THEN the pipeline SHALL degrade gracefully to manual queue processing

### Requirement 6: Chinese-First User Interface

**Owners:** [EC2, PC]

**User Story:** As an end user, I want a Chinese-first interface with bilingual documentation support, so that I can work efficiently in my preferred language.

#### Acceptance Criteria

1. WHEN using the Explorer UI THEN the interface SHALL default to Chinese with province/asset/doc-class selectors AND support query format {province, asset, doc_class, question}
2. WHEN viewing answers THEN citations SHALL display inline with title and effective date AND include citation_id for verification
3. WHEN the system refuses to answer THEN it SHALL return 422 status with refusal badge showing explanation and "request ingestion" action
4. WHEN generating compliance packs THEN they SHALL be in Chinese PDF format using headless Chrome/puppeteer with Noto CJK fonts AND CSS line-break:anywhere; word-break: break-word to avoid Hanzi clipping
5. WHEN accessing documentation THEN bilingual docs SHALL be maintained with English as development source and Chinese mirrors in /docs/zh-CN with 2-4 sentence lay overviews

### Requirement 7

**User Story:** As a security administrator, I want comprehensive data protection and access controls, so that the system maintains security best practices for sensitive regulatory information.

#### Acceptance Criteria

1. WHEN storing data THEN the system SHALL use CMEK with Cloud KMS for encryption at rest
2. WHEN accessing services THEN VPC Service Controls SHALL be implemented to reduce data exfiltration risk
3. WHEN deploying containers THEN Binary Authorization SHALL enforce signed images only
4. WHEN managing secrets THEN Secret Manager with GKE Workload Identity SHALL be used (no service account keys in code)
5. WHEN handling data THEN only public official documents SHALL be processed with no personal data collection

### Requirement 8: Opportunity Radar and Analytics

**Owners:** [IC, EC2]

**User Story:** As a business stakeholder, I want opportunity radar functionality to track market signals, so that I can identify business opportunities from official announcements.

#### Acceptance Criteria

1. WHEN accessing Radar UI THEN it SHALL display official tender/notice feeds filtered by province and asset type AND show only verified official sources
2. WHEN exporting data THEN CSV export functionality SHALL be available (no CRM in pilot phase) AND BigQuery SHALL store analytics data for lead generation
3. WHEN generating reports THEN weekly bilingual reports SHALL track groundedness %, refusal cases, latency AND include ROI metrics for IC scorecard
4. WHEN processing signals THEN the system SHALL reuse Explorer query flow but format results as territory briefs and signal lists
5. WHEN storing pack analytics THEN the system SHALL log pack_id, created_at, province, asset, doc_class, query_fingerprint, citation_ids for tracking

##

Data Contracts (MVP-Level)

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
  superseded_by UUID
);
CREATE INDEX cit_idx ON citations (province, doc_class, asset);
```

### Packs Table (Compiled Outputs)

```sql
CREATE TABLE packs (
  pack_id UUID PRIMARY KEY,
  created_at TIMESTAMP DEFAULT now(),
  province TEXT, asset TEXT, doc_class TEXT,
  query_fingerprint TEXT NOT NULL,
  citation_ids UUID[] NOT NULL
);
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

## API Contracts

### Explorer API

**POST /api/v1/query**

```json
{
  "province": "guangdong",
  "asset": "solar",
  "doc_class": "grid_connection",
  "question": "并网验收需要哪些资料？"
}
```

**200 Response:**

```json
{
  "answer_zh": "...",
  "citations": [
    {
      "citation_id": "...",
      "title": "...",
      "url": "...",
      "checksum": "...",
      "effective_date": "2025-03-01"
    }
  ]
}
```

**422 Response (Refused):**

```json
{
  "status": "refused",
  "reason": "no_first_party_citation",
  "policy": "first_party_citation_required"
}
```

**GET /api/v1/pack/{id}** → Chinese PDF (+ optional EN summary)

### Research Orchestrator API

- **POST /api/v1/discover** → Perplexity (allowlisted domains) → candidate URLs
- **POST /api/v1/verify** → Google CSE (allowlist) → canonical URLs → enqueue ingest jobs
- **POST /api/v1/ingest** → fetch → snapshot → OCR → normalize → embed → store

## Observability Requirements

### Structured Logging (JSON)

Required fields: service, trace_id, user, province, doc_class, asset, event, citation_ids, latency_ms, verdict

### Dashboards and Alerts

- p50/p95 latency; hit@k; groundedness; citation precision; refusal rate; crawl freshness
- Alerts: ingestion failures; stale sources; SLO > p95 1s Retriever; guardrail breach attempts## Fin
  al Implementation Details

### Refusal Taxonomy (Exact Error Codes)

- `no_first_party_citation`: No verified official citation exists
- `stale_citation`: Only superseded documents available
- `province_mismatch`: Query province not in enabled list
- `unsupported_doc_class`: Document class not supported for province

### Effective Date Semantics

**Rule:** Prefer the latest document whose effective_date <= now(); mark older documents as superseded_by the newer version.

### Chunking Policy

Split normalized text by clause with max 800 tokens per chunk and 100 token overlap. Persist chunk_id and parent_citation_id for answer traceability.

### Evaluator Gold Sets

Require 10 seed Q/As per province × doc_class combination to exist before enabling answers for that combination.

### SLO Targets (Specific Numbers)

- End-to-end p95 < 1000ms
- Retriever p95 < 600ms
- Ingestion freshness T+48h ≥ 95%
- Groundedness ≥ 90%
- Citation precision ≥ 95%
- Refusal accuracy ≥ 99%
