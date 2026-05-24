# test_rag.py,用于测试RAG功能,暂时保留
"""
测试 RAG 功能的独立脚本
"""
import sys
import os

# 确保可以导入 rag_simple
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rag_simple import build_index, ask_sop


def main():
    print("=" * 60)
    print("RAG 功能测试")
    print("=" * 60)

    # 第一步：构建索引（如果 SOP 目录下有 .txt 文件）
    # 注意：如果已经构建过索引且不需要重建，可以注释掉下面这行
    print("\n[1] 构建/重建索引...")
    build_index(force_rebuild=True)

    # 第二步：测试问题列表
    test_questions = [
        "我的设备冒烟了，怎么办？",
        "少了一个螺丝，可以补发吗？",
        "电脑经常死机卡顿",
        "运输过程中包装破损，机器变形了"
    ]

    print("\n[2] 开始问答测试...")
    for i, q in enumerate(test_questions, 1):
        print(f"\n--- 问题 {i} ---")
        print(f"用户: {q}")
        answer = ask_sop(q)
        print(f"RAG 回复: {answer}")
        print("-" * 50)


if __name__ == "__main__":
    main()