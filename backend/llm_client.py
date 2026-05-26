import json
import os
from typing import Dict
from langchain.chat_models import init_chat_model
from langchain_core.messages import SystemMessage, HumanMessage
from config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL_NAME

# 加载 prompt.txt 作为系统提示词
_PROMPT_PATH = os.path.join(os.path.dirname(__file__), "prompt.txt")
with open(_PROMPT_PATH, "r", encoding="utf-8") as f:
    SYSTEM_PROMPT = f.read()

model = init_chat_model(DEEPSEEK_MODEL_NAME)


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
    # 构造用户消息cl
    user_message = f"【客户投诉内容】\n{user_text}"
    if ocr_text:
        user_message += f"\n\n【图片/视频 OCR 识别结果】\n{ocr_text}"

    try:
        response = model.invoke({
            "messages":[
                SystemMessage(SYSTEM_PROMPT),
                HumanMessage(user_message),
            ]
        })
        raw = response.content.strip()

        ticket = json.loads(raw)

        # 从 LLM 返回的 JSON 中提取所需字段
        assessment = ticket.get("agent_business_assessment", {})
        extracted = ticket.get("extracted_data", {})

        return {
            "urgency_level": assessment.get("urgency_level", ""),
            "routing": ticket.get("routing_decision", ""),
            "reply": ticket.get("auto_reply_sent", ""),
            "issue_category": assessment.get("issue_category", ""),
            "business_impact": assessment.get("business_impact", ""),
            "extracted_data": {
                "order_id": str(extracted.get("order_id") or ""),
                "model_number": str(extracted.get("model_number") or ""),
                "batch_code": str(extracted.get("batch_code") or ""),
                "sn_code": str(extracted.get("sn_code") or ""),
            },
        }
    except Exception as e:
        print(f"LLM 调用失败: {e}")
        return {
            "urgency_level": "",
            "routing": "",
            "reply": "感谢您的反馈，我们已收到您的信息，客服将尽快与您联系。",
            "issue_category": "",
            "business_impact": "",
            "extracted_data": {
                "order_id": "",
                "model_number": "",
                "batch_code": "",
                "sn_code": "",
            },
        }

