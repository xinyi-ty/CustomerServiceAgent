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
from backend.warranty import check_warranty

# 简单测试
print(check_warranty("24ABC123"))   # In_Warranty
print(check_warranty("23XYZ789"))   # Out_of_Warranty
print(check_warranty(""))           # Unknown
print(check_warranty("O2ABC"))      # 清洗后 "02ABC" → 前缀 "02" → Out_of_Warranty