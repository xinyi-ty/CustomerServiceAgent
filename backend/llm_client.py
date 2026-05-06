from typing import Dict

def call_llm(user_text: str, ocr_text: str = "") -> Dict[str, any]:
    """
    参数：
        user_text: 用户输入的文本
        ocr_text: 从图片/视频中 OCR 出的附加文字（可为空）
    返回：
        字典，必须包含以下键：
        {
            "urgency_level": "Low" | "Medium" | "High",
            "routing": "frontline_worker" | "manager_dashboard" | "general_manager_dashboard",
            "reply": "给客户的初步回复（字符串）",
            "issue_category": "字符串，如 Missing_Part, Overheating, Damaged",
            "business_impact": "Safety_Hazard" | "Production_Stop" | "Normal",
            "extracted_data": {
                "order_id": str,
                "model_number": str,
                "batch_code": str,
                "sn_code": str
            }
        }
    异常处理：若调用失败或解析失败，返回默认低优先级结果。
    """
    # TODO: 实现调用大模型 API，构造 Prompt，解析 JSON
    pass