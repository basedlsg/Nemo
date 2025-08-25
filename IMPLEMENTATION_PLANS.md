# 🛠️ IMPLEMENTATION PLANS
## Priority Sub-Agent Development

---

## 🎯 **PRIORITY 1: QUERY ANALYSIS AGENT**

### **Current Problem**
System doesn't understand the difference between:
- "transportation regulations for 5 tons of coal" (regulatory query)
- "coal procurement contract" (procurement query)

### **Implementation Plan**

#### **Step 1: Intent Classification**
```python
class QueryIntentClassifier:
    def classify_intent(self, query: str) -> dict:
        intent_patterns = {
            "regulatory": [
                r"规定|办法|条例|通知|政策|法规",
                r"需要什么|如何|流程|手续|许可证",
                r"运输|运输证|运输许可"
            ],
            "procurement": [
                r"采购|招标|合同|投标|供应商",
                r"价格|成本|费用|预算",
                r"供应|交付|交货"
            ],
            "technical": [
                r"标准|规范|技术|参数|规格",
                r"质量|检测|检验|认证"
            ]
        }
        
        # Score each intent type
        scores = {}
        for intent, patterns in intent_patterns.items():
            score = sum(len(re.findall(pattern, query)) for pattern in patterns)
            scores[intent] = score
        
        return max(scores, key=scores.get)
```

#### **Step 2: Entity Extraction**
```python
class EntityExtractor:
    def extract_entities(self, query: str) -> dict:
        entities = {
            "commodity": self.extract_commodity(query),
            "weight": self.extract_weight(query),
            "transport_mode": self.extract_transport_mode(query),
            "region": self.extract_region(query),
            "document_type": self.extract_document_type(query)
        }
        return entities
    
    def extract_weight(self, query: str) -> str:
        weight_patterns = [
            r"(\d+)\s*吨",
            r"(\d+)\s*ton",
            r"(\d+)\s*t"
        ]
        for pattern in weight_patterns:
            match = re.search(pattern, query)
            if match:
                return f"{match.group(1)}吨"
        return None
```

#### **Step 3: Query Enhancement**
```python
def enhance_query(query: str, intent: dict) -> str:
    """Enhance query with relevant keywords based on intent"""
    
    base_query = query
    
    if intent["type"] == "regulatory":
        regulatory_keywords = [
            "规定", "办法", "条例", "通知", "政策",
            "许可证", "审批", "备案", "手续"
        ]
        base_query += " " + " ".join(regulatory_keywords[:3])
    
    if intent["weight"]:
        weight_keywords = [
            f"{intent['weight']}吨以下",
            f"{intent['weight']}吨以内",
            f"小型运输",
            f"轻型运输"
        ]
        base_query += " " + " ".join(weight_keywords[:2])
    
    return base_query
```

---

## 📋 **PRIORITY 2: DOCUMENT CLASSIFICATION AGENT**

### **Current Problem**
System treats all coal-related documents equally, regardless of whether they're:
- Regulatory documents (relevant)
- Procurement contracts (irrelevant for transport queries)
- Technical standards (partially relevant)

### **Implementation Plan**

#### **Step 1: Document Type Classifier**
```python
class DocumentClassifier:
    def __init__(self):
        self.classification_patterns = {
            "regulatory": {
                "keywords": ["规定", "办法", "条例", "通知", "政策", "法规"],
                "score": 100,
                "penalty": 0
            },
            "procurement": {
                "keywords": ["合同", "招标", "采购", "投标", "供应商", "价格"],
                "score": -50,  # Penalty for procurement docs
                "penalty": -50
            },
            "transport": {
                "keywords": ["运输", "物流", "配送", "运输证", "运输许可"],
                "score": 80,
                "penalty": 0
            },
            "technical": {
                "keywords": ["标准", "规范", "技术", "参数", "规格"],
                "score": 60,
                "penalty": 0
            },
            "permit": {
                "keywords": ["许可证", "审批", "备案", "手续", "证书"],
                "score": 90,
                "penalty": 0
            }
        }
    
    def classify_document(self, doc_text: str) -> dict:
        scores = {}
        for doc_type, config in self.classification_patterns.items():
            score = 0
            for keyword in config["keywords"]:
                count = doc_text.count(keyword)
                score += count * 10  # 10 points per occurrence
            
            scores[doc_type] = {
                "score": score + config["score"],
                "penalty": config["penalty"]
            }
        
        return scores
```

#### **Step 2: Content Relevance Scoring**
```python
def calculate_content_relevance(doc_text: str, query_intent: dict) -> float:
    """Calculate how relevant document content is to query intent"""
    
    relevance_score = 0
    
    # Boost for exact matches
    if query_intent.get("weight"):
        weight_pattern = query_intent["weight"]
        if weight_pattern in doc_text:
            relevance_score += 100
    
    # Boost for transport-related content
    transport_keywords = ["运输", "物流", "配送", "运输证"]
    transport_matches = sum(doc_text.count(kw) for kw in transport_keywords)
    relevance_score += transport_matches * 20
    
    # Penalty for large-scale procurement
    procurement_penalties = ["万吨", "千吨", "大批量", "规模化", "合同", "招标"]
    penalty_matches = sum(doc_text.count(kw) for kw in procurement_penalties)
    relevance_score -= penalty_matches * 30
    
    return relevance_score
```

---

## 🚛 **PRIORITY 3: TRANSPORTATION SPECIALIST AGENT**

### **Current Problem**
System doesn't distinguish between different transport scenarios:
- Small-scale transport (5 tons) vs large-scale (9000 tons)
- Different permit requirements by weight class
- Regional transport regulations

### **Implementation Plan**

#### **Step 1: Weight Classification System**
```python
class TransportWeightClassifier:
    def __init__(self):
        self.weight_classes = {
            "light": {
                "range": (0, 1),
                "keywords": ["轻型", "小型", "1吨以下", "1吨以内"],
                "permits": ["普通运输证"],
                "score": 100
            },
            "medium": {
                "range": (1, 10),
                "keywords": ["中型", "5吨", "10吨以下", "10吨以内"],
                "permits": ["道路运输证", "普通运输证"],
                "score": 80
            },
            "heavy": {
                "range": (10, 50),
                "keywords": ["重型", "大型", "20吨", "50吨以下"],
                "permits": ["道路运输证", "超限运输许可证"],
                "score": 60
            },
            "super_heavy": {
                "range": (50, float('inf')),
                "keywords": ["超重型", "超限", "万吨", "千吨"],
                "permits": ["超限运输许可证", "特殊运输许可"],
                "score": -50  # Penalty for large-scale when asking for small
            }
        }
    
    def classify_weight(self, weight_str: str) -> str:
        """Classify weight into transport categories"""
        weight_value = self.extract_weight_value(weight_str)
        
        for class_name, config in self.weight_classes.items():
            if config["range"][0] <= weight_value < config["range"][1]:
                return class_name
        
        return "unknown"
    
    def get_relevant_permits(self, weight_class: str) -> list:
        """Get relevant permits for weight class"""
        return self.weight_classes.get(weight_class, {}).get("permits", [])
```

#### **Step 2: Transport Mode Detection**
```python
class TransportModeDetector:
    def __init__(self):
        self.transport_modes = {
            "road": {
                "keywords": ["公路", "道路", "卡车", "货车", "汽车"],
                "score": 100
            },
            "rail": {
                "keywords": ["铁路", "火车", "货运列车"],
                "score": 80
            },
            "water": {
                "keywords": ["水路", "船舶", "港口", "码头"],
                "score": 80
            },
            "intermodal": {
                "keywords": ["多式联运", "综合运输"],
                "score": 90
            }
        }
    
    def detect_transport_mode(self, doc_text: str) -> dict:
        scores = {}
        for mode, config in self.transport_modes.items():
            score = 0
            for keyword in config["keywords"]:
                count = doc_text.count(keyword)
                score += count * 20
            scores[mode] = score + config["score"]
        
        return scores
```

---

## 📊 **PRIORITY 4: WEIGHT & VOLUME FILTERING AGENT**

### **Current Problem**
System returned a 9000-ton procurement contract when user asked about 5-ton transport.

### **Implementation Plan**

#### **Step 1: Weight Pattern Matching**
```python
class WeightFilter:
    def __init__(self):
        self.weight_patterns = {
            "small_scale": [
                r"(\d+)\s*吨以下",
                r"(\d+)\s*吨以内", 
                r"(\d+)\s*吨以下",
                r"小型|轻型|少量"
            ],
            "medium_scale": [
                r"(\d+)\s*吨",
                r"(\d+)\s*ton",
                r"中型|中等"
            ],
            "large_scale": [
                r"(\d+)\s*万吨",
                r"(\d+)\s*千吨",
                r"大批量|规模化|大量"
            ]
        }
    
    def analyze_weight_context(self, doc_text: str, target_weight: str) -> float:
        """Analyze if document weight context matches target weight"""
        
        target_value = self.extract_weight_value(target_weight)
        score = 0
        
        # Check for exact matches
        if target_weight in doc_text:
            score += 100
        
        # Check for appropriate scale
        if target_value <= 10:  # Small scale
            small_matches = sum(len(re.findall(pattern, doc_text)) 
                              for pattern in self.weight_patterns["small_scale"])
            score += small_matches * 50
            
            # Penalty for large scale mentions
            large_matches = sum(len(re.findall(pattern, doc_text)) 
                              for pattern in self.weight_patterns["large_scale"])
            score -= large_matches * 100
        
        return score
```

#### **Step 2: Volume Context Analysis**
```python
def analyze_volume_context(doc_text: str, target_volume: str) -> dict:
    """Analyze volume context and relevance"""
    
    context_indicators = {
        "individual": ["个人", "小型", "少量", "零售"],
        "commercial": ["商业", "企业", "公司", "批量"],
        "industrial": ["工业", "大规模", "工厂", "生产"],
        "procurement": ["采购", "招标", "合同", "供应商"]
    }
    
    context_scores = {}
    for context, keywords in context_indicators.items():
        score = sum(doc_text.count(kw) * 10 for kw in keywords)
        context_scores[context] = score
    
    return context_scores
```

---

## 🎯 **INTEGRATION STRATEGY**

### **Phase 1: Quick Wins (Week 1)**
1. Implement basic query intent classification
2. Add procurement document penalties
3. Implement weight pattern matching

### **Phase 2: Core Enhancement (Week 2)**
1. Build document classification system
2. Implement transport specialist agent
3. Add geographic context filtering

### **Phase 3: Advanced Features (Week 3)**
1. Temporal relevance scoring
2. Content relevance analysis
3. Multi-agent scoring integration

### **Phase 4: Testing & Optimization (Week 4)**
1. A/B testing with current system
2. Performance optimization
3. User feedback integration

---

## 📈 **SUCCESS METRICS**

### **Immediate Goals (Week 1)**
- 70% reduction in procurement contracts for regulatory queries
- 80% accuracy in weight-specific filtering
- 60% improvement in transport-related document relevance

### **Medium-term Goals (Month 1)**
- 90% reduction in false positives
- 85% precision for regulatory queries
- 75% user satisfaction improvement

### **Long-term Goals (Month 3)**
- 95% precision across all query types
- 90% user satisfaction
- Sub-2-second response times

---

**Next Action**: Start with Query Analysis Agent implementation as it provides the foundation for all other improvements.
