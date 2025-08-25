#!/usr/bin/env python3
"""
Get fresh document results for verification
Run this when the API is responsive to get current results
"""
import requests
import json
import time

def get_fresh_results():
    """Get fresh document results when API is available."""

    test_cases = [
        {
            'name': 'Guangdong Solar',
            'query': {
                'question': '太阳能发电并网要求',
                'province': 'guangdong',
                'doc_class': 'grid_connection',
                'asset': 'solar',
                'lang': 'zh-CN'
            }
        },
        {
            'name': 'Beijing Wind',
            'query': {
                'question': '风电技术标准',
                'province': 'beijing',
                'doc_class': 'technical_standards',
                'asset': 'wind',
                'lang': 'zh-CN'
            }
        }
    ]

    print("🔄 Getting Fresh Document Results")
    print("=" * 50)

    for test_case in test_cases:
        print(f"\n🧪 Testing: {test_case['name']}")
        print(f"Query: {test_case['query']['question']}")
        print("-" * 30)

        try:
            response = requests.post('http://localhost:8000/api/v1/query',
                                   json=test_case['query'],
                                   timeout=20)

            if response.status_code == 200:
                data = response.json()
                citations = data.get('citations', [])

                print(f"✅ Found {len(citations)} documents")

                for i, citation in enumerate(citations[:3], 1):  # Show top 3
                    print(f"\n{i}. 📄 {citation.get('title', 'No title')}")
                    print(f"   🔗 {citation.get('url', 'No URL')}")
                    print(f"   📅 {citation.get('effective_date', 'No date')}")
                    print(f"   🏛️ Government: {'.gov.cn' in citation.get('url', '') or '.gov' in citation.get('url', '')}")

                if len(citations) > 3:
                    print(f"\n... and {len(citations) - 3} more documents")

            else:
                print(f"❌ Status: {response.status_code}")

        except requests.exceptions.Timeout:
            print("⏰ Request timed out (try again when system is less busy)")
        except Exception as e:
            print(f"❌ Error: {e}")

        print()
        time.sleep(2)  # Brief pause between requests

if __name__ == "__main__":
    get_fresh_results()
