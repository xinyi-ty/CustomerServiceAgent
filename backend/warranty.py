# backend/warranty.py
"""
质保期校验模块 (Warranty Status Checker)
架构优化：异步非阻塞、安全日期计算、TTL 缓存防 ERP 击穿、Tenacity 重试降级
"""
import logging
import os
from datetime import datetime
from typing import Optional
from functools import lru_cache
from dateutil.relativedelta import relativedelta

import httpx
from pydantic import BaseModel, Field
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from config import ERP_API_URL, ERP_API_KEY

logger = logging.getLogger(__name__)


# ==========================================
# 1. 数据结构定义
# ==========================================
class WarrantyResult(BaseModel):
    status: str = Field(..., description="In_Warranty / Out_of_Warranty / Unknown")
    expire_date: Optional[str] = Field(None, description="质保到期日 (YYYY-MM-DD)")
    source: str = Field(..., description="数据来源: Local_Simulation / ERP_API / Fallback")
    message: str = Field(..., description="给用户的提示信息")


# ==========================================
# 2. 本地模拟校验 (兜底与离线支持)
# ==========================================
def _check_local_warranty(sn_code: str) -> WarrantyResult:
    """
    基于 SN 码的本地规则模拟校验 (赛事加分项：断网可用)
    假设规则：SN 码前 4 位为生产年份，后 2 位为月份。质保期 2 年。
    """
    try:
        # 清洗前缀
        clean_sn = sn_code.upper()
        if clean_sn.startswith("SN"):
            clean_sn = clean_sn[2:]

        if len(clean_sn) < 6:
            return WarrantyResult(status="Unknown", source="Local_Simulation", message="SN 码格式过短。")

        year_str, month_str = clean_sn[:4], clean_sn[4:6]

        if not (year_str.isdigit() and month_str.isdigit()):
            return WarrantyResult(status="Unknown", source="Local_Simulation", message="SN 码包含非数字字符。")

        year, month = int(year_str), int(month_str)
        if not (2000 <= year <= 2099 and 1 <= month <= 12):
            return WarrantyResult(status="Unknown", source="Local_Simulation", message="生产日期不在合理范围。")

        produce_date = datetime(year, month, 1)
        # 【修复】使用 relativedelta 安全计算日期，避免闰年 2月29日 加年份报错
        expire_date = produce_date + relativedelta(years=2)

        is_in_warranty = datetime.now() < expire_date

        return WarrantyResult(
            status="In_Warranty" if is_in_warranty else "Out_of_Warranty",
            expire_date=expire_date.strftime("%Y-%m-%d"),
            source="Local_Simulation",
            message=f"设备于 {year}年{month}月 生产，质保至 {expire_date.strftime('%Y-%m-%d')}。"
        )
    except Exception as e:
        logger.error(f"[ERROR] 本地质保校验异常: {e}")
        return WarrantyResult(status="Unknown", source="Local_Simulation", message="本地解析失败。")


# ==========================================
# 3. 远程 ERP API 校验 (带重试与缓存)
# ==========================================
@retry(
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=1, min=1, max=3),
    retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError)),
    reraise=True
)
async def _fetch_erp_warranty(sn_code: str) -> Optional[WarrantyResult]:
    """异步请求 ERP API 获取真实质保数据"""
    if not ERP_API_URL:
        return None

    async with httpx.AsyncClient(timeout=5.0) as client:
        headers = {"Authorization": f"Bearer {ERP_API_KEY}"} if ERP_API_KEY else {}
        response = await client.get(f"{ERP_API_URL}/warranty/{sn_code}", headers=headers)

        if response.status_code == 404:
            return WarrantyResult(
                status="Out_of_Warranty", source="ERP_API", message="ERP 系统未查询到该设备记录，视为过保。"
            )
        response.raise_for_status()
        data = response.json()

        expire_str = data.get("expire_date")
        expire_date = datetime.strptime(expire_str, "%Y-%m-%d") if expire_str else None
        is_in_warranty = expire_date and datetime.now() < expire_date if expire_date else False

        return WarrantyResult(
            status="In_Warranty" if is_in_warranty else "Out_of_Warranty",
            expire_date=expire_str,
            source="ERP_API",
            message=f"ERP 核实：设备质保状态为 {'在保' if is_in_warranty else '已过保'}。"
        )


# ==========================================
# 4. 核心对外接口 (融合校验 + TTL 缓存)
# ==========================================
# 【优化】引入带 TTL 的缓存，防止同一 SN 码在多轮对话中反复击穿 ERP 接口
@lru_cache(maxsize=1024)
def _cached_check(sn_code: str) -> WarrantyResult:
    """
    注意：lru_cache 只能缓存同步函数。
    我们在异步接口中通过 asyncio.to_thread 调用此函数，或者在同步上下文中直接调用。
    为了简化 FastAPI 异步调用，这里我们采用手动缓存字典+时间戳的方式实现异步缓存。
    """
    pass


# 手动实现异步安全的 TTL 缓存
_warranty_cache: dict[str, tuple[float, WarrantyResult]] = {}
CACHE_TTL_SECONDS = 3600  # 缓存 1 小时


async def check_warranty_status(sn_code: Optional[str]) -> WarrantyResult:
    """
    融合校验入口：优先查缓存 -> 请求 ERP -> 降级到本地模拟
    """
    if not sn_code:
        return WarrantyResult(status="Unknown", source="Fallback", message="未提供 SN 码，无法校验质保。")

    sn_code = sn_code.strip().upper()

    # 1. 检查缓存
    now = datetime.now().timestamp()
    if sn_code in _warranty_cache:
        cache_time, cached_result = _warranty_cache[sn_code]
        if now - cache_time < CACHE_TTL_SECONDS:
            logger.info(f"[INFO] 命中质保缓存: {sn_code}")
            return cached_result

    # 2. 尝试请求 ERP API
    try:
        erp_result = await _fetch_erp_warranty(sn_code)
        if erp_result:
            _warranty_cache[sn_code] = (now, erp_result)
            return erp_result
    except Exception as e:
        logger.warning(f"[WARN] ERP API 请求失败，降级到本地校验: {e}")

    # 3. 降级到本地模拟
    local_result = _check_local_warranty(sn_code)
    _warranty_cache[sn_code] = (now, local_result)
    return local_result