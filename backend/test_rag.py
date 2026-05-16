# test_rag.py - 测试 RAG 模块功能

import json
import os

# 确保能导入 sop_matcher
# 如果 sop_matcher.py 在当前目录，直接导入
from sop_matcher import rebuild_index, search_sop, get_sop_guide_with_rag


# 准备测试用的 SOP 文档数据（如果 data/sop_documents.json 不存在，则创建示例数据）
def ensure_test_data():
    data_dir = "data"
    os.makedirs(data_dir, exist_ok=True)
    json_path = os.path.join(data_dir, "sop_documents.json")

    if not os.path.exists(json_path):
        print("创建示例 SOP 文档数据...")
        sample_data = [
            {
                "id": "sec_2_1",
                "title": "设备冒烟、起火",
                "content": "【紧急安全警告】请立即切断设备电源，并远离设备至少2米。如果已经起火，请使用干粉灭火器，并拨打119。系统已自动通知我司技术总监，他将在15分钟内电话联系您。",
                "category": "硬件故障",
                "keywords": ["冒烟", "起火", "烧焦", "火花"],
                "urgency": "High"
            },
            {
                "id": "sec_2_5",
                "title": "配件缺失",
                "content": "您好，我们很重视您提到的配件缺失问题。请访问 https://example.com/replacement 申请免费补发配件，通常3个工作日内寄出。",
                "category": "硬件故障",
                "keywords": ["少螺丝", "缺数据线", "无说明书", "缺配件"],
                "urgency": "Low"
            },
            {
                "id": "sec_3_1",
                "title": "频繁死机、卡顿",
                "content": "系统卡顿可能是软件冲突或固件bug导致。请您尝试升级至最新固件版本，并重启设备。若问题依旧，请提供设备日志，我们会安排软件工程师分析。",
                "category": "软件问题",
                "keywords": ["死机", "卡死", "蓝屏", "无响应"],
                "urgency": "Medium"
            }
        ]
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(sample_data, f, ensure_ascii=False, indent=2)
        print(f"已创建示例数据文件: {json_path}")
    else:
        print(f"使用现有数据文件: {json_path}")


def test_rebuild_index():
    """测试重建索引"""
    print("\n=== 测试重建索引 ===")
    rebuild_index()
    print("重建完成")


def test_search():
    """测试检索功能"""
    print("\n=== 测试检索功能 ===")

    test_queries = [
        ("设备冒烟了，很危险", None),
        ("少了一个螺丝", None),
        ("电脑蓝屏死机", None),
        ("设备冒烟", "High"),  # 带紧急度过滤
    ]

    for query, urgency in test_queries:
        print(f"\n查询: {query}")
        if urgency:
            print(f"紧急度过滤: {urgency}")
        results = search_sop(query, top_k=2, urgency_filter=urgency)
        if results:
            for i, r in enumerate(results):
                print(f"  结果{i + 1}: {r['title']} (距离: {r['distance']:.4f})")
                print(f"    内容预览: {r['content'][:100]}...")
        else:
            print("  未找到相关结果")


def test_rag_guide():
    """测试 get_sop_guide_with_rag 函数"""
    print("\n=== 测试 SOP 指导生成 ===")

    test_cases = [
        ("设备冒烟，有烧焦味", None),
        ("少了一个螺丝", None),
        ("电脑经常蓝屏", None),
        ("设备冒烟", "High"),
    ]

    for query, urgency in test_cases:
        print(f"\n用户: {query}")
        if urgency:
            print(f"紧急度: {urgency}")
        result = get_sop_guide_with_rag(query, urgency)
        print(f"SOP回复: {result[:200]}...")


def main():
    print("RAG 模块测试开始")
    ensure_test_data()
    test_rebuild_index()
    test_search()
    test_rag_guide()
    print("\n✅ 所有测试完成")


if __name__ == "__main__":
    main()