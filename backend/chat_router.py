import os
import uuid
import logging
from datetime import datetime
from fastapi import APIRouter, Form, File, UploadFile
from typing import Optional

from llm_client import call_llm
from ocr_utils import extract_text_from_image, extract_text_from_video
from rag_simple import get_sop_guide
from warranty import check_warranty_status
from database import save_ticket
from config import UPLOAD_DIR
from models import ChatResponse, UrgencyLevel

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(
        message: str = Form(...),
        session_id: str = Form(""),
        history: str = Form("[]"),
        image: Optional[UploadFile] = File(None)
):
    try:
        evidence_paths = []
        ocr_text = ""
        sn_from_ocr = None

        # 1. 多模态 OCR 处理
        if image:
            image_bytes = await image.read()
            original_filename = image.filename
            ext = os.path.splitext(original_filename)[1] if original_filename else ".bin"
            safe_filename = f"{uuid.uuid4().hex}{ext}"
            file_path = os.path.join(UPLOAD_DIR, safe_filename)

            os.makedirs(UPLOAD_DIR, exist_ok=True)
            with open(file_path, "wb") as f:
                f.write(image_bytes)
            evidence_paths.append(os.path.relpath(file_path, start=os.getcwd()))

            content_type = image.content_type or ""
            if content_type.startswith("image/"):
                ocr_text, sn_from_ocr = await extract_text_from_image(image_bytes)
            elif content_type.startswith("video/"):
                ocr_text, sn_from_ocr = await extract_text_from_video(image_bytes)

        # 2. LLM 意图识别与信息抽取
        try:
            llm_result = call_llm(user_text=message, ocr_text=ocr_text)
            assessment = llm_result.get("agent_business_assessment", {})
        except Exception as e:
            logger.error(f"[ERROR] LLM 调用失败: {e}，使用降级默认值")
            llm_result = {
                "ticket_id": f"CS-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:4].upper()}",
                "extracted_data": {"order_id": None, "model_number": None, "batch_code": None, "sn_code": None},
                "agent_business_assessment": {"issue_category": "Other", "business_impact": "Normal",
                                              "urgency_level": "low", "warranty_status": "Unknown"},
                "routing_decision": "frontline_worker",
                "auto_reply_sent": "感谢您的反馈，我们已收到您的信息，客服将尽快与您联系。"
            }
            assessment = llm_result["agent_business_assessment"]

        extracted_data = llm_result.get("extracted_data", {})
        urgency_level_raw = assessment.get("urgency_level", "low")
        # 统一映射为首字母大写 (Low/Medium/High)
        urgency_level = urgency_level_raw.capitalize() if urgency_level_raw else "Low"
        issue_category = assessment.get("issue_category", "Other")
        business_impact = assessment.get("business_impact", "Normal")
        auto_reply = llm_result.get("auto_reply_sent", "")

        # 3. 安全护栏：危险关键词强制拦截
        danger_keywords = ["冒烟", "起火", "漏电", "爆炸", "冒火", "烧焦"]
        for keyword in danger_keywords:
            if keyword in message or keyword in ocr_text:
                urgency_level = "High"
                llm_result["routing_decision"] = "general_manager_dashboard"
                business_impact = "Safety_Hazard"
                auto_reply = f"[紧急警示] 检测到'{keyword}'相关安全风险，请立即停止使用设备并远离！"
                break

        # 4. RAG 知识库检索 SOP
        try:
            sop_guide = get_sop_guide(issue_category, urgency_level, message)
        except Exception as e:
            logger.error(f"[ERROR] RAG 检索失败: {e}")
            sop_guide = "[处置方案] 技术人员将在24小时内与您联系。"

        final_reply = auto_reply + "\n\n" + sop_guide

        # 5. ERP 质保校验
        sn_code = extracted_data.get("sn_code") or sn_from_ocr
        warranty_status = "Unknown"
        if sn_code:
            try:
                warranty_result = await check_warranty_status(sn_code.strip())
                warranty_status = warranty_result.status
            except Exception as e:
                logger.error(f"[ERROR] ERP 校验异常: {e}")

        # 6. 生成工单并入库
        ticket_id = llm_result.get(
            "ticket_id") or f"CS-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"
        extracted_data["evidence_images"] = evidence_paths
        extracted_data["ocr_text"] = ocr_text

        ticket = {
            "ticket_id": ticket_id,
            "created_at": datetime.now().isoformat(),
            "extracted_data": extracted_data,
            "agent_business_assessment": {
                "issue_category": issue_category,
                "business_impact": business_impact,
                "urgency_level": urgency_level,
                "warranty_status": warranty_status
            },
            "routing_decision": llm_result.get("routing_decision", "frontline_worker"),
            "auto_reply_sent": final_reply,
            "status": "未处理"
        }

        save_ticket(ticket)
        logger.info(f"[INFO] 工单 {ticket_id} 已保存，路由: {ticket['routing_decision']}")

        # 7. 返回标准 ChatResponse
        return ChatResponse(
            reply=final_reply,
            ticket_created=True,
            ticket_id=ticket_id,
            urgency_level=UrgencyLevel(urgency_level)
        )

    except Exception as e:
        logger.error(f"[ERROR] /chat 全局处理失败: {str(e)}", exc_info=True)
        # 兜底返回，确保前端不会收到 500 报错
        return ChatResponse(
            reply="抱歉，系统当前处理请求时遇到问题，请稍后再试或联系人工客服。",
            ticket_created=False,
            ticket_id=None,
            urgency_level=UrgencyLevel.MEDIUM
        )