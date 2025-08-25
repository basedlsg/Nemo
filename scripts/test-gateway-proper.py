#!/usr/bin/env python3
"""
Test the gateway with the proper request format.
"""

import asyncio
import aiohttp
import subprocess
import time
import os
import sys
import json
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

async def test_gateway_with_proper_format(session):
    """Test gateway with the correct Chinese format."""
    print("🌐 Testing Gateway with Proper Format:")
    
    # Correct format based on the models
    test_query = {
        "question": "广东省太阳能发电项目的并网规则是什么？",
        "province": "guangdong",
        "doc_class": "grid_connection",
        "asset": "solar",
        "lang": "zh-CN",
        "max_citations": 5
    }
    
    try:
        async with session.post(
            "http://localhost:8000/query",
            json=test_query,
            timeout=30
        ) as response:
            print(f"   Status: {response.status}")
            
            if response.status == 200:
                data = await response.json()
                print("   ✅ Gateway query successful!")
                
                # Show response details
                if 'answer_zh' in data:
                    answer = data['answer_zh'][:100] + "..."
                    print(f"   💡 Answer: {answer}")

                if 'citations' in data:
                    citations = data['citations']
                    print(f"   📚 Citations: {len(citations)}")
                    for i, citation in enumerate(citations[:2]):
                        print(f"      {i+1}. {citation.get('title', 'No title')}")

                if 'total_citations' in data:
                    print(f"   📊 Total Citations: {data['total_citations']}")

                if 'processing_time_ms' in data:
                    print(f"   ⚡ Processing Time: {data['processing_time_ms']}ms")
                
                return True
            else:
                error_text = await response.text()
                print(f"   ❌ Error {response.status}: {error_text[:200]}...")
                return False
                
    except Exception as e:
        print(f"   ❌ Exception: {e}")
        return False

async def test_simple_endpoints(session):
    """Test simple endpoints that should work."""
    print("\n🏥 Testing Simple Endpoints:")
    
    endpoints = [
        ("Gateway Health", "http://localhost:8000/health"),
        ("Gateway Stats", "http://localhost:8000/stats"),
        ("Radar Health", "http://localhost:8004/health"),
        ("Radar Stats", "http://localhost:8004/stats"),
        ("Citation Health", "http://localhost:8006/health"),
        ("Orchestrator Health", "http://localhost:8005/health"),
    ]
    
    results = {}
    for name, url in endpoints:
        try:
            async with session.get(url, timeout=10) as response:
                if response.status == 200:
                    print(f"   ✅ {name}: OK")
                    results[name] = True
                else:
                    print(f"   ❌ {name}: HTTP {response.status}")
                    results[name] = False
        except Exception as e:
            print(f"   ❌ {name}: {str(e)[:50]}...")
            results[name] = False
    
    return results

def start_services():
    """Start the services."""
    services = [
        {"name": "Gateway", "module": "services.gateway.api", "port": 8000},
        {"name": "Radar", "module": "services.radar.api", "port": 8004},
        {"name": "Citation", "module": "services.citation.api", "port": 8006},
        {"name": "Orchestrator", "module": "services.orchestrator.api", "port": 8005},
    ]
    
    processes = []
    
    print("🚀 Starting Services:")
    for service in services:
        print(f"   Starting {service['name']} on port {service['port']}...")
        
        cmd = [
            sys.executable, "-m", "uvicorn",
            f"{service['module']}:app",
            "--host", "0.0.0.0",
            "--port", str(service['port']),
            "--log-level", "error"
        ]
        
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        processes.append(proc)
        time.sleep(2)
    
    return processes

def cleanup(processes):
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

async def main():
    print("🧪 Testing Gateway with Proper Format")
    print("=" * 40)
    
    # Check API keys
    perplexity_key = os.getenv("PERPLEXITY_API_KEY", "")
    google_key = os.getenv("GOOGLE_CSE_API_KEY", "")
    
    print("🔧 Configuration:")
    if perplexity_key and not perplexity_key.startswith("demo"):
        print(f"   ✅ Perplexity: {perplexity_key[:10]}...")
    else:
        print("   ❌ Perplexity: Not configured")
    
    if google_key and not google_key.startswith("demo"):
        print(f"   ✅ Google CSE: {google_key[:10]}...")
    else:
        print("   ❌ Google CSE: Not configured")
    
    # Start services
    processes = start_services()
    
    try:
        print("   ⏳ Waiting for services to initialize...")
        time.sleep(8)
        
        async with aiohttp.ClientSession() as session:
            # Test simple endpoints first
            endpoint_results = await test_simple_endpoints(session)
            
            # Test gateway with proper format
            gateway_success = await test_gateway_with_proper_format(session)
            
            # Summary
            print(f"\n📊 Results:")
            healthy_endpoints = sum(endpoint_results.values())
            print(f"   Simple endpoints: {healthy_endpoints}/{len(endpoint_results)} working")
            print(f"   Gateway query: {'✅' if gateway_success else '❌'}")
            
            if gateway_success:
                print("\n🎉 SUCCESS! Gateway is working with real APIs!")
                print("🔥 System ready for Chinese energy regulation queries!")
            elif healthy_endpoints >= 4:
                print("\n⚠️  Services are healthy but gateway query needs debugging")
            else:
                print("\n❌ Multiple service issues detected")
    
    finally:
        print("\n🧹 Cleaning up...")
        cleanup(processes)
        print("✅ Done!")

if __name__ == "__main__":
    asyncio.run(main())