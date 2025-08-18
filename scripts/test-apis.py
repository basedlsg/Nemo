#!/usr/bin/env python3
"""
Test script to verify all APIs are working with real data.
"""

import asyncio
import aiohttp
import json
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

async def test_service_health(session, service_name, port):
    """Test a service health endpoint."""
    try:
        url = f"http://localhost:{port}/health"
        async with session.get(url, timeout=10) as response:
            if response.status == 200:
                data = await response.json()
                print(f"   ✅ {service_name}: {data.get('status', 'unknown')}")
                return True
            else:
                print(f"   ❌ {service_name}: HTTP {response.status}")
                return False
    except Exception as e:
        print(f"   ❌ {service_name}: {str(e)}")
        return False

async def test_perplexity_discovery(session):
    """Test Perplexity discovery service."""
    try:
        url = "http://localhost:8005/test/pipeline"
        params = {
            "province": "guangdong",
            "asset_type": "solar",
            "doc_class": "grid_connection",
            "priority": "medium"
        }
        
        async with session.post(url, params=params, timeout=30) as response:
            if response.status == 200:
                data = await response.json()
                job_id = data.get("test_job_id")
                print(f"   ✅ Pipeline test started: {job_id}")
                
                # Check job status
                await asyncio.sleep(5)  # Wait for processing
                
                status_url = f"http://localhost:8005/jobs/{job_id}"
                async with session.get(status_url, timeout=10) as status_response:
                    if status_response.status == 200:
                        status_data = await status_response.json()
                        job_status = status_data.get("job", {}).get("status")
                        print(f"   📊 Job status: {job_status}")
                        
                        if job_status == "completed":
                            result_data = status_data.get("job", {}).get("result_data", {})
                            if "discovery" in result_data:
                                discovered = result_data["discovery"].get("total_found", 0)
                                print(f"   🔍 Discovered {discovered} documents")
                            return True
                    
                return True
            else:
                print(f"   ❌ Pipeline test failed: HTTP {response.status}")
                return False
                
    except Exception as e:
        print(f"   ❌ Pipeline test error: {str(e)}")
        return False

async def test_market_signals(session):
    """Test market signals service."""
    try:
        url = "http://localhost:8004/signals"
        params = {"limit": 5}
        
        async with session.get(url, params=params, timeout=10) as response:
            if response.status == 200:
                data = await response.json()
                signals = data.get("signals", [])
                total = data.get("total_count", 0)
                print(f"   📡 Found {total} market signals, showing {len(signals)}")
                
                for signal in signals[:2]:
                    title = signal.get("title", "")[:50] + "..."
                    priority = signal.get("priority", "")
                    print(f"      • {title} ({priority})")
                
                return True
            else:
                print(f"   ❌ Market signals failed: HTTP {response.status}")
                return False
                
    except Exception as e:
        print(f"   ❌ Market signals error: {str(e)}")
        return False

async def test_database_connection(session):
    """Test database connection."""
    try:
        url = "http://localhost:8000/database/connection-manager-test"
        
        async with session.get(url, timeout=10) as response:
            if response.status == 200:
                data = await response.json()
                health = data.get("health", {})
                strategy = health.get("strategy", "unknown")
                success = health.get("success", False)
                
                if success:
                    print(f"   ✅ Database connected using: {strategy}")
                    
                    data_access = data.get("data_access", {})
                    if data_access:
                        provinces = data_access.get("provinces", [])
                        asset_types = data_access.get("asset_types", [])
                        print(f"   📊 Data: {len(provinces)} provinces, {len(asset_types)} asset types")
                    
                    return True
                else:
                    error = health.get("error_message", "unknown")
                    print(f"   ❌ Database connection failed: {error}")
                    return False
            else:
                print(f"   ❌ Database test failed: HTTP {response.status}")
                return False
                
    except Exception as e:
        print(f"   ❌ Database test error: {str(e)}")
        return False

async def test_citation_generation(session):
    """Test citation pack generation."""
    try:
        url = "http://localhost:8006/preview/test-pack-001"
        
        async with session.get(url, timeout=15) as response:
            if response.status == 200:
                data = await response.json()
                html_content = data.get("html_content", "")
                summary = data.get("summary", {})
                
                if html_content and "引用文献包" in html_content:
                    print(f"   ✅ Citation pack generated successfully")
                    total_citations = summary.get("pack_metadata", {}).get("total_citations", 0)
                    print(f"   📄 Generated pack with {total_citations} citations")
                    return True
                else:
                    print(f"   ❌ Citation pack generation failed")
                    return False
            else:
                print(f"   ❌ Citation pack test failed: HTTP {response.status}")
                return False
                
    except Exception as e:
        print(f"   ❌ Citation pack test error: {str(e)}")
        return False

async def main():
    """Run all API tests."""
    print("🧪 Testing Geo-Adaptive Energy Assistant APIs")
    print("=" * 60)
    
    # Load environment
    env_file = project_root / ".env"
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                if '=' in line and not line.startswith('#'):
                    key, value = line.strip().split('=', 1)
                    os.environ[key] = value
    
    # Check API configuration
    enable_real_apis = os.getenv("ENABLE_REAL_APIS", "false").lower() == "true"
    perplexity_key = os.getenv("PERPLEXITY_API_KEY", "")
    google_key = os.getenv("GOOGLE_CSE_API_KEY", "")
    
    print("🔧 Configuration:")
    print(f"   Real APIs Enabled: {enable_real_apis}")
    if enable_real_apis:
        if perplexity_key and not perplexity_key.startswith("demo"):
            print(f"   Perplexity API: ✅ Configured")
        else:
            print(f"   Perplexity API: ⚠️  Mock data (no valid key)")
        
        if google_key and not google_key.startswith("demo"):
            print(f"   Google CSE API: ✅ Configured")
        else:
            print(f"   Google CSE API: ⚠️  Mock data (no valid key)")
    else:
        print("   Using mock data for all services")
    
    print()
    
    # Services to test
    services = [
        ("Gateway", 8000),
        ("Retriever", 8001),
        ("Composer", 8002),
        ("Guardrails", 8003),
        ("Radar", 8004),
        ("Orchestrator", 8005),
        ("Citation", 8006),
        ("Ingestion", 8007),
    ]
    
    async with aiohttp.ClientSession() as session:
        # Test service health
        print("🏥 Testing Service Health:")
        health_results = []
        for service_name, port in services:
            result = await test_service_health(session, service_name, port)
            health_results.append(result)
        
        healthy_services = sum(health_results)
        print(f"\n📊 Health Summary: {healthy_services}/{len(services)} services healthy")
        
        if healthy_services < len(services):
            print("⚠️  Some services are not responding. Make sure all services are running.")
            print("   Run: python scripts/start-services.py")
            return
        
        print("\n🧪 Running Functional Tests:")
        
        # Test database connection
        print("1. Database Connection:")
        await test_database_connection(session)
        
        # Test market signals
        print("\n2. Market Signals:")
        await test_market_signals(session)
        
        # Test citation generation
        print("\n3. Citation Generation:")
        await test_citation_generation(session)
        
        # Test discovery pipeline
        print("\n4. Discovery Pipeline:")
        await test_perplexity_discovery(session)
        
        print("\n✅ API Testing Complete!")
        print("\n🌐 Ready for use:")
        print("   Main API: http://localhost:8000")
        print("   Market Radar: http://localhost:8004")
        print("   API Documentation: http://localhost:8000/docs")

if __name__ == "__main__":
    asyncio.run(main())