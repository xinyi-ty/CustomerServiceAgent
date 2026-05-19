import os
from dotenv import load_dotenv
#
#加载 .env 文件
load_dotenv()
#
#LLM 配置
LLM_API_KEY: str = os.getenv("LLM_API_KEY", "")
LLM_BASE_URL: str = os.getenv("LLM_BASE_URL", "https://open.bigmodel.cn/api/paas/v4/")
LLM_MODEL_NAME: str = os.getenv("LLM_MODEL_NAME", "glm-4-flash")
#
#数据库配置
DATABASE_PATH: str = os.getenv("DATABASE_PATH", "./data/tickets.db")

文件上传配置
UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", "./uploads")

服务配置
HOST: str = os.getenv("HOST", "0.0.0.0")
PORT: int = int(os.getenv("PORT", "8000"))

# 确保上传目录存在
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs("./data", exist_ok=True)



#RAG使用并修改
import os
from dotenv import load_dotenv

load_dotenv()

# 千问
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY")

# DeepSeek
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")