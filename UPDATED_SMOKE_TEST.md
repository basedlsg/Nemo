# Updated Smoke Test Plan

This document outlines the updated smoke test plan, including a new test case for refusal scenarios.

## Test Cases

### Test 1: Successful query (Guangdong solar grid connection)
**Expected:** 200 response with verbatim bullets and citations

**cURL Command:**
```bash
curl -s -v -X POST "http://localhost:8000/api/v1/query" \
  -H 'Content-Type: application/json' \
  -d '{
    "province": "guangdong",
    "doc_class": "grid_connection",
    "asset": "solar",
    "question": "并网验收需要哪些资料？",
    "lang": "zh"
  }'
```

### Test 2: Shandong wind market rules
**Expected:** 200 response with market-related content

**cURL Command:**
```bash
curl -s -X POST "http://localhost:8000/api/v1/query" \
  -H 'Content-Type: application/json' \
  -d '{
    "province": "shandong", 
    "doc_class": "market_rules",
    "asset": "wind",
    "question": "风电场参与市场交易需要满足什么条件？",
    "lang": "zh"
  }'
```

### Test 3: Inner Mongolia BESS dispatch operations
**Expected:** 200 response with dispatch-related content

**cURL Command:**
```bash
curl -s -X POST "http://localhost:8000/api/v1/query" \
  -H 'Content-Type: application/json' \
  -d '{
    "province": "inner_mongolia",
    "doc_class": "dispatch_ops", 
    "asset": "bess",
    "question": "储能电站参与调度运行有什么要求？",
    "lang": "zh"
  }'
```

### Test 4: Refusal for unsupported province
**Expected:** 200 response with a refusal message

**cURL Command:**
```bash
curl -s -X POST "http://localhost:8000/api/v1/query" \
  -H 'Content-Type: application/json' \
  -d '{
    "province": "beijing",
    "doc_class": "market_rules",
    "asset": "solar",
    "question": "光伏项目并网需要哪些手续？",
    "lang": "zh"
  }'
```

### Test 6: Health check
**Expected:** 200 response with service status

**cURL Command:**
```bash
curl -s -X GET "http://localhost:8000/_health"
```

### Test 7: API info
**Expected:** 200 response with API details

**cURL Command:**
```bash
curl -s -X GET "http://localhost:8000/"