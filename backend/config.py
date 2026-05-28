# backend/config.py
"""
全局配置模块
架构优化：环境变量注入、Optional 类型安全、启动摘要脱敏打印
"""
import os
from typing import Optional
from dotenv import load_dotenv

# 加载 .env 文件（支持项目根目录和 backend 目录）
load_dotenv()

# ================= 服务配置 =================
HOST: str = os.getenv("HOST", "0.0.0.0")
PORT: int = int(os.getenv("PORT", "8000"))

# ================= 数据库配置 =================
DATABASE_PATH: str = os.getenv("DATABASE_PATH", "./data/tickets.db")

# ================= 文件上传配置 =================
UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", "./uploads")

# 确保必要的目录存在
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs("./data", exist_ok=True)

# ================= 通用 LLM 配置 (兼容 OpenAI SDK) =================
# 【核心修改】将 DEEPSEEK_ 前缀改为 LLM_，彻底解除与单一供应商的绑定
# 支持任何兼容 OpenAI API 格式的模型 (如 Qwen, DeepSeek, Kimi, 智谱 GLM 等)
# 必须从环境变量读取，不可硬编码
LLM_API_KEY: str = os.getenv("LLM_API_KEY")
if not LLM_API_KEY:
    raise ValueError("请在 .env 文件中设置 LLM_API_KEY (大模型 API 密钥)")

# 默认提供 Qwen (阿里云百炼) 的兼容地址，也可在 .env 中覆盖为 DeepSeek 等其他地址
LLM_BASE_URL: str = os.getenv("LLM_BASE_URL", "https://aigw-nmhhht.cucloud.cn/v1")
LLM_MODEL_NAME: str = os.getenv("LLM_MODEL_NAME", "Qwen/QwQ-32B")

# ================= RAG 配置（千问 Embedding）=================
# 注意：这里保留独立的 DASHSCOPE_API_KEY，因为 RAG 的向量化模型 (Embedding)
# 可能与对话大模型 (Chat) 使用不同的服务或密钥
DASHSCOPE_API_KEY: str = os.getenv("DASHSCOPE_API_KEY")
if not DASHSCOPE_API_KEY:
    raise ValueError("请在 .env 文件中设置 DASHSCOPE_API_KEY (用于 RAG 向量检索)")

# ================= ERP 系统配置 (可选，用于质保核验) =================
# 【新增】支持对接企业真实 ERP 系统。若未配置，系统将自动降级为本地 SN 码规则模拟。
ERP_API_URL: Optional[str] = os.getenv("ERP_API_URL")
ERP_API_KEY: Optional[str] = os.getenv("ERP_API_KEY")

# ================= 启动配置摘要打印 =================
# 打印配置摘要（不打印密钥，只打印是否存在），方便排查环境问题
print("="*40)
print("✅ 系统配置加载完成")
print("="*40)
print(f"🌐 服务地址: {HOST}:{PORT}")
print(f"💾 数据库路径: {DATABASE_PATH}")
print(f"📁 上传目录: {UPLOAD_DIR}")
print("-" * 40)
print(f"🤖 通用 LLM API Key: {'✅ 已设置' if LLM_API_KEY else '❌ 未设置'}")
print(f"🔗 LLM Base URL: {LLM_BASE_URL}")
print(f"🧠 LLM 模型名称: {LLM_MODEL_NAME}")
print("-" * 40)
print(f"📚 RAG 千问 API Key: {'✅ 已设置' if DASHSCOPE_API_KEY else '❌ 未设置'}")
print("-" * 40)
# 【新增】ERP 配置状态打印
if ERP_API_URL:
    print(f"🏢 ERP 接口地址: {ERP_API_URL} (✅ 已启用真实校验)")
else:
    print(f"🏢 ERP 接口地址: ❌ 未配置 (⚠️ 将降级为本地 SN 码模拟校验)")
print("="*40)