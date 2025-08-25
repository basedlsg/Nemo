# Perplexity API Test
# Test the Perplexity AI API for Chinese government documents

$PPLX_API_KEY = "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"

Write-Host "PERPLEXITY API TEST"
Write-Host "==================="
Write-Host "Test Date: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
Write-Host ""

try {
    $headers = @{
        "Authorization" = "Bearer $PPLX_API_KEY"
        "Content-Type" = "application/json"
    }

    $prompt = "Find Chinese government documents (.gov.cn domains only) about Guangdong province 2023 distributed photovoltaic capacity limits. Return only official government URLs and their titles."
    $payload = @{
        model = "sonar-pro"
        messages = @(@{role = "user"; content = $prompt})
        max_tokens = 600
        temperature = 0.1
    }

    Write-Host "Query: Chinese government documents about Guangdong PV capacity 2023"
    Write-Host "Making Perplexity API call..."
    Write-Host ""

    $response = Invoke-RestMethod -Uri "https://api.perplexity.ai/chat/completions" -Method Post -Headers $headers -Body ($payload | ConvertTo-Json) -TimeoutSec 30

    $content = $response.choices[0].message.content
    Write-Host "RESPONSE RECEIVED:"
    Write-Host "=================="
    Write-Host $content
    Write-Host ""
    Write-Host "=================="
    Write-Host "Response Length: $($content.Length) characters"

    # Extract government URLs
    $govUrls = [regex]::Matches($content, 'https?://[^\s\]]*\.gov\.cn[^\s\]]*') | ForEach-Object { $_.Value }
    Write-Host "Government URLs found: $($govUrls.Count)"

    foreach ($url in $govUrls) {
        Write-Host "  - $url"
    }

} catch {
    Write-Host "ERROR: $($_.Exception.Message)"
    if ($_.Exception.Response) {
        $statusCode = $_.Exception.Response.StatusCode.value__
        Write-Host "HTTP Status Code: $statusCode"
    }
}

Write-Host ""
Write-Host "PERPLEXITY TEST COMPLETE"
