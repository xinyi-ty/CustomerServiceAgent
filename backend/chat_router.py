import os
import uuid
import logging
from datetime import datetime
from fastapi import APIRouter, Form, File, UploadFile
from typing import Optional

# ================= 导入自定义业务模块 =================
from llm_client import call_llm  # 大模型调用客户端 (负责意图识别与信息抽取)
from product_lookup import lookup_product, format_product_context  # 产品注册表查询
from ocr_utils import extract_text_from_image, extract_text_from_video  # 多模态 OCR 工具
from rag_simple import search_sop  # RAG 知识库检索 (前置 SOP 检索注入 LLM 上下文)
from warranty import check_warranty_status  # ERP 系统接口 (校验设备质保状态)
from database import save_ticket, generate_ticket_id  # 数据库操作 (保存工单、生成工单号)
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

        # ================= 2. RAG 前置检索：获取 SOP 上下文 =================
        sop_context = ""
        try:
            # 先用用户原始描述检索 SOP，让 LLM 后续生成基于知识库的回复
            sop_context = search_sop(message + (" " + ocr_text if ocr_text else ""), top_k=3)
            if sop_context:
                logger.info(f"[INFO] 前置 RAG 检索成功，获取 {len(sop_context)} 字符 SOP 上下文")
        except Exception as e:
            logger.warning(f"[WARN] 前置 RAG 检索失败 (不影响后续处理): {e}")

        # ================= 3. 产品注册表查询：根据 SN/订单号获取产品信息 =================
        product_context = ""
        try:
            product = lookup_product(message, ocr_text)
            if product:
                product_context = format_product_context(product)
                logger.info(f"[INFO] 产品信息命中: {product.get('model_number')}")
        except Exception as e:
            logger.warning(f"[WARN] 产品查询异常 (不影响后续): {e}")

        # ================= 4. LLM 意图识别与信息抽取 (注入 SOP + 产品上下文) =================
        try:
            # 将用户文本、OCR 结果、SOP 上下文和产品信息传给大模型
            llm_result = call_llm(user_text=message, ocr_text=ocr_text,
                                  sop_context=sop_context, product_context=product_context)
            assessment = llm_result.get("agent_business_assessment", {})
        except Exception as e:
            # 【降级策略】：如果 LLM 服务宕机或超时，使用默认值保证业务流程不中断
            logger.error(f"[ERROR] LLM 调用失败: {e}，使用降级默认值")
            llm_result = {
                "ticket_id": "CS-DEGRADE",
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
        # 保持全小写，与 models.py UrgencyLevel 枚举及 prompt.txt 格式一致
        urgency_level = urgency_level_raw.lower() if urgency_level_raw else "low"
        issue_category = assessment.get("issue_category", "Other")
        business_impact = assessment.get("business_impact", "Normal")
        auto_reply = llm_result.get("auto_reply_sent", "")

        # ================= 5. 安全护栏：危险关键词强制拦截 =================
        # 涉及人身安全时，强制最高级响应，将安全警示置顶但保留 LLM 的详细分析
        danger_keywords = ["冒烟", "起火", "漏电", "爆炸", "冒火", "烧焦"]
        for keyword in danger_keywords:
            if keyword in message or keyword in ocr_text:
                urgency_level = "high"  # 强制最高优先级
                llm_result["routing_decision"] = "general_manager_dashboard"  # 强制路由至总经理看板
                business_impact = "Safety_Hazard"  # 标记为安全隐患
                # 安全头追加到 LLM 回复前面，而非完全替换
                safety_header = f"[紧急安全警示] 检测到\"{keyword}\"风险，请立即切断设备电源并远离，确保人身安全！"
                if auto_reply and len(auto_reply) > 10:
                    auto_reply = safety_header + "\n\n" + auto_reply
                else:
                    auto_reply = safety_header
                break

        # ================= 6. 意图可识别性检查 =================
        # 当 LLM 无法定位问题类别且未提取到任何有效信息时，请求用户补充描述
        is_unclear = (
            issue_category == "Other"
            and not any([
                extracted_data.get("order_id"),
                extracted_data.get("model_number"),
                extracted_data.get("batch_code"),
                extracted_data.get("sn_code"),
            ])
            and not ocr_text
            and not evidence_paths
        )
        if is_unclear:
            logger.info(f"[INFO] 意图不明确，请求补充信息: issue_category=Other, extracted_data为空")
            clarification_reply = (
                "您好，我暂时未能准确理解您遇到的问题。为了能更高效地为您提供帮助，"
                "请您补充以下信息：\n\n"
                "1. 您的设备/产品型号是什么？\n"
                "2. 具体出现了什么故障现象？\n"
                "3. 是否方便上传故障部位的图片或视频？\n\n"
                "收到详细信息后，我将立即为您分析处理。"
            )
            return ChatResponse(
                reply=clarification_reply,
                ticket_created=False,
                ticket_id=None,
                urgency_level=UrgencyLevel.LOW
            )

        # ================= 7. ERP 质保校验 =================
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

        # ================= 8. 生成工单并入库 =================
        # 使用数据库递增序号生成标准工单号 (符合赛事 CS-YYYYMMDD-NNNN 格式)
        ticket_id = generate_ticket_id()

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
            "auto_reply_sent": auto_reply,
            "status": "未处理"
        }

        # 持久化到数据库
        save_ticket(ticket)
        logger.info(f"[INFO] 工单 {ticket_id} 已保存，路由: {ticket['routing_decision']}")

        # ================= 9. 返回标准 ChatResponse =================
        return ChatResponse(
            reply=auto_reply,
            ticket_created=True,
            ticket_id=ticket_id,
            urgency_level=UrgencyLevel(urgency_level),  # 使用枚举类型确保数据规范
            warranty_status=warranty_status  # 质保核验状态，前端展示加分项
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