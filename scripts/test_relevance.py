import requests
import json

def run_test(province: str, doc_class: str, asset: str, question: str):
    """Sends a query to the online service and prints the results."""
    url = "http://localhost:8000/query_online"
    payload = {
        "province": province,
        "doc_class": doc_class,
        "asset": asset,
        "question": question,
        "lang": "zh-CN"
    }
    headers = {"Content-Type": "application/json"}

    print(f"--- Testing Query ---")
    print(f"  Province: {province}")
    print(f"  Doc Class: {doc_class}")
    print(f"  Asset: {asset}")
    print(f"  Question: {question}")
    print("---------------------")

    try:
        response = requests.post(url, data=json.dumps(payload), headers=headers, timeout=60)
        response.raise_for_status()
        data = response.json()

        print("API Response:")
        print(f"  Answer: {data.get('answer_zh')}")
        print("  Citations:")
        for i, citation in enumerate(data.get('citations', [])):
            print(f"    {i+1}. Title: {citation.get('title')}")
            print(f"       URL: {citation.get('url')}")
            print(f"       Snippet: {citation.get('snippet')}")
        print("\\n")

    except requests.exceptions.RequestException as e:
        print(f"Error during request: {e}")
        if e.response:
            print(f"Response content: {e.response.text}")
    except json.JSONDecodeError:
        print("Failed to decode JSON from response.")
    print("=====================\\n")


if __name__ == "__main__":
    # Test Case 1: Guangdong Solar Grid Connection
    run_test("广东", "并网", "光伏", "并网验收需要哪些资料？")

    # Test Case 2: Shandong Wind Power Market Rules
    run_test("山东", "市场规则", "风电", "风电项目如何参与电力市场交易？")

    # Test Case 3: Inner Mongolia Energy Storage Dispatch
    run_test("内蒙古", "调度运行", "储能", "储能电站参与电网调度的技术要求是什么？")

    # Test Case 4: General Solar Policy
    run_test("广东", "市场规则", "光伏", "分布式光伏发电上网电价政策")

    # Test Case 5: Grid Connection Standards
    run_test("山东", "并网", "风电", "新建风电场并网技术标准")

    # Test Case 6: Inner Mongolia Coal Power Flexibility
    run_test("内蒙古", "市场规则", "煤电", "煤电灵活性改造的补偿机制")

    # Test Case 7: Guangdong BESS Ancillary Services
    run_test("广东", "市场规则", "储能", "独立储能电站如何参与辅助服务市场？")

    # Test Case 8: Shandong Solar Project Approval
    run_test("山东", "并网", "光伏", "光伏项目备案和审批流程")

    # Test Case 9: Inner Mongolia Wind Power Curtailment
    run_test("内蒙古", "调度运行", "风电", "解决风电弃风问题的措施有哪些？")

    # Test Case 10: General Grid Code
    run_test("广东", "并网", "光伏", "电力系统并网基本要求")
