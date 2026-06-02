# # # test_rag.py,用于测试RAG功能,暂时保留
# # """
# # 测试 RAG 功能的独立脚本
# # """
# # import sys
# # import os
# #
# # # 确保可以导入 rag_simple
# # sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# #
# # from rag_simple import build_index, ask_sop
# #
# #
# # def main():
# #     print("=" * 60)
# #     print("RAG 功能测试")
# #     print("=" * 60)
# #
# #     # 第一步：构建索引（如果 SOP 目录下有 .txt 文件）
# #     # 注意：如果已经构建过索引且不需要重建，可以注释掉下面这行
# #     print("\n[1] 构建/重建索引...")
# #     build_index(force_rebuild=True)
# #
# #     # 第二步：测试问题列表
# #     test_questions = [
# #         "我的设备冒烟了，怎么办？",
# #         "少了一个螺丝，可以补发吗？",
# #         "电脑经常死机卡顿",
# #         "运输过程中包装破损，机器变形了"
# #     ]
# #
# #     print("\n[2] 开始问答测试...")
# #     for i, q in enumerate(test_questions, 1):
# #         print(f"\n--- 问题 {i} ---")
# #         print(f"用户: {q}")
# #         answer = ask_sop(q)
# #         print(f"RAG 回复: {answer}")
# #         print("-" * 50)
# #
# #
# # if __name__ == "__main__":
# #     main()
#
#
# # test_rag.py
# """
# RAG 模块真实业务测试脚本 (基于 sop_document.txt)
# =======================================================================
# 使用方法：
# 1. 确保你的 data/sop 目录下有 sop_document.txt。
# 2. 确保 .env 和 config.py 配置正确。
# 3. 在项目根目录下运行：python test_rag.py
# """
# import time
# import os
# from rag_simple import build_index, get_sop_guide, SOP_DIR
#
#
# # ================= 1. 检查知识库环境 =================
# def check_sop_environment():
#     """检查 data/sop 目录下是否有真实的 SOP 文件"""
#     if not os.path.exists(SOP_DIR):
#         print(f"❌ 错误：未找到目录 {SOP_DIR}，请创建并放入你的 SOP 文件。")
#         return False
#
#     existing_files = [f for f in os.listdir(SOP_DIR) if f.endswith('.txt')]
#     if not existing_files:
#         print(f"❌ 错误：{SOP_DIR} 目录下没有 .txt 文件。")
#         return False
#
#     print(f"✅ 检测到真实知识库文件: {existing_files}，准备开始索引...\n")
#     return True
#
#
# # ================= 2. 针对真实 SOP 的硬核测试用例 =================
# # 这些用例严格对应你 sop_document.txt 中的具体业务场景
# TEST_CASES = [
#     {
#         "desc": "场景 2.1.1：安全类-冒烟起火 (High) -> 测试高危熔断与紧急话术",
#         "user_msg": "救命！我的机器后面在冒黑烟，而且非常烫，我闻到塑料烧焦的味道了！",
#         "category": "Hardware_Thermal_Runaway",  # 对应你工单示例中的分类
#         "urgency": "High"
#     },
#     {
#         "desc": "场景 2.2.1：核心部件-电机故障 (Medium) -> 测试中危专业排障",
#         "user_msg": "设备开机后马达一直有异响，主轴好像卡死了，完全无法启动。",
#         "category": "Motor_Failure",
#         "urgency": "Medium"
#     },
#     {
#         "desc": "场景 2.3.1：配件缺失 (Low) -> 测试低危标准自助流程",
#         "user_msg": "我刚收到货，拆开发现盒子里少了一根数据线，这怎么充电啊？",
#         "category": "Missing_Part",
#         "urgency": "Low"
#     },
#     {
#         "desc": "场景 2.4.2：软件-网络故障 (Medium) -> 测试具体技术指导",
#         "user_msg": "设备一直连不上WiFi，路由器没问题，但设备一直提示连接超时。",
#         "category": "Network_Issue",
#         "urgency": "Medium"
#     }
# ]
#
# # ================= 3. 主测试流程 =================
# if __name__ == "__main__":
#     print("\n" + "=" * 70)
#     print("🚀 开始执行 RAG (检索增强生成) 真实业务测试")
#     print("=" * 70 + "\n")
#
#     # 1. 环境检查
#     if not check_sop_environment():
#         exit(1)
#
#     # 2. 构建向量索引
#     # 注意：首次运行会调用阿里云百炼 API 将你的 sop_document.txt 切片并向量化
#     # 如果之前已经构建过，可以设置 force_rebuild=False 以节省时间
#     build_index(force_rebuild=True)
#
#     # 3. 执行对话测试
#     print("\n" + "=" * 70)
#     print("💬 开始模拟用户提问与 RAG 回复 (基于真实 SOP)")
#     print("=" * 70)
#
#     for i, case in enumerate(TEST_CASES, 1):
#         print(f"\n[测试用例 {i}] {case['desc']}")
#         print("-" * 70)
#         print(f"👤 用户原话 : {case['user_msg']}")
#         print(f"🏷️ 系统标签 : 类别={case['category']}, 紧急度={case['urgency']}")
#
#         # 调用核心接口 (必须传入 user_message 触发精准中文检索)
#         response = get_sop_guide(
#             issue_category=case['category'],
#             urgency_level=case['urgency'],
#             user_message=case['user_msg']
#         )
#
#         print(f"\n🤖 助手回复 :\n{response}")
#         print("=" * 70)
#         time.sleep(5)  # ⏳ 等待 3 秒，防止触发 API 网关的 Rate Limit
#
#     print("\n✅ RAG 真实业务测试流程全部结束！\n")