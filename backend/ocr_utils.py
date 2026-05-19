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
    每秒抽取一帧视频画面进行 OCR，返回合并后的文本字符串。
    """
    import tempfile
    import os
    import cv2

    tmp_path = None

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp:
            tmp.write(video_bytes)
            tmp_path = tmp.name

        cap = cv2.VideoCapture(tmp_path)

        if not cap.isOpened():
            return ""

        fps = cap.get(cv2.CAP_PROP_FPS)
        if not fps or fps <= 0:
            fps = 1

        frame_interval = int(fps)
        frame_index = 0
        texts = []

        while True:
            success, frame = cap.read()
            if not success:
                break

            if frame_index % frame_interval == 0:
                ok, buffer = cv2.imencode(".jpg", frame)
                if ok:
                    text = extract_text_from_image(buffer.tobytes())
                    if text:
                        texts.append(text)

            frame_index += 1

        cap.release()

        # 去重，避免每秒文字重复太多
        unique_texts = []
        seen = set()

        for text in texts:
            cleaned = text.strip()
            if cleaned and cleaned not in seen:
                seen.add(cleaned)
                unique_texts.append(cleaned)

        return "\n".join(unique_texts)

    except Exception as e:
        print(f"[VIDEO OCR ERROR] {e}")
        return ""

    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)