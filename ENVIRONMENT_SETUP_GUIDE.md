# 🛠️ Environment Setup Guide: Chinese Energy Compliance API

## 🚨 Current Environment Issues

### Problem Analysis
The API service cannot start due to Python environment configuration issues:

```
Error: failed to locate pyvenv.cfg
Status: Python virtual environment not found
Impact: API service startup blocked
```

### Root Cause
- Python installation incomplete or corrupted
- Missing virtual environment configuration
- Dependency installation failures
- Environment variable misconfiguration

---

## 🔧 Step-by-Step Resolution

### Step 1: Verify Python Installation

**Check Python Version:**
```powershell
python --version
# Expected: Python 3.8 or higher
```

**Check Python Path:**
```powershell
Get-Command python
# Should show Python executable path
```

### Step 2: Create Virtual Environment

**Navigate to Project Directory:**
```powershell
cd C:\Users\Flare\Nemo_Test
```

**Create Virtual Environment:**
```powershell
python -m venv venv
# Creates virtual environment in 'venv' folder
```

**Activate Virtual Environment:**
```powershell
.\venv\Scripts\Activate.ps1
# Command prompt should show (venv) prefix
```

### Step 3: Install Dependencies

**Upgrade pip:**
```powershell
python -m pip install --upgrade pip
```

**Install Requirements:**
```powershell
pip install -r requirements.txt
```

**Verify Installation:**
```powershell
pip list | Select-String -Pattern "fastapi|uvicorn|pydantic"
# Should show installed packages
```

### Step 4: Configure Environment Variables

**Create .env file:**
```powershell
# Copy env.yaml content to .env file
Copy-Item env.yaml .env
```

**Set Environment Variables:**
```powershell
# Load environment variables (if needed)
foreach ($line in Get-Content .env) {
    if ($line -match '^([^=]+)=(.*)$') {
        $key = $matches[1]
        $value = $matches[2]
        [Environment]::SetEnvironmentVariable($key, $value)
    }
}
```

### Step 5: Test API Service Startup

**Test Gateway Service:**
```powershell
python -m uvicorn services.gateway.api:app --host 0.0.0.0 --port 8000 --log-level info
```

**Verify Health Endpoint:**
```powershell
Invoke-WebRequest -Uri "http://localhost:8000/api/v1/health" -Method GET
# Should return {"ok": true}
```

---

## 📋 Alternative Installation Methods

### Option A: Use System Python (if virtual environment fails)

**Install to system Python:**
```powershell
pip install fastapi uvicorn[standard] pydantic python-dotenv requests aiohttp
```

**Start service:**
```powershell
python -m uvicorn services.gateway.api:app --host 0.0.0.0 --port 8000
```

### Option B: Use Conda Environment

**Create Conda Environment:**
```powershell
conda create -n energy-api python=3.9
conda activate energy-api
pip install -r requirements.txt
```

### Option C: Use Docker (if available)

**Build and run Docker container:**
```powershell
docker build -t energy-api .
docker run -p 8000:8000 energy-api
```

---

## 🔍 Troubleshooting Common Issues

### Issue 1: "No module named 'fastapi'"
**Solution:**
```powershell
pip install fastapi
# or
pip install -r requirements.txt
```

### Issue 2: "Port 8000 already in use"
**Solution:**
```powershell
# Kill existing process
Get-Process | Where-Object {$_.Name -like "*uvicorn*" -or $_.Name -like "*python*"} | Stop-Process -Force

# Or use different port
python -m uvicorn services.gateway.api:app --host 0.0.0.0 --port 8001
```

### Issue 3: "Permission denied" on Windows
**Solution:**
```powershell
# Run PowerShell as Administrator
Start-Process powershell -Verb RunAs

# Or set execution policy
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### Issue 4: Environment variables not loading
**Solution:**
```powershell
# Manual environment variable setup
$env:PPLX_API_KEY = "your_api_key_here"
$env:GOOGLE_API_KEY = "your_google_key_here"
$env:GOOGLE_CSE_ID = "your_cse_id_here"
```

---

## 📊 Environment Verification Checklist

### Python Environment
- [ ] Python 3.8+ installed
- [ ] Virtual environment created
- [ ] Virtual environment activated
- [ ] Dependencies installed

### API Configuration
- [ ] Environment variables set
- [ ] API keys configured
- [ ] Allowlist domains configured
- [ ] Port 8000 available

### Service Verification
- [ ] API service starts without errors
- [ ] Health endpoint responds
- [ ] Query endpoint accessible
- [ ] No import errors

---

## 🚀 Quick Start Commands

### One-Line Setup (if virtual environment works):
```powershell
cd C:\Users\Flare\Nemo_Test
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m uvicorn services.gateway.api:app --host 0.0.0.0 --port 8000 --log-level info
```

### Test Service:
```powershell
Invoke-WebRequest -Uri "http://localhost:8000/api/v1/health" -Method GET
```

---

## 📞 Support Information

### Required Environment Variables
```yaml
QUERY_MODE: "web_only"
PPLX_API_KEY: "your_perplexity_key"
GOOGLE_API_KEY: "your_google_key"
GOOGLE_CSE_ID: "your_cse_id"
ALLOWLIST_DOMAINS: "gov.cn,nea.gov.cn,ndrc.gov.cn,miit.gov.cn,mee.gov.cn"
```

### File Structure Requirements
```
Nemo_Test/
├── services/
│   └── gateway/
│       └── api.py
├── requirements.txt
├── env.yaml
└── .env (create this)
```

### Common Error Codes
- **500**: Internal server error - check logs
- **404**: Endpoint not found - verify URL
- **422**: Validation error - check request format
- **429**: Rate limit - API key issues

---

## 🎯 Next Steps After Environment Setup

1. **Start API Service** using the commands above
2. **Run Test Script**:
   ```powershell
   .\run_live_api_tests.ps1
   ```
3. **Review Results** in generated markdown file
4. **Validate** all 5 test prompts meet requirements

---

**Status:** Environment setup required before API testing can proceed.
