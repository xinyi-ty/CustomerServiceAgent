# backend/models.py
"""
Pydantic 数据模型定义
架构优化：引入 Enum 强校验拦截大模型幻觉、对齐最新无状态 Router、规范分页元数据
"""
from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime

# ==========================================
# 1. 核心枚举定义 (强校验，拦截大模型幻觉)
# ==========================================
class UrgencyLevel(str, Enum):
    """紧急度级别 (严格对应赛事路由矩阵)"""
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"

class WarrantyStatus(str, Enum):
    """质保状态 (赛事加分项：OCR 核验结果)"""
    IN_WARRANTY = "In_Warranty"
    OUT_OF_WARRANTY = "Out_of_Warranty"
    UNKNOWN = "Unknown"

class TicketStatus(str, Enum):
    """工单处理状态"""
    PENDING = "未处理"
    PROCESSING = "处理中"
    RESOLVED = "已解决"
    CLOSED = "已关闭"

class BusinessImpact(str, Enum):
    """业务影响评估"""
    NORMAL = "Normal"
    DEGRADED = "Degraded"
    CRITICAL = "Critical"

# ==========================================
# 2. 对话与多模态请求模型
# ==========================================
class ChatHistoryItem(BaseModel):
    role: str = Field(..., pattern="^(user|assistant|system)$")
    content: str

class ChatResponse(BaseModel):
    """对话接口返回模型 (对齐最新自动建档逻辑)"""
    reply: str = Field(..., description="给用户的自然语言回复 (含 SOP 指导)")
    ticket_created: bool = Field(..., description="是否已自动创建工单")
    ticket_id: Optional[str] = Field(None, description="如果创建了工单，返回工单号")
    urgency_level: Optional[UrgencyLevel] = Field(None, description="诊断出的紧急度")

# ==========================================
# 3. 工单内部数据结构 (严格约束)
# ==========================================
class ExtractedData(BaseModel):
    """从多模态/文本中提取的结构化数据"""
    order_id: Optional[str] = None
    model_number: Optional[str] = None
    batch_code: Optional[str] = None
    sn_code: Optional[str] = Field(None, description="设备序列号，用于质保核验")
    evidence_images: Optional[List[str]] = Field(default_factory=list, description="多模态证据文件路径")
    ocr_text: Optional[str] = Field(None, description="OCR 提取的原始文本")

class AgentBusinessAssessment(BaseModel):
    """AI 智能体业务评估结果"""
    issue_category: str = Field(..., description="问题类别 (如: 硬件故障, 缺件, 安全隐患)")
    business_impact: BusinessImpact = Field(BusinessImpact.NORMAL, description="业务影响程度")
    urgency_level: UrgencyLevel = Field(..., description="紧急度级别")
    warranty_status: WarrantyStatus = Field(WarrantyStatus.UNKNOWN, description="质保核验状态")

class Ticket(BaseModel):
    """标准工单模型 (对应数据库存储结构)"""
    ticket_id: str = Field(..., description="工单唯一标识 (如: CS-20260528-A1B2C3)")
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    extracted_data: ExtractedData
    agent_business_assessment: AgentBusinessAssessment
    routing_decision: str = Field(..., description="路由决策结果 (如: general_manager_dashboard)")
    auto_reply_sent: str = Field(..., description="发送给用户的完整回复 (含 SOP)")
    status: TicketStatus = Field(TicketStatus.PENDING)

# ==========================================
# 4. 列表查询与分页响应
# ==========================================
class TicketListResponse(BaseModel):
    """工单列表分页响应"""
    tickets: List[Ticket]
    total: int = Field(..., description="符合条件的工单总数")
    limit: int = Field(..., description="当前页大小")
    offset: int = Field(..., description="当前偏移量")

class TicketUpdateRequest(BaseModel):
    """更新工单状态请求"""
    ticket_id: str
    new_status: TicketStatus