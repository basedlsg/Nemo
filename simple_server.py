"""
Ultra-simple HTTP server for testing the Chinese Energy Compliance Assistant
"""

import json
import time
import socket
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

class SimpleHandler(BaseHTTPRequestHandler):
    def _send_cors_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')

    def do_OPTIONS(self):
        self.send_response(200)
        self._send_cors_headers()
        self.end_headers()

    def do_GET(self):
        if self.path == '/_health':
            self.send_response(200)
            self._send_cors_headers()
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"ok": True}).encode())
        else:
            self.send_response(404)
            self._send_cors_headers()
            self.end_headers()

    def do_POST(self):
        if self.path == '/api/v1/query':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            request_data = json.loads(post_data.decode('utf-8'))

            # Simulate processing time
            time.sleep(1)

            # Generate mock response
            response = self._generate_mock_response(request_data)

            self.send_response(200)
            self._send_cors_headers()
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(response).encode())
        else:
            self.send_response(404)
            self._send_cors_headers()
            self.end_headers()

    def _generate_mock_response(self, request_data):
        """Generate a mock response with enhanced features."""

        province = request_data.get('province', 'unknown')
        doc_class = request_data.get('doc_class', 'unknown')
        asset = request_data.get('asset', 'unknown')

        # Mock answers
        answers = {
            "guangdong": "广东省2023年分布式光伏发电项目并网容量限制是6MW。",
            "beijing": "北京市风力发电机组电网适应性技术要求中，频率跌落至49.5 Hz时的最低不脱网运行时间是100毫秒。",
            "shanghai": "上海市储能电站参与电力现货市场交易的最低装机容量门槛是2MW。",
            "shandong": "山东省2024年跨省跨区新能源项目并网调度协议签订流程的正式文件名及文号是鲁电调〔2024〕123号。",
            "inner_mongolia": "内蒙古自治区清洁能源基地生态保护红线区域内施工环境监测频次要求是每月一次。",
            "fujian": "福建省海上风电项目核准前必须取得的三个用海预审文件名称是：海域使用论证、海洋环境影响评价、海洋工程地质勘察报告。"
        }

        answer = answers.get(province, f"关于{province}的{asset}相关政策信息已检索。")

        # Enhanced citations with metadata
        citations = [
            {
                "citation_id": f"cit_001_{province}",
                "title": f"{province.upper()}省{asset}相关政策文件",
                "url": f"https://www.{province}.gov.cn/policy/2024/001.html",
                "effective_date": "2024-01-01",
                "wenhao": f"{province[:2]}能规〔2024〕001号",
                "agency": f"{province.upper()}省能源局",
                "status": "现行有效"
            }
        ]

        # Enhanced diagnostics (our new feature)
        diagnostics = {
            "query_terms": [province, doc_class, asset],
            "filters_applied": {
                "province_normalized": province,
                "doc_class_normalized": doc_class,
                "status": "现行有效"
            },
            "total_candidates": 15,
            "quality_threshold": 3.0,
            "search_strategy": "enhanced_metadata_first"
        }

        return {
            "answer_zh": answer,
            "citations": citations,
            "diagnostics": diagnostics
        }

def run_server():
    server_address = ('localhost', 8002)
    httpd = HTTPServer(server_address, SimpleHandler)
    print("🚀 Simple Test Server starting on http://localhost:8002")
    print("This demonstrates the enhanced Chinese Energy Compliance Assistant")
    httpd.serve_forever()

if __name__ == '__main__':
    run_server()
