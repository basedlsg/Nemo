# Simple Real API Call Test
# Basic demonstration of calling real APIs

# Load environment variables
$envFile = "env.yaml"
$envVars = @{}

if (Test-Path $envFile) {
    Get-Content $envFile | ForEach-Object {
        $line = $_.Trim()
        if ($line -and $line -notmatch '^#' -and $line.Contains('=')) {
            $parts = $line.Split('=', 2)
            $key = $parts[0].Trim()
            $value = $parts[1].Trim().Trim('"')
            $envVars[$key] = $value
        }
    }
}

# API Configuration
$PPLX_API_KEY = $envVars['PPLX_API_KEY']
$GOOGLE_API_KEY = $envVars['GOOGLE_API_KEY']
$GOOGLE_CSE_ID = $envVars['GOOGLE_CSE_ID']

Write-Host "🔬 Simple Real API Call Test"
Write-Host ("=" * 50)
Write-Host "Test Date: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
Write-Host ("=" * 50)

Write-Host "API Keys Available:"
Write-Host "  Perplexity: $(if ($PPLX_API_KEY) {'✅'} else {'❌'})"
Write-Host "  Google CSE: $(if ($GOOGLE_API_KEY -and $GOOGLE_CSE_ID) {'✅'} else {'❌'})"
Write-Host ""

# Test 1: Simple Google Search
Write-Host "📋 Test 1: Google Custom Search API"
Write-Host ("-" * 30)

$query = "Guangdong distributed photovoltaic capacity 2023"
Write-Host "🔍 Query: $query"

if ($GOOGLE_API_KEY -and $GOOGLE_CSE_ID) {
    try {
        $params = @{
            key = $GOOGLE_API_KEY
            cx = $GOOGLE_CSE_ID
            q = $query
            num = 3
            lr = "lang_zh"
            safe = "off"
        }

        Write-Host "🌐 Calling Google CSE API..."
        $response = Invoke-RestMethod -Uri "https://www.googleapis.com/customsearch/v1" -Method Get -Body $params -TimeoutSec 20

        Write-Host "✅ Google CSE API Response:"
        Write-Host "   Total Results: $($response.searchInformation.totalResults)"
        Write-Host "   Search Time: $($response.searchInformation.searchTime)s"

        if ($response.items) {
            Write-Host "   Results Found: $($response.items.Count)"
            for ($i = 0; $i -lt [Math]::Min(3, $response.items.Count); $i++) {
                $item = $response.items[$i]
                Write-Host "   [$($i+1)] $($item.title)"
                Write-Host "       URL: $($item.link)"
                if ($item.snippet) {
                    Write-Host "       Snippet: $($item.snippet.Substring(0, [Math]::Min(100, $item.snippet.Length)))..."
                }
                Write-Host ""
            }
        } else {
            Write-Host "   No results found"
        }

    } catch {
        Write-Host "❌ Google CSE API Error: $($_.Exception.Message)"
    }
} else {
    Write-Host "❌ Google API credentials not available"
}

Write-Host ""

# Test 2: Simple Perplexity Search
Write-Host "📋 Test 2: Perplexity API"
Write-Host ("-" * 30)

if ($PPLX_API_KEY) {
    try {
        $headers = @{
            "Authorization" = "Bearer $PPLX_API_KEY"
            "Content-Type" = "application/json"
        }

        $prompt = "Find Chinese government websites about Guangdong photovoltaic energy policy"
        $payload = @{
            model = "sonar-pro"
            messages = @(@{role = "user"; content = $prompt})
            max_tokens = 500
            temperature = 0.1
        }

        Write-Host "🌐 Calling Perplexity API..."
        $response = Invoke-RestMethod -Uri "https://api.perplexity.ai/chat/completions" -Method Post -Headers $headers -Body ($payload | ConvertTo-Json) -TimeoutSec 30

        Write-Host "✅ Perplexity API Response:"
        $content = $response.choices[0].message.content
        Write-Host "   Response Length: $($content.Length) characters"

        # Extract URLs from response
        $urlPattern = 'https?://[^\s]+'
        $urls = [regex]::Matches($content, $urlPattern) | ForEach-Object { $_.Value }

        Write-Host "   URLs Found: $($urls.Count)"
        foreach ($url in ($urls | Select-Object -First 3)) {
            Write-Host "   - $url"
        }

        Write-Host "   First 200 chars of response:"
        Write-Host "   $($content.Substring(0, [Math]::Min(200, $content.Length)))..."

    } catch {
        Write-Host "❌ Perplexity API Error: $($_.Exception.Message)"
    }
} else {
    Write-Host "❌ Perplexity API key not available"
}

Write-Host ""
Write-Host ("=" * 50)
Write-Host "🎯 Test Complete!"
Write-Host "This demonstrates real API calls to external search services"
Write-Host "Results are based on actual search engine responses, not mock data"
