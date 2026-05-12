from paddleocr import PaddleOCR
import numpy as np
import cv2

# 全局初始化（避免重复加载模型）
ocr = PaddleOCR(use_angle_cls=True, lang="en")

def extract_text_from_image(image_bytes: bytes) -> str:
    """
    输入：图片字节
    输出：OCR识别的纯文本（字符串）
    """
    try:
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if img is None:
            return ""

        result = ocr.ocr(img, cls=True)

        texts = []
        for line in result:
            for word_info in line:
                text = word_info[1][0]
                texts.append(text)

        full_text = "\n".join(texts)

        # 基础清洗（关键）
        full_text = full_text.replace("O", "0")
        full_text = full_text.replace("I", "1")

        return full_text.strip()

    except Exception as e:
        print(f"[OCR ERROR] {e}")
        return ""


def extract_text_from_video(video_bytes: bytes) -> str:
    """
    视频抽第一帧做OCR
    """
    import tempfile

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp:
            tmp.write(video_bytes)
            tmp_path = tmp.name

        cap = cv2.VideoCapture(tmp_path)
        success, frame = cap.read()
        cap.release()

        if not success:
            return ""

        _, buffer = cv2.imencode(".jpg", frame)
        return extract_text_from_image(buffer.tobytes())

    except Exception as e:
        print(f"[VIDEO OCR ERROR] {e}")
        return ""