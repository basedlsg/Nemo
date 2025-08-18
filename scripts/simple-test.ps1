# Simple GAEA Testing Script
param(
    [string]$GatewayUrl = "https://gaea-gateway-964505076225.us-central1.run.app",
    [string]$UiUrl = "https://gaea-ui-964505076225.us-central1.run.app"
)

Write-Host "Testing GAEA Energy Assistant" -ForegroundColor Green
Write-Host "Gateway: $GatewayUrl" -ForegroundColor Cyan
Write-Host "UI: $UiUrl" -ForegroundColor Cyan
Write-Host ""

# Test 1: Health Check
Write-Host "1. Testing Health Check..." -ForegroundColor Yellow
try {
    $health = Invoke-RestMethod -Uri "$GatewayUrl/health" -Method GET
    Write-Host "   Status: $($health.status)" -ForegroundColor Green
} catch {
    Write-Host "   Failed: $($_.Exception.Message)" -ForegroundColor Red
}

# Test 2: Service Statistics
Write-Host "2. Testing Service Statistics..." -ForegroundColor Yellow
try {
    $stats = Invoke-RestMethod -Uri "$GatewayUrl/stats" -Method GET
    Write-Host "   Total Queries: $($stats.total_queries)" -ForegroundColor Green
    Write-Host "   Success Rate: $([math]::Round((1 - $stats.refusal_rate) * 100, 2))%" -ForegroundColor Green
} catch {
    Write-Host "   Failed: $($_.Exception.Message)" -ForegroundColor Red
}

# Test 3: Simple Query
Write-Host "3. Testing Simple Query..." -ForegroundColor Yellow
try {
    $body = '{"province":"guangdong","doc_class":"grid_connection","asset":"solar","question":"test query","lang":"zh-CN"}'
    $response = Invoke-RestMethod -Uri "$GatewayUrl/query" -Method POST -Body $body -ContentType "application/json"
    Write-Host "   Query successful!" -ForegroundColor Green
    Write-Host "   Citations: $($response.total_citations)" -ForegroundColor Green
    Write-Host "   Processing Time: $($response.processing_time_ms)ms" -ForegroundColor Green
} catch {
    Write-Host "   Failed: $($_.Exception.Message)" -ForegroundColor Red
}

# Test 4: UI Check
Write-Host "4. Testing UI Accessibility..." -ForegroundColor Yellow
try {
    $uiResponse = Invoke-WebRequest -Uri $UiUrl -Method GET
    Write-Host "   UI Status: $($uiResponse.StatusCode)" -ForegroundColor Green
    Write-Host "   Content Length: $($uiResponse.RawContentLength) bytes" -ForegroundColor Green
} catch {
    Write-Host "   Failed: $($_.Exception.Message)" -ForegroundColor Red
}

Write-Host ""
Write-Host "Testing Complete!" -ForegroundColor Green
Write-Host "Gateway URL: $GatewayUrl" -ForegroundColor White
Write-Host "UI URL: $UiUrl" -ForegroundColor White