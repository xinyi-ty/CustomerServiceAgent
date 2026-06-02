# backend/ocr_utils.py
"""
多模态 OCR 处理模块 (图片/视频)
架构优化：异步安全 (不阻塞 FastAPI)、延迟单例加载、SN 码智能提取、视频关键帧去重
"""
import asyncio
import logging
import os
import re
import io
from typing import Optional, Tuple

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# ==========================================
# 1. OCR 引擎延迟单例加载
# ==========================================
_ocr_engine = None


def _get_ocr_engine():
    """
    延迟加载 OCR 引擎 (以 PaddleOCR 为例，若使用 EasyOCR 或云 API 请替换此处)
    使用 global 确保全局只加载一次，避免重复消耗内存和初始化时间
    """
    # 抑制 PaddlePaddle 环境检查与 oneDNN 日志
    os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "1")
    os.environ.setdefault("GLOG_minloglevel", "2")

    global _ocr_engine
    if _ocr_engine is None:
        try:
            from paddleocr import PaddleOCR
            logger.info("[INFO] 正在初始化 PaddleOCR 引擎 (首次加载较慢)...")
            # use_angle_cls=True 支持旋转文字识别，lang='ch' 支持中英混合
            _ocr_engine = PaddleOCR(use_textline_orientation=True, lang='ch')
            logger.info("[INFO] PaddleOCR 引擎初始化完成")
        except ImportError:
            logger.error("[ERROR] 未安装 paddleocr，请执行: pip install paddlepaddle paddleocr")
            raise
    return _ocr_engine


# ==========================================
# 2. 图像预处理与后处理 (赛事加分项)
# ==========================================

# OCR 识别结果置信度阈值（低于此值的文本块将被丢弃）
OCR_CONFIDENCE_THRESHOLD = 0.6


def _clean_ocr_text(text: str) -> str:
    """
    清洗 OCR 识别结果中的垃圾字符。
    策略：
    - 移除单字符（孤立的字母/符号/数字，可能是图像噪声）
    - 移除仅 2 个中文字符的短块（大概率误识别）
    - 移除纯数字且长度 < 4 的短块
    - 保留有效的 SN 码、型号、中文句子等
    """
    if not text:
        return ""
    blocks = text.split()
    cleaned = []
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        # 单字符：几乎都是噪声（如 "Q" "国" "》" "?"）
        if len(block) == 1:
            continue
        # 纯数字且 < 4 位：大概率是局部噪声（如 "888" 被 OCR 单独检出）
        if block.isdigit() and len(block) < 4:
            continue
        # 2 个汉字：大概率误识别
        if len(block) == 2 and all('一' <= c <= '鿿' for c in block):
            continue
        # 短混合内容（数字+汉字 < 5 字符）：大概率是噪声（如 "8品品"）
        if len(block) < 5:
            has_digit = any(c.isdigit() for c in block)
            has_chinese = any('一' <= c <= '鿿' for c in block)
            if has_digit and has_chinese:
                continue
        cleaned.append(block)
    return " ".join(cleaned)
def _preprocess_image(image_bytes: bytes) -> np.ndarray:
    """
    OpenCV 图像预处理：灰度化 + 轻微降噪。
    【修复】去掉 adaptiveThreshold 二值化——PaddleOCR 内部已有 CRAFT 检测+CRNN 识别预处理，
    外部二值化会破坏低对比度图片（如金属铭牌灰底灰字）的文字细节，导致识别率下降。
    """
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("[ERROR] 无法解析图像数据")

    # 转换为灰度图
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    # 仅做轻微高斯降噪，保留完整文字细节
    blurred = cv2.GaussianBlur(gray, (3, 3), 0)
    return blurred


def _extract_sn_code(ocr_text: str) -> Optional[str]:
    """
    【赛事核心】从 OCR 文本中精准提取 SN 码 (Serial Number)
    支持常见格式：SN:12345, S/N 12345, 序列号：12345, 或直接匹配 9-20 位字母数字组合

    【修复】兜底正则最小长度从 8 → 9，避免将订单号（如 JD123456）误识别为 SN 码。
    【修复】前缀匹配后若结果仍以 SN 开头则再次剥离，处理 S/N:SN202501001 这类双重前缀。
    """
    # 匹配带前缀的 SN 码
    prefix_pattern = r'(?:SN|S/N|序列号|出厂编号)[:\s\-]*([A-Za-z0-9]{9,20})'
    match = re.search(prefix_pattern, ocr_text, re.IGNORECASE)
    if match:
        code = match.group(1).upper()
        # 处理双重前缀：S/N:SN202501001 → SN202501001 → 202501001
        if code.upper().startswith("SN"):
            code = code[2:]
        return code if len(code) >= 9 else None

    # 兜底：匹配独立的 9-20 位大写字母+数字组合（排除纯数字和纯字母）
    # 最小 9 位：避免将 8 位订单号（JD123456）误识别为 SN 码
    fallback_pattern = r'\b(?=.*[A-Z])(?=.*[0-9])[A-Z0-9]{9,20}\b'
    match = re.search(fallback_pattern, ocr_text.upper())
    if match:
        return match.group(0)

    return None


# ==========================================
# 3. 同步核心逻辑 (将被丢入线程池)
# ==========================================
def _sync_extract_image(image_bytes: bytes) -> Tuple[str, Optional[str]]:
    """同步执行图片 OCR 并提取 SN 码"""
    try:
        ocr = _get_ocr_engine()
        processed_img = _preprocess_image(image_bytes)

        # PaddleOCR 返回格式: [[ [box, (text, confidence)] , ...]]
        result = ocr.ocr(processed_img)

        # 【修复】按置信度阈值过滤 + 垃圾字符清洗
        full_text = ""
        if result and result[0]:
            texts = []
            for line in result[0]:
                if not line or len(line) < 2:
                    continue
                text, confidence = line[1]
                if text and confidence is not None and confidence >= OCR_CONFIDENCE_THRESHOLD:
                    texts.append(text)
            raw_text = " ".join(texts)
            full_text = _clean_ocr_text(raw_text)

        sn_code = _extract_sn_code(full_text)
        if sn_code:
            logger.info(f"[INFO] 成功提取 SN 码: {sn_code}")

        return full_text, sn_code
    except Exception as e:
        logger.error(f"[ERROR] 图片 OCR 处理失败: {e}")
        return "", None


def _sync_extract_video(video_bytes: bytes) -> Tuple[str, Optional[str]]:
    """同步执行视频 OCR：智能抽帧 + 去重 + 文本合并"""
    try:
        ocr = _get_ocr_engine()
        # 将字节流写入临时文件供 OpenCV 读取
        temp_path = "temp_video.mp4"
        with open(temp_path, "wb") as f:
            f.write(video_bytes)

        cap = cv2.VideoCapture(temp_path)
        if not cap.isOpened():
            raise ValueError("[ERROR] 无法打开视频文件")

        fps = cap.get(cv2.CAP_PROP_FPS) or 24.0
        frame_interval = int(fps)  # 每秒抽取 1 帧

        all_texts = set()
        sn_code = None
        frame_count = 0

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            if frame_count % frame_interval == 0:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

                result = ocr.ocr(gray)
                if result and result[0]:
                    for line in result[0]:
                        if not line or len(line) < 2:
                            continue
                        text, confidence = line[1]
                        if text and confidence is not None and confidence >= OCR_CONFIDENCE_THRESHOLD:
                            clean = _clean_ocr_text(text)
                            if clean:
                                all_texts.add(clean)
                                if not sn_code:
                                    sn_code = _extract_sn_code(clean)

            frame_count += 1

        cap.release()
        import os
        if os.path.exists(temp_path):
            os.remove(temp_path)

        full_text = " ".join(list(all_texts))
        return full_text, sn_code
    except Exception as e:
        logger.error(f"[ERROR] 视频 OCR 处理失败: {e}")
        return "", None


# ==========================================
# 4. 异步对外接口 (FastAPI 调用层)
# ==========================================
async def extract_text_from_image(image_bytes: bytes) -> Tuple[str, Optional[str]]:
    """
    异步图片 OCR 接口
    使用 asyncio.to_thread 将 CPU 密集型任务卸载到默认线程池，防止阻塞事件循环
    """
    return await asyncio.to_thread(_sync_extract_image, image_bytes)


async def extract_text_from_video(video_bytes: bytes) -> Tuple[str, Optional[str]]:
    """
    异步视频 OCR 接口
    """
    return await asyncio.to_thread(_sync_extract_video, video_bytes)