"""
产品信息查询模块
=================
通过 SN 码或订单号查询产品注册表，将产品上下文注入智能体对话。
支持文本匹配和 OCR 文本中提取 SN/订单号后进行查询。
"""
import logging
import re
from typing import Optional, Dict, Tuple

from database import lookup_product_by_sn, lookup_product_by_order

logger = logging.getLogger(__name__)


def find_sn_in_text(text: str) -> Optional[str]:
    """
    从一段文本中提取可能的 SN 码。
    匹配模式：SN 前缀 + 8-20 位字母数字组合
    """
    if not text:
        return None
    # 精确匹配 SN:xxx 或 SN xxx 格式
    prefix_pattern = r'(?:SN|S/N|序列号|出厂编号)[:\s\-_]*([A-Za-z0-9]{6,20})'
    match = re.search(prefix_pattern, text, re.IGNORECASE)
    if match:
        return match.group(1).upper()
    return None


def find_order_id_in_text(text: str) -> Optional[str]:
    """
    从一段文本中提取可能的订单号。
    匹配常见订单号模式：字母前缀 + 数字组合
    """
    if not text:
        return None
    # 匹配常见的订单号格式：大写字母前缀 + 数字
    order_pattern = r'\b[A-Z]{2,8}\d{6,20}\b'
    match = re.search(order_pattern, text)
    if match:
        return match.group(0)
    return None


def lookup_product(user_text: str, ocr_text: str = "") -> Optional[Dict]:
    """
    综合查询：从用户文本和 OCR 文本中提取 SN/订单号，返回产品信息。
    优先使用 SN 码查询，其次订单号。
    """
    combined = user_text + " " + ocr_text if ocr_text else user_text

    # 1. 优先 SN 码查询
    sn = find_sn_in_text(combined)
    if sn:
        product = lookup_product_by_sn(sn)
        if product:
            logger.info(f"[INFO] 产品查询命中 SN: {sn} → {product.get('model_number')}")
            return product

    # 2. 其次订单号查询
    order = find_order_id_in_text(combined)
    if order:
        product = lookup_product_by_order(order)
        if product:
            logger.info(f"[INFO] 产品查询命中订单: {order} → {product.get('model_number')}")
            return product

    logger.info(f"[INFO] 产品查询未命中: 未找到匹配的 SN 或订单号")
    return None


def format_product_context(product: Optional[Dict]) -> str:
    """
    将产品信息格式化为 LLM 可读的上下文文本。
    仅提供产品身份信息，保修状态由 warranty.py 统一核验。
    """
    if not product:
        return ""

    model = product.get("model_number", "未知型号")
    prod_name = product.get("product_name", "")
    batch = product.get("batch_code", "未知")
    order = product.get("order_id", "未知")
    sn = product.get("sn_code", "未知")

    lines = [
        f"【系统查询到您的设备信息】",
        f"  产品型号：{model} {prod_name}".strip(),
        f"  SN 序列号：{sn}",
        f"  订单编号：{order}",
    ]
    if batch and batch != "未知":
        lines.append(f"  批次编码：{batch}")
    return "\n".join(lines)
