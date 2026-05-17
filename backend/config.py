"""
config.py - 配置管理模块

负责从环境变量读取所有配置项，提供全局统一的配置接口。
所有配置项都有合理的默认值，确保程序在缺少配置时也能优雅降级。
"""

import os
from typing import Optional
from dotenv import load_dotenv

# ====================
# 加载 .env 文件
# ====================

# 查找并加载 .env 文件（从当前目录向上查找）
# 这样无论从哪个目录运行都能找到配置文件
load_dotenv()

# ====================
# 大模型 API 配置
# ====================

# 智谱 AI API Key（必填）
LLM_API_KEY: str = os.getenv("LLM_API_KEY", "")

# 大模型 API 基础 URL（默认智谱 AI）
LLM_BASE_URL: str = os.getenv(
    "LLM_BASE_URL", 
    "https://open.bigmodel.cn/api/paas/v4/"
)

# 大模型名称（默认智谱 GLM-4-Flash，免费且快速）
LLM_MODEL_NAME: str = os.getenv("LLM_MODEL_NAME", "glm-4-flash")

# 大模型调用超时时间（秒）
LLM_TIMEOUT: int = int(os.getenv("LLM_TIMEOUT", "30"))

# 大模型最大重试次数
LLM_MAX_RETRIES: int = int(os.getenv("LLM_MAX_RETRIES", "2"))

# ====================
# 数据库配置
# ====================

# SQLite 数据库文件路径
DATABASE_PATH: str = os.getenv("DATABASE_PATH", "./data/tickets.db")

# 确保 data 目录存在（延迟到使用时创建，这里只负责提供路径）
def ensure_data_dir() -> None:
    """确保数据库目录存在"""
    db_dir = os.path.dirname(DATABASE_PATH)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)

# ====================
# 文件上传配置
# ====================

# 临时文件上传目录
UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", "./uploads")

# 上传文件大小限制（MB）
MAX_FILE_SIZE_MB: int = int(os.getenv("MAX_FILE_SIZE_MB", "10"))

# 上传文件大小限制（字节）
MAX_FILE_SIZE_BYTES: int = MAX_FILE_SIZE_MB * 1024 * 1024

# 允许的图片格式
ALLOWED_IMAGE_EXTENSIONS: list = [".jpg", ".jpeg", ".png", ".bmp", ".webp"]

# 允许的视频格式（可选，加分项）
ALLOWED_VIDEO_EXTENSIONS: list = [".mp4", ".avi", ".mov", ".mkv"]

# ====================
# 服务配置
# ====================

# 后端服务端口
SERVER_PORT: int = int(os.getenv("SERVER_PORT", "8000"))

# 后端服务主机（0.0.0.0 表示允许外部访问）
SERVER_HOST: str = os.getenv("SERVER_HOST", "0.0.0.0")

# 是否启用调试模式（开发环境 true，生产环境 false）
DEBUG_MODE: bool = os.getenv("DEBUG_MODE", "true").lower() == "true"

# API 是否启用跨域（开发环境启用，生产环境可限制具体域名）
CORS_ORIGINS: list = os.getenv("CORS_ORIGINS", "*").split(",")

# ====================
# OCR 配置
# ====================

# PaddleOCR 使用设备（cpu / cuda / gpu）
OCR_DEVICE: str = os.getenv("OCR_DEVICE", "cpu")

# OCR 语言（ch 中文简体，en 英文，ch_en 中英文混合）
OCR_LANG: str = os.getenv("OCR_LANG", "ch")

# 是否启用 OCR（如果为 false，则跳过 OCR 直接返回空字符串）
OCR_ENABLED: bool = os.getenv("OCR_ENABLED", "true").lower() == "true"

# 是否启用视频抽帧 OCR（加分项，默认关闭）
VIDEO_OCR_ENABLED: bool = os.getenv("VIDEO_OCR_ENABLED", "false").lower() == "true"

# 视频抽帧间隔（秒），默认抽取第一帧
VIDEO_FRAME_INTERVAL: float = float(os.getenv("VIDEO_FRAME_INTERVAL", "0"))

# ====================
# 保修校验配置
# ====================

# 保修年限（默认 2 年）
WARRANTY_YEARS: int = int(os.getenv("WARRANTY_YEARS", "2"))

# 保修规则说明（用于提示）
WARRANTY_RULE: str = f"自生产日期起 {WARRANTY_YEARS} 年内保修"

# 模拟保修数据库路径（可选，用于存放 SN 码映射表）
WARRANTY_DB_PATH: Optional[str] = os.getenv("WARRANTY_DB_PATH", None)

# ====================
# SOP 知识库配置（可选，RAG 增强）
# ====================

# SOP 知识库文件路径（JSON 格式）
SOP_KNOWLEDGE_PATH: str = os.getenv("SOP_KNOWLEDGE_PATH", "./data/sop_knowledge.json")

# 是否启用 RAG 向量检索（false 则使用简单字典匹配）
RAG_ENABLED: bool = os.getenv("RAG_ENABLED", "false").lower() == "true"

# 向量数据库路径（RAG 模式使用）
CHROMA_DB_PATH: str = os.getenv("CHROMA_DB_PATH", "./data/chroma_db")

# ====================
# 工单配置
# ====================

# 工单 ID 前缀
TICKET_ID_PREFIX: str = os.getenv("TICKET_ID_PREFIX", "CS")

# 日志级别（DEBUG, INFO, WARNING, ERROR）
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

# ====================
# 配置验证函数
# ====================

def validate_config() -> tuple[bool, list[str]]:
    """
    验证配置是否有效
    
    Returns:
        (is_valid, error_messages): 是否有效，以及错误信息列表
    """
    errors = []
    
    # 检查大模型 API Key（非调试模式时必填）
    if not DEBUG_MODE and not LLM_API_KEY:
        errors.append("生产环境下必须在 .env 文件中设置 LLM_API_KEY")
    
    # 检查数据库目录是否可创建
    db_dir = os.path.dirname(DATABASE_PATH)
    if db_dir and not os.path.exists(db_dir):
        try:
            # 尝试创建目录（不在这里执行，只做提醒）
            pass
        except Exception:
            errors.append(f"无法创建数据库目录: {db_dir}")
    
    # 检查上传目录是否可写
    if not os.path.exists(UPLOAD_DIR):
        try:
            os.makedirs(UPLOAD_DIR, exist_ok=True)
        except Exception as e:
            errors.append(f"无法创建上传目录 {UPLOAD_DIR}: {str(e)}")
    
    # 检查保修年限是否合理
    if WARRANTY_YEARS <= 0 or WARRANTY_YEARS > 10:
        errors.append(f"保修年限应在 1-10 年之间，当前值: {WARRANTY_YEARS}")
    
    return len(errors) == 0, errors


def print_config() -> None:
    """打印当前配置（用于调试，注意隐藏敏感信息）"""
    print("\n" + "=" * 50)
    print("当前配置信息")
    print("=" * 50)
    
    # 大模型配置（隐藏 API Key）
    masked_key = LLM_API_KEY[:8] + "..." + LLM_API_KEY[-4:] if len(LLM_API_KEY) > 12 else "未设置"
    print(f"LLM_API_KEY:      {masked_key}")
    print(f"LLM_BASE_URL:     {LLM_BASE_URL}")
    print(f"LLM_MODEL_NAME:   {LLM_MODEL_NAME}")
    print(f"LLM_TIMEOUT:      {LLM_TIMEOUT}s")
    
    # 数据库配置
    print(f"DATABASE_PATH:    {DATABASE_PATH}")
    
    # 文件上传配置
    print(f"UPLOAD_DIR:       {UPLOAD_DIR}")
    print(f"MAX_FILE_SIZE:    {MAX_FILE_SIZE_MB}MB")
    
    # 服务配置
    print(f"SERVER_HOST:      {SERVER_HOST}")
    print(f"SERVER_PORT:      {SERVER_PORT}")
    print(f"DEBUG_MODE:       {DEBUG_MODE}")
    
    # OCR 配置
    print(f"OCR_ENABLED:      {OCR_ENABLED}")
    print(f"OCR_DEVICE:       {OCR_DEVICE}")
    print(f"OCR_LANG:         {OCR_LANG}")
    
    # 保修配置
    print(f"WARRANTY_YEARS:   {WARRANTY_YEARS}")
    
    # RAG 配置
    print(f"RAG_ENABLED:      {RAG_ENABLED}")
    
    # 其他
    print(f"TICKET_ID_PREFIX: {TICKET_ID_PREFIX}")
    print(f"LOG_LEVEL:        {LOG_LEVEL}")
    print("=" * 50 + "\n")


# ====================
# 便捷函数
# ====================

def is_api_configured() -> bool:
    """检查大模型 API 是否已配置"""
    return bool(LLM_API_KEY)


def get_upload_dir_abs() -> str:
    """获取上传目录的绝对路径"""
    return os.path.abspath(UPLOAD_DIR)


def get_db_path_abs() -> str:
    """获取数据库文件的绝对路径"""
    return os.path.abspath(DATABASE_PATH)


# ====================
# 模块初始化（可选）
# ====================

# 如果不在调试模式，检查关键配置
if not DEBUG_MODE:
    if not is_api_configured():
        print("⚠️  警告: 生产模式下未配置 LLM_API_KEY，请在 .env 文件中设置")
    
    # 确保必要的目录存在
    ensure_data_dir()
    os.makedirs(UPLOAD_DIR, exist_ok=True)

# 如果在调试模式，打印配置信息（方便调试）
if DEBUG_MODE:
    print_config()
