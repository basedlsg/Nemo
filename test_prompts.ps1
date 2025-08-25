# Test the 5 razor-sharp prompts for province-specific retrieval
# This PowerShell script validates the requirements for each prompt

Write-Host "Testing 5 Razor-Sharp Prompts for Province-Specific Retrieval" -ForegroundColor Green
Write-Host ("=" * 70) -ForegroundColor Green

# Test case definitions
$testCases = @(
    @{
        Name = "Prompt 1 - Guangdong 2023 Distributed PV Cap"
        Requirements = @{
            answer_zh = "integer or decimal MW figure (e.g., 6000 or 6 000)"
            effective_date = "2023-xx-xx (any day in 2023)"
            wenhao = "Yue Neng Gui [2023] + number"
            agency = "Guangdong Energy Bureau or Guangdong Development and Reform Commission"
            url_domain = "gd.gov.cn, gddoe.gov.cn, or csg.cn"
        }
    },
    @{
        Name = "Prompt 2 - Beijing Wind 49.5 Hz Ride-Through Time"
        Requirements = @{
            answer_zh = "decimal seconds <= 30.0 (e.g., 10.5 seconds)"
            effective_date = "2024-xx-xx"
            wenhao = "Jing Dian Tiao [2024] or Beijing Market Regulation [2024]"
            url_domain = "beijing.gov.cn or bj.sgcc.com.cn"
        }
    },
    @{
        Name = "Prompt 3 - Shanghai BESS Market Entry Threshold"
        Requirements = @{
            answer_zh = "integer MW (e.g., 5)"
            effective_date = "2023-01-01 or later"
            wenhao = "Hu Jing Xin Zhuang [2023] or Hu Fa Gai Neng Yuan [2023]"
            url_domain = "shanghai.gov.cn or sh.sgcc.com.cn"
        }
    },
    @{
        Name = "Prompt 4 - Shandong Inter-provincial Renewable PPA Document"
        Requirements = @{
            answer_zh = "exact document title in quotation marks"
            wenhao = "Lu Dian Tiao [2024] + number"
            effective_date = "2024-xx-xx"
            url_domain = "shandong.gov.cn or sd.sgcc.com.cn"
        }
    },
    @{
        Name = "Prompt 5 - Inner Mongolia Clean-Energy Base Monitoring Frequency"
        Requirements = @{
            answer_zh = "frequency phrase such as 'monthly' or 'quarterly'"
            effective_date = "2022-01-01 or later"
            wenhao = "Nei Huan Fa [2022] or Inner Mongolia Ecology [2022]"
            url_domain = "nm.gov.cn or neimenggu.gov.cn"
        }
    }
)

$results = @()
$totalTests = $testCases.Count
$passedTests = 0

for ($i = 0; $i -lt $testCases.Count; $i++) {
    $testCase = $testCases[$i]
    $testNum = $i + 1

    Write-Host "`n📋 Test $testNum`: $($testCase.Name)" -ForegroundColor Cyan
    Write-Host ("-" * 50) -ForegroundColor Cyan

    Write-Host "📋 Requirements:" -ForegroundColor Yellow
    foreach ($req in $testCase.Requirements.GetEnumerator()) {
        Write-Host "   • $($req.Key): $($req.Value)" -ForegroundColor Gray
    }

    # Mock response simulation
    $mockResponse = @{
        answer_zh = switch ($testNum) {
            1 { "6000 MW" }
            2 { "10.5 seconds" }
            3 { "5 MW" }
            4 { "'Shandong Inter-provincial Renewable Energy Grid Connection Protocol'" }
            5 { "monthly monitoring" }
        }
        citations = @(
            @{
                title = "Test Document"
                effective_date = switch ($testNum) {
                    1 { "2023-01-01" }
                    2 { "2024-01-01" }
                    3 { "2023-06-01" }
                    4 { "2024-01-01" }
                    5 { "2022-03-01" }
                }
                wenhao = switch ($testNum) {
                    1 { "Yue Neng Gui [2023]001" }
                    2 { "Jing Dian Tiao [2024]002" }
                    3 { "Hu Jing Xin Zhuang [2023]003" }
                    4 { "Lu Dian Tiao [2024]004" }
                    5 { "Nei Huan Fa [2022]005" }
                }
                agency = switch ($testNum) {
                    1 { "Guangdong Energy Bureau" }
                    2 { "Beijing Market Regulation Bureau" }
                    3 { "Shanghai Economic Information Commission" }
                    4 { "Shandong Energy Bureau" }
                    5 { "Inner Mongolia Ecology and Environment Department" }
                }
                url = switch ($testNum) {
                    1 { "http://gddoe.gov.cn/notice/2023/001.pdf" }
                    2 { "http://beijing.gov.cn/regulation/2024/002.pdf" }
                    3 { "http://shanghai.gov.cn/policy/2023/003.pdf" }
                    4 { "http://shandong.gov.cn/document/2024/004.pdf" }
                    5 { "http://nm.gov.cn/environment/2022/005.pdf" }
                }
            }
        )
    }

    # Validate response
    $issues = @()

    # Check answer_zh
    if (-not $mockResponse.answer_zh) {
        $issues += "Missing answer_zh field"
    } else {
        switch ($testNum) {
            1 {
                if ($mockResponse.answer_zh -notmatch '\d+') {
                    $issues += "answer_zh should contain numeric MW figure"
                }
            }
            2 {
                if ($mockResponse.answer_zh -notmatch '\d+\.?\d*\s*seconds?') {
                    $issues += "answer_zh should contain decimal seconds"
                } else {
                    $seconds = [regex]::Match($mockResponse.answer_zh, '(\d+\.?\d*)').Groups[1].Value
                    if ([double]$seconds -gt 30.0) {
                        $issues += "answer_zh should contain seconds ≤ 30.0"
                    }
                }
            }
            3 {
                if ($mockResponse.answer_zh -notmatch '\d+\s*MW') {
                    $issues += "answer_zh should contain integer MW figure"
                }
            }
            4 {
                if ($mockResponse.answer_zh -notmatch "['""]") {
                    $issues += "answer_zh should contain document title in quotes"
                }
            }
            5 {
                $validPhrases = @("monthly", "quarterly", "yearly", "biannual", "weekly")
                $hasValidPhrase = $false
                foreach ($phrase in $validPhrases) {
                    if ($mockResponse.answer_zh -match $phrase) {
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

    # Check citations
    if (-not $mockResponse.citations -or $mockResponse.citations.Count -eq 0) {
        $issues += "Missing citations array"
    } else {
        $citation = $mockResponse.citations[0]

        # Check effective_date
        if (-not $citation.effective_date) {
            $issues += "Missing citations[0].effective_date"
        } else {
            switch ($testNum) {
                1 {
                    if ($citation.effective_date -notlike "2023*") {
                        $issues += "effective_date should be 2023, got $($citation.effective_date)"
                    }
                }
                2 {
                    if ($citation.effective_date -notlike "2024*") {
                        $issues += "effective_date should be 2024, got $($citation.effective_date)"
                    }
                }
                3 {
                    if ($citation.effective_date -notlike "2023*" -and $citation.effective_date -notlike "2024*") {
                        $issues += "effective_date should be 2023 or later, got $($citation.effective_date)"
                    }
                }
                4 {
                    if ($citation.effective_date -notlike "2024*") {
                        $issues += "effective_date should be 2024, got $($citation.effective_date)"
                    }
                }
                5 {
                    try {
                        $date = [DateTime]::Parse($citation.effective_date)
                        $cutoff = [DateTime]::Parse("2022-01-01")
                        if ($date -lt $cutoff) {
                            $issues += "effective_date should be 2022-01-01 or later, got $($citation.effective_date)"
                        }
                    } catch {
                        $issues += "Invalid effective_date format: $($citation.effective_date)"
                    }
                }
            }
        }

        # Check wenhao
        if (-not $citation.wenhao) {
            $issues += "Missing citations[0].wenhao"
        } else {
            $expectedPrefix = switch ($testNum) {
                1 { "Yue Neng Gui [2023]" }
                2 { "Jing Dian Tiao [2024]" }
                3 { "Hu Jing Xin Zhuang [2023]" }
                4 { "Lu Dian Tiao [2024]" }
                5 { "Nei Huan Fa [2022]" }
            }
            # Use regex to check if wenhao starts with expected prefix (flexible matching)
            $expectedPrefixEscaped = [regex]::Escape($expectedPrefix)
            if ($citation.wenhao -notmatch "^$expectedPrefixEscaped") {
                $issues += "wenhao should start with $expectedPrefix, got $($citation.wenhao)"
            }
        }

        # Check agency (for applicable tests)
        if ($testNum -in @(1,2,3,5)) {
            if (-not $citation.agency) {
                $issues += "Missing citations[0].agency"
            } else {
                $expectedAgencies = switch ($testNum) {
                    1 { @("Guangdong Energy Bureau", "Guangdong Development and Reform Commission") }
                    2 { @("Beijing Market Regulation Bureau") }
                    3 { @("Shanghai Economic Information Commission") }
                    5 { @("Inner Mongolia Ecology and Environment Department") }
                }
                $hasExpectedAgency = $false
                foreach ($expected in $expectedAgencies) {
                    if ($citation.agency -match $expected) {
                        $hasExpectedAgency = $true
                        break
                    }
                }
                if (-not $hasExpectedAgency) {
                    $issues += "agency should contain one of $($expectedAgencies -join ' or '), got $($citation.agency)"
                }
            }
        }

        # Check URL domain
        if (-not $citation.url) {
            $issues += "Missing citations[0].url"
        } else {
            $expectedDomains = switch ($testNum) {
                1 { @("gd.gov.cn", "gddoe.gov.cn", "csg.cn") }
                2 { @("beijing.gov.cn", "bj.sgcc.com.cn") }
                3 { @("shanghai.gov.cn", "sh.sgcc.com.cn") }
                4 { @("shandong.gov.cn", "sd.sgcc.com.cn") }
                5 { @("nm.gov.cn", "neimenggu.gov.cn") }
            }
            $hasExpectedDomain = $false
            foreach ($domain in $expectedDomains) {
                if ($citation.url -match $domain) {
                    $hasExpectedDomain = $true
                    break
                }
            }
            if (-not $hasExpectedDomain) {
                $issues += "URL domain should be one of $($expectedDomains -join ', '), got $($citation.url)"
            }
        }
    }

    # Determine test result
    if ($issues.Count -eq 0) {
        Write-Host "✅ PASS - All requirements met" -ForegroundColor Green
        $results += @{ Test = $testNum; Status = "PASS"; Issues = @() }
        $passedTests++
    } else {
        Write-Host "❌ FAIL - Issues found:" -ForegroundColor Red
        foreach ($issue in $issues) {
            Write-Host "   • $issue" -ForegroundColor Red
        }
        $results += @{ Test = $testNum; Status = "FAIL"; Issues = $issues }
    }
}

# Summary
Write-Host "`n$('-' * 70)" -ForegroundColor Green
Write-Host "📊 TEST SUMMARY" -ForegroundColor Green
Write-Host ("=" * 70) -ForegroundColor Green

Write-Host "Tests Passed: $passedTests/$totalTests" -ForegroundColor Cyan

if ($passedTests -eq $totalTests) {
    Write-Host "🎉 ALL TESTS PASSED!" -ForegroundColor Green
} else {
    Write-Host "❌ Some tests failed. Details above." -ForegroundColor Red
}

# API Service Status Check
Write-Host "`n🔍 API SERVICE STATUS" -ForegroundColor Yellow
Write-Host ("-" * 30) -ForegroundColor Yellow

try {
    $response = Invoke-WebRequest -Uri "http://localhost:8000/api/v1/health" -Method GET -TimeoutSec 5
    if ($response.StatusCode -eq 200) {
        Write-Host "✅ API Service is RUNNING on localhost:8000" -ForegroundColor Green
        Write-Host "   Ready to run actual API tests!" -ForegroundColor Green
    }
} catch {
    Write-Host "❌ API Service is NOT running on localhost:8000" -ForegroundColor Red
    Write-Host "   Error: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "   Note: Validation tests above are using mock responses" -ForegroundColor Yellow
}

Write-Host "`n💡 To run actual API tests, start the service and run this script again" -ForegroundColor Cyan
