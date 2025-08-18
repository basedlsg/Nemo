# Smoke test script for Geo-Adaptive Energy Assistant (PowerShell)
# Tests the complete pipeline: API Gateway -> Query Processing -> Response

param(
    [string]$ApiUrl = "http://localhost:8000"
)

Write-Host "=== Smoke Test: Geo-Adaptive Energy Assistant ===" -ForegroundColor Green
Write-Host "Testing API at: $ApiUrl" -ForegroundColor Yellow

function Invoke-ApiTest {
    param(
        [string]$TestName,
        [string]$Method = "POST",
        [string]$Endpoint,
        [hashtable]$Body = $null,
        [string]$ExpectedResult
    )
    
    Write-Host ""
    Write-Host "Test: $TestName" -ForegroundColor Cyan
    Write-Host "Expected: $ExpectedResult" -ForegroundColor Gray
    
    try {
        $headers = @{
            "Content-Type" = "application/json"
        }
        
        $params = @{
            Uri = "$ApiUrl$Endpoint"
            Method = $Method
            Headers = $headers
        }
        
        if ($Body) {
            $params.Body = ($Body | ConvertTo-Json -Depth 10)
        }
        
        $response = Invoke-RestMethod @params
        $response | ConvertTo-Json -Depth 10 | Write-Host
        
        Write-Host "✅ Test passed" -ForegroundColor Green
    }
    catch {
        Write-Host "❌ Test failed: $($_.Exception.Message)" -ForegroundColor Red
        if ($_.Exception.Response) {
            $statusCode = $_.Exception.Response.StatusCode
            Write-Host "Status Code: $statusCode" -ForegroundColor Red
        }
    }
    
    Write-Host "----------------------------------------" -ForegroundColor Gray
}

# Test 1: Successful query (Guangdong solar grid connection)
Invoke-ApiTest -TestName "Guangdong Solar Grid Connection Query" -Endpoint "/api/v1/query" -Body @{
    province = "guangdong"
    doc_class = "grid_connection"
    asset = "solar"
    question = "并网验收需要哪些资料？"
    lang = "zh"
} -ExpectedResult "200 response with verbatim bullets and citations"

# Test 2: Shandong wind market rules
Invoke-ApiTest -TestName "Shandong Wind Market Rules Query" -Endpoint "/api/v1/query" -Body @{
    province = "shandong"
    doc_class = "market_rules"
    asset = "wind"
    question = "风电场参与市场交易需要满足什么条件？"
    lang = "zh"
} -ExpectedResult "200 response with market-related content"

# Test 3: Inner Mongolia BESS dispatch operations
Invoke-ApiTest -TestName "Inner Mongolia BESS Dispatch Operations" -Endpoint "/api/v1/query" -Body @{
    province = "inner_mongolia"
    doc_class = "dispatch_ops"
    asset = "bess"
    question = "储能电站参与调度运行有什么要求？"
    lang = "zh"
} -ExpectedResult "200 response with dispatch-related content"

# Test 4: Force refusal (asking for personal recommendations)
Invoke-ApiTest -TestName "Force Refusal - Personal Recommendations" -Endpoint "/api/v1/query" -Body @{
    province = "guangdong"
    doc_class = "grid_connection"
    asset = "solar"
    question = "给出所有并网流程的你自己的建议和意见"
    lang = "zh"
} -ExpectedResult "422 response with refusal code and policy information"

# Test 5: Force refusal (vague query)
Invoke-ApiTest -TestName "Force Refusal - Vague Query" -Endpoint "/api/v1/query" -Body @{
    province = "guangdong"
    doc_class = "grid_connection"
    question = "怎么办？"
    lang = "zh"
} -ExpectedResult "422 response with query_too_vague refusal"

# Test 6: Health check
Invoke-ApiTest -TestName "Health Check" -Method "GET" -Endpoint "/health" -ExpectedResult "200 response with service status"

# Test 7: API info
Invoke-ApiTest -TestName "API Information" -Method "GET" -Endpoint "/" -ExpectedResult "200 response with API details"

Write-Host ""
Write-Host "=== Smoke Test Complete ===" -ForegroundColor Green
Write-Host ""
Write-Host "Expected Results Summary:" -ForegroundColor Yellow
Write-Host "- Tests 1-3: Should return 200 with Chinese answers and citations"
Write-Host "- Tests 4-5: Should return 422 with structured refusal responses"
Write-Host "- Test 6: Should return 200 with healthy service status"
Write-Host "- Test 7: Should return 200 with API information"
Write-Host ""
Write-Host "All responses should include:" -ForegroundColor Yellow
Write-Host "- Proper Chinese text encoding"
Write-Host "- Trace IDs for request tracking"
Write-Host "- Processing time metrics"
Write-Host "- Structured error codes for refusals"