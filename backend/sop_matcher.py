def get_sop_guide(issue_category: str, urgency_level: str) -> str:
    """
    参数：
        issue_category: 如 "Missing_Part", "Overheating"
        urgency_level: "Low", "Medium", "High"
    返回：
        一段给客户的具体处置建议（如“请立即断电...”或“请访问链接补发配件”）
    """
    # TODO: 实现基于关键词或向量检索的 SOP 匹配
    # 初期可用 if-else 字典映射，后期可升级为 RAG
    pass
print("hello world")