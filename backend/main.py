# backend/main.py
from chat_router import router as chat_router
from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uuid
from datetime import datetime
import logging
import os

from database import init_db, save_ticket, get_all_tickets
from config import PORT, HOST, UPLOAD_DIR   # 确保导入 UPLOAD_DIR

# 导入实际功能模块
from llm_client import call_llm
from ocr_utils import extract_text_from_image, extract_text_from_video
from rag_simple import get_sop_guide, build_index, _get_chroma_collection
from warranty import check_warranty

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时初始化数据库
    init_db()
    logger.info("数据库初始化完成")

    # 确保上传目录存在
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    logger.info(f"上传目录已准备: {UPLOAD_DIR}")

    # 检查 RAG 索引是否存在，若不存在则自动构建（确保 SOP 知识库可用）
    try:
        collection = _get_chroma_collection()
        if collection.count() == 0:
            logger.warning("RAG 向量库为空，正在自动构建索引...")
            build_index(force_rebuild=True)
        else:
            logger.info(f"RAG 向量库已就绪，共 {collection.count()} 个片段")
    except Exception as e:
        logger.error(f"RAG 索引检查失败: {e}，将禁用 RAG 功能")

    logger.info("服务启动完成")
    yield
    logger.info("服务关闭")


app = FastAPI(title="客诉自动回复与出单分发智能体", lifespan=lifespan)
app.include_router(chat_router)

# 允许跨域（前端调用）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/process")
async def process_complaint(
    text: str = Form(...),
    image: UploadFile = File(None)
):
    """
    处理客诉，返回标准工单 JSON
    """
    try:
        # ---------- 1. 处理上传文件并保存 ----------
        evidence_paths = []      # 存储保存后的文件路径（相对路径或绝对路径）
        ocr_text = ""
        if image:
            # 读取文件内容
            image_bytes = await image.read()
            logger.info(f"收到文件: {image.filename}, 大小: {len(image_bytes)} 字节")

            # 保存文件到 UPLOAD_DIR
            # 生成唯一文件名，保留原始扩展名
            original_filename = image.filename
            ext = os.path.splitext(original_filename)[1] if original_filename else ".bin"
            safe_filename = f"{uuid.uuid4().hex}{ext}"
            file_path = os.path.join(UPLOAD_DIR, safe_filename)
            with open(file_path, "wb") as f:
                f.write(image_bytes)
            # 存储相对路径（相对于项目根目录），或者绝对路径，建议使用相对路径便于部署
            relative_path = os.path.relpath(file_path, start=os.getcwd())
            evidence_paths.append(relative_path)
            logger.info(f"文件已保存: {relative_path}")

            # 进行 OCR 识别
            content_type = image.content_type or ""
            if content_type.startswith("image/"):
                ocr_text = extract_text_from_image(image_bytes)
                logger.info(f"图片 OCR 提取文本长度: {len(ocr_text)}")
            elif content_type.startswith("video/"):
                ocr_text = extract_text_from_video(image_bytes)
                logger.info(f"视频 OCR 提取文本长度: {len(ocr_text)}")
            else:
                logger.warning(f"不支持的文件类型: {content_type}")

        # ---------- 2. 调用大模型分析 ----------
        try:
            llm_result = call_llm(user_text=text, ocr_text=ocr_text)
            logger.info(f"LLM 分析完成: urgency={llm_result['urgency_level']}, category={llm_result['issue_category']}")
        except Exception as e:
            logger.error(f"LLM 调用失败: {e}，使用降级默认值")
            llm_result = {
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

        # ---------- 3. 危险关键词硬规则（最终安全兜底） ----------
        danger_keywords = ["冒烟", "起火", "漏电", "爆炸", "冒火", "烧焦"]
        for keyword in danger_keywords:
            if keyword in text:
                llm_result["urgency_level"] = "High"
                llm_result["routing"] = "general_manager_dashboard"
                llm_result["business_impact"] = "Safety_Hazard"
                llm_result["reply"] = f"紧急警示：检测到'{keyword}'相关安全风险，请立即停止使用设备！"
                logger.warning(f"危险关键词 '{keyword}' 触发，覆盖 LLM 结果为高紧急")
                break

        urgency_level = llm_result.get("urgency_level", "Low")
        issue_category = llm_result.get("issue_category", "")

        # ---------- 4. 获取 SOP 指导 ----------
        sop_guide = ""
        try:
            sop_guide = get_sop_guide(issue_category, urgency_level)
            logger.info(f"SOP 指导获取成功，长度: {len(sop_guide)}")
        except Exception as e:
            logger.error(f"SOP 指导获取失败: {e}，使用默认处理方案")
            if urgency_level == "High":
                sop_guide = "【紧急处置】请立即切断设备电源，远离现场，并等待专业人员处理。"
            elif issue_category == "Missing_Part":
                sop_guide = "【处置方案】缺失配件请访问官网申请补发，或联系客服。"
            else:
                sop_guide = "【处置方案】技术人员将在24小时内与您联系。"

        # ---------- 5. 拼接自动回复 ----------
        auto_reply = llm_result.get("reply", "") + "\n" + sop_guide

        # ---------- 6. 保修校验 ----------
        sn_code = llm_result.get("extracted_data", {}).get("sn_code", "")
        warranty_status = check_warranty(sn_code)
        logger.info(f"SN码: {sn_code if sn_code else '无'} -> 保修状态: {warranty_status}")

        # ---------- 7. 生成工单 ID 和时间 ----------
        ticket_id = f"CS-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"
        created_at = datetime.now().isoformat()

        # ---------- 8. 组装完整工单（包含 evidence_images） ----------
        # 合并 extracted_data：先将 LLM 提取的数据作为基础，再添加上传文件路径
        extracted_data = llm_result.get("extracted_data", {})
        extracted_data["evidence_images"] = evidence_paths   # 添加关键字段

        ticket = {
            "ticket_id": ticket_id,
            "created_at": created_at,
            "extracted_data": extracted_data,
            "agent_business_assessment": {
                "issue_category": issue_category,
                "business_impact": llm_result.get("business_impact", "Normal"),
                "urgency_level": urgency_level,
                "warranty_status": warranty_status
            },
            "routing_decision": llm_result.get("routing", "frontline_worker"),
            "auto_reply_sent": auto_reply
        }

        # ---------- 9. 保存到数据库 ----------
        save_ticket(ticket)
        logger.info(f"工单 {ticket_id} 已保存，包含 {len(evidence_paths)} 个证据文件")

        return ticket

    except Exception as e:
        logger.error(f"处理失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"处理失败: {str(e)}")


@app.get("/history")
async def history():
    """返回所有历史工单（按时间倒序）"""
    try:
        tickets = get_all_tickets()
        # 确保每条工单都有 created_at 字段
        for t in tickets:
            if "created_at" not in t:
                t["created_at"] = "未知时间"
            # 如果工单中没有 evidence_images 字段，补充空列表（兼容旧数据）
            if "evidence_images" not in t.get("extracted_data", {}):
                t.setdefault("extracted_data", {})["evidence_images"] = []
        return {"tickets": tickets}
    except Exception as e:
        logger.error(f"查询历史工单失败: {e}")
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")


@app.get("/health")
async def health():
    """健康检查接口"""
    return {"status": "ok", "rag_available": True}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=HOST, port=PORT)