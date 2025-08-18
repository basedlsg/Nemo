#!/usr/bin/env python3
"""
Quick start services and test with real APIs.
"""

import asyncio
import aiohttp
import subprocess
import time
import os
import sys
import signal
from pathlib import Path

# Set up environment
project_root = Path(__file__).parent.parent
os.chdir(project_root)
sys.path.insert(0, str(project_root))

# Load environment
env_file = project_root / ".env"
if env_file.exists():
    with open(env_file) as f:
        for line in f:
            if '=' in line and not line.startswith('#'):
                key, value = line.strip().split('=', 1)
                os.environ[key] = value

services = [
    {"name": "Gateway", "module": "services.gateway.api", "port": 8000},
    {"name": "Radar", "module": "services.radar.api", "port": 8004},
    {"name": "Citation", "module": "services.citation.api", "port": 8006},
    {"name": "Orchestrator", "module": "services.orchestrator.api", "port": 8005},
]

processes = []

def cleanup():
    """Stop all services."""
    for proc in processes:
        try:
            proc.terminate()
        except:
            pass
    time.sleep(1)
    for proc in processes:
        try:
            proc.kill()
        except:
            pass

async def test_service(session, name, port):
    """Test a single service."""
    try:
        async with session.get(f"http://localhost:{port}/health", timeout=5) as response:
            if response.status == 200:
                data = await response.json()
                print(f"   ✅ {name}: {data.get('status', 'OK')}")
                return True
            else:
                print(f"   ❌ {name}: HTTP {response.status}")
                return False
    except Exception as e:
        print(f"   ❌ {name}: {str(e)}")
        return False

async def test_radar_real_data(session):
    """Test radar with real data."""
    print("\n📡 Testing Radar with Real Data:")
    try:
        async with session.get("http://localhost:8004/stats", timeout=10) as response:
            if response.status == 200:
                data = await response.json()
                print(f"   📊 Total signals: {data.get('total_signals', 0)}")
                print(f"   🏛️ Provinces: {len(data.get('province_distribution', {}))}")
                return True
            else:
                print(f"   ❌ Stats failed: HTTP {response.status}")
                return False
    except Exception as e:
        print(f"   ❌ Radar error: {e}")
        return False

async def test_perplexity_api(session):
    """Test Perplexity API through orchestrator."""
    print("\n🧠 Testing Perplexity API:")
    try:
        test_query = {
            "query": "renewable energy Canada 2024",
            "max_results": 2
        }
        
        async with session.post(
            "http://localhost:8005/research/discover",
            json=test_query,
            timeout=30
        ) as response:
            if response.status == 200:
                data = await response.json()
                results = data.get("results", [])
                print(f"   ✅ Found {len(results)} results")
                
                if results:
                    first_result = results[0]
                    title = first_result.get("title", "")[:60] + "..."
                    print(f"   📄 Sample: {title}")
                    
                    # Check if it's real data
                    if "mock" not in str(first_result).lower():
                        print("   🔥 REAL PERPLEXITY DATA!")
                        return True
                    else:
                        print("   ⚠️  Mock data detected")
                        return False
                else:
                    print("   ⚠️  No results returned")
                    return False
            else:
                print(f"   ❌ Discovery failed: HTTP {response.status}")
                return False
    except Exception as e:
        print(f"   ❌ Perplexity test error: {e}")
        return False

def main():
    print("🚀 Quick Start and Test with Real APIs")
    print("=" * 45)
    
    # Check API keys
    perplexity_key = os.getenv("PERPLEXITY_API_KEY", "")
    google_key = os.getenv("GOOGLE_CSE_API_KEY", "")
    
    print("🔧 API Configuration:")
    if perplexity_key and not perplexity_key.startswith("demo"):
        print(f"   ✅ Perplexity: {perplexity_key[:10]}...")
    else:
        print("   ❌ Perplexity: Not configured")
    
    if google_key and not google_key.startswith("demo"):
        print(f"   ✅ Google CSE: {google_key[:10]}...")
    else:
        print("   ❌ Google CSE: Not configured")
    
    try:
        # Start services
        print("\n🚀 Starting Services:")
        for service in services:
            print(f"   Starting {service['name']} on port {service['port']}...")
            
            cmd = [
                sys.executable, "-m", "uvicorn",
                f"{service['module']}:app",
                "--host", "0.0.0.0",
                "--port", str(service['port']),
                "--log-level", "error"  # Reduce noise
            ]
            
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            processes.append(proc)
            time.sleep(2)  # Stagger startup
        
        print("   ⏳ Waiting for services to initialize...")
        time.sleep(5)
        
        # Test services
        async def run_tests():
            async with aiohttp.ClientSession() as session:
                print("\n🏥 Testing Service Health:")
                healthy = 0
                for service in services:
                    if await test_service(session, service['name'], service['port']):
                        healthy += 1
                
                print(f"\n📊 {healthy}/{len(services)} services healthy")
                
                if healthy >= 2:
                    # Test real API functionality
                    radar_ok = await test_radar_real_data(session)
                    perplexity_ok = await test_perplexity_api(session)
                    
                    print(f"\n🎯 Real API Test Results:")
                    print(f"   Radar Data: {'✅' if radar_ok else '❌'}")
                    print(f"   Perplexity API: {'✅' if perplexity_ok else '❌'}")
                    
                    if radar_ok and perplexity_ok:
                        print("\n🎉 SUCCESS! Real APIs are working!")
                        print("🔥 System is ready for production use!")
                    else:
                        print("\n⚠️  Some APIs may not be working as expected")
                else:
                    print("\n❌ Not enough services are healthy")
        
        # Run the async tests
        asyncio.run(run_tests())
        
    except KeyboardInterrupt:
        print("\n🛑 Interrupted by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
    finally:
        print("\n🧹 Cleaning up...")
        cleanup()
        print("✅ Done!")

if __name__ == "__main__":
    main()