# test_rag_only.py
from rag import ask_sop

if __name__ == "__main__":
    test_questions = [
        "我的设备冒烟了，怎么办？",
        "少了一个螺丝，可以补发吗？",
        "电脑经常死机卡顿",
        "运输过程中包装破损，机器变形了"
    ]
    for q in test_questions:
        print("\n" + "="*50)
        print(f"用户问题: {q}")
        print("-" * 30)
        answer = ask_sop(q)
        print(f"RAG回复: {answer}")
        print("="*50)