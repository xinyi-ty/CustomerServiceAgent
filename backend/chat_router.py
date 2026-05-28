# backend/chat_router.py
"""
智能对话路由模块
完全依赖前端传递的对话历史，后端不存储会话状态
"""
import json
import logging
import re
import uuid
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, File, Form, UploadFile, HTTPException
from openai import OpenAI
from config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL_NAME
from ocr_utils import extract_text_from_image, extract_text_from_video
from database import save_ticket

logger = logging.getLogger(__name__)

if not DEEPSEEK_API_KEY:
    raise ValueError("请在 .env 中设置 DEEPSEEK_API_KEY")
_chat_client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)

router = APIRouter(prefix="/chat", tags=["对话"])

# 临时存储工单预览数据（仅用于确认创建，不长期存储会话）
preview_storage = {}

HELP_PHONE = "123456789"


def extract_json_from_text(text: str) -> Optional[dict]:
    """从文本中提取 JSON"""
    json_block = re.search(r'```json\s*([\s\S]*?)\s*```', text, re.DOTALL)
    if json_block:
        try:
            return json.loads(json_block.group(1))
        except:
            pass
    brace_match = re.search(r'(\{[\s\S]*\})', text)
    if brace_match:
        try:
            return json.loads(brace_match.group(1))
        except:
            pass
    return None


def parse_reply_and_json(full_text: str):
    """提取回复和工单预览JSON"""
    reply_match = re.search(r'<reply>(.*?)</reply>', full_text, re.DOTALL)
    if reply_match:
        reply = reply_match.group(1).strip()
    else:
        # 移除可能的 JSON 块
        tmp = re.sub(r'```json.*?```', '', full_text, flags=re.DOTALL)
        tmp = re.sub(r'\{.*\}', '', tmp, flags=re.DOTALL)
        reply = tmp.strip()
        if not reply:
            reply = full_text.strip()

    json_match = re.search(r'<json>(.*?)</json>', full_text, re.DOTALL)
    ticket_preview = None
    if json_match:
        try:
            ticket_preview = json.loads(json_match.group(1))
        except:
            pass
    else:
        ticket_preview = extract_json_from_text(full_text)

    if ticket_preview and ticket_preview.get("urgency_level") and ticket_preview.get("category"):
        return reply, ticket_preview
    return reply, None


@router.post("")
async def chat_endpoint(
    session_id: str = Form(...),
    message: str = Form(...),
    history: str = Form(None),
    image: UploadFile = File(None)
):
    """
    多轮对话接口，对话历史完全由前端传递
    """
    try:
        # 1. OCR 处理
        ocr_text = ""
        if image:
            image_bytes = await image.read()
            content_type = image.content_type or ""
            if content_type.startswith("image/"):
                ocr_text = extract_text_from_image(image_bytes)
            elif content_type.startswith("video/"):
                ocr_text = extract_text_from_video(image_bytes)
            else:
                logger.warning(f"不支持的文件类型: {content_type}")

        # 2. 解析前端传递的对话历史
        conversation_history = []
        if history:
            try:
                history_list = json.loads(history)
                conversation_history = history_list[-10:]  # 最多10条
            except json.JSONDecodeError:
                logger.warning("解析历史消息失败")

        # 3. 构建对话上下文（用于模型）
        context = ""
        if conversation_history:
            recent = conversation_history[-6:]  # 最近6条
            context = "\n".join([f"{msg['role']}: {msg['content']}" for msg in recent])

        # 4. 系统提示词
        system_prompt = (
            "你是一个专业的客服诊断助手。你的任务是根据用户描述判断问题是否可以创建工单。\n\n"
            "【重要规则】\n"
            "1. 如果用户描述的信息充足（能够明确判断紧急度 Low/Medium/High 和问题类别），则输出：\n"
            "   <reply>你对用户的自然语言回复</reply>\n"
            "   <json>{\"urgency_level\":\"Low/Medium/High\", \"category\":\"问题类别\", \"extracted_data\":{\"order_id\":\"...\", \"model_number\":\"...\", \"batch_code\":\"...\"}}</json>\n"
            "2. 如果信息不足，无法判断紧急度和类别，请先委婉道歉（例如：很抱歉，目前您提供的信息还不够充分），然后礼貌地请求用户补充具体的故障现象或细节。\n"
            "   示例：<reply>很抱歉，根据您当前提供的信息，我暂时无法准确判断问题的严重程度。能否请您再详细描述一下故障情况？例如：设备出现什么异常现象？有没有异味、冒烟或异响？发生故障时您正在做什么操作？</reply>\n"
            "3. 不要输出任何多余的解释或标签之外的文字。"
        )

        user_prompt = f"用户问题：{message}"
        if ocr_text:
            user_prompt += f"\n[图片/视频识别文字]: {ocr_text}"
        if context:
            user_prompt += f"\n对话历史：\n{context}"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        # 5. 调用大模型
        response = _chat_client.chat.completions.create(
            model=DEEPSEEK_MODEL_NAME,
            messages=messages,
            temperature=0.2,
            max_tokens=800,
            timeout=30.0,
        )
        full_text = response.choices[0].message.content.strip()
        reply, ticket_preview = parse_reply_and_json(full_text)

        # 6. 处理结果
        preview_id = None
        if ticket_preview:
            preview_id = str(uuid.uuid4())
            ticket_preview["auto_reply_sent"] = reply
            preview_storage[preview_id] = ticket_preview
            # 成功定性，不需要额外附加电话
            return {
                "reply": reply,
                "ticket_preview": ticket_preview,
                "preview_id": preview_id
            }
        else:
            # 无法定性，确保回复中包含道歉和请求补充信息（如果模型没做到，可以补充默认文案）
            if "抱歉" not in reply and "对不起" not in reply:
                reply = "很抱歉，您提供的信息还不够充分。" + reply
            if "请" not in reply or "描述" not in reply:
                reply += " 能否请您再详细描述一下故障的具体表现？例如：设备出现了什么异常？有没有冒烟、异味或异响？"
            # 附加人工电话
            if HELP_PHONE not in reply:
                reply += f"\n\n您也可以直接拨打人工客服电话 {HELP_PHONE} 寻求帮助。"
            return {
                "reply": reply,
                "ticket_preview": None,
                "preview_id": None
            }

    except Exception as e:
        logger.error(f"会话 {session_id} 处理失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"对话服务错误: {str(e)}")


@router.post("/create_ticket")
async def create_ticket_from_preview(
    preview_id: str = Form(...),
    session_id: str = Form(...)
):
    preview_data = preview_storage.pop(preview_id, None)
    if not preview_data:
        raise HTTPException(status_code=404, detail="预览数据不存在或已过期")

    try:
        ticket_id = f"CS-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6]}"
        ticket = {
            "ticket_id": ticket_id,
            "extracted_data": preview_data.get("extracted_data", {}),
            "agent_business_assessment": {
                "issue_category": preview_data.get("category", ""),
                "business_impact": preview_data.get("business_impact", "Normal"),
                "urgency_level": preview_data.get("urgency_level", "Low"),
                "warranty_status": "Unknown"
            },
            "routing_decision": "frontline_worker",
            "auto_reply_sent": preview_data.get("auto_reply_sent", "")
        }
        urgency = preview_data.get("urgency_level")
        if urgency == "High":
            ticket["routing_decision"] = "general_manager_dashboard"
        elif urgency == "Medium":
            ticket["routing_decision"] = "manager_dashboard"
        else:
            ticket["routing_decision"] = "frontline_worker"

        save_ticket(ticket)
        return {"ticket_id": ticket_id, "success": True}
    except Exception as e:
        logger.error(f"创建工单失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"创建工单失败: {str(e)}")