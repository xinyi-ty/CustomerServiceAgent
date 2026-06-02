# backend/mock_erp_server.py
"""
模拟企业 ERP 质保校验接口 (Mock Server)
用于本地联调，运行在 8001 端口，模拟真实 ERP 的各种响应状态（包括故障）
"""
import asyncio
import logging
from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException, Header

logger = logging.getLogger(__name__)

app = FastAPI(title="Mock ERP System", description="模拟的工厂 ERP 质保查询 API")

# 模拟的鉴权 Token (需与主系统的 .env 保持一致)
MOCK_API_KEY = "mock_secret_token_123"

# 模拟的 ERP 数据库 (仅保留正常业务数据)
MOCK_DB = {
    "SN202501001": {"expire_date": (datetime.now() + timedelta(days=365)).strftime("%Y-%m-%d"), "status": "active"},  # 在保
    "SN202005002": {"expire_date": "2022-05-01", "status": "expired"},  # 过保
    "SN999999999": None  # 查无此机
}

@app.get("/warranty/{sn_code}")
async def get_warranty_status(sn_code: str, authorization: str = Header(None)):
    logger.info(f"收到请求: SN={sn_code}")

    # 1. 鉴权校验
    if authorization != f"Bearer {MOCK_API_KEY}":
        logger.warning("鉴权失败")
        raise HTTPException(status_code=401, detail="Invalid API Key")

    # 2. 模拟网络延迟/超时
    if sn_code.upper() == "SN_TIMEOUT":
        logger.warning("模拟 ERP 响应缓慢 (Sleep 6秒)...")
        await asyncio.sleep(6)
        return {
            "sn_code": sn_code,
            "expire_date": "2026-01-01",
            "device_model": "X-Pro 2000",
            "factory": "Shenzhen Plant A"
        }

    # 3. 模拟系统崩溃
    if sn_code.upper() == "SN_ERROR":
        logger.error("模拟 ERP 内部错误 (返回 500)...")
        raise HTTPException(status_code=500, detail="Internal Server Error")

    # 4. 正常业务查询
    record = MOCK_DB.get(sn_code.upper())
    if record is None:
        logger.warning(f"未找到记录: {sn_code}")
        raise HTTPException(status_code=404, detail="Device not found")

    logger.info(f"查询成功: {record}")
    return {
        "sn_code": sn_code,
        "expire_date": record["expire_date"],
        "device_model": "X-Pro 2000",
        "factory": "Shenzhen Plant A"
    }

if __name__ == "__main__":
    import uvicorn
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    logger.info("模拟 ERP 系统启动中...")
    logger.info("接口地址: http://127.0.0.1:8001/warranty/{sn_code}")
    uvicorn.run(app, host="127.0.0.1", port=8001)