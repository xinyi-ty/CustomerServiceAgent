import os
import uuid
import logging
from datetime import datetime
from fastapi import APIRouter, Form, File, UploadFile
from typing import Optional

# ================= 导入自定义业务模块 =================
from llm_client import call_llm  # 大模型调用客户端 (负责意图识别与信息抽取)
from ocr_utils import extract_text_from_image, extract_text_from_video  # 多模态 OCR 工具
from rag_simple import get_sop_guide  # RAG 知识库检索 (获取标准排障 SOP)
from warranty import check_warranty_status  # ERP 系统接口 (校验设备质保状态)
from database import save_ticket  # 数据库操作 (保存工单)
from config import UPLOAD_DIR  # 配置文件 (文件上传目录)
from models import ChatResponse, UrgencyLevel  # Pydantic 数据模型 (规范 API 响应格式)

# 初始化日志记录器
logger = logging.getLogger(__name__)
# 初始化 FastAPI 路由
router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(
        message: str = Form(...),  # 用户输入的文本问题 (必填)
        session_id: str = Form(""),  # 会话 ID (用于追踪上下文)
        history: str = Form("[]"),  # 历史对话记录 (JSON 字符串)
        image: Optional[UploadFile] = File(None)  # 用户上传的多模态凭证 (图片/视频，选填)
):
    """
    核心客诉处理接口
    接收用户反馈，经过 OCR、LLM、RAG、ERP 等多环节处理，生成标准工单并返回回复。
    """
    try:
        # 初始化证据文件路径列表和 OCR 提取结果
        evidence_paths = []
        ocr_text = ""
        sn_from_ocr = None

        # ================= 1. 多模态 OCR 处理 =================
        if image:
            # 读取文件字节流
            image_bytes = await image.read()
            original_filename = image.filename
            # 提取文件扩展名，防止恶意文件名，使用 UUID 重命名以确保安全
            ext = os.path.splitext(original_filename)[1] if original_filename else ".bin"
            safe_filename = f"{uuid.uuid4().hex}{ext}"
            file_path = os.path.join(UPLOAD_DIR, safe_filename)

            # 确保上传目录存在，并将文件写入磁盘
            os.makedirs(UPLOAD_DIR, exist_ok=True)
            with open(file_path, "wb") as f:
                f.write(image_bytes)
            # 记录相对路径，作为工单的附件证据
            evidence_paths.append(os.path.relpath(file_path, start=os.getcwd()))

            # 根据文件 MIME 类型，调用对应的 OCR 模型提取文本和 SN 码
            content_type = image.content_type or ""
            if content_type.startswith("image/"):
                ocr_text, sn_from_ocr = await extract_text_from_image(image_bytes)
            elif content_type.startswith("video/"):
                ocr_text, sn_from_ocr = await extract_text_from_video(image_bytes)

        # ================= 2. LLM 意图识别与信息抽取 =================
        try:
            # 将用户文本和 OCR 结果传给大模型，获取结构化 JSON 结果
            llm_result = call_llm(user_text=message, ocr_text=ocr_text)
            assessment = llm_result.get("agent_business_assessment", {})
        except Exception as e:
            # 【降级策略】：如果 LLM 服务宕机或超时，使用默认值保证业务流程不中断
            logger.error(f"[ERROR] LLM 调用失败: {e}，使用降级默认值")
            llm_result = {
                "ticket_id": f"CS-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:4].upper()}",
                "extracted_data": {"order_id": None, "model_number": None, "batch_code": None, "sn_code": None},
                "agent_business_assessment": {
                    "issue_category": "Other",
                    "business_impact": "Normal",
                    "urgency_level": "low",
                    "warranty_status": "Unknown"
                },
                "routing_decision": "frontline_worker",
                "auto_reply_sent": "感谢您的反馈，我们已收到您的信息，客服将尽快与您联系。"
            }
            assessment = llm_result["agent_business_assessment"]

        # 解析 LLM 返回的结构化数据
        extracted_data = llm_result.get("extracted_data", {})
        urgency_level_raw = assessment.get("urgency_level", "low")
        # 统一紧急度格式为首字母大写 (Low/Medium/High)
        urgency_level = urgency_level_raw.capitalize() if urgency_level_raw else "Low"
        issue_category = assessment.get("issue_category", "Other")
        business_impact = assessment.get("business_impact", "Normal")
        auto_reply = llm_result.get("auto_reply_sent", "")

        # ================= 3. 安全护栏：危险关键词强制拦截 =================
        # 硬件客诉涉及人身安全时，必须绕过 AI 的判断，执行最高级别的硬规则拦截
        danger_keywords = ["冒烟", "起火", "漏电", "爆炸", "冒火", "烧焦"]
        for keyword in danger_keywords:
            if keyword in message or keyword in ocr_text:
                urgency_level = "High"  # 强制最高优先级
                llm_result["routing_decision"] = "general_manager_dashboard"  # 强制路由至总经理看板
                business_impact = "Safety_Hazard"  # 标记为安全隐患
                auto_reply = f"[紧急警示] 检测到'{keyword}'相关安全风险，请立即停止使用设备并远离！"
                break

        # ================= 4. RAG 知识库检索 SOP =================
        try:
            # 根据问题类别和紧急度，从向量数据库中检索最匹配的标准排障指南
            sop_guide = get_sop_guide(issue_category, urgency_level, message)
        except Exception as e:
            logger.error(f"[ERROR] RAG 检索失败: {e}")
            sop_guide = "[处置方案] 技术人员将在24小时内与您联系。"

        # 将 AI 安抚话术与 SOP 排障指南拼接成最终回复
        final_reply = auto_reply + "\n\n" + sop_guide

        # ================= 5. ERP 质保校验 =================
        # 优先使用 LLM 从文本中提取的 SN 码，如果没有则使用 OCR 从图片中识别的 SN 码
        sn_code = extracted_data.get("sn_code") or sn_from_ocr
        warranty_status = "Unknown"
        if sn_code:
            try:
                # 调用 ERP 接口核验设备是否过保
                warranty_result = await check_warranty_status(sn_code.strip())
                warranty_status = warranty_result.status
            except Exception as e:
                logger.error(f"[ERROR] ERP 校验异常: {e}")

        # ================= 6. 生成工单并入库 =================
        # 生成唯一工单号 (格式: CS-日期-随机码)
        ticket_id = llm_result.get(
            "ticket_id") or f"CS-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"

        # 将附件路径和 OCR 原文补充到提取数据中
        extracted_data["evidence_images"] = evidence_paths
        extracted_data["ocr_text"] = ocr_text

        # 严格按照《赛事要求》的 JSON 结构组装工单字典
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

        # 持久化到数据库
        save_ticket(ticket)
        logger.info(f"[INFO] 工单 {ticket_id} 已保存，路由: {ticket['routing_decision']}")

        # ================= 7. 返回标准 ChatResponse =================
        return ChatResponse(
            reply=final_reply,
            ticket_created=True,
            ticket_id=ticket_id,
            urgency_level=UrgencyLevel(urgency_level)  # 使用枚举类型确保数据规范
        )

    except Exception as e:
        # 【全局兜底】：捕获所有未预料的异常，防止 FastAPI 直接抛出 500 Internal Server Error
        logger.error(f"[ERROR] /chat 全局处理失败: {str(e)}", exc_info=True)
        return ChatResponse(
            reply="抱歉，系统当前处理请求时遇到问题，请稍后再试或联系人工客服。",
            ticket_created=False,
            ticket_id=None,
            urgency_level=UrgencyLevel.MEDIUM
        )