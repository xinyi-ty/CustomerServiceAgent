def check_warranty(sn_code: str) -> str:
    """
    输入：SN码
    输出：
    In_Warranty / Out_of_Warranty / Unknown
    """
    try:
        if not sn_code:
            return "Unknown"

        sn_code = sn_code.strip().upper()
        sn_code = sn_code.replace(" ", "")

        # OCR常见错误修正
        sn_code = sn_code.replace("O", "0")

        if len(sn_code) < 2:
            return "Unknown"

        prefix = sn_code[:2]

        if prefix in ["24", "25"]:
            return "In_Warranty"
        else:
            return "Out_of_Warranty"

    except Exception as e:
        print(f"[WARRANTY ERROR] {e}")
        return "Unknown"