import os
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

# ================= LLM 配置（DeepSeek）=================
# 必须从环境变量读取，不可硬编码
DEEPSEEK_API_KEY: str = os.getenv("DEEPSEEK_API_KEY")
if not DEEPSEEK_API_KEY:
    raise ValueError("请在 .env 文件中设置 DEEPSEEK_API_KEY")

DEEPSEEK_BASE_URL: str = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
DEEPSEEK_MODEL_NAME: str = os.getenv("DEEPSEEK_MODEL_NAME", "deepseek-chat")

# ================= RAG 配置（千问 Embedding）=================
DASHSCOPE_API_KEY: str = os.getenv("DASHSCOPE_API_KEY")
if not DASHSCOPE_API_KEY:
    raise ValueError("请在 .env 文件中设置 DASHSCOPE_API_KEY")

# ================= 其他可选配置 =================
# 例如 OCR 模型路径等，可根据需要扩展

# 打印配置摘要（不打印密钥，只打印是否存在）
print("=== 配置加载完成 ===")
print(f"服务地址: {HOST}:{PORT}")
print(f"数据库路径: {DATABASE_PATH}")
print(f"上传目录: {UPLOAD_DIR}")
print(f"DeepSeek API Key: {'已设置' if DEEPSEEK_API_KEY else '未设置'}")
print(f"DeepSeek Base URL: {DEEPSEEK_BASE_URL}")
print(f"DeepSeek 模型: {DEEPSEEK_MODEL_NAME}")
print(f"千问 API Key: {'已设置' if DASHSCOPE_API_KEY else '未设置'}")