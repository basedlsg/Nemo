#!/usr/bin/env python3
"""
Setup script to configure all external APIs for the Geo-Adaptive Energy Assistant.
This script will guide you through obtaining and configuring all necessary API keys.
"""

import os
import sys
import json
import requests
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional

class APISetupManager:
    """Manages the setup and configuration of all external APIs."""
    
    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.env_file = self.project_root / ".env.production"
        self.config_dir = self.project_root / "config"
        self.config_dir.mkdir(exist_ok=True)
        
        self.api_keys = {}
        self.setup_status = {}
    
    def print_header(self, title: str):
        """Print a formatted header."""
        print("\n" + "="*60)
        print(f" {title}")
        print("="*60)
    
    def print_step(self, step: str, description: str):
        """Print a formatted step."""
        print(f"\n🔧 {step}")
        print(f"   {description}")
    
    def setup_perplexity_api(self) -> bool:
        """Setup Perplexity API for discovery service."""
        self.print_header("PERPLEXITY API SETUP")
        
        print("""
Perplexity API is used for discovering Chinese energy regulatory documents.

To get your API key:
1. Go to https://www.perplexity.ai/settings/api
2. Sign up or log in to your account
3. Generate a new API key
4. Copy the key (starts with 'pplx-')

Cost: ~$0.20 per 1K tokens (very affordable for our use case)
""")
        
        api_key = input("Enter your Perplexity API key (or press Enter to skip): ").strip()
        
        if not api_key:
            print("⚠️  Skipping Perplexity API - discovery service will use mock data")
            return False
        
        if not api_key.startswith('pplx-'):
            print("❌ Invalid Perplexity API key format. Should start with 'pplx-'")
            return False
        
        # Test the API key
        try:
            headers = {
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            }
            
            test_payload = {
                "model": "llama-3.1-sonar-small-128k-online",
                "messages": [
                    {"role": "user", "content": "Test query"}
                ],
                "max_tokens": 10
            }
            
            response = requests.post(
                'https://api.perplexity.ai/chat/completions',
                headers=headers,
                json=test_payload,
                timeout=10
            )
            
            if response.status_code == 200:
                print("✅ Perplexity API key validated successfully!")
                self.api_keys['PERPLEXITY_API_KEY'] = api_key
                self.setup_status['perplexity'] = True
                return True
            else:
                print(f"❌ Perplexity API validation failed: {response.status_code}")
                print(f"Response: {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ Error testing Perplexity API: {e}")
            return False
    
    def setup_google_cse_api(self) -> bool:
        """Setup Google Custom Search Engine API."""
        self.print_header("GOOGLE CUSTOM SEARCH ENGINE SETUP")
        
        print("""
Google CSE API is used for verifying discovered URLs.

To set up Google Custom Search Engine:

1. Go to https://console.cloud.google.com/apis/library
2. Enable the "Custom Search API"
3. Go to https://console.cloud.google.com/apis/credentials
4. Create credentials -> API Key
5. Go to https://cse.google.com/cse/
6. Create a new search engine
7. Add sites: *.gd.gov.cn, *.shandong.gov.cn, *.nmg.gov.cn
8. Get your Search Engine ID

Cost: $5 per 1K queries (we'll use ~100 queries/day)
""")
        
        api_key = input("Enter your Google CSE API key: ").strip()
        engine_id = input("Enter your Custom Search Engine ID: ").strip()
        
        if not api_key or not engine_id:
            print("⚠️  Skipping Google CSE API - verification service will use mock data")
            return False
        
        # Test the API
        try:
            test_url = f"https://www.googleapis.com/customsearch/v1?key={api_key}&cx={engine_id}&q=test&num=1"
            response = requests.get(test_url, timeout=10)
            
            if response.status_code == 200:
                print("✅ Google CSE API validated successfully!")
                self.api_keys['GOOGLE_CSE_API_KEY'] = api_key
                self.api_keys['GOOGLE_CSE_ENGINE_ID'] = engine_id
                self.setup_status['google_cse'] = True
                return True
            else:
                print(f"❌ Google CSE API validation failed: {response.status_code}")
                print(f"Response: {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ Error testing Google CSE API: {e}")
            return False
    
    def setup_google_cloud_services(self) -> bool:
        """Setup Google Cloud services (Document AI, Vertex AI)."""
        self.print_header("GOOGLE CLOUD SERVICES SETUP")
        
        print("""
Google Cloud services are used for:
- Document AI: OCR processing of Chinese PDFs
- Vertex AI: Text embeddings for semantic search

To set up Google Cloud:

1. Go to https://console.cloud.google.com/
2. Create a new project or select existing one
3. Enable the following APIs:
   - Document AI API
   - Vertex AI API
   - Cloud Storage API
4. Create a service account:
   - Go to IAM & Admin -> Service Accounts
   - Create service account with roles:
     * Document AI User
     * Vertex AI User
     * Storage Object Admin
5. Download the JSON key file

Cost: 
- Document AI: $1.50 per 1K pages
- Vertex AI: $0.025 per 1K tokens
""")
        
        project_id = input("Enter your Google Cloud Project ID: ").strip()
        
        if not project_id:
            print("⚠️  Skipping Google Cloud services - will use mock data")
            return False
        
        # Check for service account key file
        key_file_path = input("Enter path to your service account JSON key file: ").strip()
        
        if not key_file_path or not os.path.exists(key_file_path):
            print("❌ Service account key file not found")
            return False
        
        # Copy the key file to our config directory
        target_key_file = self.config_dir / "gcp-service-account.json"
        
        try:
            import shutil
            shutil.copy2(key_file_path, target_key_file)
            
            # Set environment variable for testing
            os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = str(target_key_file)
            
            # Test the credentials
            try:
                from google.cloud import documentai
                from google.cloud import aiplatform
                
                # Test Document AI
                client = documentai.DocumentProcessorServiceClient()
                print("✅ Document AI client initialized successfully!")
                
                # Test Vertex AI
                aiplatform.init(project=project_id, location="us-central1")
                print("✅ Vertex AI initialized successfully!")
                
                self.api_keys['GOOGLE_CLOUD_PROJECT'] = project_id
                self.api_keys['GOOGLE_APPLICATION_CREDENTIALS'] = str(target_key_file)
                self.setup_status['google_cloud'] = True
                return True
                
            except Exception as e:
                print(f"❌ Error testing Google Cloud services: {e}")
                return False
                
        except Exception as e:
            print(f"❌ Error setting up Google Cloud credentials: {e}")
            return False
    
    def setup_database(self) -> bool:
        """Setup database configuration."""
        self.print_header("DATABASE SETUP")
        
        print("""
Database options:
1. SQLite (local file) - Good for development and testing
2. PostgreSQL (local) - Good for production-like testing
3. AlloyDB (Google Cloud) - Production deployment

For now, we'll use SQLite with real data for immediate testing.
""")
        
        use_sqlite = input("Use SQLite database for testing? (Y/n): ").strip().lower()
        
        if use_sqlite != 'n':
            db_path = self.project_root / "data" / "gaea_production.db"
            db_path.parent.mkdir(exist_ok=True)
            
            self.api_keys['DATABASE_URL'] = f"sqlite:///{db_path}"
            self.api_keys['SQLITE_DB_PATH'] = str(db_path)
            self.setup_status['database'] = True
            
            print(f"✅ SQLite database configured at: {db_path}")
            return True
        
        return False
    
    def update_env_file(self):
        """Update the .env.production file with configured API keys."""
        self.print_step("UPDATING CONFIGURATION", "Writing API keys to .env.production")
        
        # Read current env file
        env_content = ""
        if self.env_file.exists():
            env_content = self.env_file.read_text()
        
        # Update with real API keys
        for key, value in self.api_keys.items():
            # Replace placeholder values
            if f"{key}=" in env_content:
                # Find and replace the line
                lines = env_content.split('\n')
                for i, line in enumerate(lines):
                    if line.startswith(f"{key}="):
                        lines[i] = f"{key}={value}"
                        break
                env_content = '\n'.join(lines)
            else:
                # Add new key
                env_content += f"\n{key}={value}"
        
        # Update feature flags based on what we configured
        feature_flags = {
            'ENABLE_REAL_APIS': 'true',
            'ENABLE_PERPLEXITY': str(self.setup_status.get('perplexity', False)).lower(),
            'ENABLE_GOOGLE_CSE': str(self.setup_status.get('google_cse', False)).lower(),
            'ENABLE_DOCAI': str(self.setup_status.get('google_cloud', False)).lower(),
            'ENABLE_VERTEX_AI': str(self.setup_status.get('google_cloud', False)).lower(),
        }
        
        for key, value in feature_flags.items():
            if f"{key}=" in env_content:
                lines = env_content.split('\n')
                for i, line in enumerate(lines):
                    if line.startswith(f"{key}="):
                        lines[i] = f"{key}={value}"
                        break
                env_content = '\n'.join(lines)
        
        # Write updated content
        self.env_file.write_text(env_content)
        print(f"✅ Configuration updated in {self.env_file}")
    
    def install_dependencies(self):
        """Install additional dependencies for real API usage."""
        self.print_step("INSTALLING DEPENDENCIES", "Installing required Python packages")
        
        additional_packages = [
            "google-cloud-documentai",
            "google-cloud-aiplatform", 
            "google-cloud-storage",
            "requests",
            "jieba",  # Chinese text processing
        ]
        
        for package in additional_packages:
            try:
                subprocess.run([sys.executable, "-m", "pip", "install", package], 
                             check=True, capture_output=True)
                print(f"✅ Installed {package}")
            except subprocess.CalledProcessError as e:
                print(f"❌ Failed to install {package}: {e}")
    
    def create_startup_script(self):
        """Create a startup script to run all services."""
        self.print_step("CREATING STARTUP SCRIPT", "Generating service startup script")
        
        startup_script = self.project_root / "scripts" / "start-all-services.py"
        
        script_content = '''#!/usr/bin/env python3
"""
Startup script for all Geo-Adaptive Energy Assistant services.
Runs all microservices with real API integration.
"""

import asyncio
import subprocess
import sys
import time
import os
from pathlib import Path

# Set environment
os.environ['ENV'] = 'production'
env_file = Path(__file__).parent.parent / '.env.production'
if env_file.exists():
    # Load environment variables
    with open(env_file) as f:
        for line in f:
            if '=' in line and not line.startswith('#'):
                key, value = line.strip().split('=', 1)
                os.environ[key] = value

services = [
    {"name": "Gateway", "script": "services/gateway/api.py", "port": 8000},
    {"name": "Retriever", "script": "services/retriever/api.py", "port": 8001},
    {"name": "Composer", "script": "services/composer/api.py", "port": 8002},
    {"name": "Guardrails", "script": "services/guardrails/api.py", "port": 8003},
    {"name": "Radar", "script": "services/radar/api.py", "port": 8004},
    {"name": "Orchestrator", "script": "services/orchestrator/api.py", "port": 8005},
    {"name": "Citation", "script": "services/citation/api.py", "port": 8006},
    {"name": "Ingestion", "script": "services/ingestion/request_api.py", "port": 8007},
]

def start_service(service):
    """Start a single service."""
    print(f"🚀 Starting {service['name']} on port {service['port']}...")
    
    cmd = [
        sys.executable, "-m", "uvicorn",
        f"{service['script'].replace('/', '.').replace('.py', '')}:app",
        "--host", "0.0.0.0",
        "--port", str(service['port']),
        "--reload"
    ]
    
    return subprocess.Popen(cmd, cwd=Path(__file__).parent.parent)

def main():
    print("🌟 Starting Geo-Adaptive Energy Assistant with Real APIs")
    print("=" * 60)
    
    processes = []
    
    try:
        # Start all services
        for service in services:
            proc = start_service(service)
            processes.append(proc)
            time.sleep(2)  # Stagger startup
        
        print("\\n✅ All services started!")
        print("\\n📊 Service URLs:")
        for service in services:
            print(f"   {service['name']}: http://localhost:{service['port']}")
        
        print("\\n🌐 Web Interface: http://localhost:3000")
        print("\\n📡 API Gateway: http://localhost:8000")
        print("\\nPress Ctrl+C to stop all services...")
        
        # Wait for interrupt
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\\n🛑 Stopping all services...")
        for proc in processes:
            proc.terminate()
        
        # Wait for graceful shutdown
        time.sleep(2)
        
        # Force kill if needed
        for proc in processes:
            if proc.poll() is None:
                proc.kill()
        
        print("✅ All services stopped.")

if __name__ == "__main__":
    main()
'''
        
        startup_script.write_text(script_content)
        startup_script.chmod(0o755)
        
        print(f"✅ Startup script created: {startup_script}")
    
    def run_setup(self):
        """Run the complete API setup process."""
        print("🌟 Geo-Adaptive Energy Assistant - API Setup")
        print("=" * 60)
        print("This script will help you configure all external APIs for real data processing.")
        print("You can skip any API to use mock data for that service.")
        
        # Setup each API
        self.setup_perplexity_api()
        self.setup_google_cse_api()
        self.setup_google_cloud_services()
        self.setup_database()
        
        # Update configuration
        self.update_env_file()
        self.install_dependencies()
        self.create_startup_script()
        
        # Summary
        self.print_header("SETUP COMPLETE")
        
        print("✅ API Setup Summary:")
        for service, status in self.setup_status.items():
            status_icon = "✅" if status else "⚠️"
            status_text = "ENABLED" if status else "MOCK DATA"
            print(f"   {status_icon} {service.upper()}: {status_text}")
        
        print(f"\\n📁 Configuration saved to: {self.env_file}")
        print(f"🚀 Start all services with: python scripts/start-all-services.py")
        print(f"🌐 Web interface will be at: http://localhost:3000")
        print(f"📡 API gateway will be at: http://localhost:8000")
        
        if any(self.setup_status.values()):
            print("\\n🎉 You now have REAL API integration enabled!")
            print("   The system will use live data from external services.")
        else:
            print("\\n⚠️  All services will use mock data.")
            print("   Run this script again to configure real APIs.")

if __name__ == "__main__":
    setup_manager = APISetupManager()
    setup_manager.run_setup()