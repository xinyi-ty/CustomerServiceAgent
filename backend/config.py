import os
from dotenv import load_dotenv

load_dotenv()

LLM_API_KEY: str = os.getenv("LLM_API_KEY", "")
LLM_BASE_URL: str = os.getenv("LLM_BASE_URL", "https://open.bigmodel.cn/api/paas/v4/")
LLM_MODEL_NAME: str = os.getenv("LLM_MODEL_NAME", "glm-4-flash")
DATABASE_PATH: str = os.getenv("DATABASE_PATH", "./data/tickets.db")
UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", "./uploads")