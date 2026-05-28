# backend/ocr_utils.py
"""
多模态 OCR 处理模块 (图片/视频)
架构优化：异步安全 (不阻塞 FastAPI)、延迟单例加载、SN 码智能提取、视频关键帧去重
"""
import asyncio
import logging
import re
import io
from typing import Optional, Tuple, List
from functools import lru_cache

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
    global _ocr_engine
    if _ocr_engine is None:
        try:
            from paddleocr import PaddleOCR
            logger.info("[INFO] 正在初始化 PaddleOCR 引擎 (首次加载较慢)...")
            # use_angle_cls=True 支持旋转文字识别，lang='ch' 支持中英混合
            _ocr_engine = PaddleOCR(use_angle_cls=True, lang='ch', show_log=False)
            logger.info("[INFO] PaddleOCR 引擎初始化完成")
        except ImportError:
            logger.error("[ERROR] 未安装 paddleocr，请执行: pip install paddlepaddle paddleocr")
            raise
    return _ocr_engine


# ==========================================
# 2. 图像预处理与后处理 (赛事加分项)
# ==========================================
def _preprocess_image(image_bytes: bytes) -> np.ndarray:
    """OpenCV 图像预处理：灰度化 + 自适应二值化，提升暗光/反光图片识别率"""
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("[ERROR] 无法解析图像数据")

    # 转换为灰度图
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    # 自适应二值化 (处理光照不均)
    binary = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)
    return binary


def _extract_sn_code(ocr_text: str) -> Optional[str]:
    """
    【赛事核心】从 OCR 文本中精准提取 SN 码 (Serial Number)
    支持常见格式：SN:12345, S/N 12345, 序列号：12345, 或直接匹配 8-20 位字母数字组合
    """
    # 匹配带前缀的 SN 码
    prefix_pattern = r'(?:SN|S/N|序列号|出厂编号)[:\s\-]*([A-Za-z0-9]{8,20})'
    match = re.search(prefix_pattern, ocr_text, re.IGNORECASE)
    if match:
        return match.group(1).upper()

    # 兜底：匹配独立的 8-20 位大写字母+数字组合 (排除纯数字和纯字母)
    fallback_pattern = r'\b(?=.*[A-Z])(?=.*[0-9])[A-Z0-9]{8,20}\b'
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
        result = ocr.ocr(processed_img, cls=True)

        full_text = ""
        if result and result[0]:
            texts = [line[1][0] for line in result[0] if line[1]]
            full_text = " ".join(texts)

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
                # 简单去重：计算图像哈希，避免对静止画面重复 OCR
                img_hash = cv2.img_hash.pHash(gray)[0]

                result = ocr.ocr(gray, cls=True)
                if result and result[0]:
                    for line in result[0]:
                        text = line[1][0]
                        all_texts.add(text)
                        if not sn_code:
                            sn_code = _extract_sn_code(text)

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