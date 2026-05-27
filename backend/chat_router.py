# backend/chat_router.py
"""
智能对话路由模块
支持多轮记忆对话，独立于工单分析接口
"""
import json
import logging
from fastapi import APIRouter, File, Form, UploadFile, HTTPException
from openai import OpenAI
from config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL_NAME
from ocr_utils import extract_text_from_image, extract_text_from_video

# 配置日志
logger = logging.getLogger(__name__)

# 创建 OpenAI 客户端（专用于对话）
if not DEEPSEEK_API_KEY:
    raise ValueError("请在 .env 中设置 DEEPSEEK_API_KEY")
_chat_client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)

# 创建路由（前缀 /chat）
router = APIRouter(prefix="/chat", tags=["对话"])


@router.post("")
async def chat_endpoint(
    session_id: str = Form(...),
    message: str = Form(...),
    history: str = Form(None),
    image: UploadFile = File(None)
):
    """
    多轮对话接口

    - session_id: 会话标识（前端生成并存储）
    - message: 当前用户消息
    - history: JSON 字符串，格式 [{"role":"user","content":"..."}, ...]
    - image: 可选图片/视频文件

    返回：{"reply": "助手回复", "ticket_id": "可选工单号"}
    """
    try:
        # ---------- 1. 处理图片/视频 OCR ----------
        ocr_text = ""
        if image:
            image_bytes = await image.read()
            content_type = image.content_type or ""
            if content_type.startswith("image/"):
                ocr_text = extract_text_from_image(image_bytes)
                logger.info(f"会话 {session_id} 图片OCR提取 {len(ocr_text)} 字符")
            elif content_type.startswith("video/"):
                ocr_text = extract_text_from_video(image_bytes)
                logger.info(f"会话 {session_id} 视频OCR提取 {len(ocr_text)} 字符")
            else:
                logger.warning(f"不支持的文件类型: {content_type}")

        # ---------- 2. 构建消息列表 ----------
        messages = []

        # 系统提示词（温和专业的客服风格）
        system_prompt = (
            "你是一个专业、耐心的智能客服助手。"
            "请根据对话历史回复用户。"
            "如果用户要求创建工单，请引导用户提供必要的订单号、产品型号、故障描述等信息，"
            "并告知用户提交工单后系统会生成工单号。"
            "不要编造信息。"
        )
        messages.append({"role": "system", "content": system_prompt})

        # 添加历史消息（最多10条，避免超长）
        if history:
            try:
                history_list = json.loads(history)
                # 只保留最近10条
                for h in history_list[-10:]:
                    # 确保角色正确
                    role = h.get("role", "user")
                    content = h.get("content", "")
                    messages.append({"role": role, "content": content})
            except json.JSONDecodeError:
                logger.warning(f"会话 {session_id} 解析历史消息失败")

        # 当前用户消息（附加 OCR 文本）
        user_content = message
        if ocr_text:
            user_content += f"\n[系统识别图片/视频文字]: {ocr_text}"
        messages.append({"role": "user", "content": user_content})

        # ---------- 3. 调用大模型 ----------
        response = _chat_client.chat.completions.create(
            model=DEEPSEEK_MODEL_NAME,
            messages=messages,
            temperature=0.7,      # 对话可稍具创造性
            max_tokens=800,
            timeout=30.0,
        )
        reply = response.choices[0].message.content.strip()

        # ---------- 4. 可选：检测是否需要生成工单 ----------
        ticket_id = None
        # 简单关键词检测（可根据需要扩展）
        if any(keyword in message for keyword in ["生成工单", "创建工单", "提交工单"]):
            # 这里可以调用现有的工单生成逻辑，但需要从对话历史提取关键字段。
            # 为保持简单，先返回提示，让用户使用原有工单提交页面。
            reply += "\n\n💡 如需正式提交工单，请点击上方「提交工单」按钮，系统将为您生成正式工单。"
            # 如果想要自动生成，可以在这里调用 call_llm 并将当前会话摘要作为输入（较复杂，暂不实现）
            # 若后续需要，可扩展

        logger.info(f"会话 {session_id} 助手回复长度: {len(reply)}")
        return {"reply": reply, "ticket_id": ticket_id}

    except Exception as e:
        logger.error(f"会话 {session_id} 处理失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"对话服务错误: {str(e)}")