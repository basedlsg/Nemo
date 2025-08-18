#!/usr/bin/env python3
"""
Debug script to check what's happening with the deployed service.
"""

import asyncio
import aiohttp
import json
import sys

SERVICE_URL = "https://gaea-gateway-964505076225.us-central1.run.app"

async def debug_service():
    """Debug the deployed service."""
    print("🔍 Debugging deployed service...")
    
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=60)) as session:
        
        # Test 1: Check if service is responding
        print("\n1. Basic connectivity test...")
        try:
            async with session.get(f"{SERVICE_URL}/") as response:
                print(f"   Status: {response.status}")
                if response.status == 200:
                    data = await response.json()
                    print(f"   Service: {data.get('service', 'Unknown')}")
                    print(f"   Version: {data.get('version', 'Unknown')}")
                else:
                    print(f"   Error: HTTP {response.status}")
        except Exception as e:
            print(f"   Exception: {e}")
        
        # Test 2: Check health endpoint
        print("\n2. Health check...")
        try:
            async with session.get(f"{SERVICE_URL}/health") as response:
                print(f"   Status: {response.status}")
                if response.status == 200:
                    data = await response.json()
                    print(f"   Overall status: {data.get('status', 'Unknown')}")
                    services = data.get('services', {})
                    for service, status in services.items():
                        print(f"   {service}: {status}")
                else:
                    text = await response.text()
                    print(f"   Error: {text}")
        except Exception as e:
            print(f"   Exception: {e}")
        
        # Test 3: Try a simple query with longer timeout
        print("\n3. Simple query test (60s timeout)...")
        try:
            query_data = {
                "question": "测试",
                "province": "guangdong",
                "doc_class": "grid_connection"
            }
            
            async with session.post(
                f"{SERVICE_URL}/query",
                json=query_data,
                headers={"Content-Type": "application/json"}
            ) as response:
                print(f"   Status: {response.status}")
                
                if response.status in [200, 422]:
                    data = await response.json()
                    print(f"   Response type: {'Success' if response.status == 200 else 'Refusal'}")
                    
                    if "trace_id" in data:
                        print(f"   Trace ID: {data['trace_id']}")
                    
                    if "error" in data:
                        print(f"   Error: {data['error']}")
                        print(f"   Reason: {data.get('reason', 'Unknown')}")
                    
                    if "answer_zh" in data:
                        answer = data["answer_zh"]
                        print(f"   Answer length: {len(answer)} chars")
                        print(f"   Answer preview: {answer[:100]}...")
                    
                    if "citations" in data:
                        citations = data["citations"]
                        print(f"   Citations: {len(citations)}")
                        if citations:
                            print(f"   First citation: {citations[0].get('title', 'No title')}")
                
                else:
                    text = await response.text()
                    print(f"   Error response: {text[:200]}...")
                    
        except asyncio.TimeoutError:
            print("   Timeout after 60 seconds")
        except Exception as e:
            print(f"   Exception: {e}")
        
        # Test 4: Check if we can get any response from query endpoint
        print("\n4. Minimal query test...")
        try:
            minimal_query = {
                "question": "test",
                "province": "guangdong", 
                "doc_class": "grid_connection"
            }
            
            async with session.post(
                f"{SERVICE_URL}/query",
                json=minimal_query,
                headers={"Content-Type": "application/json"},
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                print(f"   Status: {response.status}")
                
                # Get response headers
                headers = dict(response.headers)
                if "x-trace-id" in headers:
                    print(f"   Trace ID: {headers['x-trace-id']}")
                if "x-processing-time-ms" in headers:
                    print(f"   Processing time: {headers['x-processing-time-ms']}ms")
                
                # Try to get response body
                try:
                    if response.content_type == "application/json":
                        data = await response.json()
                        print(f"   JSON response keys: {list(data.keys())}")
                    else:
                        text = await response.text()
                        print(f"   Text response: {text[:100]}...")
                except:
                    print("   Could not parse response body")
                    
        except asyncio.TimeoutError:
            print("   Timeout after 30 seconds")
        except Exception as e:
            print(f"   Exception: {e}")

if __name__ == "__main__":
    asyncio.run(debug_service())