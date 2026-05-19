# backend/main.py
from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uuid
from datetime import datetime
from typing import Dict, Any

# 导入各个模块（其他同学会实现）
from database import init_db, save_ticket, get_all_tickets
from config import PORT, HOST

# 这些模块目前还未实现，先注释掉，等同学完成后取消注释
from llm_client import call_llm
from ocr_utils import extract_text_from_image
from rag_simple import get_sop_guide
from warranty import check_warranty


# 使用 lifespan 替代已废弃的 on_event
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时执行
    init_db()
    print("服务启动完成")
    yield
    # 关闭时执行（如果需要）
    print("服务关闭")


# 创建 FastAPI 应用
app = FastAPI(
    title="客诉自动回复与出单分发智能体",
    description="基于大模型 Agent 的智能客服系统",
    version="1.0.0",
    lifespan=lifespan
)

# 允许跨域（允许前端调用）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],           # 允许所有来源
    allow_credentials=True,
    allow_methods=["*"],           # 允许所有 HTTP 方法
    allow_headers=["*"],           # 允许所有请求头
)


@app.post("/process")
async def process_complaint(
    text: str = Form(...),
    image: UploadFile = File(None)
):
    """
    接收文本和可选图片/视频，返回标准工单 JSON。
    
    Args:
        text: 用户投诉文本
        image: 可选的图片或视频文件
    
    Returns:
        标准工单 JSON
    """
    try:
        # ========== 1. 处理图片 OCR（如果有图片） ==========
        ocr_text = ""
        if image:
            # 读取图片字节
            image_bytes = await image.read()
            # 调用 OCR 提取文字（等 ocr_utils 完成后取消注释）
            # from ocr_utils import extract_text_from_image
            # ocr_text = extract_text_from_image(image_bytes)
            print(f"收到图片: {image.filename}, 大小: {len(image_bytes)} 字节")
        
        # ========== 2. 调用大模型 ==========
        # 临时 Mock 数据（等 llm_client 完成后替换）
        # from llm_client import call_llm
        # llm_result = call_llm(user_text=text, ocr_text=ocr_text)
        
        # Mock 数据：模拟大模型返回结果
        llm_result = {
            "urgency_level": "Low",           # Low / Medium / High
            "routing": "frontline_worker",    # frontline_worker / manager_dashboard / general_manager_dashboard
            "reply": "您好，已收到您的反馈。",
            "issue_category": "Missing_Part",
            "business_impact": "Normal",
            "extracted_data": {
                "order_id": None,
                "model_number": None,
                "batch_code": None,
                "sn_code": None
            }
        }
        
        # 简单规则：检测高危险关键词（临时兜底逻辑）
        danger_keywords = ["冒烟", "起火", "漏电", "爆炸", "冒火", "烧焦"]
        for keyword in danger_keywords:
            if keyword in text:
                llm_result["urgency_level"] = "High"
                llm_result["routing"] = "general_manager_dashboard"
                llm_result["business_impact"] = "Safety_Hazard"
                llm_result["reply"] = f"紧急警示：检测到'{keyword}'相关安全风险，请立即停止使用设备！"
                break
        
        # 提取变量
        urgency_level = llm_result.get("urgency_level", "Low")
        issue_category = llm_result.get("issue_category", "")
        
        # ========== 3. 获取 SOP 指导 ==========
        sop_extra = ""
        # 等 sop_matcher 完成后取消注释
        # from sop_matcher import get_sop_guide
        # sop_extra = get_sop_guide(issue_category, urgency_level)
        
        # Mock SOP 指导
        if urgency_level == "High":
            sop_extra = "【紧急处置】请立即切断设备电源，远离现场，并等待专业人员处理。"
        elif issue_category == "Missing_Part":
            sop_extra = "【处置方案】缺失配件请访问官网申请补发，或联系客服。"
        else:
            sop_extra = "【处置方案】技术人员将在24小时内与您联系。"
        
        # ========== 4. 拼接最终回复 ==========
        auto_reply = llm_result.get("reply", "") + "\n" + sop_extra
        
        # ========== 5. 保修校验（如果有 SN 码） ==========
        warranty_status = "Unknown"
        sn_code = llm_result.get("extracted_data", {}).get("sn_code", "")
        if sn_code:
            # 等 warranty 完成后取消注释
            # from warranty import check_warranty
            # warranty_status = check_warranty(sn_code)
            # 临时 Mock：根据 SN 前缀判断
            if sn_code[:2] in ["24", "25"]:
                warranty_status = "In_Warranty"
            else:
                warranty_status = "Out_of_Warranty"
        
        # ========== 6. 组装完整工单 ==========
        ticket_id = f"CS-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"
        
        ticket = {
            "ticket_id": ticket_id,
            "extracted_data": llm_result.get("extracted_data", {}),
            "agent_business_assessment": {
                "issue_category": issue_category,
                "business_impact": llm_result.get("business_impact", "Normal"),
                "urgency_level": urgency_level,
                "warranty_status": warranty_status
            },
            "routing_decision": llm_result.get("routing", "frontline_worker"),
            "auto_reply_sent": auto_reply
        }
        
        # ========== 7. 保存到数据库 ==========
        save_ticket(ticket)
        
        # ========== 8. 返回工单 ==========
        return ticket
        
    except Exception as e:
        print(f"处理失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"处理失败: {str(e)}")


@app.get("/history")
async def history():
    """返回所有历史工单"""
    try:
        tickets = get_all_tickets()
        return {"tickets": tickets}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")


@app.get("/health")
async def health():
    """健康检查接口"""
    return {"status": "ok", "message": "服务运行正常"}


@app.get("/")
async def root():
    """根路径，返回 API 信息"""
    return {
        "name": "客诉自动回复与出单分发智能体",
        "version": "1.0.0",
        "endpoints": {
            "POST /process": "提交客诉",
            "GET /history": "查看历史工单",
            "GET /health": "健康检查"
        }
    }


# 本地运行入口
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=HOST, port=PORT)