# # 测试脚本
# # import logging
# #
# # import json
# #
# # from backend.llm_client import call_llm
# #
# # if __name__ == "__main__":
# #     logging.basicConfig(level=logging.INFO)
# #     result = call_llm("设备冒烟了，怎么办？")
# #     print(json.dumps(result, ensure_ascii=False, indent=2))
# # from backend.ocr_utils import extract_text_from_image
# #
# # with open("img.png", "rb") as f:
# #     img_bytes = f.read()
# # text = extract_text_from_image(img_bytes)
# # print(text)
# # from backend.warranty import check_warranty
# #
# # # 简单测试
# # print(check_warranty("24ABC123"))   # In_Warranty
# # print(check_warranty("23XYZ789"))   # Out_of_Warranty
# # print(check_warranty(""))           # Unknown
# # print(check_warranty("O2ABC"))      # 清洗后 "02ABC" → 前缀 "02" → Out_of_Warranty
#
# from openai import OpenAI
# #
# # 配置信息
# # 请从 .env 文件或环境变量读取 API Key，不要在代码中硬编码凭据
# API_KEY = ""  # TODO: 替换为您的 API Key（开发调试用，提交前请清空）
# BASE_URL = "https://aigw-nmhhht.cucloud.cn/v1"
# MODEL_NAME = "Qwen/QwQ-32B"
#
# # 初始化客户端
# client = OpenAI(api_key=API_KEY, base_url=BASE_URL)
#
# # 发送测试请求
# try:
#     completion = client.chat.completions.create(
#         model=MODEL_NAME,
#         messages=[{"role": "user", "content": "你好"}],
#         timeout=30.0
#     )
#     print("调用成功！")
#     print("回复内容：", completion.choices[0].message.content)
# except Exception as e:
#     print("调用失败，请检查配置。错误详情：", e)
# #
# #
# #
# # import requests
# #
# # API_KEY = "sk-XPscDKH1z8sPylMWmxk7nMg6FTeW5zKh"
# # API_URL = "https://aigw-nmhhht.cucloud.cn/v1/models"
# #
# # headers = {
# #     "Authorization": f"Bearer {API_KEY}",
# #     "Content-Type": "application/json"
# # }
# #
# # try:
# #     response = requests.get(API_URL, headers=headers, timeout=10)
# #     print(f"状态码: {response.status_code}")
# #     print(f"响应内容: {response.text}")
# #     if response.status_code == 200:
# #         models = response.json()
# #         print("\n可用的模型列表:")
# #         for model in models.get("data", []):
# #             print(f"  - {model.get('id')}")
# #     else:
# #         print("API 地址可能不对，或者平台不支持这个接口。")
# # except Exception as e:
# #     print(f"请求失败: {e}")
#
#
# # test_role_history.py
# # import requests
# # import json
# #
# # BASE_URL = "http://localhost:8000"
# #
# # def test_role(role_name, role_param):
# #     url = f"{BASE_URL}/history"
# #     if role_param:
# #         url += f"?role={role_param}"
# #     print(f"\n=== 测试角色: {role_name} (参数: {role_param if role_param else '无'}) ===")
# #     try:
# #         resp = requests.get(url)
# #         resp.raise_for_status()
# #         data = resp.json()
# #         tickets = data.get("tickets", [])
# #         print(f"共获取 {len(tickets)} 个工单")
# #         for i, t in enumerate(tickets[:5]):  # 只显示前5个
# #             urgency = t.get("agent_business_assessment", {}).get("urgency_level", "未知")
# #             category = t.get("agent_business_assessment", {}).get("issue_category", "未知")
# #             print(f"  {i+1}. ID: {t.get('ticket_id')} | 紧急度: {urgency} | 类别: {category}")
# #         if len(tickets) > 5:
# #             print(f"  ... 还有 {len(tickets)-5} 个工单未显示")
# #     except Exception as e:
# #         print(f"请求失败: {e}")
# #
# # if __name__ == "__main__":
# #     test_role("全部（无角色）", None)
# #     test_role("一线员工 (frontline)", "frontline")
# #     test_role("部门经理 (manager)", "manager")
# #     test_role("总经理 (general)", "general")
# # backend/test_erp_mock.py
# # """
# # ERP Mock Server 自动化测试脚本
# # 用于验证鉴权、正常查询、404、500错误以及超时降级机制
# # """
# # import asyncio
# # import httpx
# # import time
# #
# # # 配置 (请确保与您的 warranty.py 和 mock_erp_server.py 保持一致)
# # ERP_BASE_URL = "http://127.0.0.1:8001"
# # MOCK_API_KEY = "mock_secret_token_123"
# # HEADERS = {"Authorization": f"Bearer {MOCK_API_KEY}"}
# #
# # # 测试用例定义
# # TEST_CASES = [
# #     {"name": "✅ 正常在保设备", "sn": "SN202501001", "expect_status": 200},
# #     {"name": "⚠️ 已过保设备", "sn": "SN202005002", "expect_status": 200},
# #     {"name": "❌ 查无此机 (404)", "sn": "SN999999999", "expect_status": 404},
# #     {"name": "❌ 错误 Token (401)", "sn": "SN202501001", "expect_status": 401, "bad_token": True},
# #     {"name": "💥 ERP 内部崩溃 (500)", "sn": "SN_ERROR", "expect_status": 500},
# #     {"name": "⏳ 模拟超时 (触发 httpx Timeout)", "sn": "SN_TIMEOUT", "expect_status": "timeout"},
# # ]
# #
# #
# # async def run_tests():
# #     print("🚀 开始执行 ERP Mock Server 自动化测试...\n")
# #
# #     # 设置 5 秒超时，模拟主系统的 httpx 超时配置
# #     async with httpx.AsyncClient(base_url=ERP_BASE_URL, timeout=5.0) as client:
# #         for case in TEST_CASES:
# #             print(f"👉 测试用例: {case['name']} (SN: {case['sn']})")
# #
# #             headers = {"Authorization": "Bearer wrong_token"} if case.get("bad_token") else HEADERS
# #
# #             start_time = time.time()
# #             try:
# #                 response = await client.get(f"/warranty/{case['sn']}", headers=headers)
# #                 elapsed = time.time() - start_time
# #
# #                 if case["expect_status"] == "timeout":
# #                     print(f"   ❌ 失败: 预期超时，但收到了 {response.status_code} ({elapsed:.2f}s)\n")
# #                 elif response.status_code == case["expect_status"]:
# #                     print(f"   ✅ 通过: 收到预期的 {response.status_code} ({elapsed:.2f}s)")
# #                     if response.status_code == 200:
# #                         print(f"      数据: {response.json()}\n")
# #                     else:
# #                         print(f"      错误信息: {response.text}\n")
# #                 else:
# #                     print(f"   ❌ 失败: 预期 {case['expect_status']}，实际 {response.status_code} ({elapsed:.2f}s)\n")
# #
# #             except httpx.TimeoutException:
# #                 elapsed = time.time() - start_time
# #                 if case["expect_status"] == "timeout":
# #                     print(f"   ✅ 通过: 成功触发 httpx.TimeoutException ({elapsed:.2f}s)\n")
# #                 else:
# #                     print(f"   ❌ 失败: 意外发生超时 ({elapsed:.2f}s)\n")
# #             except httpx.ConnectError:
# #                 print("   🛑 致命错误: 无法连接到 Mock Server，请先运行 `python mock_erp_server.py`！\n")
# #                 break
# #             except Exception as e:
# #                 print(f"   ❌ 发生未知异常: {e}\n")
# #
# #
# # if __name__ == "__main__":
# #     asyncio.run(run_tests())