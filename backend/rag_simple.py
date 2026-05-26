# rag_simple.py
"""
基于千问 Embedding + DeepSeek 的 RAG 检索增强生成模块
=======================================================================
功能：
    1. 读取指定目录下的所有 .txt 文件作为 SOP 知识库
    2. 将长文本切分成小块，使用千问 text-embedding-v4 模型向量化
    3. 将向量存入 ChromaDB 数据库，构建索引
    4. 对用户问题，先检索最相关的知识块，再调用 DeepSeek 生成回答

依赖环境变量（.env 文件）：
    DASHSCOPE_API_KEY      # 阿里云千问 API 密钥
    DEEPSEEK_API_KEY       # DeepSeek API 密钥
    DEEPSEEK_BASE_URL      # DeepSeek API 地址（默认 https://api.deepseek.com/v1）

使用方法：
    from rag_simple import build_index, ask_sop
    build_index(force_rebuild=True)   # 首次使用或知识库更新时调用
    answer = ask_sop("你的问题")
"""

import os
import glob
import chromadb
from dotenv import load_dotenv
from langchain_text_splitters import RecursiveCharacterTextSplitter
import dashscope
from dashscope import TextEmbedding
from openai import OpenAI

# ========================= 1. 加载环境变量 =========================
# 尝试多个可能的 .env 文件位置，确保无论从哪个目录运行都能找到
possible_env_paths = [
    os.path.join(os.path.dirname(__file__), '..', '.env'),  # 项目根目录
    os.path.join(os.path.dirname(__file__), '.env'),  # backend 目录下
    '.env'  # 当前工作目录
]
env_loaded = False
for env_path in possible_env_paths:
    if os.path.exists(env_path):
        load_dotenv(dotenv_path=env_path, override=True)
        print(f"已加载环境变量: {env_path}")
        env_loaded = True
        break
if not env_loaded:
    print("警告: 未找到 .env 文件，请确保在项目根目录或 backend 目录下创建 .env 文件")

# ========================= 2. 配置参数 =========================
SOP_DIR = "data/sop"  # 存放 .txt 知识库文件的目录（相对路径）
CHROMA_PERSIST_DIR = "./chroma_db"  # ChromaDB 持久化目录
COLLECTION_NAME = "sop_knowledge"  # ChromaDB 集合名称

CHUNK_SIZE = 500  # 文本分块大小（字符数）
CHUNK_OVERLAP = 50  # 分块之间的重叠字符数，保持上下文连贯
TOP_K = 3  # 检索时返回最相关的段落数量

EMBEDDING_MODEL = "text-embedding-v4"  # 千问 embedding 模型
DEEPSEEK_MODEL = "deepseek-chat"  # DeepSeek 对话模型

# ========================= 3. 全局客户端初始化 =========================
_chroma_client = None  # ChromaDB 客户端（延迟初始化）
_collection = None  # ChromaDB 集合（延迟初始化）
_deepseek_client = None  # DeepSeek OpenAI 客户端（延迟初始化）

# 设置千问 API Key
qwen_api_key = os.getenv("DASHSCOPE_API_KEY")
if qwen_api_key:
    dashscope.api_key = qwen_api_key
    print("已设置 dashscope.api_key")
else:
    print("错误: 未找到 DASHSCOPE_API_KEY 环境变量，请检查 .env 文件")

# 检查 DeepSeek API Key（稍后在调用时还会检查一次）
deepseek_api_key = os.getenv("DEEPSEEK_API_KEY")
deepseek_base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
if not deepseek_api_key:
    print("错误: 未找到 DEEPSEEK_API_KEY 环境变量，请检查 .env 文件")


# ========================= 4. 辅助函数 =========================

def _get_chroma_collection():
    """获取 ChromaDB 集合（如果不存在则自动创建）"""
    global _chroma_client, _collection
    if _chroma_client is None:
        _chroma_client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)
    if _collection is None:
        _collection = _chroma_client.get_or_create_collection(name=COLLECTION_NAME)
    return _collection


def _get_embedding(text: str):
    """
    调用千问 Embedding API，将单个文本转换为向量
    :param text: 输入文本
    :return: 浮点数列表（向量）
    """
    if not dashscope.api_key:
        raise RuntimeError("dashscope.api_key 未设置，请检查环境变量 DASHSCOPE_API_KEY")
    resp = TextEmbedding.call(model=EMBEDDING_MODEL, input=text)
    if resp.status_code == 200:
        return resp.output["embeddings"][0]["embedding"]
    else:
        raise RuntimeError(f"Embedding 失败: {resp.message}")


def _get_embeddings_batch(texts: list):
    """
    批量获取向量（用于索引构建，减少 API 调用次数）
    :param texts: 文本列表
    :return: 向量列表，顺序与输入一致
    """
    if not dashscope.api_key:
        raise RuntimeError("dashscope.api_key 未设置，请检查环境变量 DASHSCOPE_API_KEY")
    resp = TextEmbedding.call(model=EMBEDDING_MODEL, input=texts)
    if resp.status_code == 200:
        embeds = [None] * len(texts)
        for item in resp.output["embeddings"]:
            embeds[item["text_index"]] = item["embedding"]
        return embeds
    else:
        raise RuntimeError(f"批量 Embedding 失败: {resp.message}")


def _get_deepseek_client():
    """获取 DeepSeek OpenAI 兼容客户端（单例模式）"""
    global _deepseek_client
    if _deepseek_client is None:
        if not deepseek_api_key:
            raise ValueError("请在 .env 中设置 DEEPSEEK_API_KEY")
        _deepseek_client = OpenAI(api_key=deepseek_api_key, base_url=deepseek_base_url)
    return _deepseek_client


# ========================= 5. 索引构建 =========================

def build_index(force_rebuild=False):
    """
    读取 SOP_DIR 下的所有 .txt 文件，切分、向量化后存入 ChromaDB
    :param force_rebuild: 是否强制删除现有索引并重新构建
    """
    print("[build_index] 开始构建索引...")

    # 如果需要强制重建，先删除整个集合
    if force_rebuild:
        tmp_client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)
        try:
            tmp_client.delete_collection(COLLECTION_NAME)
            print(f"已删除旧集合 {COLLECTION_NAME}")
        except Exception as e:
            print(f"删除集合时出错（可能是集合不存在）: {e}")
        # 重置全局变量，让下一次 _get_chroma_collection 重新创建集合
        global _collection, _chroma_client
        _collection = None
        _chroma_client = None

    # 获取集合（如果不存在则自动创建）
    collection = _get_chroma_collection()

    # 获取所有 .txt 文件路径
    txt_dir = os.path.join(os.path.dirname(__file__), SOP_DIR)
    if not os.path.exists(txt_dir):
        print(f"目录不存在: {txt_dir}，请先创建并放入 .txt 文件")
        return

    file_paths = glob.glob(os.path.join(txt_dir, "*.txt"))
    if not file_paths:
        print(f"在 {txt_dir} 下未找到任何 .txt 文件")
        return

    # 读取所有文件内容
    raw_docs = []
    for path in file_paths:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
            if content.strip():
                raw_docs.append(content)
                print(f"已读取: {path} ({len(content)} 字符)")

    # 文本分块
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", "。", "！", "？", "；", " ", ""]
    )
    all_chunks = []
    for doc in raw_docs:
        chunks = splitter.split_text(doc)
        all_chunks.extend(chunks)
        print(f"  切分为 {len(chunks)} 块")

    if not all_chunks:
        print("没有文本块可索引")
        return

    # 生成唯一 ID
    ids = [f"chunk_{i}" for i in range(len(all_chunks))]

    # 批量向量化
    print(f"正在计算 {len(all_chunks)} 个文本块的向量（调用千问 API）...")
    embeddings = _get_embeddings_batch(all_chunks)
    # 过滤空文本和无效 embedding
    filtered_chunks = []
    filtered_embeddings = []
    filtered_ids = []
    for i, (chunk, emb) in enumerate(zip(all_chunks, embeddings)):
        if chunk and chunk.strip() and emb is not None:
            filtered_chunks.append(chunk)
            filtered_embeddings.append(emb)
            filtered_ids.append(f"chunk_{i}")

    if not filtered_chunks:
        print("没有有效的文本块和向量可存入索引")
        return

    # 存入 ChromaDB
    collection.add(
        ids=filtered_ids,
        documents=filtered_chunks,
        embeddings=filtered_embeddings
    )
    print(f"索引构建完成，共 {len(filtered_chunks)} 个片段")

   



# ========================= 6. 检索 =========================

def retrieve(query: str, top_k: int = TOP_K):
    """
    根据用户问题，从向量库中检索最相关的 SOP 段落
    :param query: 用户输入的问题
    :param top_k: 返回的结果数量
    :return: 列表，每个元素为字典，包含 content、id、distance
    """
    collection = _get_chroma_collection()
    # 将问题转为向量
    query_vec = _get_embedding(query)
    # 在 ChromaDB 中查询最相似的 top_k 个文档
    results = collection.query(
        query_embeddings=[query_vec],
        n_results=top_k
    )
    retrieved = []
    if results['documents'] and results['documents'][0]:
        for i, doc in enumerate(results['documents'][0]):
            retrieved.append({
                "content": doc,
                "id": results['ids'][0][i],
                "distance": results['distances'][0][i] if results['distances'] else None
            })
    return retrieved


# ========================= 7. 生成回答 =========================

def generate_answer(question: str, retrieved_chunks: list) -> str:
    """
    基于检索到的知识块，调用 DeepSeek 生成最终回答
    :param question: 原始用户问题
    :param retrieved_chunks: retrieve 函数返回的列表
    :return: 回答字符串
    """
    if not retrieved_chunks:
        context = "未找到相关的 SOP 知识。"
    else:
        # 将多个段落用换行分隔，作为上下文
        context = "\n\n".join([chunk["content"] for chunk in retrieved_chunks])

    system_prompt = """你是一个专业的客服助手。请严格依据下方提供的【参考知识】回答用户的问题。
如果参考知识中包含具体的处置步骤或话术，请直接采用。
如果参考知识不足以回答问题，请如实告知用户并建议联系人工客服。
不要编造不存在的信息。"""

    user_prompt = f"""【参考知识】
{context}

【用户问题】
{question}

请基于参考知识，给出准确、有用的回复。"""

    client = _get_deepseek_client()
    response = client.chat.completions.create(
        model=DEEPSEEK_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.1,  # 低温度让回答更保守、更基于事实
        max_tokens=500
    )
    return response.choices[0].message.content or "抱歉，未能生成回答，请稍后再试。"

# ========================= 8. 统一入口 =========================

def ask_sop(question: str) -> str:
    """
    主入口函数：输入用户问题，输出基于 SOP 知识库的回复
    内部自动完成 检索 -> 生成 的全流程
    :param question: 用户问题（字符串）
    :return: 回答（字符串）
    """
    chunks = retrieve(question)
    answer = generate_answer(question, chunks)
    return answer

# ========================= 9. 适配 main.py 的接口 =========================

def get_sop_guide(issue_category: str, urgency_level: str) -> str:
    """
    适配 main.py 的接口：根据问题类别和紧急度返回 SOP 指导
    
    Args:
        issue_category: 问题类别（如 "Missing_Part", "Overheating"）
        urgency_level: 紧急度（"Low", "Medium", "High"）
    
    Returns:
        SOP 指导文本
    """
    # 构建查询问题
    query = f"{issue_category} {urgency_level}"
    
    # 高紧急度快速响应
    if urgency_level == "High":
        high_priority_response = "【紧急处置】请立即切断设备电源，远离现场，等待专业人员处理。"
        try:
            detailed = ask_sop(f"{issue_category} 紧急处置")
            if detailed and len(detailed) > 10 and "未找到" not in detailed:
                return f"{high_priority_response}\n\n详细处置:\n{detailed}"
        except:
            pass
        return high_priority_response
    
    # 正常检索
    try:
        answer = ask_sop(query)
        # 如果返回的是错误信息，返回默认值
        if "未找到" in answer or len(answer) < 5:
            return f"【处理方案】您的 {issue_category} 问题已收到，技术人员将尽快与您联系。"
        return answer
    except Exception as e:
        print(f"SOP 检索失败: {e}")
        return f"【处理方案】您的 {issue_category} 问题已收到，技术人员将尽快与您联系。"


# ========================= 10. 测试代码 =========================
if __name__ == "__main__":
    # 首次运行需要构建索引
    print("=" * 50)
    print("RAG 模块测试")
    print("=" * 50)
    
    # 构建索引（首次运行或知识库更新时执行）
    build_index(force_rebuild=True)
    
    # 测试检索
    test_questions = [
        "Missing_Part Low",
        "Overheating High",
        "设备冒烟怎么办？"
    ]
    
    for q in test_questions:
        print(f"\n问题: {q}")
        answer = ask_sop(q)
        print(f"回答: {answer}")