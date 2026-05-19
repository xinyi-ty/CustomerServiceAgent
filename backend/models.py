from pydantic import BaseModel
from typing import Optional, Dict, Any, List

class ComplaintRequest(BaseModel):
    """客诉请求"""
    text: str
    image_base64: Optional[str] = None  # DataURL 格式

class ExtractedData(BaseModel):
    """提取的关键信息"""
    order_id: Optional[str] = None
    model_number: Optional[str] = None
    batch_code: Optional[str] = None
    sn_code: Optional[str] = None

class Assessment(BaseModel):
    """业务评估"""
    issue_category: str  # 如 "Missing_Part", "Overheating"
    business_impact: str  # "Safety_Hazard", "Production_Stop", "Normal"
    urgency_level: str  # "Low", "Medium", "High"
    warranty_status: str  # "In_Warranty", "Out_of_Warranty", "Unknown"

class TicketResponse(BaseModel):
    """工单响应"""
    ticket_id: str
    extracted_data: Dict[str, Any]
    agent_business_assessment: Assessment
    routing_decision: str  # "frontline_worker", "manager_dashboard", "general_manager_dashboard"
    auto_reply_sent: str

class HistoryResponse(BaseModel):
    """历史工单响应"""
    tickets: List[Dict[str, Any]]
