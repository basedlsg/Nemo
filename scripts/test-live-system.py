#!/usr/bin/env python3
"""
Test the live Geo-Adaptive Energy Assistant system with real APIs.
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

async def test_gateway_query(session):
    """Test the main gateway query endpoint."""
    print("\n🌐 Testing Gateway Query Processing:")
    try:
        test_query = {
            "query": "What are the latest renewable energy projects in Ontario?",
            "context": {
                "user_location": "Ontario, Canada",
                "research_depth": "standard"
            }
        }
        
        async with session.post(
            "http://localhost:8000/query",
            json=test_query,
            timeout=45
        ) as response:
            if response.status == 200:
                data = await response.json()
                print(f"   ✅ Query processed successfully")
                print(f"   📝 Response type: {data.get('response_type', 'unknown')}")
                
                answer = data.get('answer', '')
                if answer:
                    print(f"   💡 Answer preview: {answer[:100]}...")
                
                sources = data.get('sources', [])
                if sources:
                    print(f"   📚 Sources found: {len(sources)}")
                    for i, source in enumerate(sources[:2], 1):
                        title = source.get('title', '')[:50] + "..."
                        print(f"      {i}. {title}")
                
                # Check if real APIs were used
                metadata = data.get('metadata', {})
                if metadata.get('used_real_apis'):
                    print("   🔥 REAL APIS WERE USED!")
                    return True
                else:
                    print("   ⚠️  Mock data may have been used")
                    return False
            else:
                print(f"   ❌ Query failed: HTTP {response.status}")
                error_text = await response.text()
                print(f"      Error: {error_text[:150]}...")
                return False
    except Exception as e:
        print(f"   ❌ Gateway test error: {e}")
        return False

async def test_radar_market_data(session):
    """Test the radar market signals."""
    print("\n📡 Testing Market Radar:")
    try:
        # Test market signals
        async with session.get("http://localhost:8004/signals?limit=5", timeout=10) as response:
            if response.status == 200:
                data = await response.json()
                signals = data.get("signals", [])
                total = data.get("total_count", 0)
                
                print(f"   ✅ Found {total} total market signals")
                print(f"   📋 Showing {len(signals)} recent signals:")
                
                for i, signal in enumerate(signals[:3], 1):
                    title = signal.get("title", "")[:60] + "..."
                    priority = signal.get("priority", "")
                    province = signal.get("province", "")
                    asset_type = signal.get("asset_type", "")
                    
                    print(f"      {i}. {title}")
                    print(f"         {priority} priority | {province} | {asset_type}")
                
                return len(signals) > 0
            else:
                print(f"   ❌ Radar failed: HTTP {response.status}")
                return False
    except Exception as e:
        print(f"   ❌ Radar test error: {e}")
        return False

async def test_citation_generation(session):
    """Test citation pack generation."""
    print("\n📄 Testing Citation Generation:")
    try:
        citation_request = {
            "sources": [
                {
                    "title": "Ontario Renewable Energy Incentives 2024",
                    "url": "https://example.com/ontario-renewable-2024",
                    "content": "Ontario has announced new incentives for renewable energy projects...",
                    "publication_date": "2024-01-15",
                    "author": "Ontario Energy Ministry"
                },
                {
                    "title": "Solar Power Growth in Canada",
                    "url": "https://example.com/solar-canada-growth",
                    "content": "Solar power installations have increased by 25% in Canada...",
                    "publication_date": "2024-02-01",
                    "author": "Canadian Solar Association"
                }
            ],
            "query": "renewable energy incentives Ontario",
            "format_type": "html"
        }
        
        async with session.post(
            "http://localhost:8006/generate",
            json=citation_request,
            timeout=30
        ) as response:
            if response.status == 200:
                data = await response.json()
                print(f"   ✅ Citation pack generated successfully")
                
                pack_id = data.get('pack_id', '')
                if pack_id:
                    print(f"   📦 Pack ID: {pack_id}")
                
                download_url = data.get('download_url', '')
                if download_url:
                    print(f"   🔗 Download URL: {download_url}")
                
                return True
            else:
                print(f"   ❌ Citation generation failed: HTTP {response.status}")
                return False
    except Exception as e:
        print(f"   ❌ Citation test error: {e}")
        return False

async def test_orchestrator_pipeline(session):
    """Test the orchestrator research pipeline."""
    print("\n🔄 Testing Research Pipeline:")
    try:
        # Test the pipeline endpoint
        pipeline_request = {
            "query": "wind energy projects British Columbia 2024",
            "research_depth": "quick",
            "max_sources": 3
        }
        
        async with session.post(
            "http://localhost:8005/test/pipeline",
            json=pipeline_request,
            timeout=60
        ) as response:
            if response.status == 200:
                data = await response.json()
                print(f"   ✅ Pipeline test completed")
                print(f"   📊 Status: {data.get('status', 'unknown')}")
                
                # Show pipeline steps
                steps = data.get('pipeline_steps', [])
                if steps:
                    print(f"   🔧 Pipeline steps executed: {len(steps)}")
                    for step in steps[:3]:
                        step_name = step.get('step', '')
                        step_status = step.get('status', '')
                        print(f"      - {step_name}: {step_status}")
                
                # Check for real API usage
                used_real_apis = data.get('used_real_apis', False)
                if used_real_apis:
                    print("   🔥 REAL APIS USED IN PIPELINE!")
                    return True
                else:
                    print("   ⚠️  Pipeline may have used mock data")
                    return False
            else:
                print(f"   ❌ Pipeline test failed: HTTP {response.status}")
                return False
    except Exception as e:
        print(f"   ❌ Pipeline test error: {e}")
        return False

def main():
    print("🚀 Live System Test with Real APIs")
    print("=" * 40)
    
    # Check API configuration
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
                "--log-level", "error"
            ]
            
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            processes.append(proc)
            time.sleep(2)
        
        print("   ⏳ Waiting for services to initialize...")
        time.sleep(8)
        
        # Run comprehensive tests
        async def run_tests():
            async with aiohttp.ClientSession() as session:
                print("\n🧪 Running Comprehensive Tests:")
                
                # Test each component
                gateway_ok = await test_gateway_query(session)
                radar_ok = await test_radar_market_data(session)
                citation_ok = await test_citation_generation(session)
                orchestrator_ok = await test_orchestrator_pipeline(session)
                
                # Summary
                print(f"\n📊 Test Results Summary:")
                print(f"   Gateway Query: {'✅' if gateway_ok else '❌'}")
                print(f"   Market Radar: {'✅' if radar_ok else '❌'}")
                print(f"   Citation Generation: {'✅' if citation_ok else '❌'}")
                print(f"   Research Pipeline: {'✅' if orchestrator_ok else '❌'}")
                
                total_passed = sum([gateway_ok, radar_ok, citation_ok, orchestrator_ok])
                
                if total_passed >= 3:
                    print(f"\n🎉 SUCCESS! {total_passed}/4 components working!")
                    print("🔥 System is operational with real APIs!")
                    
                    if gateway_ok and orchestrator_ok:
                        print("\n🌟 FULL PIPELINE OPERATIONAL!")
                        print("   Ready for production queries!")
                elif total_passed >= 2:
                    print(f"\n⚠️  Partial success: {total_passed}/4 components working")
                    print("   System has basic functionality")
                else:
                    print(f"\n❌ System issues: Only {total_passed}/4 components working")
        
        # Run the tests
        asyncio.run(run_tests())
        
    except KeyboardInterrupt:
        print("\n🛑 Interrupted by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
    finally:
        print("\n🧹 Cleaning up...")
        cleanup()
        print("✅ Test complete!")

if __name__ == "__main__":
    main()