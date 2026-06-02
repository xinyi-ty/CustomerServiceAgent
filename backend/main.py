from chat_router import router as chat_router
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
import os

from database import init_db, get_all_tickets, get_tickets_by_urgency, update_ticket_status
from config import PORT, HOST
from rag_simple import build_index, chroma_client, COLLECTION_NAME

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    logger.info("[INFO] 数据库初始化完成")

    try:
        collection = chroma_client.get_or_create_collection(name=COLLECTION_NAME)
        if collection.count() == 0:
            logger.warning("[WARN] RAG 向量库为空，正在自动构建索引...")
            build_index(force_rebuild=True)
        else:
            logger.info(f"[INFO] RAG 向量库已就绪，共 {collection.count()} 个片段")
    except Exception as e:
        logger.error(f"[ERROR] RAG 索引检查失败: {e}")

    logger.info("[INFO] AI 售后主服务启动完成")
    yield
    logger.info("[INFO] 服务关闭")


app = FastAPI(title="客诉自动回复与出单分发智能体", lifespan=lifespan)

# 挂载核心业务路由
app.include_router(chat_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/ticket/{ticket_id}/process")
async def process_ticket(ticket_id: str):
    success = update_ticket_status(ticket_id, "已处理")
    if not success:
        raise HTTPException(status_code=404, detail="工单不存在")
    return {"success": True, "ticket_id": ticket_id, "status": "已处理"}


@app.get("/history")
async def history(
        role: str = Query(None, description="角色: frontline, manager, general"),
        ticket_id: str = Query(None, description="工单号（支持部分匹配）"),
        limit: int = Query(99999, description="返回条数上限")
):
    try:
        if role == "frontline":
            base_tickets = get_tickets_by_urgency("low")
        elif role == "manager":
            base_tickets = get_tickets_by_urgency("medium")
        elif role == "general":
            base_tickets = get_tickets_by_urgency("high")
        else:
            base_tickets = get_all_tickets(limit=limit)

        if ticket_id:
            filtered = [t for t in base_tickets if ticket_id.lower() in t.get("ticket_id", "").lower()]
        else:
            filtered = base_tickets

        filtered.sort(key=lambda x: (0 if x.get("status") == "未处理" else 1, x.get("ticket_id", "")), reverse=False)

        for t in filtered:
            if "created_at" not in t:
                t["created_at"] = "未知时间"
            if "evidence_images" not in t.get("extracted_data", {}):
                t.setdefault("extracted_data", {})["evidence_images"] = []

        return {"tickets": filtered}
    except Exception as e:
        logger.error(f"[ERROR] 查询历史工单失败: {e}")
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")


@app.get("/health")
async def health():
    return {"status": "ok", "rag_available": True}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=HOST, port=PORT)