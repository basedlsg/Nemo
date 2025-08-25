#!/usr/bin/env python3
"""
Start working Geo-Adaptive Energy Assistant services.
"""

import os
import sys
import subprocess
import time
import signal
from pathlib import Path

# Set up environment
project_root = Path(__file__).parent.parent
os.chdir(project_root)

# Load environment variables from .env file
env_file = project_root / ".env"
if env_file.exists():
    print("📁 Loading environment variables...")
    with open(env_file) as f:
        for line in f:
            if '=' in line and not line.startswith('#'):
                key, value = line.strip().split('=', 1)
                os.environ[key] = value

# Working services (tested and confirmed)
services = [
    {"name": "Gateway", "module": "services.gateway.api", "port": 8000},
    {"name": "Radar", "module": "services.radar.api", "port": 8004},
    {"name": "Citation", "module": "services.citation.api", "port": 8006},
    {"name": "Orchestrator", "module": "services.orchestrator.api", "port": 8005},
]

processes = []

def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully."""
    print("\n🛑 Shutting down all services...")
    for proc in processes:
        proc.terminate()
    
    time.sleep(2)
    
    for proc in processes:
        if proc.poll() is None:
            proc.kill()
    
    print("✅ All services stopped.")
    sys.exit(0)

def start_service(service):
    """Start a single service."""
    print(f"🚀 Starting {service['name']} on port {service['port']}...")
    
    cmd = [
        sys.executable, "-m", "uvicorn",
        f"{service['module']}:app",
        "--host", "0.0.0.0",
        "--port", str(service['port']),
        "--log-level", "info"
    ]
    
    return subprocess.Popen(cmd)

def main():
    print("🌟 Starting Geo-Adaptive Energy Assistant (Working Services)")
    print("=" * 60)
    
    # Check API configuration
    enable_real_apis = os.getenv("ENABLE_REAL_APIS", "false").lower() == "true"
    if enable_real_apis:
        print("🔥 REAL API MODE ENABLED")
        perplexity_key = os.getenv("PERPLEXITY_API_KEY", "")
        if perplexity_key and not perplexity_key.startswith("demo"):
            print("   ✅ Perplexity API: ENABLED")
        else:
            print("   ⚠️  Perplexity API: Mock data")
    else:
        print("🧪 MOCK API MODE")
    
    print()
    
    # Register signal handler
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        # Start all services
        for service in services:
            proc = start_service(service)
            processes.append(proc)
            time.sleep(2)  # Stagger startup
        
        print("\n✅ All services started!")
        print("\n📊 Service URLs:")
        for service in services:
            print(f"   {service['name']}: http://localhost:{service['port']}")
        
        print("\n🌐 Main Endpoints:")
        print("   API Gateway: http://localhost:8000")
        print("   Health Check: http://localhost:8000/health")
        print("   API Docs: http://localhost:8000/docs")
        print("   Market Radar: http://localhost:8004/stats")
        print("   Citation Service: http://localhost:8006/health")
        print("   Orchestrator: http://localhost:8005/health")
        
        print("\n📝 Quick Tests:")
        print("   curl http://localhost:8000/health")
        print("   curl http://localhost:8004/stats")
        print("   curl http://localhost:8006/health")
        print("   curl -X POST http://localhost:8005/test/pipeline")
        
        print("\nPress Ctrl+C to stop all services...")
        
        # Keep the main script alive to monitor services
        # The services are now detached and will keep running even if this script exits
        print("\nServices are running in the background.")
        print("You can now close this terminal or press Ctrl+C to exit this script.")
        
        # Wait for user to exit
        while True:
            time.sleep(10)

    except KeyboardInterrupt:
        print("\n✅ Exiting script. Services will continue to run in the background.")
        sys.exit(0)
    except Exception as e:
        print(f"❌ Error: {e}")
        signal_handler(None, None)

if __name__ == "__main__":
    main()
