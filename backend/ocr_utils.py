def extract_text_from_image(image_bytes: bytes) -> str:
    """
    参数：图片文件的字节数据
    返回：图片中所有文字，用空格或换行连接。若没有文字返回空字符串。
    """
    # TODO: 集成 PaddleOCR 或百度 OCR API
    pass

def extract_text_from_video(video_bytes: bytes) -> str:
    """
    参数：视频文件的字节数据
    返回：视频第一帧中的文字，若无则返回空字符串。
    （可选实现，非必需但加分）
    """
    # TODO: 用 opencv 读取第一帧，保存为临时图片，调用 extract_text_from_image
    pass