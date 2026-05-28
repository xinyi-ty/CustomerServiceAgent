# backend/mock_erp_server.py
"""
模拟企业 ERP 质保校验接口 (Mock Server)
用于本地联调，运行在 8001 端口，模拟真实 ERP 的各种响应状态（包括故障）
"""
import asyncio
from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException, Header

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
    print(f"\n[ERP Mock] 收到请求: SN={sn_code}, Token={authorization}")

    # 1. 鉴权校验
    if authorization != f"Bearer {MOCK_API_KEY}":
        print("[ERP Mock] ❌ 鉴权失败")
        raise HTTPException(status_code=401, detail="Invalid API Key")

    # 2. 模拟网络延迟/超时 (使用 asyncio.sleep 避免阻塞事件循环)
    if sn_code.upper() == "SN_TIMEOUT":
        print("[ERP Mock] ⏳ 模拟 ERP 响应缓慢 (Sleep 6秒，将触发主系统超时)...")
        await asyncio.sleep(6)
        # 超时后依然返回正常数据，用于测试主系统的 httpx 超时拦截机制
        return {
            "sn_code": sn_code,
            "expire_date": "2026-01-01",
            "device_model": "X-Pro 2000",
            "factory": "Shenzhen Plant A"
        }

    # 3. 模拟系统崩溃 (测试主系统的 Tenacity 重试与降级机制)
    if sn_code.upper() == "SN_ERROR":
        print("[ERP Mock] 💥 模拟 ERP 内部错误 (返回 500)...")
        raise HTTPException(status_code=500, detail="Internal Server Error")

    # 4. 正常业务查询
    record = MOCK_DB.get(sn_code.upper())
    if record is None:
        print(f"[ERP Mock] ⚠️ 未找到记录: {sn_code}")
        raise HTTPException(status_code=404, detail="Device not found")

    print(f"[ERP Mock] ✅ 查询成功: {record}")
    return {
        "sn_code": sn_code,
        "expire_date": record["expire_date"],
        "device_model": "X-Pro 2000",
        "factory": "Shenzhen Plant A"
    }

if __name__ == "__main__":
    import uvicorn
    print("=" * 40)
    print("🏭 模拟 ERP 系统启动中...")
    print("🔗 接口地址: http://127.0.0.1:8001/warranty/{sn_code}")
    print("=" * 40)
    uvicorn.run(app, host="127.0.0.1", port=8001)