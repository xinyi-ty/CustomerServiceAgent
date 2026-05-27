# 测试脚本
# import logging
#
# import json
#
# from backend.llm_client import call_llm
#
# if __name__ == "__main__":
#     logging.basicConfig(level=logging.INFO)
#     result = call_llm("设备冒烟了，怎么办？")
#     print(json.dumps(result, ensure_ascii=False, indent=2))
# from backend.ocr_utils import extract_text_from_image
#
# with open("img.png", "rb") as f:
#     img_bytes = f.read()
# text = extract_text_from_image(img_bytes)
# print(text)
# from backend.warranty import check_warranty
#
# # 简单测试
# print(check_warranty("24ABC123"))   # In_Warranty
# print(check_warranty("23XYZ789"))   # Out_of_Warranty
# print(check_warranty(""))           # Unknown
# print(check_warranty("O2ABC"))      # 清洗后 "02ABC" → 前缀 "02" → Out_of_Warranty

from openai import OpenAI
#
# # 配置信息
# API_KEY = "sk-XPscDKH1z8sPylMWmxk7nMg6FTeW5zKh"  # 您的 API Key
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
#
#
#
# import requests
#
# API_KEY = "sk-XPscDKH1z8sPylMWmxk7nMg6FTeW5zKh"
# API_URL = "https://aigw-nmhhht.cucloud.cn/v1/models"
#
# headers = {
#     "Authorization": f"Bearer {API_KEY}",
#     "Content-Type": "application/json"
# }
#
# try:
#     response = requests.get(API_URL, headers=headers, timeout=10)
#     print(f"状态码: {response.status_code}")
#     print(f"响应内容: {response.text}")
#     if response.status_code == 200:
#         models = response.json()
#         print("\n可用的模型列表:")
#         for model in models.get("data", []):
#             print(f"  - {model.get('id')}")
#     else:
#         print("API 地址可能不对，或者平台不支持这个接口。")
# except Exception as e:
#     print(f"请求失败: {e}")