"""
main.py - FastAPI 主入口

定义所有 API 端点，串联各个模块（OCR、LLM、SOP、保修校验、数据库）。
使用 Mock 数据让整个流程可以先跑通，后续其他同学替换为真实实现。
"""

from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import Optional, Dict, Any
from datetime import datetime
import uuid
import os
import time
import asyncio
import json

# 导入配置
from backend.config import (
    DEBUG_MODE,
    UPLOAD_DIR,
    MAX_FILE_SIZE_BYTES,
    SERVER_HOST,
    SERVER_PORT,
    ensure_data_dir
)

# 导入数据模型
from backend.models import (
    TicketResponse,
    Assessment,
    generate_ticket_id,
    create_mock_ticket_response
)

# 导入各模块（目前是骨架，后续会被真实实现替换）
from backend.database import init_db, save_ticket, get_all_tickets
from backend.llm_client import call_llm
from backend.ocr_utils import extract_text_from_image, extract_text_from_video
from backend.sop_matcher import get_sop_guide
from backend.warranty import check_warranty

# 创建 FastAPI 应用
app = FastAPI(
    title="客诉自动回复与出单分发智能体",
    description="""
    基于大模型的客诉自动处理系统
    
    ## 功能说明
    - 接收文字投诉和图片/视频证据
    - 自动提取关键信息（订单号、型号、SN码等）
    - 评估紧急度并路由到对应部门
    - 生成前置排障指导
    - 工单入库和历史查询
    
    ## 验收案例
    1. 配件缺失 → 低紧急度 → 一线员工
    2. 设备冒烟（带图片）→ 高紧急度 → 总经理看板
    """,
    version="1.0.0"
)

# ====================
# 中间件配置
# ====================

# 配置 CORS（允许前端跨域访问）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 开发环境允许所有来源
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ====================
# 启动事件
# ====================

@app.on_event("startup")
async def startup_event():
    """应用启动时执行"""
    print("\n" + "=" * 60)
    print("客诉智能体服务启动中...")
    print("=" * 60)
    
    # 确保必要的目录存在
    ensure_data_dir()
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    
    # 初始化数据库
    init_db()
    
    print(f"✅ 数据库已初始化: {os.path.abspath('./data/tickets.db')}")
    print(f"✅ 上传目录: {os.path.abspath(UPLOAD_DIR)}")
    print(f"✅ 调试模式: {DEBUG_MODE}")
    print(f"✅ 大模型 API 配置: {'已配置' if call_llm.__name__ != 'call_llm_mock' else '使用 Mock 模式'}")
    print("=" * 60)
    print("服务已就绪！")
    print(f"API 文档: http://localhost:{SERVER_PORT}/docs")
    print("=" * 60 + "\n")


@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭时执行"""
    print("服务正在关闭...")


# ====================
# 辅助函数
# ====================

async def save_upload_file(file: UploadFile) -> str:
    """
    保存上传的文件到本地
    
    Args:
        file: 上传的文件对象
        
    Returns:
        保存的文件路径
    """
    # 生成唯一文件名
    file_ext = os.path.splitext(file.filename)[1]
    unique_filename = f"{uuid.uuid4().hex}{file_ext}"
    file_path = os.path.join(UPLOAD_DIR, unique_filename)
    
    # 保存文件
    content = await file.read()
    
    # 检查文件大小
    if len(content) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"文件大小超过限制（最大 {MAX_FILE_SIZE_BYTES // 1024 // 1024}MB）"
        )
    
    with open(file_path, "wb") as f:
        f.write(content)
    
    return file_path


def is_video_file(filename: str) -> bool:
    """判断是否为视频文件"""
    video_extensions = ['.mp4', '.avi', '.mov', '.mkv', '.flv']
    return any(filename.lower().endswith(ext) for ext in video_extensions)


def is_image_file(filename: str) -> bool:
    """判断是否为图片文件"""
    image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']
    return any(filename.lower().endswith(ext) for ext in image_extensions)


# ====================
# Mock 实现（用于测试，后续会被替换）
# ====================

def call_llm_mock(user_text: str, ocr_text: str = "") -> Dict[str, Any]:
    """
    Mock 大模型调用
    
    返回模拟的大模型结果，用于在真实实现完成前测试流程
    """
    print(f"\n[MOCK LLM] 收到用户文本: {user_text[:50]}...")
    print(f"[MOCK LLM] OCR 文本: {ocr_text[:50] if ocr_text else '无'}")
    
    # 根据关键词模拟不同结果
    text_lower = user_text.lower()
    
    # 高紧急度（冒烟、起火、漏电等）
    if any(keyword in text_lower for keyword in ["冒烟", "起火", "烧", "漏电", "爆炸", "冒火"]):
        return {
            "urgency_level": "High",
            "routing": "general_manager_dashboard",
            "reply": "您好，已收到您的故障反馈。该问题涉及安全隐患，已触发最高级响应，我们的技术总监将尽快与您联系。",
            "issue_category": "Safety_Hazard",
            "business_impact": "Safety_Hazard",
            "extracted_data": {
                "order_id": "JD9988776655",
                "model_number": "Pro-Max-V2",
                "batch_code": "X11",
                "sn_code": "SN20241234001"
            }
        }
    
    # 中紧急度（核心部件、批次缺陷等）
    elif any(keyword in text_lower for keyword in ["电机", "屏幕", "不工作", "死机", "批次"]):
        return {
            "urgency_level": "Medium",
            "routing": "manager_dashboard",
            "reply": "您好，已收到您关于设备故障的反馈。我们将安排部门经理跟进处理。",
            "issue_category": "Malfunction",
            "business_impact": "Production_Stop",
            "extracted_data": {
                "order_id": "JD9988776655",
                "model_number": "Pro-Max-V2",
                "batch_code": "X11",
                "sn_code": ""
            }
        }
    
    # 低紧急度（缺件、说明书等）
    else:
        return {
            "urgency_level": "Low",
            "routing": "frontline_worker",
            "reply": "您好，已收到您的反馈。我们的客服人员将为您处理。",
            "issue_category": "Missing_Part",
            "business_impact": "Normal",
            "extracted_data": {
                "order_id": "",
                "model_number": "",
                "batch_code": "",
                "sn_code": ""
            }
        }


def extract_text_from_image_mock(image_bytes: bytes) -> str:
    """Mock OCR 提取"""
    print(f"[MOCK OCR] 收到图片，大小: {len(image_bytes)} bytes")
    # 模拟从图片中提取到 SN 码
    return "SN码: SN20241234001 订单号: JD9988776655"


def get_sop_guide_mock(issue_category: str, urgency_level: str) -> str:
    """Mock SOP 匹配"""
    print(f"[MOCK SOP] 问题类别: {issue_category}, 紧急度: {urgency_level}")
    
    if urgency_level == "High":
        return "\n【紧急处置】请立即切断设备电源，远离设备，等待专业人员处理。"
    elif issue_category == "Missing_Part":
        return "\n【处置建议】请访问官网补件申请页面，填写订单号即可申请补发配件。"
    else:
        return "\n【处置建议】请等待客服人员与您联系，或拨打客服热线400-888-6666。"


def check_warranty_mock(sn_code: str) -> str:
    """Mock 保修校验"""
    print(f"[MOCK Warranty] SN码: {sn_code}")
    
    if not sn_code:
        return "Unknown"
    
    # 模拟规则：SN 码以 24 或 25 开头为在保
    if sn_code.startswith(("24", "25")):
        return "In_Warranty"
    else:
        return "Out_of_Warranty"


# ====================
# 临时替换为 Mock（后续删除，使用真实导入）
# ====================

# 如果当前是 Mock 模式（没有真实实现），替换为 Mock 函数
# 注意：当其他同学实现后，应该删除这些 Mock 替换
if DEBUG_MODE and call_llm.__name__ == 'call_llm':
    # 检查是否还是原始的 pass 函数
    try:
        import inspect
        if inspect.signature(call_llm).return_annotation != str:
            # 如果还是占位函数，替换为 Mock
            import sys
            sys.modules['backend.llm_client'].call_llm = call_llm_mock
            sys.modules['backend.ocr_utils'].extract_text_from_image = extract_text_from_image_mock
            sys.modules['backend.sop_matcher'].get_sop_guide = get_sop_guide_mock
            sys.modules['backend.warranty'].check_warranty = check_warranty_mock
            print("⚠️  使用 Mock 模块（真实实现尚未完成）")
    except:
        pass


# ====================
# API 端点
# ====================

@app.get("/")
async def root():
    """根路径"""
    return {
        "message": "客诉自动回复与出单分发智能体 API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health"
    }


@app.get("/health")
async def health():
    """健康检查"""
    return {
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0"
    }


@app.post("/process")
async def process_complaint(
    text: str = Form(..., description="投诉文本内容"),
    image: Optional[UploadFile] = File(None, description="图片或视频文件（可选）")
):
    """
    处理客诉主接口
    
    接收用户投诉文本和可选的图片/视频证据，返回标准化工单。
    
    处理流程：
    1. 如果有图片/视频，提取 OCR 文字
    2. 调用大模型分析，提取关键信息和评估
    3. 根据评估结果匹配 SOP 指导
    4. 如果提取到 SN 码，校验保修状态
    5. 生成完整工单并保存到数据库
    """
    start_time = time.time()
    
    print("\n" + "=" * 60)
    print(f"[新请求] {datetime.now().isoformat()}")
    print(f"投诉文本: {text[:100]}...")
    
    # ====================
    # 步骤 1: 处理上传文件（如果有）
    # ====================
    ocr_text = ""
    saved_file_path = None
    
    if image:
        try:
            print(f"[步骤1] 处理上传文件: {image.filename}")
            
            # 读取文件内容
            file_bytes = await image.read()
            
            # 保存文件（用于后续参考）
            saved_file_path = await save_upload_file(image)
            print(f"文件已保存: {saved_file_path}")
            
            # 根据文件类型提取文字
            if is_video_file(image.filename):
                # 视频文件（加分项）
                print("检测到视频文件，提取第一帧...")
                ocr_text = extract_text_from_video(file_bytes)
            else:
                # 图片文件
                print("检测到图片文件，执行 OCR...")
                ocr_text = extract_text_from_image(file_bytes)
            
            print(f"OCR 提取结果: {ocr_text[:100] if ocr_text else '无文字'}")
            
        except HTTPException as e:
            raise e
        except Exception as e:
            print(f"文件处理错误: {str(e)}")
            raise HTTPException(status_code=400, detail=f"文件处理失败: {str(e)}")
    
    # ====================
    # 步骤 2: 调用大模型
    # ====================
    print("\n[步骤2] 调用大模型分析...")
    try:
        llm_result = call_llm(user_text=text, ocr_text=ocr_text)
        print(f"大模型返回: {json.dumps(llm_result, ensure_ascii=False)[:200]}...")
    except Exception as e:
        print(f"大模型调用失败: {str(e)}")
        # 降级处理：使用默认值
        llm_result = {
            "urgency_level": "Low",
            "routing": "frontline_worker",
            "reply": "系统处理中，请稍后查看处理结果。",
            "issue_category": "Other",
            "business_impact": "Normal",
            "extracted_data": {
                "order_id": "",
                "model_number": "",
                "batch_code": "",
                "sn_code": ""
            }
        }
    
    # 提取大模型返回的数据
    urgency_level = llm_result.get("urgency_level", "Low")
    routing_decision = llm_result.get("routing", "frontline_worker")
    llm_reply = llm_result.get("reply", "感谢您的反馈，我们会尽快处理。")
    issue_category = llm_result.get("issue_category", "Other")
    business_impact = llm_result.get("business_impact", "Normal")
    extracted_data = llm_result.get("extracted_data", {})
    
    # ====================
    # 步骤 3: 匹配 SOP 指导
    # ====================
    print("\n[步骤3] 匹配 SOP 指导...")
    try:
        sop_guide = get_sop_guide(issue_category, urgency_level)
        print(f"SOP 指导: {sop_guide[:100]}...")
    except Exception as e:
        print(f"SOP 匹配失败: {str(e)}")
        sop_guide = ""
    
    # ====================
    # 步骤 4: 保修状态校验
    # ====================
    sn_code = extracted_data.get("sn_code", "")
    warranty_status = "Unknown"
    
    if sn_code:
        print(f"\n[步骤4] 校验保修状态，SN码: {sn_code}")
        try:
            warranty_status = check_warranty(sn_code)
            print(f"保修状态: {warranty_status}")
        except Exception as e:
            print(f"保修校验失败: {str(e)}")
            warranty_status = "Unknown"
    
    # ====================
    # 步骤 5: 组装最终回复
    # ====================
    auto_reply = llm_reply
    if sop_guide:
        auto_reply += "\n" + sop_guide
    
    # 如果有保修信息，添加到回复中
    if warranty_status == "In_Warranty":
        auto_reply += "\n\n【保修提示】您的设备在保修期内，维修/更换将免费处理。"
    elif warranty_status == "Out_of_Warranty":
        auto_reply += "\n\n【保修提示】您的设备已过保修期，维修将产生费用，客服会与您沟通。"
    
    # ====================
    # 步骤 6: 生成工单
    # ====================
    ticket_id = generate_ticket_id()
    processing_time_ms = int((time.time() - start_time) * 1000)
    
    # 构建评估对象
    assessment = Assessment(
        issue_category=issue_category,
        business_impact=business_impact,
        urgency_level=urgency_level,
        warranty_status=warranty_status
    )
    
    # 构建工单响应
    ticket_response = TicketResponse(
        ticket_id=ticket_id,
        extracted_data=extracted_data,
        agent_business_assessment=assessment,
        routing_decision=routing_decision,
        auto_reply_sent=auto_reply,
        created_at=datetime.now().isoformat(),
        processing_time_ms=processing_time_ms
    )
    
    # ====================
    # 步骤 7: 保存到数据库
    # ====================
    print(f"\n[步骤7] 保存工单到数据库...")
    try:
        # 转换为字典保存
        ticket_dict = ticket_response.model_dump()
        save_ticket(ticket_dict)
        print(f"工单已保存，ID: {ticket_id}")
    except Exception as e:
        print(f"保存工单失败: {str(e)}")
        # 不影响返回，继续执行
    
    # ====================
    # 步骤 8: 返回结果
    # ====================
    print(f"\n✅ 处理完成，耗时: {processing_time_ms}ms")
    print(f"工单ID: {ticket_id}")
    print(f"紧急度: {urgency_level}")
    print(f"路由: {routing_decision}")
    print("=" * 60)
    
    return ticket_response.model_dump()


@app.get("/history")
async def get_history(limit: Optional[int] = 100):
    """
    获取历史工单列表
    
    Args:
        limit: 返回的最大工单数量（默认100）
    
    Returns:
        工单列表
    """
    print(f"\n[历史查询] 获取最近 {limit} 条工单")
    
    try:
        tickets = get_all_tickets()
        
        # 限制返回数量
        if len(tickets) > limit:
            tickets = tickets[:limit]
        
        print(f"找到 {len(tickets)} 条工单记录")
        
        return {
            "tickets": tickets,
            "total": len(tickets),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        print(f"查询历史失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")


@app.get("/history/{ticket_id}")
async def get_ticket_detail(ticket_id: str):
    """
    获取单个工单详情
    
    Args:
        ticket_id: 工单 ID
        
    Returns:
        工单详细信息
    """
    print(f"\n[工单详情] 查询工单: {ticket_id}")
    
    try:
        tickets = get_all_tickets()
        
        for ticket in tickets:
            if ticket.get("ticket_id") == ticket_id:
                return ticket
        
        raise HTTPException(status_code=404, detail=f"工单 {ticket_id} 不存在")
    except HTTPException:
        raise
    except Exception as e:
        print(f"查询失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")


# ====================
# 测试接口（仅开发使用）
# ====================

@app.post("/test/mock")
async def test_mock():
    """
    测试接口：生成一个 Mock 工单用于测试
    
    仅开发环境使用
    """
    if not DEBUG_MODE:
        raise HTTPException(status_code=404, detail="Not Found")
    
    mock_ticket = create_mock_ticket_response()
    return mock_ticket.model_dump()


@app.post("/test/clear-db")
async def clear_db():
    """
    清空数据库（仅测试用）
    
    仅开发环境使用
    """
    if not DEBUG_MODE:
        raise HTTPException(status_code=404, detail="Not Found")
    
    import sqlite3
    from backend.config import DATABASE_PATH
    
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM tickets")
    conn.commit()
    conn.close()
    
    return {"message": "数据库已清空", "timestamp": datetime.now().isoformat()}


# ====================
# 启动入口
# ====================

if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "backend.main:app",
        host=SERVER_HOST,
        port=SERVER_PORT,
        reload=DEBUG_MODE,
        log_level="info"
    )
