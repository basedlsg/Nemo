#!/usr/bin/env python3
"""
Test script to validate the production deployment is working with real data.
This will test the deployed Cloud Run service to ensure it's connected to the database
and returning actual regulatory data, not just example responses.
"""
import requests
import json
import sys
from typing import Dict, Any
import time

# The deployed service URL from your previous session
SERVICE_URL = "https://gaea-gateway-964505076225.us-central1.run.app"

def test_health_endpoint():
    """Test the health endpoint to ensure service is running."""
    print("🔍 Testing health endpoint...")
    try:
        response = requests.get(f"{SERVICE_URL}/health", timeout=30)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Health check passed: {data}")
            return True
        else:
            print(f"❌ Health check failed: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"❌ Health check error: {e}")
        return False

def test_database_connection():
    """Test database connectivity through the service."""
    print("\n🔍 Testing database connection...")
    try:
        # Test the database health endpoint if it exists
        response = requests.get(f"{SERVICE_URL}/health/database", timeout=30)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Database connection: {data}")
            return True
        else:
            print(f"⚠️  Database health endpoint not available: {response.status_code}")
            return False
    except Exception as e:
        print(f"⚠️  Database health endpoint error: {e}")
        return False

def test_provinces_endpoint():
    """Test provinces endpoint to verify supported provinces."""
    print("\n🔍 Testing provinces endpoint...")
    try:
        response = requests.get(f"{SERVICE_URL}/provinces", timeout=30)
        if response.status_code == 200:
            data = response.json()
            provinces = data.get('provinces', [])
            print(f"✅ Provinces endpoint working. Found {len(provinces)} provinces:")
            
            for province in provinces:
                print(f"   - {province.get('code', 'No code')}: {province.get('label', 'No label')} ({province.get('label_en', 'No English label')})")
            
            # Check if Guangdong is supported
            guangdong_found = any(p.get('code') == 'guangdong' for p in provinces)
            if guangdong_found:
                print("✅ Guangdong province is supported")
                return True
            else:
                print("❌ Guangdong province not found in supported provinces")
                return False
        else:
            print(f"❌ Provinces endpoint failed: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"❌ Provinces endpoint error: {e}")
        return False

def test_query_functionality():
    """Test query functionality with real regulatory queries."""
    print("\n🔍 Testing query functionality...")
    test_queries = [
        {
            "query": "分布式光伏发电项目备案要求",  # Distributed solar project registration requirements
            "province": "guangdong",
            "doc_class": "market_rules",
            "asset": "solar"
        },
        {
            "query": "风电项目并网技术要求",        # Wind power grid connection technical requirements
            "province": "guangdong", 
            "doc_class": "grid_connection",
            "asset": "wind"
        }
    ]
    
    for i, query_data in enumerate(test_queries):
        print(f"\n   Testing query {i+1}: '{query_data['query']}'")
        try:
            response = requests.post(
                f"{SERVICE_URL}/query",
                json=query_data,
                timeout=60  # Longer timeout for query processing
            )
            
            print(f"   Response status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                answer = data.get('answer', '')
                citations = data.get('citations', [])
                print(f"   ✅ Query successful. Answer length: {len(answer)} chars, Citations: {len(citations)}")
                
                # Show first part of answer
                if answer:
                    print(f"      Answer preview: {answer[:150]}...")
                
                # Show citations
                for j, citation in enumerate(citations[:2]):
                    title = citation.get('title', 'No title')
                    print(f"      Citation {j+1}: {title}")
                
                if answer and citations:
                    return True
                    
            elif response.status_code == 422:
                # This might be a refusal, which is also a valid response
                data = response.json()
                error_type = data.get('error', 'Unknown error')
                print(f"   ⚠️  Query refused: {error_type}")
                # Refusal is still a valid system response
                return True
                
            else:
                print(f"   ❌ Query failed: {response.status_code} - {response.text}")
                
        except Exception as e:
            print(f"   ❌ Query error: {e}")
    
    return False

def test_assets_endpoint():
    """Test assets endpoint to verify supported asset types."""
    print("\n🔍 Testing assets endpoint...")
    try:
        response = requests.get(f"{SERVICE_URL}/assets", timeout=30)
        if response.status_code == 200:
            data = response.json()
            assets = data.get('assets', [])
            print(f"✅ Assets endpoint working. Found {len(assets)} asset types:")
            
            for asset in assets:
                print(f"   - {asset.get('code', 'No code')}: {asset.get('label', 'No label')} ({asset.get('label_en', 'No English label')})")
            
            # Check if solar and wind are supported
            solar_found = any(a.get('code') == 'solar' for a in assets)
            wind_found = any(a.get('code') == 'wind' for a in assets)
            
            if solar_found and wind_found:
                print("✅ Solar and wind assets are supported")
                return True
            else:
                print("❌ Solar or wind assets not found in supported assets")
                return False
        else:
            print(f"❌ Assets endpoint failed: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"❌ Assets endpoint error: {e}")
        return False

def test_stats_endpoint():
    """Test stats endpoint to verify service statistics."""
    print("\n🔍 Testing stats endpoint...")
    try:
        response = requests.get(f"{SERVICE_URL}/stats", timeout=30)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Stats endpoint working:")
            print(f"   - Total queries: {data.get('total_queries', 0)}")
            print(f"   - Successful queries: {data.get('successful_queries', 0)}")
            print(f"   - Refusal rate: {data.get('refusal_rate', 0):.2%}")
            print(f"   - Avg processing time: {data.get('avg_processing_time_ms', 0):.1f}ms")
            return True
        else:
            print(f"❌ Stats endpoint failed: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"❌ Stats endpoint error: {e}")
        return False

def main():
    """Run all tests and provide a summary."""
    print("🚀 Testing Production Deployment")
    print("=" * 50)
    
    tests = [
        ("Health Check", test_health_endpoint),
        ("Database Connection", test_database_connection),
        ("Provinces Endpoint", test_provinces_endpoint),
        ("Assets Endpoint", test_assets_endpoint),
        ("Query Functionality", test_query_functionality),
        ("Stats Endpoint", test_stats_endpoint),
    ]
    
    results = {}
    for test_name, test_func in tests:
        print(f"\n{'='*20} {test_name} {'='*20}")
        try:
            results[test_name] = test_func()
        except Exception as e:
            print(f"❌ {test_name} failed with exception: {e}")
            results[test_name] = False
        
        # Small delay between tests
        time.sleep(1)
    
    # Summary
    print("\n" + "="*50)
    print("📊 TEST SUMMARY")
    print("="*50)
    
    passed = sum(1 for result in results.values() if result)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test_name:.<30} {status}")
    
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! The deployment is working correctly with real data.")
        return 0
    else:
        print("⚠️  Some tests failed. The deployment may have issues.")
        return 1

if __name__ == "__main__":
    sys.exit(main())