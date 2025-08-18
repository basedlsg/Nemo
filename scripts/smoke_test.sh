#!/bin/bash

# Smoke test script for Geo-Adaptive Energy Assistant
# Tests the complete pipeline: API Gateway -> Query Processing -> Response

set -e

API_URL="${API_GATEWAY_URL:-http://localhost:8000}"
echo "Testing API at: $API_URL"

echo "=== Smoke Test: Geo-Adaptive Energy Assistant ==="

# Test 1: Successful query (Guangdong solar grid connection)
echo ""
echo "Test 1: Guangdong Solar Grid Connection Query"
echo "Expected: 200 response with verbatim bullets and citations"

curl -s -X POST "$API_URL/api/v1/query" \
  -H 'Content-Type: application/json' \
  -d '{
    "province": "guangdong",
    "doc_class": "grid_connection",
    "asset": "solar",
    "question": "并网验收需要哪些资料？",
    "lang": "zh"
  }' | jq '.'

echo ""
echo "----------------------------------------"

# Test 2: Shandong wind market rules
echo ""
echo "Test 2: Shandong Wind Market Rules Query"
echo "Expected: 200 response with market-related content"

curl -s -X POST "$API_URL/api/v1/query" \
  -H 'Content-Type: application/json' \
  -d '{
    "province": "shandong", 
    "doc_class": "market_rules",
    "asset": "wind",
    "question": "风电场参与市场交易需要满足什么条件？",
    "lang": "zh"
  }' | jq '.'

echo ""
echo "----------------------------------------"

# Test 3: Inner Mongolia BESS dispatch operations
echo ""
echo "Test 3: Inner Mongolia BESS Dispatch Operations"
echo "Expected: 200 response with dispatch-related content"

curl -s -X POST "$API_URL/api/v1/query" \
  -H 'Content-Type: application/json' \
  -d '{
    "province": "inner_mongolia",
    "doc_class": "dispatch_ops", 
    "asset": "bess",
    "question": "储能电站参与调度运行有什么要求？",
    "lang": "zh"
  }' | jq '.'

echo ""
echo "----------------------------------------"

# Test 4: Force refusal (asking for personal recommendations)
echo ""
echo "Test 4: Force Refusal - Personal Recommendations"
echo "Expected: 422 response with refusal code and policy information"

curl -s -X POST "$API_URL/api/v1/query" \
  -H 'Content-Type: application/json' \
  -d '{
    "province": "guangdong",
    "doc_class": "grid_connection",
    "asset": "solar", 
    "question": "给出所有并网流程的你自己的建议和意见",
    "lang": "zh"
  }' | jq '.'

echo ""
echo "----------------------------------------"

# Test 5: Force refusal (vague query)
echo ""
echo "Test 5: Force Refusal - Vague Query"
echo "Expected: 422 response with query_too_vague refusal"

curl -s -X POST "$API_URL/api/v1/query" \
  -H 'Content-Type: application/json' \
  -d '{
    "province": "guangdong",
    "doc_class": "grid_connection",
    "question": "怎么办？",
    "lang": "zh"
  }' | jq '.'

echo ""
echo "----------------------------------------"

# Test 6: Health check
echo ""
echo "Test 6: Health Check"
echo "Expected: 200 response with service status"

curl -s -X GET "$API_URL/health" | jq '.'

echo ""
echo "----------------------------------------"

# Test 7: API info
echo ""
echo "Test 7: API Information"
echo "Expected: 200 response with API details"

curl -s -X GET "$API_URL/" | jq '.'

echo ""
echo "=== Smoke Test Complete ==="
echo ""
echo "Expected Results Summary:"
echo "- Tests 1-3: Should return 200 with Chinese answers and citations"
echo "- Tests 4-5: Should return 422 with structured refusal responses"
echo "- Test 6: Should return 200 with healthy service status"
echo "- Test 7: Should return 200 with API information"
echo ""
echo "All responses should include:"
echo "- Proper Chinese text encoding"
echo "- Trace IDs for request tracking"
echo "- Processing time metrics"
echo "- Structured error codes for refusals"