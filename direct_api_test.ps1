# Direct API Test with Hardcoded Keys
# Real API calls using the actual keys from env.yaml

# API Keys from env.yaml
$PPLX_API_KEY = "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"
$GOOGLE_API_KEY = "AIzaSyAM6Ko33ubRd_d8tkr6b4rocOqRXgyAy0Q"
$GOOGLE_CSE_ID = "c2902a74ad3664d41"

Write-Host "DIRECT API TEST - Real API Calls"
Write-Host "=================================="
Write-Host "Test Date: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
Write-Host ""

# Test 1: Google Custom Search API
Write-Host "TEST 1: Google Custom Search API"
Write-Host "Query: Guangdong photovoltaic capacity 2023"
Write-Host "-----------------------------------"

try {
    $params = @{
        key = $GOOGLE_API_KEY
        cx = $GOOGLE_CSE_ID
        q = "Guangdong photovoltaic capacity 2023"
        num = 3
        lr = "lang_zh"
    }

    Write-Host "Making Google API call..."
    $response = Invoke-RestMethod -Uri "https://www.googleapis.com/customsearch/v1" -Method Get -Body $params -TimeoutSec 20

    Write-Host "SUCCESS: Google API Response"
    Write-Host "Total Results: $($response.searchInformation.totalResults)"
    Write-Host "Search Time: $($response.searchInformation.searchTime)s"
    Write-Host ""

    if ($response.items) {
        Write-Host "TOP 3 RESULTS:"
        for ($i = 0; $i -lt [Math]::Min(3, $response.items.Count); $i++) {
            $item = $response.items[$i]
            Write-Host "[$($i+1)] $($item.title)"
            Write-Host "    URL: $($item.link)"
            if ($item.snippet) {
                $snippet = $item.snippet
                if ($snippet.Length -gt 100) {
                    $snippet = $snippet.Substring(0, 100) + "..."
                }
                Write-Host "    Snippet: $snippet"
            }
            Write-Host ""
        }
    } else {
        Write-Host "No results found"
    }

} catch {
    Write-Host "ERROR: $($_.Exception.Message)"
    if ($_.Exception.Response) {
        $statusCode = $_.Exception.Response.StatusCode.value__
        Write-Host "HTTP Status Code: $statusCode"
    }
}

Write-Host ""
Write-Host "TEST 2: Perplexity API"
Write-Host "Query: Chinese government energy policy documents"
Write-Host "-----------------------------------"

try {
    $headers = @{
        "Authorization" = "Bearer $PPLX_API_KEY"
        "Content-Type" = "application/json"
    }

    $prompt = "Find Chinese government websites (.gov.cn) about Guangdong photovoltaic energy policy and capacity limits"
    $payload = @{
        model = "sonar-pro"
        messages = @(@{role = "user"; content = $prompt})
        max_tokens = 500
        temperature = 0.1
    }

    Write-Host "Making Perplexity API call..."
    $response = Invoke-RestMethod -Uri "https://api.perplexity.ai/chat/completions" -Method Post -Headers $headers -Body ($payload | ConvertTo-Json) -TimeoutSec 30

    Write-Host "SUCCESS: Perplexity API Response"
    $content = $response.choices[0].message.content
    Write-Host "Response Length: $($content.Length) characters"
    Write-Host ""

    # Extract URLs from response
    $urlPattern = 'https?://[^\s\]]+'
    $urls = [regex]::Matches($content, $urlPattern) | ForEach-Object { $_.Value } | Where-Object { $_ -match '\.gov\.cn' }

    Write-Host "Government URLs Found: $($urls.Count)"
    foreach ($url in ($urls | Select-Object -First 5)) {
        Write-Host "  - $url"
    }

    Write-Host ""
    Write-Host "RESPONSE PREVIEW (first 300 chars):"
    $preview = $content.Substring(0, [Math]::Min(300, $content.Length))
    Write-Host "$preview"

} catch {
    Write-Host "ERROR: $($_.Exception.Message)"
    if ($_.Exception.Response) {
        $statusCode = $_.Exception.Response.StatusCode.value__
        Write-Host "HTTP Status Code: $statusCode"
    }
}

Write-Host ""
Write-Host "=================================="
Write-Host "DIRECT API TEST COMPLETE"
Write-Host "This demonstrates real API calls to:"
Write-Host "  - Google Custom Search Engine"
Write-Host "  - Perplexity AI"
Write-Host "Results are from actual search engines, not mock data"
Write-Host "=================================="
