# backend/main.py
from chat_router import router as chat_router
from fastapi import FastAPI, File, Form, UploadFile, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uuid
from datetime import datetime
import logging
import os

from database import init_db, save_ticket, get_all_tickets, get_tickets_by_urgency, update_ticket_status
from config import PORT, HOST, UPLOAD_DIR

from llm_client import call_llm
from ocr_utils import extract_text_from_image, extract_text_from_video
from rag_simple import get_sop_guide, build_index, _get_chroma_collection
from warranty import check_warranty

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    logger.info("数据库初始化完成")
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    logger.info(f"上传目录已准备: {UPLOAD_DIR}")
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
    try:
        evidence_paths = []
        ocr_text = ""
        if image:
            image_bytes = await image.read()
            logger.info(f"收到文件: {image.filename}, 大小: {len(image_bytes)} 字节")
            original_filename = image.filename
            ext = os.path.splitext(original_filename)[1] if original_filename else ".bin"
            safe_filename = f"{uuid.uuid4().hex}{ext}"
            file_path = os.path.join(UPLOAD_DIR, safe_filename)
            with open(file_path, "wb") as f:
                f.write(image_bytes)
            relative_path = os.path.relpath(file_path, start=os.getcwd())
            evidence_paths.append(relative_path)
            logger.info(f"文件已保存: {relative_path}")
            content_type = image.content_type or ""
            if content_type.startswith("image/"):
                ocr_text = extract_text_from_image(image_bytes)
            elif content_type.startswith("video/"):
                ocr_text = extract_text_from_video(image_bytes)

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
                "extracted_data": {"order_id": "", "model_number": "", "batch_code": "", "sn_code": ""},
            }

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

        try:
            sop_guide = get_sop_guide(issue_category, urgency_level)
        except Exception:
            if urgency_level == "High":
                sop_guide = "【紧急处置】请立即切断设备电源，远离现场，并等待专业人员处理。"
            elif issue_category == "Missing_Part":
                sop_guide = "【处置方案】缺失配件请访问官网申请补发，或联系客服。"
            else:
                sop_guide = "【处置方案】技术人员将在24小时内与您联系。"

        auto_reply = llm_result.get("reply", "") + "\n" + sop_guide

        sn_code = llm_result.get("extracted_data", {}).get("sn_code", "")
        warranty_status = check_warranty(sn_code)

        ticket_id = f"CS-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"
        created_at = datetime.now().isoformat()

        extracted_data = llm_result.get("extracted_data", {})
        extracted_data["evidence_images"] = evidence_paths

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
            "auto_reply_sent": auto_reply,
            "status": "未处理"   # 新增状态字段，默认为未处理
        }

        save_ticket(ticket)
        logger.info(f"工单 {ticket_id} 已保存，状态：未处理")
        return ticket

    except Exception as e:
        logger.error(f"处理失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"处理失败: {str(e)}")


@app.post("/ticket/{ticket_id}/process")
async def process_ticket(ticket_id: str):
    """将工单标记为已处理"""
    success = update_ticket_status(ticket_id, "已处理")
    if not success:
        raise HTTPException(status_code=404, detail="工单不存在")
    return {"success": True, "ticket_id": ticket_id, "status": "已处理"}


@app.get("/history")
async def history(
    role: str = Query(None, description="角色: frontline, manager, general"),
    ticket_id: str = Query(None, description="工单号（支持部分匹配）")
):
    """
    根据角色和工单号返回工单：
    - 按角色过滤（frontline -> Low, manager -> Medium, general -> High）
    - 若提供 ticket_id，则在此基础上进一步模糊匹配
    - 返回结果按状态排序：未处理在前，已处理在后；同状态内按创建时间倒序
    """
    try:
        # 第一步：按角色获取基础列表
        if role == "frontline":
            base_tickets = get_tickets_by_urgency("Low")
        elif role == "manager":
            base_tickets = get_tickets_by_urgency("Medium")
        elif role == "general":
            base_tickets = get_tickets_by_urgency("High")
        else:
            base_tickets = get_all_tickets()

        # 第二步：按 ticket_id 过滤
        if ticket_id:
            filtered = [
                t for t in base_tickets
                if ticket_id.lower() in t.get("ticket_id", "").lower()
            ]
        else:
            filtered = base_tickets

        # 第三步：排序 — 未处理在前，已处理在后；同状态按创建时间倒序
        filtered.sort(key=lambda x: (0 if x.get("status") == "未处理" else 1, x.get("created_at", "")))

        # 补充缺失字段
        for t in filtered:
            if "created_at" not in t:
                t["created_at"] = "未知时间"
            if "evidence_images" not in t.get("extracted_data", {}):
                t.setdefault("extracted_data", {})["evidence_images"] = []

        return {"tickets": filtered}
    except Exception as e:
        logger.error(f"查询历史工单失败: {e}")
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")


@app.get("/health")
async def health():
    return {"status": "ok", "rag_available": True}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=HOST, port=PORT)