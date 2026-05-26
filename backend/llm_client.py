import json
import os
import re
import logging
from typing import Dict, Any
from openai import OpenAI
from config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL_NAME

# 配置日志
logger = logging.getLogger(__name__)

# 加载 prompt.txt 作为系统提示词
_PROMPT_PATH = os.path.join(os.path.dirname(__file__), "prompt.txt")
try:
    with open(_PROMPT_PATH, "r", encoding="utf-8") as f:
        SYSTEM_PROMPT = f.read()
except FileNotFoundError:
    logger.error(f"未找到提示词文件: {_PROMPT_PATH}")
    SYSTEM_PROMPT = "你是一个专业的客服助手，请根据用户输入输出标准 JSON 格式的工单。"

_client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)


def _extract_json_from_response(raw: str) -> Dict[str, Any]:
    """
    从 LLM 返回的字符串中提取 JSON 对象。
    支持：
    - 纯 JSON
    - ```json ... ``` 包裹的 JSON
    - 文本中第一个 { ... } 对象
    """
    # 尝试匹配 ```json 或 ``` 代码块
    pattern = r"```(?:json)?\s*(\{.*?\})\s*```"
    match = re.search(pattern, raw, re.DOTALL)
    if match:
        json_str = match.group(1)
    else:
        # 寻找第一个 { 和最后一个 }
        first_brace = raw.find('{')
        last_brace = raw.rfind('}')
        if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
            json_str = raw[first_brace:last_brace + 1]
        else:
            json_str = raw
    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        logger.error(f"JSON 解析失败: {e}\n原始内容前500字符: {raw[:500]}")
        raise


def call_llm(user_text: str, ocr_text: str = "") -> Dict[str, Any]:
    """
    调用大模型进行客诉分析

    Args:
        user_text: 用户输入的文本
        ocr_text: 从图片/视频中 OCR 出的附加文字（可为空）

    Returns:
        字典，包含以下键：
        - urgency_level: "Low" | "Medium" | "High"
        - routing: "frontline_worker" | "manager_dashboard" | "general_manager_dashboard"
        - reply: 给客户的初步回复
        - issue_category: 问题类别
        - business_impact: "Safety_Hazard" | "Production_Stop" | "Normal"
        - extracted_data: 包含 order_id, model_number, batch_code, sn_code
    """
    # 构造用户消息
    user_message = f"【客户投诉内容】\n{user_text}"
    if ocr_text:
        user_message += f"\n\n【图片/视频 OCR 识别结果】\n{ocr_text}"

    # 默认返回值（业务兜底）
    default_result = {
        "urgency_level": "Low",
        "routing": "frontline_worker",
        "reply": "感谢您的反馈，我们已收到您的信息，客服将尽快与您联系。",
        "issue_category": "Other",
        "business_impact": "Normal",
        "extracted_data": {
            "order_id": "",
            "model_number": "",
            "batch_code": "",
            "sn_code": "",
        },
    }

    try:
        response = _client.chat.completions.create(
            model=DEEPSEEK_MODEL_NAME,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            temperature=0.3,
            max_tokens=1024,  # 限制输出长度，避免过长
        )
        raw = response.choices[0].message.content.strip()
        logger.debug(f"LLM 原始返回: {raw[:200]}...")

        ticket = _extract_json_from_response(raw)

        # 提取所需字段
        assessment = ticket.get("agent_business_assessment", {})
        extracted = ticket.get("extracted_data", {})

        return {
            "urgency_level": assessment.get("urgency_level") or default_result["urgency_level"],
            "routing": ticket.get("routing_decision") or default_result["routing"],
            "reply": ticket.get("auto_reply_sent") or default_result["reply"],
            "issue_category": assessment.get("issue_category") or default_result["issue_category"],
            "business_impact": assessment.get("business_impact") or default_result["business_impact"],
            "extracted_data": {
                "order_id": str(extracted.get("order_id") or ""),
                "model_number": str(extracted.get("model_number") or ""),
                "batch_code": str(extracted.get("batch_code") or ""),
                "sn_code": str(extracted.get("sn_code") or ""),
            },
        }
    except Exception as e:
        logger.error(f"LLM 调用或解析失败: {e}", exc_info=True)
        return default_result