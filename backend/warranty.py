def check_warranty(sn_code: str) -> str:
    """
    参数：从图片 OCR 提取或用户提供的 SN 码
    返回值：
        "In_Warranty"    -- 在保
        "Out_of_Warranty" -- 过保
        "Unknown"        -- 无法判断（如 SN 为空或格式错误）
    """
    # TODO: 实现模拟保修数据库（可读本地 JSON 或写死在代码中）
    # 示例规则：若 SN 前两位是 24 或 25 为在保，否则过保
    pass