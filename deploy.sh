#!/bin/bash

# Chinese Energy Compliance Assistant - Deployment Script
# This script helps set up and deploy the application

set -e

echo "🚀 Chinese Energy Compliance Assistant - Deployment"
echo "=================================================="

# Check Python version
echo "📋 Checking Python version..."
python --version

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python -m venv venv
fi

# Activate virtual environment
echo "🔄 Activating virtual environment..."
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install/update dependencies
echo "📥 Installing dependencies..."
pip install -r requirements.txt

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "⚠️  .env file not found!"
    echo "📋 Copying .env.example to .env..."
    cp .env.example .env
    echo "✏️  Please edit .env file with your API keys before running the application"
fi

# Check for required API keys
echo "🔑 Checking API keys..."
if grep -q "your_perplexity_api_key_here" .env; then
    echo "⚠️  PPLX_API_KEY not configured in .env file"
fi

if grep -q "your_google_api_key_here" .env; then
    echo "⚠️  GOOGLE_API_KEY not configured in .env file"
fi

if grep -q "your_google_cse_id_here" .env; then
    echo "⚠️  GOOGLE_CSE_ID not configured in .env file"
fi

# Run database migrations if they exist
if [ -f "services/storage/migrations/run_migrations.py" ]; then
    echo "🗄️  Running database migrations..."
    python -m services.storage.migrations.run_migrations
fi

# Test import
echo "🧪 Testing imports..."
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

echo "🎉 Deployment preparation complete!"
echo ""
echo "Next steps:"
echo "1. Edit .env file with your API keys"
echo "2. Run: python main.py"
echo "3. Or run: uvicorn services.gateway.api:app --host 0.0.0.0 --port 8000"
echo "4. Test: python test_six_queries.py"
echo ""
echo "API will be available at: http://localhost:8000"
echo "Documentation at: http://localhost:8000/docs"
