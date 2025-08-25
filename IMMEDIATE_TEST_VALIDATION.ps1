# Immediate Test Validation: Five Razor-Sharp Prompts
# This script runs validation tests using mock responses
# Execute this to see the validation logic in action

Write-Host "Immediate Validation Test: Five Razor-Sharp Prompts" -ForegroundColor Green
Write-Host ("=" * 60) -ForegroundColor Green
Write-Host "Test Date: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor Cyan
Write-Host "Status: VALIDATION LOGIC DEMONSTRATION" -ForegroundColor Yellow
Write-Host ""

# Mock API responses that demonstrate the expected format
$mockResponses = @(
    # Test 1: Guangdong 2023 Distributed PV Cap
    @{
        TestName = "Guangdong 2023 Distributed PV Cap"
        MockResponse = @{
            answer_zh = "6000 MW"
            citations = @(
                @{
                    title = "Notice on Issuing Guangdong Province 2023 Distributed PV Capacity Limit"
                    effective_date = "2023-01-15"
                    wenhao = "Yue Neng Gui [2023] 001"
                    agency = "Guangdong Energy Bureau"
                    url = "http://gddoe.gov.cn/notice/2023/001.pdf"
                }
            )
            processing_time_ms = 2340
            trace_id = "trace_123456789"
            sections = 1
            total_citations = 1
        }
        Requirements = @{
            answer_zh = "Contains integer/decimal MW figure"
            effective_date = "2023-XX-XX"
            wenhao = "Yue Neng Gui [2023]"
            agency = "Guangdong Energy Bureau"
            url_domain = "gd.gov.cn|gddoe.gov.cn|csg.cn"
        }
    },
    # Test 2: Beijing Wind 49.5 Hz Ride-Through Time
    @{
        TestName = "Beijing Wind 49.5 Hz Ride-Through Time"
        MockResponse = @{
            answer_zh = "10.5 seconds"
            citations = @(
                @{
                    title = "Beijing Wind Power Grid Connection Technical Standards"
                    effective_date = "2024-03-20"
                    wenhao = "Jing Dian Tiao [2024] 002"
                    agency = "Beijing Market Regulation Bureau"
                    url = "http://beijing.gov.cn/regulation/2024/002.pdf"
                }
            )
            processing_time_ms = 1870
            trace_id = "trace_987654321"
            sections = 1
            total_citations = 1
        }
        Requirements = @{
            answer_zh = "Decimal seconds <= 30.0"
            effective_date = "2024-XX-XX"
            wenhao = "Jing Dian Tiao [2024]|Beijing Market Regulation [2024]"
            url_domain = "beijing.gov.cn|bj.sgcc.com.cn"
        }
    },
    # Test 3: Shanghai BESS Market Entry Threshold
    @{
        TestName = "Shanghai BESS Market Entry Threshold"
        MockResponse = @{
            answer_zh = "5 MW"
            citations = @(
                @{
                    title = "Shanghai BESS Participation in Power Market Regulations"
                    effective_date = "2023-06-10"
                    wenhao = "Hu Jing Xin Zhuang [2023] 003"
                    agency = "Shanghai Economic Information Commission"
                    url = "http://shanghai.gov.cn/policy/2023/003.pdf"
                }
            )
            processing_time_ms = 2150
            trace_id = "trace_456789123"
            sections = 1
            total_citations = 1
        }
        Requirements = @{
            answer_zh = "Integer MW figure"
            effective_date = "2023-01-01 or later"
            wenhao = "Hu Jing Xin Zhuang [2023]|Hu Fa Gai Neng Yuan [2023]"
            url_domain = "shanghai.gov.cn|sh.sgcc.com.cn"
        }
    },
    # Test 4: Shandong Inter-provincial Renewable PPA Document
    @{
        TestName = "Shandong Inter-provincial Renewable PPA Document"
        MockResponse = @{
            answer_zh = "'Shandong Inter-provincial Renewable Energy Grid Connection Protocol'"
            citations = @(
                @{
                    title = "Shandong Inter-provincial Renewable Energy Grid Connection Protocol"
                    effective_date = "2024-02-15"
                    wenhao = "Lu Dian Tiao [2024] 004"
                    agency = "Shandong Energy Bureau"
                    url = "http://shandong.gov.cn/document/2024/004.pdf"
                }
            )
            processing_time_ms = 1980
            trace_id = "trace_789123456"
            sections = 1
            total_citations = 1
        }
        Requirements = @{
            answer_zh = "Document title in quotes"
            effective_date = "2024-XX-XX"
            wenhao = "Lu Dian Tiao [2024]"
            url_domain = "shandong.gov.cn|sd.sgcc.com.cn"
        }
    },
    # Test 5: Inner Mongolia Clean-Energy Base Monitoring Frequency
    @{
        TestName = "Inner Mongolia Clean-Energy Base Monitoring Frequency"
        MockResponse = @{
            answer_zh = "monthly monitoring"
            citations = @(
                @{
                    title = "Inner Mongolia Clean Energy Base Environmental Monitoring Regulations"
                    effective_date = "2022-08-25"
                    wenhao = "Nei Huan Fa [2022] 005"
                    agency = "Inner Mongolia Ecology and Environment Department"
                    url = "http://nm.gov.cn/environment/2022/005.pdf"
                }
            )
            processing_time_ms = 1620
            trace_id = "trace_321654987"
            sections = 1
            total_citations = 1
        }
        Requirements = @{
            answer_zh = "Frequency phrase"
            effective_date = "2022-01-01 or later"
            wenhao = "Nei Huan Fa [2022]|Inner Mongolia Ecology [2022]"
            url_domain = "nm.gov.cn|neimenggu.gov.cn"
        }
    }
)

function Test-ValidationLogic {
    param(
        [object]$Response,
        [hashtable]$Requirements
    )

    $issues = @()

    # Validate answer_zh
    if (-not $Response.answer_zh) {
        $issues += "Missing answer_zh field"
    } else {
        $answer_zh = $Response.answer_zh

        switch ($Requirements.answer_zh) {
            "Contains integer/decimal MW figure" {
                if ($answer_zh -notmatch '\d+') {
                    $issues += "answer_zh should contain numeric MW figure"
                }
            }
            "Decimal seconds <= 30.0" {
                if ($answer_zh -notmatch '\d+\.?\d*\s*seconds?') {
                    $issues += "answer_zh should contain decimal seconds"
                } else {
                    $seconds = [regex]::Match($answer_zh, '(\d+\.?\d*)').Groups[1].Value
                    if ([double]$seconds -gt 30.0) {
                        $issues += "answer_zh should contain seconds <= 30.0"
                    }
                }
            }
            "Integer MW figure" {
                if ($answer_zh -notmatch '\d+\s*MW') {
                    $issues += "answer_zh should contain integer MW figure"
                }
            }
            "Document title in quotes" {
                if ($answer_zh -notmatch "['""]") {
                    $issues += "answer_zh should contain document title in quotes"
                }
            }
            "Frequency phrase" {
                $validPhrases = @("monthly", "quarterly", "yearly", "biannual", "weekly")
                $hasValidPhrase = $false
                foreach ($phrase in $validPhrases) {
                    if ($answer_zh -match $phrase) {
                        $hasValidPhrase = $true
                        break
                    }
                }
                if (-not $hasValidPhrase) {
                    $issues += "answer_zh should contain frequency phrase"
                }
            }
        }
    }

    # Validate citations
    if (-not $Response.citations -or $Response.citations.Count -eq 0) {
        $issues += "Missing citations array"
    } else {
        $citation = $Response.citations[0]

        # Validate effective_date
        if (-not $citation.effective_date) {
            $issues += "Missing citations[0].effective_date"
        } else {
            $effectiveDate = $citation.effective_date
            switch ($Requirements.effective_date) {
                "2023-XX-XX" {
                    if ($effectiveDate -notlike "2023*") {
                        $issues += "effective_date should be 2023, got $effectiveDate"
                    }
                }
                "2024-XX-XX" {
                    if ($effectiveDate -notlike "2024*") {
                        $issues += "effective_date should be 2024, got $effectiveDate"
                    }
                }
                "2023-01-01 or later" {
                    try {
                        $date = [DateTime]::Parse($effectiveDate)
                        $cutoff = [DateTime]::Parse("2023-01-01")
                        if ($date -lt $cutoff) {
                            $issues += "effective_date should be 2023-01-01 or later, got $effectiveDate"
                        }
                    } catch {
                        $issues += "Invalid effective_date format: $effectiveDate"
                    }
                }
                "2022-01-01 or later" {
                    try {
                        $date = [DateTime]::Parse($effectiveDate)
                        $cutoff = [DateTime]::Parse("2022-01-01")
                        if ($date -lt $cutoff) {
                            $issues += "effective_date should be 2022-01-01 or later, got $effectiveDate"
                        }
                    } catch {
                        $issues += "Invalid effective_date format: $effectiveDate"
                    }
                }
            }
        }

        # Validate wenhao
        if (-not $citation.wenhao) {
            $issues += "Missing citations[0].wenhao"
        } else {
            $wenhao = $citation.wenhao
            $expectedPatterns = $Requirements.wenhao -split '\|'
            $hasValidWenhao = $false
            foreach ($pattern in $expectedPatterns) {
                if ($wenhao -match $pattern) {
                    $hasValidWenhao = $true
                    break
                }
            }
            if (-not $hasValidWenhao) {
                $issues += "wenhao should match pattern $($Requirements.wenhao), got $wenhao"
            }
        }

        # Validate URL domain
        if (-not $citation.url) {
            $issues += "Missing citations[0].url"
        } else {
            $url = $citation.url
            $expectedDomains = $Requirements.url_domain -split '\|'
            $hasValidDomain = $false
            foreach ($domain in $expectedDomains) {
                if ($url -match $domain) {
                    $hasValidDomain = $true
                    break
                }
            }
            if (-not $hasValidDomain) {
                $issues += "URL should contain domain $($Requirements.url_domain), got $url"
            }
        }
    }

    return @{
        IsValid = ($issues.Count -eq 0)
        Issues = $issues
        Requirements = $Requirements
    }
}

# Run validation tests
$testResults = @()

foreach ($test in $mockResponses) {
    Write-Host ""
    Write-Host "Test: $($test.TestName)" -ForegroundColor Cyan
    Write-Host ("-" * 50) -ForegroundColor Cyan

    # Display mock response
    Write-Host "Mock Response:" -ForegroundColor Gray
    Write-Host ($test.MockResponse | ConvertTo-Json -Depth 10) -ForegroundColor Gray

    # Display requirements
    Write-Host ""
    Write-Host "Requirements:" -ForegroundColor Yellow
    foreach ($req in $test.Requirements.GetEnumerator()) {
        Write-Host "   • $($req.Key): $($req.Value)" -ForegroundColor Gray
    }

    # Validate
    $validation = Test-ValidationLogic -Response $test.MockResponse -Requirements $test.Requirements

    Write-Host ""
    Write-Host "Validation Results:" -ForegroundColor Green

    if ($validation.IsValid) {
        Write-Host "PASS - All requirements met!" -ForegroundColor Green
    } else {
        Write-Host "FAIL - Issues found:" -ForegroundColor Red
        foreach ($issue in $validation.Issues) {
            Write-Host "   • $issue" -ForegroundColor Red
        }
    }

    $testResults += @{
        TestName = $test.TestName
        IsValid = $validation.IsValid
        Issues = $validation.Issues
        MockResponse = $test.MockResponse
        Requirements = $test.Requirements
    }
}

# Summary
Write-Host ""
Write-Host ("=" * 60) -ForegroundColor Green
Write-Host "VALIDATION SUMMARY" -ForegroundColor Green
Write-Host ("=" * 60) -ForegroundColor Green

$passedTests = ($testResults | Where-Object { $_.IsValid }).Count
$totalTests = $testResults.Count

Write-Host "Tests Passed: $passedTests/$totalTests" -ForegroundColor Cyan

if ($passedTests -eq $totalTests) {
    Write-Host "ALL VALIDATION TESTS PASSED!" -ForegroundColor Green
    Write-Host ""
    Write-Host "This demonstrates the validation logic that will be applied" -ForegroundColor Cyan
    Write-Host "to real API responses once the service environment is configured." -ForegroundColor Cyan
} else {
    Write-Host "Some validation tests failed. Review issues above." -ForegroundColor Red
}

Write-Host ""
Write-Host "Next Steps:" -ForegroundColor Yellow
Write-Host "1. Resolve Python environment issues using ENVIRONMENT_SETUP_GUIDE.md" -ForegroundColor Gray
Write-Host "2. Start the API service on localhost:8000" -ForegroundColor Gray
Write-Host "3. Run .\run_live_api_tests.ps1 for actual API testing" -ForegroundColor Gray
Write-Host "4. Review results in generated markdown report" -ForegroundColor Gray

# Save results to file
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$outputFile = "VALIDATION_TEST_RESULTS_$timestamp.md"

$report = @"
# Validation Test Results: Five Razor-Sharp Prompts

## Summary

**Test Date:** $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")
**Tests Passed:** $passedTests/$totalTests
**Status:** Demonstration of validation logic

---

## Detailed Results

"@

foreach ($result in $testResults) {
    $report += @"

### Test: $($result.TestName)

**Status:** $(if ($result.IsValid) { "PASS" } else { "FAIL" })

#### Mock Response:
``````json
$($result.MockResponse | ConvertTo-Json -Depth 10)
``````
"@
    if (-not $result.IsValid) {
        $report += @"

#### Issues Found:
"@
        foreach ($issue in $result.Issues) {
            $report += "- $issue`n"
        }
    }
}

$report | Out-File -FilePath $outputFile -Encoding UTF8

Write-Host ""
Write-Host "Results saved to: $outputFile" -ForegroundColor Green
