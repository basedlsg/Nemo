# UI Connection Diagnostic Script
param(
    [string]$UiUrl = "https://gaea-ui-964505076225.us-central1.run.app"
)

Write-Host "Diagnosing UI Connection Issues" -ForegroundColor Green
Write-Host "UI URL: $UiUrl" -ForegroundColor Cyan
Write-Host ""

# Test 1: UI Main Page
Write-Host "1. Testing UI Main Page..." -ForegroundColor Yellow
try {
    $response = Invoke-WebRequest -Uri $UiUrl -Method GET
    Write-Host "   OK UI Status: $($response.StatusCode)" -ForegroundColor Green
    Write-Host "   Content Length: $($response.RawContentLength) bytes" -ForegroundColor Gray
} catch {
    Write-Host "   FAIL UI Failed: $($_.Exception.Message)" -ForegroundColor Red
}

# Test 2: Health Check via UI Rewrite
Write-Host "2. Testing Health Check via UI Rewrite..." -ForegroundColor Yellow
try {
    $health = Invoke-RestMethod -Uri "$UiUrl/api/v1/health" -Method GET
    Write-Host "   OK Health via UI: $($health.status)" -ForegroundColor Green
    Write-Host "   Services: $($health.services.Keys -join ', ')" -ForegroundColor Gray
} catch {
    Write-Host "   FAIL Health via UI Failed: $($_.Exception.Message)" -ForegroundColor Red
}

# Test 3: Direct Gateway Health
Write-Host "3. Testing Direct Gateway Health..." -ForegroundColor Yellow
try {
    $directHealth = Invoke-RestMethod -Uri "https://gaea-gateway-964505076225.us-central1.run.app/health" -Method GET
    Write-Host "   OK Direct Gateway: $($directHealth.status)" -ForegroundColor Green
} catch {
    Write-Host "   FAIL Direct Gateway Failed: $($_.Exception.Message)" -ForegroundColor Red
}

# Test 4: Query via UI Rewrite
Write-Host "4. Testing Query via UI Rewrite..." -ForegroundColor Yellow
try {
    $body = '{"province":"guangdong","doc_class":"grid_connection","asset":"solar","question":"test","lang":"zh-CN"}'
    $queryResponse = Invoke-RestMethod -Uri "$UiUrl/api/v1/query" -Method POST -Body $body -ContentType "application/json"
    Write-Host "   OK Query via UI: Success" -ForegroundColor Green
    Write-Host "   Citations: $($queryResponse.total_citations)" -ForegroundColor Gray
    Write-Host "   Trace ID: $($queryResponse.trace_id)" -ForegroundColor Gray
} catch {
    Write-Host "   FAIL Query via UI Failed: $($_.Exception.Message)" -ForegroundColor Red
}

Write-Host ""
Write-Host "Diagnosis Complete!" -ForegroundColor Green
Write-Host ""
Write-Host "If health check via UI fails but direct gateway works:" -ForegroundColor Cyan
Write-Host "   - The Next.js rewrite configuration may need time to propagate" -ForegroundColor Gray
Write-Host "   - Try refreshing the browser page" -ForegroundColor Gray
Write-Host "   - Check browser developer console for errors" -ForegroundColor Gray
Write-Host ""
Write-Host "UI URL: $UiUrl" -ForegroundColor White
Write-Host "Direct Gateway: https://gaea-gateway-964505076225.us-central1.run.app" -ForegroundColor White