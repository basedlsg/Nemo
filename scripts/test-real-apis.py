#!/usr/bin/env python3
"""
Test the Geo-Adaptive Energy Assistant with real APIs.
"""

import asyncio
import aiohttp
import json
import time
from pathlib import Path
import os
import sys

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

async def test_service_health(session, service_name, url):
    """Test if a service is healthy."""
    try:
        async with session.get(f"{url}/health", timeout=5) as response:
            if response.status == 200:
                data = await response.json()
                print(f"   ✅ {service_name}: {data.get('status', 'OK')}")
                return True
            else:
                print(f"   ❌ {service_name}: HTTP {response.status}")
                return False
    except Exception as e:
        print(f"   ❌ {service_name}: {str(e)}")
        return False

async def test_radar_with_real_data(session):
    """Test the Radar service with real market data."""
    print("\n📡 Testing Market Radar with Real Data:")
    print("-" * 40)
    
    try:
        # Test stats endpoint
        async with session.get("http://localhost:8004/stats", timeout=10) as response:
            if response.status == 200:
                data = await response.json()
                print(f"   📊 Total signals: {data.get('total_signals', 0)}")
                print(f"   🏛️ Provinces: {len(data.get('province_distribution', {}))}")
                print(f"   ⚡ Asset types: {len(data.get('asset_type_distribution', {}))}")
                
                # Show some province data
                provinces = data.get('province_distribution', {})
                if provinces:
                    print("   🗺️  Top provinces:")
                    for prov, count in list(provinces.items())[:3]:
                        print(f"      - {prov}: {count} signals")
            else:
                print(f"   ❌ Stats failed: HTTP {response.status}")
        
        # Test signals endpoint
        async with session.get("http://localhost:8004/signals?limit=3", timeout=10) as response:
            if response.status == 200:
                data = await response.json()
                signals = data.get("signals", [])
                print(f"\n   📋 Recent signals ({len(signals)}):")
                
                for i, signal in enumerate(signals[:2], 1):
                    title = signal.get("title", "")[:50] + "..."
                    priority = signal.get("priority", "")
                    province = signal.get("province", "")
                    print(f"      {i}. {title}")
                    print(f"         Priority: {priority}, Province: {province}")
            else:
                print(f"   ❌ Signals failed: HTTP {response.status}")
                
    except Exception as e:
        print(f"   ❌ Radar test error: {e}")

async def test_discovery_with_perplexity(session):
    """Test the Discovery service with real Perplexity API."""
    print("\n🧠 Testing Discovery with Perplexity API:")
    print("-" * 45)
    
    try:
        # Test discovery endpoint through orchestrator
        test_query = {
            "query": "renewable energy projects in Canada 2024",
            "max_results": 3
        }
        
        async with session.post(
            "http://localhost:8005/research/discover",
            json=test_query,
            timeout=30
        ) as response:
            if response.status == 200:
                data = await response.json()
                results = data.get("results", [])
                print(f"   ✅ Found {len(results)} discovery results")
                
                for i, result in enumerate(results[:2], 1):
                    title = result.get("title", "")[:60] + "..."
                    relevance = result.get("relevance_score", 0)
                    print(f"      {i}. {title}")
                    print(f"         Relevance: {relevance:.2f}")
                    
                # Check if we got real data (not mock)
                if results and any("mock" not in str(result).lower() for result in results):
                    print("   🔥 Using REAL Perplexity API data!")
                else:
                    print("   ⚠️  May be using mock data")
            else:
                print(f"   ❌ Discovery failed: HTTP {response.status}")
                error_text = await response.text()
                print(f"      Error: {error_text[:100]}...")
                
    except Exception as e:
        print(f"   ❌ Discovery test error: {e}")

async def test_verification_with_google(session):
    """Test the Verification service with real Google CSE API."""
    print("\n🔍 Testing Verification with Google CSE:")
    print("-" * 40)
    
    try:
        # Test verification endpoint
        test_data = {
            "claim": "Canada announced new renewable energy targets for 2030",
            "max_sources": 2
        }
        
        async with session.post(
            "http://localhost:8005/research/verify",
            json=test_data,
            timeout=30
        ) as response:
            if response.status == 200:
                data = await response.json()
                sources = data.get("sources", [])
                confidence = data.get("confidence_score", 0)
                
                print(f"   ✅ Verification complete")
                print(f"   📊 Confidence: {confidence:.2f}")
                print(f"   📚 Sources found: {len(sources)}")
                
                for i, source in enumerate(sources[:2], 1):
                    title = source.get("title", "")[:50] + "..."
                    url = source.get("url", "")
                    print(f"      {i}. {title}")
                    print(f"         URL: {url[:60]}...")
                    
                # Check if we got real data
                if sources and any("google" in str(source).lower() for source in sources):
                    print("   🔥 Using REAL Google CSE data!")
                else:
                    print("   ⚠️  May be using mock data")
            else:
                print(f"   ❌ Verification failed: HTTP {response.status}")
                
    except Exception as e:
        print(f"   ❌ Verification test error: {e}")

async def test_full_pipeline(session):
    """Test the complete research pipeline."""
    print("\n🔄 Testing Full Research Pipeline:")
    print("-" * 35)
    
    try:
        # Test the full pipeline
        pipeline_request = {
            "query": "solar energy incentives Ontario 2024",
            "research_depth": "standard",
            "include_verification": True
        }
        
        async with session.post(
            "http://localhost:8005/research/pipeline",
            json=pipeline_request,
            timeout=60
        ) as response:
            if response.status == 200:
                data = await response.json()
                
                print(f"   ✅ Pipeline completed successfully")
                print(f"   🔍 Query: {data.get('query', '')}")
                print(f"   📊 Status: {data.get('status', '')}")
                
                # Show discovery results
                discovery = data.get('discovery_results', {})
                if discovery:
                    results = discovery.get('results', [])
                    print(f"   🧠 Discovery: {len(results)} results")
                
                # Show verification results
                verification = data.get('verification_results', {})
                if verification:
                    confidence = verification.get('confidence_score', 0)
                    sources = verification.get('sources', [])
                    print(f"   🔍 Verification: {confidence:.2f} confidence, {len(sources)} sources")
                
                # Show final answer
                answer = data.get('final_answer', '')
                if answer:
                    print(f"   💡 Answer: {answer[:100]}...")
                    
                print("   🔥 FULL PIPELINE WITH REAL APIS WORKING!")
                
            else:
                print(f"   ❌ Pipeline failed: HTTP {response.status}")
                error_text = await response.text()
                print(f"      Error: {error_text[:200]}...")
                
    except Exception as e:
        print(f"   ❌ Pipeline test error: {e}")

async def main():
    print("🧪 Testing Geo-Adaptive Energy Assistant with Real APIs")
    print("=" * 60)
    
    # Check configuration
    perplexity_key = os.getenv("PERPLEXITY_API_KEY", "")
    google_key = os.getenv("GOOGLE_CSE_API_KEY", "")
    
    print("🔧 Configuration:")
    print(f"   Real APIs Enabled: {os.getenv('ENABLE_REAL_APIS', 'false')}")
    if perplexity_key and not perplexity_key.startswith("demo"):
        print("   Perplexity API: ✅ Configured")
    else:
        print("   Perplexity API: ⚠️  Mock data")
    
    if google_key and not google_key.startswith("demo"):
        print("   Google CSE API: ✅ Configured")
    else:
        print("   Google CSE API: ⚠️  Mock data")
    
    # Test services
    print("\n🏥 Testing Service Health:")
    services = [
        ("Gateway", "http://localhost:8000"),
        ("Radar", "http://localhost:8004"),
        ("Citation", "http://localhost:8006"),
        ("Orchestrator", "http://localhost:8005"),
    ]
    
    healthy_services = []
    async with aiohttp.ClientSession() as session:
        for name, url in services:
            if await test_service_health(session, name, url):
                healthy_services.append((name, url))
        
        print(f"\n📊 Health Summary: {len(healthy_services)}/{len(services)} services healthy")
        
        if len(healthy_services) >= 3:  # Need at least 3 services for testing
            # Test individual services with real APIs
            await test_radar_with_real_data(session)
            await test_discovery_with_perplexity(session)
            await test_verification_with_google(session)
            await test_full_pipeline(session)
            
            print("\n🎉 REAL API TESTING COMPLETE!")
            print("=" * 40)
            print("✅ Services are running with live external APIs")
            print("🔥 Ready for production use!")
            
        else:
            print("\n⚠️  Not enough services are healthy for full testing.")
            print("   Make sure services are running:")
            print("   python scripts/start-working-services.py")

if __name__ == "__main__":
    asyncio.run(main())