# Chinese Energy Compliance Assistant

A sophisticated AI-powered assistant for Chinese energy compliance and regulatory information retrieval, enhanced with metadata-first retrieval and deterministic filtering capabilities.

## 🚀 Features

### Core Functionality
- **Multi-Province Support**: Coverage across all major Chinese provinces and municipalities
- **Document Classification**: Support for regulations, technical standards, market rules, grid connection, project approval, and environmental protection documents
- **Asset Types**: Solar, wind, BESS, renewable energy, clean energy, offshore wind
- **Bilingual Interface**: Chinese (zh-CN) and English support

### Enhanced Retrieval System (Latest Version)
- **Metadata-First Approach**: Filters documents by province, document class, and status before ranking
- **Deterministic Filtering**: Hard filters applied before scoring for guaranteed relevance
- **Chinese Government Document Support**:
  - 文号 (Official document numbers)
  - 发布机关 (Publishing agencies)
  - 实施日期 (Effective dates)
  - 发布日期 (Publication dates)
  - 状态 (Document status: 现行有效/失效/废止)
- **Canonical Source Registry**: Prioritized government portals for each province
- **Enhanced Scoring**: Multi-factor algorithm combining relevance, authority, and recency
- **Inline Diagnostics**: Transparent search process with applied filters and scoring details

### API Response Format
```json
{
  "answer_zh": "广东省2023年分布式光伏发电项目并网容量限制是6MW。",
  "citations": [
    {
      "citation_id": "cit_001_guangdong",
      "title": "广东省分布式光伏发电项目并网容量限制政策文件",
      "url": "https://www.guangdong.gov.cn/policy/2024/001.html",
      "effective_date": "2024-01-01",
      "wenhao": "粤能规〔2024〕001号",
      "agency": "广东省能源局",
      "status": "现行有效"
    }
  ],
  "diagnostics": {
    "query_terms": ["guangdong", "regulations", "solar"],
    "filters_applied": {
      "province_normalized": "guangdong",
      "doc_class_normalized": "regulations",
      "status": "现行有效"
    },
    "total_candidates": 15,
    "quality_threshold": 3.0,
    "search_strategy": "enhanced_metadata_first"
  }
}
```

## 📋 Prerequisites

- Python 3.8+
- Virtual environment (recommended)
- API Keys for:
  - Perplexity AI (PPLX_API_KEY)
  - Google Custom Search Engine (GOOGLE_API_KEY, GOOGLE_CSE_ID)

## 🛠️ Installation

1. **Clone the repository**
   ```bash
   git clone [repository-url]
   cd chinese-energy-compliance-assistant
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

   **Note**: This project requires Python 3.11+ and the following key dependencies have been added:
   - `pyppeteer>=1.0.2` - For PDF generation in citation packs
   - `vertexai>=0.0.1` - For Google Cloud Vertex AI embeddings
   - `google-cloud-aiplatform>=1.36.4` - For Vertex AI integration

   If you encounter dependency conflicts, you may need to upgrade pydantic:
   ```bash
   pip install --upgrade pydantic
   ```

4. **Set up environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your API keys
   ```

5. **Run database migrations**
   ```bash
   python -m services.storage.migrations.run_migrations
   ```

## 🚀 Quick Start

1. **Start the server**
   ```bash
   python main.py
   # or
   uvicorn services.gateway.api:app --host 0.0.0.0 --port 8000
   ```

2. **Access the API**
   - Health check: `http://localhost:8000/_health`
   - API documentation: `http://localhost:8000/docs`
   - Query endpoint: `http://localhost:8000/api/v1/query`

3. **Test the system**
   ```bash
   python test_six_queries.py
   ```

## 📖 API Usage

### Query Endpoint
**POST** `/api/v1/query`

**Request Body:**
```json
{
  "province": "guangdong",
  "doc_class": "regulations",
  "asset": "solar",
  "question": "广东省2023年分布式光伏发电项目并网容量限制是多少？",
  "lang": "zh-CN"
}
```

**Response:**
```json
{
  "answer_zh": "广东省2023年分布式光伏发电项目并网容量限制是6MW。",
  "citations": [...],
  "diagnostics": {...}
}
```

### Supported Parameters

| Parameter | Type | Description | Options |
|-----------|------|-------------|---------|
| `province` | string | Target province | `guangdong`, `beijing`, `shanghai`, `shandong`, `inner_mongolia`, `fujian` |
| `doc_class` | string | Document classification | `regulations`, `technical_standards`, `market_rules`, `grid_connection`, `project_approval`, `environmental_protection` |
| `asset` | string | Energy asset type | `solar`, `wind`, `bess`, `renewable`, `clean_energy`, `offshore_wind` |
| `question` | string | Specific query in Chinese | Any relevant question |
| `lang` | string | Language preference | `zh-CN`, `en-US` |

## 🔍 Enhanced Features Explained

### 1. Metadata-First Retrieval
The system implements a **filter-first, rank-second** approach:
1. **Query Normalization**: Expand terms with Chinese synonyms
2. **Hard Filtering**: Apply deterministic filters (province, doc_class, status)
3. **Metadata Extraction**: Parse Chinese government document metadata
4. **Enhanced Scoring**: Multi-factor scoring with authority weighting
5. **Canonical Prioritization**: Trusted government sources prioritized

### 2. Chinese Government Document Support
- **文号 Pattern**: `粤能规〔2024〕001号`, `发改〔2023〕002号`
- **Agency Extraction**: `广东省能源局`, `国家发改委`
- **Date Normalization**: Handles various Chinese date formats
- **Status Classification**: `现行有效`, `失效`, `废止`, `部分失效`

### 3. Source Registry
Pre-configured canonical government portals for each province:
- **Guangdong**: `drc.gd.gov.cn`, `www.gd.gov.cn`
- **Beijing**: `www.beijing.gov.cn`, `fgw.beijing.gov.cn`
- **Shanghai**: `www.shanghai.gov.cn`, `fgw.sh.gov.cn`
- And more...

### 4. Quality Assurance
- **Strict Refusal Threshold**: Documents scoring < 3.0 trigger detailed refusals
- **Authority Validation**: Official government domains prioritized
- **Metadata Completeness**: Documents with complete metadata score higher
- **Recency Weighting**: Recent documents receive relevance boosts

### 5. Transparency Features
- **Inline Diagnostics**: Shows applied filters and scoring rationale
- **Search Statistics**: Number of candidates and quality thresholds
- **Strategy Information**: Which retrieval approach was used
- **Enhanced Refusals**: Detailed explanations when no suitable documents found

## 🧪 Testing

### Recent Fixes Applied
✅ **Dependencies Added**: pyppeteer, vertexai, google-cloud-aiplatform
✅ **Core Models Implemented**: QueryContext, ProcessingMetrics
✅ **Error Handling Enhanced**: ErrorFormatter, RefusalHTTPException
✅ **Syntax Errors Fixed**: test_verification.py class definition
✅ **Pydantic Modernized**: Updated to v2 validators
✅ **FastAPI Modernized**: Replaced @app.on_event with lifespan managers

### Six Comprehensive Test Queries

1. **Guangdong 2023 Distributed PV Cap**
   - Tests MW/GW capacity extraction
   - Validates 2023 effective date
   - Checks `*.gd.gov.cn` domain

2. **Beijing Wind Grid-Adaptation**
   - Tests technical standard compliance
   - Validates frequency response requirements
   - Checks Beijing government domains

3. **Shanghai BESS Market Entry**
   - Tests market rule compliance
   - Validates MW threshold extraction
   - Checks Shanghai government domains

4. **Shandong Inter-provincial Renewable**
   - Tests document flow requirements
   - Validates official document naming
   - Checks Shandong government domains

5. **Inner Mongolia Clean-Energy Base**
   - Tests environmental monitoring frequency
   - Validates ecological protection requirements
   - Checks Inner Mongolia domains

6. **Fujian Offshore-Wind Pre-approval**
   - Tests sea use approval requirements
   - Validates three-document checklist
   - Checks Fujian government domains

### Running Tests
```bash
# Run all six test queries
python test_six_queries.py

# Run unit tests
pytest tests/unit/

# Run with custom timeout (seconds)
python -c "
import requests
# Custom test logic here
"
```

**Note**: If you encounter import errors related to pydantic or dependencies, try:
```bash
pip install --upgrade pydantic
pip install --upgrade pydantic-core
```

## 📁 Project Structure

```
chinese-energy-compliance-assistant/
├── services/
│   ├── gateway/
│   │   ├── api.py              # FastAPI application
│   │   └── health.py           # Health check endpoints
│   ├── online/
│   │   ├── query_online.py     # Enhanced query processing
│   │   └── search.py           # Search implementation
│   ├── core/
│   │   ├── models.py           # Pydantic models
│   │   ├── query_normalize.py  # Query normalization
│   │   ├── metadata_extractor.py # Chinese document parsing
│   │   ├── retrieval.py        # Retrieval system
│   │   └── utils.py            # Utility functions
│   ├── storage/
│   │   ├── migrations/         # Database migrations
│   │   └── database.py         # Database connection
│   └── config/
│       └── settings.py         # Configuration
├── data/
│   ├── registry/
│   │   └── sources.yaml        # Canonical source registry
│   └── storage/
│       └── migrations/         # SQL migration files
├── tests/
│   ├── test_six_queries.py     # Six comprehensive tests
│   ├── test_server.py          # Mock server for testing
│   └── simple_server.py        # Simple test server
├── docs/
│   ├── ENHANCED_SYSTEM_TEST_REPORT.md # Detailed test report
│   └── CHIEF_ARCHITECT_REPORT.md       # Architecture overview
├── main.py                     # Application entry point
├── requirements.txt            # Python dependencies
├── .env.example               # Environment template
├── .gitignore                # Git ignore rules
└── README.md                 # This file
```

## 🔧 Configuration

### Environment Variables
```bash
# Required API Keys
PPLX_API_KEY=your_perplexity_api_key
GOOGLE_API_KEY=your_google_api_key
GOOGLE_CSE_ID=your_google_cse_id

# System Configuration
FEATURE_ONLINE_QUERY=true
QUERY_MODE=web_only
ALLOWLIST_DOMAINS=*.gov.cn,*.sina.com.cn

# Server Configuration
HOST=0.0.0.0
PORT=8000
LOG_LEVEL=info
```

### Database Configuration
The system uses PostgreSQL with pgvector extension for enhanced document retrieval.

## 🚀 Deployment

### Local Development
```bash
# Install dependencies
pip install -r requirements.txt

# Set up environment
cp .env.example .env
# Edit .env with your keys

# Run migrations
python -m services.storage.migrations.run_migrations

# Start server
python main.py
```

### Production Deployment
```bash
# Using uvicorn
uvicorn services.gateway.api:app --host 0.0.0.0 --port 8000 --workers 4

# Using gunicorn
gunicorn services.gateway.api:app --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000 --workers 4
```

## 📊 Performance & Evaluation

### Expected Improvements
- **+60% Precision**: Through deterministic filtering
- **+45% Relevance**: Through metadata-first ranking
- **+80% Authority**: Through canonical source prioritization
- **100% Transparency**: Through inline diagnostics

### Evaluation Metrics
- **Recall@5**: Percentage of relevant documents in top 5 results
- **nDCG@5**: Normalized Discounted Cumulative Gain
- **MRR**: Mean Reciprocal Rank
- **Refusal Precision**: Accuracy of low-confidence rejections

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is proprietary. All rights reserved.

## 📞 Support

For questions or issues, please create an issue in the repository or contact the development team.

---

**Version**: 2.0.0 (Enhanced)
**Status**: Production Ready
**Last Updated**: January 2025