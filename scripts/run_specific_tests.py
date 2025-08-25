#!/usr/bin/env python3
"""
Run the 6 specific test cases with exact requirements
"""
import requests
import json

def run_test(test_num, test_name, payload):
    print(f"\n{'='*60}")
    print(f"TEST {test_num}: {test_name}")
    print('='*60)

    try:
        response = requests.post(
            'http://localhost:8000/api/v1/query',
            json=payload,
            timeout=None  # No timeout - let it complete
        )

        print(f"Status Code: {response.status_code}")

        if response.status_code == 200:
            data = response.json()

            # Print the answer
            answer = data.get('answer_zh', 'No answer provided')
            print(f"Answer: {answer}")

            # Print citations
            citations = data.get('citations', [])
            print(f"Citations found: {len(citations)}")

            for i, citation in enumerate(citations, 1):
                print(f"\nCitation {i}:")
                print(f"  Title: {citation.get('title', 'No title')}")
                print(f"  URL: {citation.get('url', 'No URL')}")
                print(f"  Date: {citation.get('effective_date', 'No date')}")
                print(f"  ID: {citation.get('citation_id', 'No ID')}")

        else:
            print(f"Error response: {response.text}")

    except requests.exceptions.Timeout:
        print("⏳ Request is taking a long time but will complete...")
        print("💡 This is expected for complex Chinese government document searches")
    except Exception as e:
        print(f"❌ Exception: {e}")
        print("🔄 Will continue with next test...")

def main():
    # Test 1: Guangdong 2023 Distributed PV Cap
    test1 = {
        "province": "guangdong",
        "doc_class": "regulations",
        "asset": "solar",
        "question": "广东省2023年分布式光伏发电项目并网容量限制是多少？",
        "lang": "zh-CN"
    }
    run_test(1, "Guangdong 2023 Distributed PV Cap", test1)

    # Test 2: Beijing Wind Grid-Adaptation Clause
    test2 = {
        "province": "beijing",
        "doc_class": "technical_standards",
        "asset": "wind",
        "question": "北京市风力发电机组电网适应性技术要求中，频率跌落至49.5 Hz时的最低不脱网运行时间是多少秒？",
        "lang": "zh-CN"
    }
    run_test(2, "Beijing Wind Grid-Adaptation Clause", test2)

    # Test 3: Shanghai BESS Market Entry Permit
    test3 = {
        "province": "shanghai",
        "doc_class": "market_rules",
        "asset": "bess",
        "question": "上海市储能电站参与电力现货市场交易的最低装机容量门槛是多少MW？",
        "lang": "zh-CN"
    }
    run_test(3, "Shanghai BESS Market Entry Permit", test3)

    # Test 4: Shandong Inter-provincial Renewable PPA Flow
    test4 = {
        "province": "shandong",
        "doc_class": "grid_connection",
        "asset": "renewable",
        "question": "山东省2024年跨省跨区新能源项目并网调度协议签订流程的正式文件名及文号？",
        "lang": "zh-CN"
    }
    run_test(4, "Shandong Inter-provincial Renewable PPA Flow", test4)

    # Test 5: Inner Mongolia Clean-Energy Base Environmental Monitoring
    test5 = {
        "province": "inner_mongolia",
        "doc_class": "environmental_protection",
        "asset": "clean_energy",
        "question": "内蒙古自治区清洁能源基地生态保护红线区域内施工环境监测频次要求？",
        "lang": "zh-CN"
    }
    run_test(5, "Inner Mongolia Clean-Energy Base Environmental Monitoring", test5)

    # Test 6: Fujian Offshore-Wind Pre-approval Checklist
    test6 = {
        "province": "fujian",
        "doc_class": "project_approval",
        "asset": "offshore_wind",
        "question": "福建省海上风电项目核准前必须取得的三个用海预审文件名称？",
        "lang": "zh-CN"
    }
    run_test(6, "Fujian Offshore-Wind Pre-approval Checklist", test6)

if __name__ == "__main__":
    main()
