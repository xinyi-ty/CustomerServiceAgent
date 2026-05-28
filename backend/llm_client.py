import json
import os
import re
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from enum import Enum

from openai import OpenAI, APIError, APITimeoutError, RateLimitError
from pydantic import BaseModel, Field, ValidationError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL_NAME

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

_client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)
logger.info(f"[INFO] LLM Client initialized | Model: {LLM_MODEL_NAME} | URL: {LLM_BASE_URL}")

_PROMPT_PATH = os.path.join(os.path.dirname(__file__), "prompt.txt")
try:
    with open(_PROMPT_PATH, "r", encoding="utf-8") as f:
        SYSTEM_PROMPT = f.read()
except FileNotFoundError:
    logger.error(f"[ERROR] Prompt file not found: {_PROMPT_PATH}")
    SYSTEM_PROMPT = "你是一个专业的客服助手，请根据用户输入输出标准 JSON 格式的工单。"


class UrgencyLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class BusinessImpact(str, Enum):
    NORMAL = "Normal"
    PRODUCTION_STOP = "Production_Stop"
    SAFETY_HAZARD = "Safety_Hazard"


class RoutingDecision(str, Enum):
    FRONTLINE = "frontline_worker"
    MANAGER = "manager_dashboard"
    GM = "general_manager_dashboard"


class ExtractedData(BaseModel):
    order_id: Optional[str] = None
    model_number: Optional[str] = None
    batch_code: Optional[str] = None
    sn_code: Optional[str] = None


class AgentBusinessAssessment(BaseModel):
    issue_category: str
    business_impact: BusinessImpact
    urgency_level: UrgencyLevel
    warranty_status: str = "Unknown"


class TicketSchema(BaseModel):
    ticket_id: str
    extracted_data: ExtractedData
    agent_business_assessment: AgentBusinessAssessment
    routing_decision: RoutingDecision
    auto_reply_sent: str


def _generate_ticket_id() -> str:
    now = datetime.now()
    date_str = now.strftime("%Y%m%d")
    pseudo_seq = str(int(now.strftime("%S")) * 100 + int(now.microsecond / 10000)).zfill(4)[:4]
    return f"CS-{date_str}-{pseudo_seq}"


def _check_warranty_status(ocr_text: str, sn_code: Optional[str]) -> str:
    if not sn_code:
        match = re.search(r"SN[:\s]*([A-Za-z0-9\-]+)", ocr_text, re.IGNORECASE)
        if match:
            sn_code = match.group(1)
    if not sn_code:
        return "Unknown"
    if sn_code.startswith("2023") or sn_code.startswith("2024") or sn_code.startswith("2025"):
        return "In_Warranty"
    return "Out_of_Warranty"


def _clean_llm_response(raw_content: str) -> str:
    """深度清洗大模型返回的脏数据（如 <think> 标签、Markdown 标记）"""
    if not raw_content:
        return ""
    # 1. 截断 </think> 之后的内容（针对网关吞掉开头标签的情况）
    if '</think>' in raw_content:
        raw_content = raw_content.split('</think>')[-1].strip()
    # 2. 正则移除完整的 <think>...</think>
    raw_content = re.sub(r'(?s)<think>.*?</think>', '', raw_content).strip()
    # 3. 移除 Markdown 代码块标记
    raw_content = re.sub(r'^```(?:json)?\s*', '', raw_content)
    raw_content = re.sub(r'\s*```$', '', raw_content).strip()
    return raw_content


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    # 【核心修复】增加 ValueError 和 JSONDecodeError 的捕获，确保解析失败也能重试
    retry=retry_if_exception_type((APIError, APITimeoutError, RateLimitError, ValueError, json.JSONDecodeError)),
    reraise=True
)
def _call_llm_api(user_message: str) -> dict:
    response = _client.chat.completions.create(
        model=LLM_MODEL_NAME,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        temperature=0.2,
        max_tokens=1024,
        response_format={"type": "json_object"}
    )

    raw_content = response.choices[0].message.content or ""
    cleaned_content = _clean_llm_response(raw_content)

    if not cleaned_content:
        logger.error("[ERROR] LLM 返回空内容或清洗后为空")
        raise ValueError("Empty LLM response")

    try:
        return json.loads(cleaned_content)
    except json.JSONDecodeError as e:
        logger.error(f"[ERROR] JSON 解析失败，尝试正则提取。原始内容: {cleaned_content[:200]}")
        # 终极兜底：正则提取最外层 JSON
        match = re.search(r'\{[\s\S]*\}', cleaned_content)
        if match:
            return json.loads(match.group(0))
        raise e  # 抛出异常触发 tenacity 重试


def call_llm(user_text: str, ocr_text: str = "") -> Dict[str, Any]:
    user_message = f"【客户投诉内容】\n{user_text}"
    if ocr_text:
        user_message += f"\n\n【图片/视频 OCR 识别结果】\n{ocr_text}"

    real_ticket_id = _generate_ticket_id()
    user_message += f"\n\n【系统指令】请使用此工单ID: {real_ticket_id}"

    default_result = {
        "ticket_id": real_ticket_id,
        "extracted_data": {"order_id": None, "model_number": None, "batch_code": None, "sn_code": None},
        "agent_business_assessment": {
            "issue_category": "Other",
            "business_impact": "Normal",
            "urgency_level": "low",
            "warranty_status": "Unknown"
        },
        "routing_decision": "frontline_worker",
        "auto_reply_sent": "感谢您的反馈，系统正在升级维护中，人工客服将尽快与您联系。"
    }

    try:
        raw_json_dict = _call_llm_api(user_message)
        raw_json_dict["ticket_id"] = real_ticket_id

        extracted_sn = raw_json_dict.get("extracted_data", {}).get("sn_code")
        warranty_status = _check_warranty_status(ocr_text, extracted_sn)
        if "agent_business_assessment" in raw_json_dict:
            raw_json_dict["agent_business_assessment"]["warranty_status"] = warranty_status

        validated_ticket = TicketSchema(**raw_json_dict)
        return validated_ticket.model_dump(mode="json")

    except Exception as e:
        logger.error(f"[ERROR] LLM 调用或校验彻底失败: {e}", exc_info=True)
        return default_result