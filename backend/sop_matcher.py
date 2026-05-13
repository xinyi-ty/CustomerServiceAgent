def get_sop_guide(issue_category: str, urgency_level: str) -> str:
    """
    参数：
        issue_category: 如 "Missing_Part", "Overheating"
        urgency_level: "Low", "Medium", "High"
    返回：
        一段给客户的具体处置建议（如“请立即断电...”或“请访问链接补发配件”）
    """
    # 简单字典映射实现：根据问题类别和紧急程度返回客服处置建议
    templates = {
        "missing_part": {
            "Low": (
                "抱歉给您带来不便。您的订单已记录缺件信息，" 
                "我们会在2个工作日内安排补发或提供自助补件链接（请提供订单号）。"
            ),
            "Medium": (
                "抱歉，您收到缺件。已为您提交补发申请，预计1个工作日内处理。"
                "请确认收件地址或如需优先处理请回复‘加急’并提供联系电话。"
            ),
            "High": (
                "非常抱歉，发现关键配件缺失。已立即为您转人工优先处理，" 
                "请保持电话畅通或提供最佳联系时间。"
            ),
        },
        "overheating": {
            "Low": (
                "设备运行偏热。建议将设备放在通风处，避免遮挡散热孔并短时休息后重试。"
                "如仍有问题，请提供使用场景与设备型号。"
            ),
            "Medium": (
                "检测到过热可能影响使用，请先关闭设备并拔掉电源，冷却10分钟后重启。"
                "若重启后仍异常，请拍照/视频并联系我们以便进一步排查或安排维修。"
            ),
            "High": (
                "存在安全风险，请立即断电并停止使用。请勿自行拆机，" 
                "已将工单标为高优先级并建议尽快联系售后或等待我们的人工回访。"
            ),
        },
    }
    # 正规化输入
    def _normalize(s: str) -> str:
        return (s or "").strip().lower()

    cat = _normalize(issue_category)
    urg = (urgency_level or "").strip().capitalize()
    if urg not in ("Low", "Medium", "High"):
        urg = "Low"
 
    suggestion = None
    # 直接匹配已知分类
    if cat in templates:
        suggestion = templates[cat].get(urg)
    else:
        # 简单关键词匹配以覆盖大小写或不同表达
        if "missing" in cat or "缺件" in cat or "part" in cat:
            suggestion = templates["missing_part"].get(urg)
        elif "overheat" in cat or "过热" in cat or "热" in cat:
            suggestion = templates["overheating"].get(urg)

    # 最后回退默认文本
    if not suggestion:
        fallback = {
            "Low": "感谢您的反馈。已记录问题，客服将在48小时内跟进。如需加速处理，请提供更多信息或选择人工协助。",
            "Medium": "已将问题提交技术处理，预计24小时内跟进。请提供设备型号、订单号和图片/视频以便排查。",
            "High": "已将工单标为高优先级并转人工处理，请保持联系方式畅通。若有安全风险请立即断电并等待我们的进一步指示。",
        }
        suggestion = fallback.get(urg, fallback["Low"]) 

    return suggestion
