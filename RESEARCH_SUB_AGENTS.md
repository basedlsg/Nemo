# 🔬 RESEARCH SUB-AGENTS FRAMEWORK
## Chinese Energy Compliance Document Retrieval Enhancement

### **🎯 Problem Statement**
Current system returns coal procurement contracts when user asks for "transportation regulations for 5 tons of coal" - indicating poor relevance filtering and context understanding.

---

## 🏗️ **SUB-AGENT ARCHITECTURE**

### **1. 🎯 QUERY ANALYSIS AGENT**
**Purpose**: Parse and understand user intent with high precision

**Responsibilities**:
- Extract key entities (commodity, weight, transport mode, region)
- Classify query type (regulatory, procedural, compliance)
- Identify temporal context (current regulations vs historical)
- Determine scope (national, provincial, municipal)

**Example Input**: "transportation for 5 tons of coal in Guangdong"
**Output**:
```json
{
  "commodity": "coal",
  "weight": "5 tons",
  "transport_mode": "road/unspecified",
  "region": "Guangdong",
  "query_type": "regulatory",
  "document_class": "transport_permits",
  "priority_keywords": ["运输", "许可证", "5吨", "煤炭", "广东"]
}
```

### **2. 📋 DOCUMENT CLASSIFICATION AGENT**
**Purpose**: Categorize documents by type and relevance

**Categories**:
- **Regulatory Documents**: 规定, 办法, 条例, 通知
- **Procedural Guides**: 指南, 流程, 操作手册
- **Permits & Licenses**: 许可证, 审批, 备案
- **Procurement Contracts**: 合同, 招标, 采购
- **Technical Standards**: 标准, 规范, 技术参数
- **Transportation Specific**: 运输, 物流, 配送

**Scoring System**:
- Regulatory: +100 points
- Transportation-related: +80 points
- Weight-specific: +60 points
- Region-specific: +50 points
- Procurement: -50 points (penalty)

### **3. 🚛 TRANSPORTATION SPECIALIST AGENT**
**Purpose**: Focus on transport-specific regulations and requirements

**Expertise Areas**:
- **Weight Classifications**: 
  - < 1 ton: 轻型运输
  - 1-10 tons: 中型运输
  - 10-50 tons: 重型运输
  - > 50 tons: 超重型运输

- **Transport Modes**:
  - Road transport: 公路运输
  - Rail transport: 铁路运输
  - Water transport: 水路运输
  - Intermodal: 多式联运

- **Permit Requirements**:
  - 道路运输证
  - 危险货物运输许可证
  - 超限运输许可证
  - 临时通行证

### **4. 📊 WEIGHT & VOLUME FILTERING AGENT**
**Purpose**: Match documents to specific weight/volume requirements

**Filtering Logic**:
```python
def weight_relevance_score(doc_text, target_weight):
    weight_patterns = {
        "5吨": ["5吨", "5t", "5 ton", "5吨以下", "5吨以内"],
        "10吨": ["10吨", "10t", "10 ton", "10吨以下"],
        "large_scale": ["万吨", "千吨", "大批量", "规模化"]
    }
    
    # Penalize documents mentioning large quantities when asking for small
    if target_weight == "5吨" and any(pattern in doc_text for pattern in weight_patterns["large_scale"]):
        return -100
    
    # Boost documents with exact weight matches
    if any(pattern in doc_text for pattern in weight_patterns[target_weight]):
        return +100
```

### **5. 🗺️ GEOGRAPHIC CONTEXT AGENT**
**Purpose**: Filter by geographic relevance and jurisdiction

**Functions**:
- **Province Matching**: Exact province name matching
- **Jurisdiction Hierarchy**: National → Provincial → Municipal → County
- **Transport Routes**: Identify relevant transport corridors
- **Regional Variations**: Different regulations by region

**Example**: Guangdong coal transport vs Inner Mongolia coal transport

### **6. ⏰ TEMPORAL RELEVANCE AGENT**
**Purpose**: Prioritize current and relevant regulations

**Time-based Scoring**:
- **Current Year**: +100 points
- **Last 2 Years**: +80 points
- **Last 5 Years**: +50 points
- **Historical (>5 years)**: +20 points
- **Superseded**: -50 points

### **7. 🔍 CONTENT RELEVANCE AGENT**
**Purpose**: Deep content analysis for semantic relevance

**Analysis Methods**:
- **Keyword Density**: Frequency of relevant terms
- **Context Analysis**: Surrounding text relevance
- **Document Structure**: Headers, sections, appendices
- **Citation Networks**: Related regulations and references

---

## 🎯 **ENHANCED QUERY PROCESSING PIPELINE**

### **Phase 1: Query Understanding**
```
User Query → Query Analysis Agent → Structured Intent
```

### **Phase 2: Document Retrieval**
```
Structured Intent → Multiple Search Strategies → Candidate Documents
```

### **Phase 3: Multi-Agent Scoring**
```
Candidate Documents → [Classification + Transport + Weight + Geographic + Temporal + Content] Agents → Relevance Scores
```

### **Phase 4: Result Ranking**
```
Scored Documents → Weighted Ranking → Filtered Results
```

---

## 📊 **IMPROVED SCORING ALGORITHM**

### **Base Scoring Formula**:
```python
def calculate_relevance_score(document, query_intent):
    score = 0
    
    # Document classification bonus/penalty
    score += classification_agent.score(document)
    
    # Transportation relevance
    score += transport_agent.score(document, query_intent.transport_mode)
    
    # Weight matching
    score += weight_agent.score(document, query_intent.weight)
    
    # Geographic relevance
    score += geographic_agent.score(document, query_intent.region)
    
    # Temporal relevance
    score += temporal_agent.score(document)
    
    # Content relevance
    score += content_agent.score(document, query_intent)
    
    return score
```

### **Example Scoring**:
**Query**: "transportation for 5 tons of coal in Guangdong"

| Document Type | Classification | Transport | Weight | Geographic | Temporal | Content | **Total** |
|---------------|----------------|-----------|---------|------------|----------|---------|-----------|
| Transport Permit Guide | +100 | +80 | +60 | +50 | +80 | +70 | **440** |
| Coal Procurement Contract | -50 | -20 | -100 | +30 | +50 | -30 | **-120** |
| 5-ton Transport Regulation | +100 | +100 | +100 | +50 | +80 | +90 | **520** |

---

## 🚀 **IMPLEMENTATION ROADMAP**

### **Phase 1: Query Analysis Enhancement**
- Implement intent parsing
- Add entity extraction
- Create query classification

### **Phase 2: Document Classification**
- Build document type classifier
- Implement scoring system
- Add procurement penalty

### **Phase 3: Specialized Agents**
- Transport specialist
- Weight/volume filtering
- Geographic context

### **Phase 4: Integration & Testing**
- Combine all agents
- Optimize scoring weights
- A/B test improvements

---

## 📈 **EXPECTED IMPROVEMENTS**

### **Current System**:
- Returns procurement contracts for transport queries
- No weight-specific filtering
- Poor document type classification

### **Enhanced System**:
- ✅ Prioritizes regulatory documents
- ✅ Filters by weight/volume requirements
- ✅ Geographic context awareness
- ✅ Transport-specific relevance
- ✅ Temporal relevance scoring
- ✅ Procurement document penalties

### **Success Metrics**:
- **Relevance Score**: Target 80%+ relevant documents in top 3
- **False Positive Reduction**: 90% reduction in procurement contracts for regulatory queries
- **Precision**: 95%+ accuracy for weight-specific queries
- **User Satisfaction**: Measured through query success rate

---

**Next Steps**: Implement Query Analysis Agent and Document Classification Agent as priority improvements.
