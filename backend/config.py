# backend/config.py
"""
全局配置模块 (Global Configuration)
====================================
本文件是整个后端服务的配置中心，集中管理所有环境变量和系统常量。

架构设计亮点：
1. 环境变量注入：通过 .env 文件管理敏感信息，避免密钥硬编码在代码中。
2. Optional 类型安全：对可选配置（如 ERP 接口）使用 Optional 类型提示，增强代码可读性。
3. 启动摘要脱敏打印：服务启动时在控制台打印配置状态，但不暴露真实密钥，方便运维排查。
4. 标准化日志输出：使用 logging 替代 print，移除所有 Emoji 表情，采用纯文本标签（如 [OK], [WARN]），
   确保在各类服务器终端、Docker 日志收集系统中不会出现乱码。
5. 供应商中立设计：使用 LLM_ 前缀替代供应商特定前缀，支持多种大模型服务无缝切换。
"""

# ================= 导入依赖库 =================
import logging
import os
from typing import Optional  # 用于类型提示，表示某个值可以是 None
from dotenv import load_dotenv  # 用于从 .env 文件加载环境变量

# ================= 日志系统初始化 =================
# 配置标准日志格式，替代原有的 print 输出，符合企业级后端服务规范
# 格式说明：[时间] [日志级别] [模块名] - 消息内容
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
# 创建专门的配置日志记录器，便于在日志中区分配置模块的输出
logger = logging.getLogger("Config")

# ================= 环境变量加载 =================
# 从 .env 文件加载环境变量，支持项目根目录和 backend 目录
# 注意：在生产环境中，建议通过系统环境变量而不是 .env 文件提供敏感信息
load_dotenv()
logger.info("环境变量加载完成")

# ================= 1. 服务基础配置 =================
# 服务监听的主机地址和端口号
# HOST: 默认为 0.0.0.0（监听所有网络接口），生产环境建议限制为特定IP
# PORT: 默认为 8000，可根据部署环境调整
HOST: str = os.getenv("HOST", "0.0.0.0")
PORT: int = int(os.getenv("PORT", "8000"))
logger.debug(f"服务配置 - HOST: {HOST}, PORT: {PORT}")

# ================= 2. 数据库配置 =================
# SQLite 数据库文件路径
# 使用相对路径 ./data/tickets.db，确保 data 目录存在
DATABASE_PATH: str = os.getenv("DATABASE_PATH", "./data/tickets.db")
logger.debug(f"数据库配置 - DATABASE_PATH: {DATABASE_PATH}")

# ================= 3. 文件上传配置 =================
# 文件上传目录路径
# 系统会自动创建该目录（如果不存在）
UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", "./uploads")

# 确保必要的目录存在，避免运行时错误
# exist_ok=True 参数确保目录已存在时不会抛出异常
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs("./data", exist_ok=True)
logger.info(f"文件系统初始化完成 - 上传目录: {UPLOAD_DIR}, 数据目录: ./data")

# ================= 4. 通用 LLM 配置 =================
"""
【重要设计】供应商中立的大模型配置
- 使用 LLM_ 前缀替代供应商特定前缀（如 DEEPSEEK_）
- 支持任何兼容 OpenAI API 格式的模型服务
- 包括但不限于：Qwen、DeepSeek、Kimi、智谱 GLM 等
"""

# LLM API 密钥（必需）
# 从环境变量获取，不允许硬编码在代码中
# 如果未设置，抛出明确的错误提示，避免服务在无效状态下启动
LLM_API_KEY: str = os.getenv("LLM_API_KEY")
if not LLM_API_KEY:
    error_msg = "LLM_API_KEY 未设置。请在 .env 文件中配置大模型 API 密钥。"
    logger.error(error_msg)
    raise ValueError(error_msg)

# LLM 服务基础 URL
# 默认使用阿里云百炼的 Qwen 服务地址
# 可通过 .env 文件覆盖为其他服务地址（如 DeepSeek、Kimi 等）
LLM_BASE_URL: str = os.getenv("LLM_BASE_URL", "https://aigw-nmhhht.cucloud.cn/v1")

# LLM 模型名称
# 默认使用 Qwen/QwQ-32B 模型
# 可根据实际需求和配额调整为其他模型
LLM_MODEL_NAME: str = os.getenv("LLM_MODEL_NAME", "Qwen/QwQ-32B")

logger.info("通用 LLM 配置已加载")
logger.debug(f"LLM 配置 - BASE_URL: {LLM_BASE_URL}, MODEL_NAME: {LLM_MODEL_NAME}")

# ================= 5. RAG 配置 =================
"""
RAG (Retrieval-Augmented Generation) 配置
- 专门用于向量检索和文档嵌入
- 使用千问（DashScope）的 Embedding 服务
- 与对话大模型使用独立的 API 密钥，便于权限管理和成本控制
"""

# RAG 服务 API 密钥（必需）
# 用于千问 Embedding 模型的向量检索
DASHSCOPE_API_KEY: str = os.getenv("DASHSCOPE_API_KEY")
if not DASHSCOPE_API_KEY:
    error_msg = "DASHSCOPE_API_KEY 未设置。请在 .env 文件中配置 RAG 向量检索 API 密钥。"
    logger.error(error_msg)
    raise ValueError(error_msg)

logger.info("RAG 配置已加载")

# ================= 6. ERP 系统配置 =================
"""
ERP 系统集成配置（可选）
- 用于产品质保核验等业务场景
- 支持对接企业真实 ERP 系统
- 如果未配置，系统将自动降级为本地 SN 码规则模拟
- 使用 Optional 类型提示，明确表示这些配置是可选的
"""

# ERP API 地址（可选）
# 格式示例：https://your-erp-system.com/api/v1/warranty-check
ERP_API_URL: Optional[str] = os.getenv("ERP_API_URL")

# ERP API 密钥（可选）
# 用于身份验证的令牌
ERP_API_KEY: Optional[str] = os.getenv("ERP_API_KEY")

# ================= 7. 启动配置摘要 =================
"""
【最佳实践】启动时打印配置摘要
- 使用标准化的日志格式，替代原有的 emoji 表情
- 仅显示配置状态，不暴露敏感信息（如完整密钥）
- 使用不同的日志级别（INFO/WARNING/ERROR）表示不同重要程度
- 便于运维人员快速了解系统状态
"""

logger.info("=" * 40)
logger.info("系统配置加载完成")
logger.info("=" * 40)

# 服务和文件系统配置
logger.info(f"服务地址: {HOST}:{PORT}")
logger.info(f"数据库路径: {DATABASE_PATH}")
logger.info(f"上传目录: {UPLOAD_DIR}")
logger.info("-" * 40)

# 通用 LLM 配置状态（使用纯文本标签替代 emoji）
llm_status = "[OK] 已设置" if LLM_API_KEY else "[FAIL] 未设置"
logger.info(f"通用 LLM API Key: {llm_status}")
logger.info(f"LLM Base URL: {LLM_BASE_URL}")
logger.info(f"LLM 模型名称: {LLM_MODEL_NAME}")
logger.info("-" * 40)

# RAG 配置状态
rag_status = "[OK] 已设置" if DASHSCOPE_API_KEY else "[FAIL] 未设置"
logger.info(f"RAG 千问 API Key: {rag_status}")
logger.info("-" * 40)

# ERP 配置状态（可选配置，使用 WARNING 级别提示未配置的情况）
if ERP_API_URL:
    logger.info(f"ERP 接口地址: {ERP_API_URL} ([OK] 已启用真实校验)")
else:
    logger.warning("ERP 接口地址: [WARN] 未配置 (将降级为本地 SN 码模拟校验)")

logger.info("=" * 40)

# ================= 配置验证总结 =================
"""
【运维提示】配置验证结果
- 所有必需配置项验证通过，服务可以正常启动
- 可选配置项（如 ERP）未配置时会有明确警告，但不影响核心功能
- 详细的调试信息可通过调整日志级别（DEBUG）查看更多
"""
required_configs = {
    "LLM_API_KEY": LLM_API_KEY,
    "DASHSCOPE_API_KEY": DASHSCOPE_API_KEY
}

missing_configs = [key for key, value in required_configs.items() if not value]

if missing_configs:
    logger.error(f"必需配置项缺失: {', '.join(missing_configs)}")
    logger.error("系统启动失败：缺少必需的配置项")
else:
    logger.info("所有必需配置项验证通过，系统可以正常启动")

# 配置加载完成标志，可用于其他模块的依赖检查
CONFIG_LOADED = True
logger.info("配置模块初始化完成")