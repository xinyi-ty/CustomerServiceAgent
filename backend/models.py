"""
models.py - 数据模型定义

定义 FastAPI 请求和响应的数据结构，使用 Pydantic 进行自动校验。
所有 API 的输入输出都通过这些模型进行类型约束。
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, Dict, Any, List
from datetime import datetime
import uuid
import re


# ====================
# 请求模型
# ====================

class ComplaintRequest(BaseModel):
    """
    客诉请求模型
    
    前端提交客诉时使用的数据格式
    """
    text: str = Field(..., description="用户输入的投诉文本", min_length=1, max_length=5000)
    image_base64: Optional[str] = Field(None, description="图片的 Base64 编码（DataURL 格式）")
    
    # 也可以支持直接文件上传（FastAPI 的 UploadFile 单独处理，这里只做备用）
    
    @field_validator('text')
    @classmethod
    def text_not_empty(cls, v: str) -> str:
        """验证文本不能为空或只包含空白字符"""
        if not v or not v.strip():
            raise ValueError('投诉文本不能为空')
        return v.strip()
    
    @field_validator('image_base64')
    @classmethod
    def validate_base64(cls, v: Optional[str]) -> Optional[str]:
        """验证 Base64 格式（如果提供）"""
        if v is not None:
            # 检查是否是 DataURL 格式
            if v.startswith('data:image/'):
                # 可以进一步验证，但保持简单
                pass
            elif len(v) > 10 * 1024 * 1024:  # 10MB 限制
                raise ValueError('图片 Base64 编码过大（超过 10MB）')
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "text": "我的机器冒烟了，很危险！订单号: JD9988776655",
                "image_base64": "data:image/jpeg;base64,/9j/4AAQSkZJRg..."
            }
        }


# ====================
# 响应模型 - 提取的数据
# ====================

class ExtractedData(BaseModel):
    """
    从客诉中提取的关键数据
    
    由大模型从用户输入和 OCR 结果中提取
    """
    order_id: Optional[str] = Field(None, description="订单号", max_length=100)
    model_number: Optional[str] = Field(None, description="产品型号", max_length=100)
    batch_code: Optional[str] = Field(None, description="批次号", max_length=50)
    sn_code: Optional[str] = Field(None, description="SN 码（序列号）", max_length=50)
    
    # 可选：图片证据路径（存储上传的文件路径）
    evidence_images: Optional[List[str]] = Field(default_factory=list, description="证据图片路径")
    
    class Config:
        json_schema_extra = {
            "example": {
                "order_id": "JD9988776655",
                "model_number": "Pro-Max-V2",
                "batch_code": "X11",
                "sn_code": "SN20241234001",
                "evidence_images": ["/uploads/img_001.jpg"]
            }
        }


# ====================
# 响应模型 - 业务评估
# ====================

class Assessment(BaseModel):
    """
    业务评估模型
    
    大模型对投诉的客观评估结果
    """
    issue_category: str = Field(..., description="问题类别", examples=["Missing_Part", "Overheating", "Damaged", "Safety_Hazard"])
    business_impact: str = Field(..., description="业务影响", examples=["Safety_Hazard", "Production_Stop", "Normal"])
    urgency_level: str = Field(..., description="紧急度", examples=["Low", "Medium", "High"])
    warranty_status: str = Field(..., description="保修状态", examples=["In_Warranty", "Out_of_Warranty", "Unknown"])
    
    # 字段验证
    @field_validator('urgency_level')
    @classmethod
    def validate_urgency(cls, v: str) -> str:
        """验证紧急度值是否合法"""
        allowed = ["Low", "Medium", "High"]
        if v not in allowed:
            raise ValueError(f'紧急度必须是 {allowed} 之一')
        return v
    
    @field_validator('business_impact')
    @classmethod
    def validate_impact(cls, v: str) -> str:
        """验证业务影响值是否合法"""
        allowed = ["Safety_Hazard", "Production_Stop", "Normal"]
        if v not in allowed:
            raise ValueError(f'业务影响必须是 {allowed} 之一')
        return v
    
    @field_validator('warranty_status')
    @classmethod
    def validate_warranty(cls, v: str) -> str:
        """验证保修状态值是否合法"""
        allowed = ["In_Warranty", "Out_of_Warranty", "Unknown"]
        if v not in allowed:
            raise ValueError(f'保修状态必须是 {allowed} 之一')
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "issue_category": "Hardware_Thermal_Runaway",
                "business_impact": "Safety_Hazard",
                "urgency_level": "High",
                "warranty_status": "In_Warranty"
            }
        }


# ====================
# 响应模型 - 完整工单
# ====================

class TicketResponse(BaseModel):
    """
    工单响应模型
    
    系统处理完客诉后返回的完整工单数据
    """
    ticket_id: str = Field(..., description="工单唯一标识", examples=["CS-20260517-001"])
    extracted_data: Dict[str, Any] = Field(..., description="提取的结构化数据")
    agent_business_assessment: Assessment = Field(..., description="Agent 业务评估")
    routing_decision: str = Field(..., description="路由决策", examples=["frontline_worker", "manager_dashboard", "general_manager_dashboard"])
    auto_reply_sent: str = Field(..., description="发送给客户的自动回复内容", max_length=2000)
    
    # 可选字段
    created_at: Optional[str] = Field(None, description="创建时间")
    processing_time_ms: Optional[int] = Field(None, description="处理耗时（毫秒）")
    
    @field_validator('routing_decision')
    @classmethod
    def validate_routing(cls, v: str) -> str:
        """验证路由决策值是否合法"""
        allowed = ["frontline_worker", "manager_dashboard", "general_manager_dashboard"]
        if v not in allowed:
            raise ValueError(f'路由决策必须是 {allowed} 之一')
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "ticket_id": "CS-20260517-001",
                "extracted_data": {
                    "order_id": "JD9988776655",
                    "model_number": "Pro-Max-V2",
                    "batch_code": "X11",
                    "sn_code": "SN20241234001"
                },
                "agent_business_assessment": {
                    "issue_category": "Hardware_Thermal_Runaway",
                    "business_impact": "Safety_Hazard",
                    "urgency_level": "High",
                    "warranty_status": "In_Warranty"
                },
                "routing_decision": "general_manager_dashboard",
                "auto_reply_sent": "您好，已收到您的故障反馈。为保障您的安全，请立即切断设备电源并停止使用。",
                "created_at": "2026-05-17T10:30:00"
            }
        }


# ====================
# 辅助模型
# ====================

class HealthResponse(BaseModel):
    """健康检查响应模型"""
    status: str = Field(..., description="服务状态", examples=["ok"])
    timestamp: str = Field(..., description="当前时间戳")
    version: str = Field(default="1.0.0", description="API 版本")
    
    class Config:
        json_schema_extra = {
            "example": {
                "status": "ok",
                "timestamp": "2026-05-17T10:30:00",
                "version": "1.0.0"
            }
        }


class HistoryResponse(BaseModel):
    """历史工单查询响应模型"""
    tickets: List[Dict[str, Any]] = Field(..., description="工单列表")
    total: int = Field(..., description="工单总数")
    
    class Config:
        json_schema_extra = {
            "example": {
                "tickets": [
                    {
                        "ticket_id": "CS-20260517-001",
                        "extracted_data": {},
                        "agent_business_assessment": {},
                        "routing_decision": "frontline_worker",
                        "auto_reply_sent": "..."
                    }
                ],
                "total": 1
            }
        }


class ErrorResponse(BaseModel):
    """错误响应模型"""
    error: str = Field(..., description="错误信息")
    detail: Optional[str] = Field(None, description="详细错误信息")
    timestamp: str = Field(..., description="错误发生时间")
    
    class Config:
        json_schema_extra = {
            "example": {
                "error": "Internal Server Error",
                "detail": "Failed to call LLM API",
                "timestamp": "2026-05-17T10:30:00"
            }
        }


# ====================
# 内部模型（用于数据库存储）
# ====================

class TicketRecord(BaseModel):
    """
    数据库工单记录模型（内部使用）
    """
    id: Optional[int] = None
    ticket_id: str
    raw_json: str  # 存储完整的 TicketResponse JSON 字符串
    created_at: Optional[str] = None
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "id": self.id,
            "ticket_id": self.ticket_id,
            "raw_json": self.raw_json,
            "created_at": self.created_at
        }


# ====================
# 工具函数
# ====================

def generate_ticket_id() -> str:
    """
    生成工单 ID
    
    格式: CS-YYYYMMDD-XXX
    例如: CS-20260517-001
    
    Returns:
        工单 ID 字符串
    """
    today = datetime.now().strftime("%Y%m%d")
    # 使用 UUID 的后几位作为唯一标识（简化版）
    unique_suffix = str(uuid.uuid4().hex)[:4].upper()
    return f"CS-{today}-{unique_suffix}"


def validate_ticket_id(ticket_id: str) -> bool:
    """
    验证工单 ID 格式是否正确
    
    Args:
        ticket_id: 工单 ID
        
    Returns:
        是否有效
    """
    pattern = r'^CS-\d{8}-[A-Z0-9]{4}$'
    return bool(re.match(pattern, ticket_id))


def create_mock_ticket_response() -> TicketResponse:
    """
    创建 Mock 工单响应（用于测试）
    
    Returns:
        模拟的工单响应对象
    """
    return TicketResponse(
        ticket_id=generate_ticket_id(),
        extracted_data={
            "order_id": "TEST001",
            "model_number": "Test-Model",
            "batch_code": "B001",
            "sn_code": "SN001"
        },
        agent_business_assessment=Assessment(
            issue_category="Test_Issue",
            business_impact="Normal",
            urgency_level="Low",
            warranty_status="Unknown"
        ),
        routing_decision="frontline_worker",
        auto_reply_sent="这是一个测试回复。",
        created_at=datetime.now().isoformat()
    )


# ====================
# 常量定义
# ====================

# 紧急度映射（数值化，方便排序）
URGENCY_LEVELS = {
    "Low": 0,
    "Medium": 1,
    "High": 2
}

# 路由目标说明
ROUTING_TARGETS = {
    "frontline_worker": "一线员工 - 处理常规问题",
    "manager_dashboard": "部门经理 - 处理核心部件问题",
    "general_manager_dashboard": "总经理看板 - 处理安全/重大事故"
}

# 业务影响说明
BUSINESS_IMPACTS = {
    "Safety_Hazard": "安全隐患 - 可能造成人身伤害",
    "Production_Stop": "停工 - 影响生产运营",
    "Normal": "正常 - 常规质量问题"
}

# 问题类别示例
ISSUE_CATEGORIES = [
    "Missing_Part",      # 缺件
    "Damaged",           # 损坏
    "Overheating",       # 过热
    "Noise",             # 噪音
    "Malfunction",       # 故障
    "Software_Issue",    # 软件问题
    "Safety_Hazard",     # 安全隐患
    "Other"              # 其他
]

# 保修状态
WARRANTY_STATUSES = {
    "In_Warranty": "在保",
    "Out_of_Warranty": "过保",
    "Unknown": "未知"
}
