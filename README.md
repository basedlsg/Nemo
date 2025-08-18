# Geo-Adaptive Energy Assistant

A specialized system that normalizes provincial energy regulations across Chinese provinces and provides compliance guidance only when official first-party citations exist. The system enforces a strict policy of refusing to answer questions without verified official documentation.

## Overview

The geo-adaptive energy assistant covers market procedures, grid connection requirements, and dispatch codes for renewable energy assets (wind/solar), battery storage (BESS), and coal flexibility projects. The pilot focuses on Shandong, Guangdong, and Inner Mongolia provinces.

### Key Features

- **Citation-Required Responses**: Only answers with verified first-party official citations
- **Chinese-First Interface**: Default zh-CN output with optional English summaries  
- **Cloud-Agnostic Architecture**: Portable Kubernetes deployment with standard interfaces
- **Multi-Province Support**: Shandong, Guangdong, Inner Mongolia (Sichuan queued)
- **Refusal-by-Default Policy**: Clear explanations when no official sources exist

## Quick Start

### Prerequisites

- Python 3.11+
- Docker and Docker Compose
- kubectl and Helm (for Kubernetes deployment)
- Google Cloud SDK (for GCP services)

### Development Setup

1. Clone the repository and set up the development environment:
```bash
make dev
source venv/bin/activate
```

2. Configure environment variables:
```bash
cp .env.example .env
# Edit .env with your API keys and configuration
```

3. Run the development stack:
```bash
# Start API gateway
make run-api

# Start Explorer UI (in another terminal)
make run-explorer

# Start Radar UI (in another terminal)  
make run-radar
```

### Testing

```bash
# Run all tests
make test

# Run specific test suites
make test-unit
make test-integration
make test-rag
```

## Architecture

### Core Components

- **API Gateway**: FastAPI-based request routing and validation
- **NeMo Services**: Retriever, Guardrails, and Evaluator microservices
- **Research Pipeline**: Discovery (Perplexity) → Verification (Google CSE) → Ingestion
- **Explorer UI**: Chinese-first compliance query interface
- **Radar UI**: Market signals and opportunity tracking

### Data Flow

```
Query → API Gateway → NeMo Retriever → Guardrails → Response/Refusal
                                    ↓
Discovery → Verification → Ingestion → OCR → Normalization → Vector Storage
```

## API Usage

### Query Energy Regulations

```bash
curl -X POST "http://localhost:8000/api/v1/query" \
  -H "Content-Type: application/json" \
  -d '{
    "province": "guangdong",
    "asset": "solar", 
    "doc_class": "grid_connection",
    "question": "并网验收需要哪些资料？"
  }'
```

### Response Format

**Success (200):**
```json
{
  "answer_zh": "根据广东电力交易中心规定...",
  "citations": [{
    "citation_id": "uuid",
    "title": "广东省分布式光伏并网管理办法",
    "url": "https://gzpec.cn/...",
    "checksum": "sha256...",
    "effective_date": "2025-03-01"
  }]
}
```

**Refusal (422):**
```json
{
  "status": "refused",
  "reason": "no_first_party_citation", 
  "policy": "first_party_citation_required"
}
```

## Deployment

### Kubernetes

```bash
# Apply infrastructure
make infra-apply

# Deploy to staging
make deploy-staging

# Deploy to production
make deploy-prod
```

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `PPLX_API_KEY` | Perplexity API key for discovery | Yes |
| `GOOGLE_API_KEY` | Google API key for CSE verification | Yes |
| `GOOGLE_CSE_ID` | Custom Search Engine ID | Yes |
| `DATABASE_URL` | AlloyDB connection string | Yes |
| `GCS_BUCKET` | Storage bucket for document snapshots | Yes |

## Quality Gates

The system enforces strict quality thresholds:

- **Groundedness**: ≥90% (answers must be grounded in cited text)
- **Citation Precision**: ≥95% (no irrelevant citations)
- **Refusal Accuracy**: ≥99% (correct refusal when no citations)
- **Latency**: p95 < 1000ms end-to-end, p95 < 600ms retriever

## Contributing

1. Follow conventional commits format
2. Run pre-commit hooks: `pre-commit install`
3. Ensure all tests pass: `make test`
4. Update documentation for new features

## License

MIT License - see LICENSE file for details.