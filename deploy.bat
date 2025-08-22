@echo off
REM Chinese Energy Compliance Assistant - Windows Deployment Script
REM This script helps set up and deploy the application on Windows

echo 🚀 Chinese Energy Compliance Assistant - Deployment
echo ==================================================

REM Check Python version
echo 📋 Checking Python version...
python --version

REM Create virtual environment if it doesn't exist
if not exist "venv" (
    echo 📦 Creating virtual environment...
    python -m venv venv
)

REM Activate virtual environment
echo 🔄 Activating virtual environment...
call venv\Scripts\activate.bat

REM Install/update dependencies
echo 📥 Installing dependencies...
pip install -r requirements.txt

REM Check if .env file exists
if not exist ".env" (
    echo ⚠️  .env file not found!
    echo 📋 Copying .env.example to .env...
    copy .env.example .env
    echo ✏️  Please edit .env file with your API keys before running the application
)

REM Check for required API keys
echo 🔑 Checking API keys...
findstr "your_perplexity_api_key_here" .env >nul
if %errorlevel%==0 (
    echo ⚠️  PPLX_API_KEY not configured in .env file
)

findstr "your_google_api_key_here" .env >nul
if %errorlevel%==0 (
    echo ⚠️  GOOGLE_API_KEY not configured in .env file
)

findstr "your_google_cse_id_here" .env >nul
if %errorlevel%==0 (
    echo ⚠️  GOOGLE_CSE_ID not configured in .env file
)

REM Run database migrations if they exist
if exist "services\storage\migrations\run_migrations.py" (
    echo 🗄️  Running database migrations...
    python -m services.storage.migrations.run_migrations
)

REM Test import
echo 🧪 Testing imports...
python -c "
import sys
import os
sys.path.append(os.getcwd())

try:
    from services.gateway.api import app
    print('✅ App import successful')
except Exception as e:
    print(f'❌ Import error: {e}')
    exit(1)
"

echo 🎉 Deployment preparation complete!
echo.
echo Next steps:
echo 1. Edit .env file with your API keys
echo 2. Run: python main.py
echo 3. Or run: uvicorn services.gateway.api:app --host 0.0.0.0 --port 8000
echo 4. Test: python test_six_queries.py
echo.
echo API will be available at: http://localhost:8000
echo Documentation at: http://localhost:8000/docs

pause
