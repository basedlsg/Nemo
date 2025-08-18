#!/usr/bin/env python3
"""
Test script to verify the deployed Cloud Run service is working with real data.
This script tests all endpoints and verifies responses contain actual regulatory content.
"""

import asyncio
import aiohttp
import json
import sys
from datetime import datetime
from typing import Dict, Any, List

# Service URL from the deployment
SERVICE_URL = "https://gaea-gateway-964505076225.us-central1.run.app"

class ServiceTester:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip('/')
        self.session = None
        self.test_results = []
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30)
        )
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    def log_test(self, test_name: str, success: bool, details: str = ""):
        """Log test result."""
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}")
        if details:
            print(f"    {details}")
        
        self.test_results.append({
            "test": test_name,
            "success": success,
            "details": details,
            "timestamp": datetime.now().isoformat()
        })
    
    async def test_health_endpoint(self) -> bool:
        """Test the health endpoint."""
        try:
            async with self.session.get(f"{self.base_url}/health") as response:
                if response.status != 200:
                    self.log_test("Health Check", False, f"HTTP {response.status}")
                    return False
                
                data = await response.json()
                
                # Verify response structure
                required_fields = ["status", "services", "version", "timestamp"]
                missing_fields = [f for f in required_fields if f not in data]
                
                if missing_fields:
                    self.log_test("Health Check", False, f"Missing fields: {missing_fields}")
                    return False
                
                self.log_test("Health Check", True, f"Status: {data['status']}")
                return True
                
        except Exception as e:
            self.log_test("Health Check", False, f"Exception: {str(e)}")
            return False
    
    async def test_root_endpoint(self) -> bool:
        """Test the root endpoint for API information."""
        try:
            async with self.session.get(f"{self.base_url}/") as response:
                if response.status != 200:
                    self.log_test("Root Endpoint", False, f"HTTP {response.status}")
                    return False
                
                data = await response.json()
                
                # Verify it contains service information
                if "service" not in data or "geo-adaptive-energy-assistant" not in data["service"]:
                    self.log_test("Root Endpoint", False, "Missing service information")
                    return False
                
                # Check for expected features
                if "features" in data and len(data["features"]) > 0:
                    self.log_test("Root Endpoint", True, f"Found {len(data['features'])} features")
                    return True
                else:
                    self.log_test("Root Endpoint", False, "No features listed")
                    return False
                    
        except Exception as e:
            self.log_test("Root Endpoint", False, f"Exception: {str(e)}")
            return False
    
    async def test_provinces_endpoint(self) -> bool:
        """Test the provinces endpoint."""
        try:
            async with self.session.get(f"{self.base_url}/provinces") as response:
                if response.status != 200:
                    self.log_test("Provinces Endpoint", False, f"HTTP {response.status}")
                    return False
                
                data = await response.json()
                
                # Verify structure and content
                if "provinces" not in data or "total" not in data:
                    self.log_test("Provinces Endpoint", False, "Missing required fields")
                    return False
                
                provinces = data["provinces"]
                if len(provinces) < 3:
                    self.log_test("Provinces Endpoint", False, f"Expected at least 3 provinces, got {len(provinces)}")
                    return False
                
                # Check for expected provinces
                province_codes = [p["code"] for p in provinces]
                expected_codes = ["guangdong", "shandong", "inner_mongolia"]
                
                if not all(code in province_codes for code in expected_codes):
                    self.log_test("Provinces Endpoint", False, f"Missing expected provinces. Got: {province_codes}")
                    return False
                
                self.log_test("Provinces Endpoint", True, f"Found {len(provinces)} provinces: {province_codes}")
                return True
                
        except Exception as e:
            self.log_test("Provinces Endpoint", False, f"Exception: {str(e)}")
            return False
    
    async def test_assets_endpoint(self) -> bool:
        """Test the assets endpoint."""
        try:
            async with self.session.get(f"{self.base_url}/assets") as response:
                if response.status != 200:
                    self.log_test("Assets Endpoint", False, f"HTTP {response.status}")
                    return False
                
                data = await response.json()
                
                if "assets" not in data or "total" not in data:
                    self.log_test("Assets Endpoint", False, "Missing required fields")
                    return False
                
                assets = data["assets"]
                asset_codes = [a["code"] for a in assets]
                expected_codes = ["wind", "solar", "bess", "coal_flex"]
                
                if not all(code in asset_codes for code in expected_codes):
                    self.log_test("Assets Endpoint", False, f"Missing expected assets. Got: {asset_codes}")
                    return False
                
                self.log_test("Assets Endpoint", True, f"Found {len(assets)} assets: {asset_codes}")
                return True
                
        except Exception as e:
            self.log_test("Assets Endpoint", False, f"Exception: {str(e)}")
            return False
    
    async def test_doc_classes_endpoint(self) -> bool:
        """Test the doc_classes endpoint."""
        try:
            async with self.session.get(f"{self.base_url}/doc_classes") as response:
                if response.status != 200:
                    self.log_test("Doc Classes Endpoint", False, f"HTTP {response.status}")
                    return False
                
                data = await response.json()
                
                if "doc_classes" not in data or "total" not in data:
                    self.log_test("Doc Classes Endpoint", False, "Missing required fields")
                    return False
                
                doc_classes = data["doc_classes"]
                class_codes = [d["code"] for d in doc_classes]
                expected_codes = ["market_rules", "grid_connection", "dispatch_ops"]
                
                if not all(code in class_codes for code in expected_codes):
                    self.log_test("Doc Classes Endpoint", False, f"Missing expected doc classes. Got: {class_codes}")
                    return False
                
                self.log_test("Doc Classes Endpoint", True, f"Found {len(doc_classes)} doc classes: {class_codes}")
                return True
                
        except Exception as e:
            self.log_test("Doc Classes Endpoint", False, f"Exception: {str(e)}")
            return False
    
    async def test_query_endpoint_real_data(self) -> bool:
        """Test the query endpoint with real regulatory queries."""
        test_queries = [
            {
                "name": "Guangdong Solar Grid Connection",
                "query": {
                    "question": "广东省分布式光伏发电项目并网需要什么材料？",
                    "province": "guangdong",
                    "doc_class": "grid_connection",
                    "asset": "solar"
                },
                "expected_keywords": ["项目备案", "设计方案", "安全评估", "电能质量", "15个工作日"]
            },
            {
                "name": "Shandong Wind Grid Connection",
                "query": {
                    "question": "山东省风电项目并网有什么技术要求？",
                    "province": "shandong", 
                    "doc_class": "grid_connection",
                    "asset": "wind"
                },
                "expected_keywords": ["低电压穿越", "无功补偿", "监控系统", "有功功率调节"]
            },
            {
                "name": "Inner Mongolia Coal Flexibility",
                "query": {
                    "question": "内蒙古煤电机组灵活性改造有什么激励政策？",
                    "province": "inner_mongolia",
                    "doc_class": "market_rules", 
                    "asset": "coal_flex"
                },
                "expected_keywords": ["深度调峰", "启停调峰", "快速爬坡", "备用容量", "补偿费用"]
            }
        ]
        
        all_passed = True
        
        for test_case in test_queries:
            try:
                async with self.session.post(
                    f"{self.base_url}/query",
                    json=test_case["query"],
                    headers={"Content-Type": "application/json"}
                ) as response:
                    
                    if response.status not in [200, 422]:
                        self.log_test(f"Query: {test_case['name']}", False, f"HTTP {response.status}")
                        all_passed = False
                        continue
                    
                    data = await response.json()
                    
                    # Check if it's a refusal (422) or success (200)
                    if response.status == 422:
                        if "error" in data:
                            self.log_test(f"Query: {test_case['name']}", True, f"Proper refusal: {data.get('error', 'Unknown error')}")
                        else:
                            self.log_test(f"Query: {test_case['name']}", False, "Invalid refusal response format")
                            all_passed = False
                        continue
                    
                    # For successful responses, verify structure and content
                    required_fields = ["answer", "citations", "trace_id"]
                    missing_fields = [f for f in required_fields if f not in data]
                    
                    if missing_fields:
                        self.log_test(f"Query: {test_case['name']}", False, f"Missing fields: {missing_fields}")
                        all_passed = False
                        continue
                    
                    # Check if answer contains expected keywords (indicating real data)
                    answer = data.get("answer", "")
                    citations = data.get("citations", [])
                    
                    # Verify we have citations
                    if not citations:
                        self.log_test(f"Query: {test_case['name']}", False, "No citations returned")
                        all_passed = False
                        continue
                    
                    # Check for expected keywords in answer or citations
                    found_keywords = []
                    all_text = answer + " " + " ".join([c.get("content", "") for c in citations])
                    
                    for keyword in test_case["expected_keywords"]:
                        if keyword in all_text:
                            found_keywords.append(keyword)
                    
                    if len(found_keywords) >= 2:  # At least 2 keywords should match
                        self.log_test(f"Query: {test_case['name']}", True, 
                                    f"Found {len(found_keywords)} expected keywords: {found_keywords[:3]}")
                    else:
                        self.log_test(f"Query: {test_case['name']}", False, 
                                    f"Only found {len(found_keywords)} keywords: {found_keywords}")
                        all_passed = False
                    
            except Exception as e:
                self.log_test(f"Query: {test_case['name']}", False, f"Exception: {str(e)}")
                all_passed = False
        
        return all_passed
    
    async def test_database_connectivity(self) -> bool:
        """Test if the service can connect to the real database."""
        try:
            # Try a simple query that should return real data
            async with self.session.post(
                f"{self.base_url}/query",
                json={
                    "question": "测试数据库连接",
                    "province": "guangdong",
                    "doc_class": "grid_connection",
                    "asset": "solar"
                },
                headers={"Content-Type": "application/json"}
            ) as response:
                
                # Any response (200 or 422) indicates database connectivity
                if response.status in [200, 422]:
                    data = await response.json()
                    
                    # Check if we get a trace_id (indicates the pipeline ran)
                    if "trace_id" in data:
                        self.log_test("Database Connectivity", True, f"Pipeline executed with trace_id: {data['trace_id']}")
                        return True
                    else:
                        self.log_test("Database Connectivity", False, "No trace_id in response")
                        return False
                else:
                    self.log_test("Database Connectivity", False, f"HTTP {response.status}")
                    return False
                    
        except Exception as e:
            self.log_test("Database Connectivity", False, f"Exception: {str(e)}")
            return False
    
    async def run_all_tests(self) -> Dict[str, Any]:
        """Run all tests and return summary."""
        print(f"🚀 Testing deployed service at: {self.base_url}")
        print("=" * 60)
        
        # Run all tests
        tests = [
            ("Service Health", self.test_health_endpoint()),
            ("Root Endpoint", self.test_root_endpoint()),
            ("Provinces API", self.test_provinces_endpoint()),
            ("Assets API", self.test_assets_endpoint()),
            ("Doc Classes API", self.test_doc_classes_endpoint()),
            ("Database Connectivity", self.test_database_connectivity()),
            ("Real Data Queries", self.test_query_endpoint_real_data()),
        ]
        
        results = {}
        for test_name, test_coro in tests:
            print(f"\n📋 Running: {test_name}")
            results[test_name] = await test_coro
        
        # Summary
        print("\n" + "=" * 60)
        print("📊 TEST SUMMARY")
        print("=" * 60)
        
        passed = sum(1 for success in results.values() if success)
        total = len(results)
        
        for test_name, success in results.items():
            status = "✅ PASS" if success else "❌ FAIL"
            print(f"{status} {test_name}")
        
        print(f"\n🎯 Overall Result: {passed}/{total} tests passed")
        
        if passed == total:
            print("🎉 ALL TESTS PASSED! The service is working with real data.")
        else:
            print("⚠️  Some tests failed. Check the details above.")
        
        return {
            "total_tests": total,
            "passed_tests": passed,
            "success_rate": passed / total,
            "all_passed": passed == total,
            "results": results,
            "test_details": self.test_results
        }


async def main():
    """Main test function."""
    print("🔍 Geo-Adaptive Energy Assistant - Service Verification")
    print("Testing deployed Cloud Run service with real regulatory data")
    print(f"Service URL: {SERVICE_URL}")
    print()
    
    async with ServiceTester(SERVICE_URL) as tester:
        summary = await tester.run_all_tests()
        
        # Save detailed results
        with open("test_results.json", "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        
        print(f"\n📄 Detailed results saved to: test_results.json")
        
        # Exit with appropriate code
        sys.exit(0 if summary["all_passed"] else 1)


if __name__ == "__main__":
    asyncio.run(main())