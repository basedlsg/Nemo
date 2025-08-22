import requests
import json
import time

base = "http://localhost:8001/api/v1/query"
headers = {"Content-Type": "application/json"}

# Test 1 - Guangdong 2023 Distributed PV Cap
test1 = {
  "province": "guangdong",
  "doc_class": "regulations",
  "asset": "solar",
  "question": "广东省2023年分布式光伏发电项目并网容量限制是多少？",
  "lang": "zh-CN"
}

# Test 2 - Beijing Wind Grid-Adaptation Clause
test2 = {
  "province": "beijing",
  "doc_class": "technical_standards",
  "asset": "wind",
  "question": "北京市风力发电机组电网适应性技术要求中，频率跌落至49.5 Hz时的最低不脱网运行时间是多少秒？",
  "lang": "zh-CN"
}

# Test 3 - Shanghai BESS Market Entry Permit
test3 = {
  "province": "shanghai",
  "doc_class": "market_rules",
  "asset": "bess",
  "question": "上海市储能电站参与电力现货市场交易的最低装机容量门槛是多少MW？",
  "lang": "zh-CN"
}

# Test 4 - Shandong Inter-provincial Renewable PPA Flow
test4 = {
  "province": "shandong",
  "doc_class": "grid_connection",
  "asset": "renewable",
  "question": "山东省2024年跨省跨区新能源项目并网调度协议签订流程的正式文件名及文号？",
  "lang": "zh-CN"
}

# Test 5 - Inner Mongolia Clean-Energy Base Environmental Monitoring
test5 = {
  "province": "inner_mongolia",
  "doc_class": "environmental_protection",
  "asset": "clean_energy",
  "question": "内蒙古自治区清洁能源基地生态保护红线区域内施工环境监测频次要求？",
  "lang": "zh-CN"
}

# Test 6 - Fujian Offshore-Wind Pre-approval Checklist
test6 = {
  "province": "fujian",
  "doc_class": "project_approval",
  "asset": "offshore_wind",
  "question": "福建省海上风电项目核准前必须取得的三个用海预审文件名称？",
  "lang": "zh-CN"
}

tests = [test1, test2, test3, test4, test5, test6]
test_names = [
    "Guangdong 2023 Distributed PV Cap",
    "Beijing Wind Grid-Adaptation Clause",
    "Shanghai BESS Market Entry Permit",
    "Shandong Inter-provincial Renewable PPA Flow",
    "Inner Mongolia Clean-Energy Base Environmental Monitoring",
    "Fujian Offshore-Wind Pre-approval Checklist"
]

def check_test1_criteria(data):
    """Check if Test 1 meets criteria"""
    if "answer_zh" not in data:
        return False, "No answer_zh field"

    answer = data["answer_zh"]
    # Check for numeric MW/GW figure
    import re
    mw_match = re.search(r'(\d+(?:\.\d+)?)\s*MW', answer)
    gw_match = re.search(r'(\d+(?:\.\d+)?)\s*GW', answer)

    if not (mw_match or gw_match):
        return False, f"No numeric capacity found in answer: {answer}"

    # Check citations
    if "citations" not in data or not data["citations"]:
        return False, "No citations provided"

    for citation in data["citations"]:
        url = citation.get("url", "")
        effective_date = citation.get("effective_date", "")
        title = citation.get("title", "")

        # Check URL domain
        valid_domains = ["gd.gov.cn", "gddoe.gov.cn", "csg.cn"]
        if not any(domain in url for domain in valid_domains):
            continue  # Try next citation

        # Check date range
        if effective_date and "2023" in effective_date:
            # Check title contains required terms
            if "分布式光伏" in title and "并网容量" in title:
                return True, "All criteria met"

    return False, "No citation met all domain, date, and title criteria"

def run_test(test_num, test_data, test_name):
    print(f"\n{'='*60}")
    print(f"Test {test_num}: {test_name}")
    print('='*60)

    try:
        print("Sending request...")
        r = requests.post(base, data=json.dumps(test_data), headers=headers, timeout=300)

        print(f"Status Code: {r.status_code}")

        if r.status_code == 200:
            data = r.json()

            # Print key response parts
            print("\nAnswer:")
            print(data.get("answer_zh", "No answer provided"))

            print(f"\nCitations count: {len(data.get('citations', []))}")
            for i, citation in enumerate(data.get('citations', [])[:2], 1):
                print(f"  {i}. {citation.get('title', 'No title')}")
                print(f"     URL: {citation.get('url', 'No URL')}")
                print(f"     Date: {citation.get('effective_date', 'No date')}")

            # Check criteria for Test 1
            if test_num == 1:
                passed, reason = check_test1_criteria(data)
                print(f"\nResult: {'✅ PASS' if passed else '❌ FAIL'}")
                print(f"Reason: {reason}")
            else:
                print(f"\nResult: Manual inspection needed")

        else:
            print(f"Error Response: {r.text}")

    except requests.exceptions.Timeout:
        print("⏳ Request timed out (300s) - server may not be running")
    except Exception as e:
        print(f"❌ Exception: {e}")

def main():
    print("🚀 Chinese Energy Compliance Assistant - Six Test Queries")
    print("Running tests with 300s timeout per request...")

    for i, (test_data, test_name) in enumerate(zip(tests, test_names), 1):
        run_test(i, test_data, test_name)
        time.sleep(2)  # Brief pause between tests

    print(f"\n{'='*60}")
    print("Testing complete!")
    print("Note: Tests 2-6 require manual inspection of criteria")
    print("="*60)

if __name__ == "__main__":
    main()
