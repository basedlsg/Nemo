# Basic API Demo - Real API Calls
# Simple demonstration without complex formatting

# Load API keys from env.yaml
$envFile = "env.yaml"
$PPLX_API_KEY = ""
$GOOGLE_API_KEY = ""
$GOOGLE_CSE_ID = ""

if (Test-Path $envFile) {
    Get-Content $envFile | ForEach-Object {
        $line = $_.Trim()
        if ($line -and $line -notmatch '^#' -and $line.Contains('=')) {
            $parts = $line.Split('=', 2)
            $key = $parts[0].Trim()
            $value = $parts[1].Trim().Trim('"')
            if ($key -eq 'PPLX_API_KEY') { $PPLX_API_KEY = $value }
            if ($key -eq 'GOOGLE_API_KEY') { $GOOGLE_API_KEY = $value }
            if ($key -eq 'GOOGLE_CSE_ID') { $GOOGLE_CSE_ID = $value }
        }
    }
}

Write-Host "BASIC API DEMO - Real API Calls"
Write-Host "================================="

# Test 1: Google Search
Write-Host "Test 1: Google Custom Search"
Write-Host "Query: Guangdong photovoltaic capacity"

if ($GOOGLE_API_KEY -and $GOOGLE_CSE_ID) {
    try {
        $params = @{
            key = $GOOGLE_API_KEY
            cx = $GOOGLE_CSE_ID
            q = "Guangdong photovoltaic capacity 2023"
            num = 2
        }

        Write-Host "Making Google API call..."
        $response = Invoke-RestMethod -Uri "https://www.googleapis.com/customsearch/v1" -Method Get -Body $params

        Write-Host "SUCCESS: Google API responded"
        Write-Host "Total results found: $($response.searchInformation.totalResults)"

        if ($response.items) {
            Write-Host "First result title: $($response.items[0].title)"
            Write-Host "First result URL: $($response.items[0].link)"
        }

    } catch {
        Write-Host "ERROR: $($_.Exception.Message)"
    }
} else {
    Write-Host "Google API credentials not available"
}

Write-Host ""

# Test 2: Perplexity Search
Write-Host "Test 2: Perplexity API"
Write-Host "Query: Chinese government energy policy"

if ($PPLX_API_KEY) {
    try {
        $headers = @{
            "Authorization" = "Bearer $PPLX_API_KEY"
            "Content-Type" = "application/json"
        }

        $payload = @{
            model = "sonar-pro"
            messages = @(@{role = "user"; content = "Find Chinese government energy policy documents"})
            max_tokens = 300
            temperature = 0.1
        }

        Write-Host "Making Perplexity API call..."
        $response = Invoke-RestMethod -Uri "https://api.perplexity.ai/chat/completions" -Method Post -Headers $headers -Body ($payload | ConvertTo-Json)

        Write-Host "SUCCESS: Perplexity API responded"
        $content = $response.choices[0].message.content
        Write-Host "Response length: $($content.Length) characters"
        Write-Host "First 100 characters: $($content.Substring(0, [Math]::Min(100, $content.Length)))"

    } catch {
        Write-Host "ERROR: $($_.Exception.Message)"
    }
} else {
    Write-Host "Perplexity API key not available"
}

Write-Host ""
Write-Host "DEMO COMPLETE"
Write-Host "This shows real API calls to external search services"
Write-Host "Results are from actual search engines, not mock data"
