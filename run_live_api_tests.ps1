# PowerShell script to run actual API tests for the 5 razor-sharp prompts
# Execute this script when the API service is properly configured and running

param(
    [string]$ApiUrl = "http://localhost:8000/api/v1/query",
    [string]$HealthUrl = "http://localhost:8000/api/v1/health",
    [int]$TimeoutSeconds = 30
)

Write-Host "🔬 Live API Test Suite: Five Razor-Sharp Prompts" -ForegroundColor Green
Write-Host ("=" * 60) -ForegroundColor Green
Write-Host "Test Date: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor Cyan
Write-Host "API Endpoint: $ApiUrl" -ForegroundColor Cyan
Write-Host ""

# Test prompts as provided by user
$testPrompts = @(
    @{
        Name = "Guangdong 2023 Distributed PV Cap"
        Payload = @{
            province = "guangdong"
            doc_class = "regulations"
            asset = "solar"
            question = "广东省2023年分布式光伏发电项目年度新增并网容量上限是多少兆瓦？请给出文件文号及发布机关。"
            lang = "zh-CN"
        }
        Requirements = @{
            answer_zh = "Contains integer/decimal MW figure"
            effective_date = "2023-XX-XX"
            wenhao = "粤能规〔2023〕"
            agency = "广东省能源局"
            url_domain = "gd.gov.cn|gddoe.gov.cn|csg.cn"
        }
    },
    @{
        Name = "Beijing Wind 49.5 Hz Ride-Through Time"
        Payload = @{
            province = "beijing"
            doc_class = "technical_standards"
            asset = "wind"
            question = "北京市2024年风力发电机组在49.5 Hz时的最低不脱网运行时间是多少秒？请引用技术标准文号。"
            lang = "zh-CN"
        }
        Requirements = @{
            answer_zh = "Decimal seconds <= 30.0"
            effective_date = "2024-XX-XX"
            wenhao = "京电调〔2024〕|北京市市场监管局〔2024〕"
            url_domain = "beijing.gov.cn|bj.sgcc.com.cn"
        }
    },
    @{
        Name = "Shanghai BESS Market Entry Threshold"
        Payload = @{
            province = "shanghai"
            doc_class = "market_rules"
            asset = "bess"
            question = "上海市储能电站参与电力现货市场的最低装机准入门槛是多少兆瓦？请提供文件文号及实施日期。"
            lang = "zh-CN"
        }
        Requirements = @{
            answer_zh = "Integer MW figure"
            effective_date = "2023-01-01 or later"
            wenhao = "沪经信装〔2023〕|沪发改能源〔2023〕"
            url_domain = "shanghai.gov.cn|sh.sgcc.com.cn"
        }
    },
    @{
        Name = "Shandong Inter-provincial Renewable PPA Document"
        Payload = @{
            province = "shandong"
            doc_class = "grid_connection"
            asset = "renewable"
            question = "山东省2024年跨省跨区新能源发电项目并网调度协议签订流程的正式文件全称及文号是什么？"
            lang = "zh-CN"
        }
        Requirements = @{
            answer_zh = "Document title in quotes"
            effective_date = "2024-XX-XX"
            wenhao = "鲁电调〔2024〕"
            url_domain = "shandong.gov.cn|sd.sgcc.com.cn"
        }
    },
    @{
        Name = "Inner Mongolia Clean-Energy Base Monitoring Frequency"
        Payload = @{
            province = "inner_mongolia"
            doc_class = "environmental_protection"
            asset = "clean_energy"
            question = "内蒙古自治区清洁能源基地生态保护红线区域内施工期的环境监测频次要求是多少？请引用最新有效文件文号。"
            lang = "zh-CN"
        }
        Requirements = @{
            answer_zh = "Frequency phrase"
            effective_date = "2022-01-01 or later"
            wenhao = "内环发〔2022〕|内蒙古自治区生态环境厅〔2022〕"
            url_domain = "nm.gov.cn|neimenggu.gov.cn"
        }
    }
)

function Test-ApiHealth {
    Write-Host "🏥 Testing API Health..." -ForegroundColor Yellow
    try {
        $response = Invoke-WebRequest -Uri $HealthUrl -Method GET -TimeoutSec $TimeoutSeconds
        if ($response.StatusCode -eq 200) {
            Write-Host "✅ API Service is HEALTHY" -ForegroundColor Green
            return $true
        } else {
            Write-Host "❌ API Service responded with status: $($response.StatusCode)" -ForegroundColor Red
            return $false
        }
    } catch {
        Write-Host "❌ API Service is NOT accessible: $($_.Exception.Message)" -ForegroundColor Red
        return $false
    }
}

function Invoke-ApiTest {
    param(
        [hashtable]$TestCase
    )

    Write-Host ""
    Write-Host "📋 Test: $($TestCase.Name)" -ForegroundColor Cyan
    Write-Host ("-" * 50) -ForegroundColor Cyan

    # Log request payload
    Write-Host "📤 Request Payload:" -ForegroundColor Gray
    $payloadJson = $TestCase.Payload | ConvertTo-Json -Depth 10
    Write-Host $payloadJson -ForegroundColor Gray

    try {
        $startTime = Get-Date

        $response = Invoke-WebRequest -Uri $ApiUrl -Method POST `
            -Body ($TestCase.Payload | ConvertTo-Json -Depth 10) `
            -ContentType "application/json" `
            -TimeoutSec $TimeoutSeconds

        $endTime = Get-Date
        $processingTime = ($endTime - $startTime).TotalMilliseconds

        Write-Host ""
        Write-Host "📥 Response (Status: $($response.StatusCode))" -ForegroundColor Green
        Write-Host "⚡ Processing Time: $([math]::Round($processingTime, 2))ms" -ForegroundColor Cyan

        $responseData = $response.Content | ConvertFrom-Json

        # Log full response
        Write-Host "Full Response:" -ForegroundColor Gray
        Write-Host ($responseData | ConvertTo-Json -Depth 10) -ForegroundColor Gray

        # Validate response
        $validationResult = Test-ResponseValidation -Response $responseData -Requirements $TestCase.Requirements

        return @{
            TestName = $TestCase.Name
            Status = "SUCCESS"
            StatusCode = $response.StatusCode
            ProcessingTime = $processingTime
            Response = $responseData
            Validation = $validationResult
            RawResponse = $response.Content
        }

    } catch {
        Write-Host ""
        Write-Host "❌ Request Failed: $($_.Exception.Message)" -ForegroundColor Red

        return @{
            TestName = $TestCase.Name
            Status = "FAILED"
            Error = $_.Exception.Message
        }
    }
}

function Test-ResponseValidation {
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
                if ($answer_zh -notmatch '\d+\.?\d*\s*秒') {
                    $issues += "answer_zh should contain decimal seconds"
                } else {
                    $seconds = [regex]::Match($answer_zh, '(\d+\.?\d*)').Groups[1].Value
                    if ([double]$seconds -gt 30.0) {
                        $issues += "answer_zh should contain seconds <= 30.0"
                    }
                }
            }
            "Integer MW figure" {
                if ($answer_zh -notmatch '\d+\s*兆瓦') {
                    $issues += "answer_zh should contain integer MW figure"
                }
            }
            "Document title in quotes" {
                if ($answer_zh -notmatch '[""《]') {
                    $issues += "answer_zh should contain document title in quotes"
                }
            }
            "Frequency phrase" {
                $validPhrases = @("每月", "每季度", "每年", "每半年", "每周")
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

function Write-TestResults {
    param(
        [array]$Results
    )

    Write-Host ""
    Write-Host ("=" * 60) -ForegroundColor Green
    Write-Host "📊 TEST RESULTS SUMMARY" -ForegroundColor Green
    Write-Host ("=" * 60) -ForegroundColor Green

    $passedTests = 0
    $totalTests = $Results.Count

    foreach ($result in $Results) {
        Write-Host ""
        Write-Host "Test: $($result.TestName)" -ForegroundColor Cyan

        if ($result.Status -eq "SUCCESS") {
            $passedTests++
            Write-Host "Status: ✅ PASS" -ForegroundColor Green

            if ($result.Validation.IsValid) {
                Write-Host "Validation: ✅ All requirements met" -ForegroundColor Green
            } else {
                Write-Host "Validation: ❌ Issues found:" -ForegroundColor Red
                foreach ($issue in $result.Validation.Issues) {
                    Write-Host "   • $issue" -ForegroundColor Red
                }
            }

            Write-Host "Status Code: $($result.StatusCode)" -ForegroundColor Gray
            Write-Host "Processing Time: $([math]::Round($result.ProcessingTime, 2))ms" -ForegroundColor Gray

        } else {
            Write-Host "Status: ❌ FAILED" -ForegroundColor Red
            Write-Host "Error: $($result.Error)" -ForegroundColor Red
        }
    }

    Write-Host ""
    Write-Host ("=" * 60) -ForegroundColor Green
    Write-Host "📈 OVERALL RESULTS" -ForegroundColor Green
    Write-Host ("=" * 60) -ForegroundColor Green
    Write-Host "Tests Passed: $passedTests/$totalTests" -ForegroundColor Cyan

    if ($passedTests -eq $totalTests) {
        Write-Host "🎉 ALL TESTS PASSED!" -ForegroundColor Green
    } else {
        Write-Host "❌ Some tests failed. Review details above." -ForegroundColor Red
    }

    return ($passedTests -eq $totalTests)
}

# Main execution
Write-Host "🔍 Checking API Health..." -ForegroundColor Yellow
$apiHealthy = Test-ApiHealth

if (-not $apiHealthy) {
    Write-Host "❌ API service is not healthy. Cannot proceed with tests." -ForegroundColor Red
    Write-Host "💡 Please start the API service and run this script again." -ForegroundColor Yellow
    exit 1
}

Write-Host ""
Write-Host "🚀 Starting API Tests..." -ForegroundColor Green

$testResults = @()

foreach ($testPrompt in $testPrompts) {
    $result = Invoke-ApiTest -TestCase $testPrompt
    $testResults += $result
}

# Write results to file
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$outputFile = "API_TEST_RESULTS_$timestamp.md"

Write-Host ""
Write-Host "💾 Saving detailed results to: $outputFile" -ForegroundColor Yellow

$Write-TestResults -Results $testResults | Out-Null

# Create detailed markdown report
$report = @"
# 🔬 API Test Results: Five Razor-Sharp Prompts

## 📊 Test Summary

**Test Date:** $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")
**API Endpoint:** $ApiUrl
**Tests Passed:** $passedTests/$totalTests

---

## 📋 Detailed Test Results

"@

foreach ($result in $testResults) {
    $report += @"

### Test: $($result.TestName)

**Status:** $($result.Status)

"@

    if ($result.Status -eq "SUCCESS") {
        $report += "**Status Code:** $($result.StatusCode)`n"
        $report += "**Processing Time:** $([math]::Round($result.ProcessingTime, 2))ms`n"

        if ($result.Validation.IsValid) {
            $report += "**Validation:** ✅ All requirements met`n"
        } else {
            $report += "**Validation:** ❌ Issues found:`n"
            foreach ($issue in $result.Validation.Issues) {
                $report += "- $issue`n"
            }
        }

        $report += @"

**Raw Response:**
``````json
$($result.RawResponse | ConvertFrom-Json | ConvertTo-Json -Depth 10)
``````
"@
    } else {
        $report += "**Error:** $($result.Error)`n"
    }
}

$report | Out-File -FilePath $outputFile -Encoding UTF8

Write-Host "✅ Test results saved to $outputFile" -ForegroundColor Green
Write-Host ""
Write-Host "🎯 Test execution completed!" -ForegroundColor Green
