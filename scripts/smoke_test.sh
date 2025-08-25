#!/bin/bash

# Smoke test script for Geo-Adaptive Energy Assistant
# Tests the complete pipeline: API Gateway -> Query Processing -> Response

set -ex


API_URL="${API_GATEWAY_URL:-http://localhost:8000}"
echo "Testing API at: $API_URL"

echo "=== Smoke Test: Geo-Adaptive Energy Assistant ==="

# Test 1: Successful query (Guangdong solar grid connection)
echo ""
echo "Test 1: Guangdong Solar Grid Connection Query"
echo "Expected: 200 response with verbatim bullets and citations"

curl -s -v -X POST "$API_URL/api/v1/query" \
  -H 'Content-Type: application/json' \
  -d '{
    "province": "guangdong",
    "doc_class": "grid_connection",
    "asset": "solar",
    "question": "并网验收需要哪些资料？",
    "lang": "zh-CN"
  }'

echo ""
echo "----------------------------------------"

echo ""
echo "=== Smoke Test Complete ==="
echo ""