# rag_simple.py
"""
基于千问 embedding + DeepSeek 生成的 RAG 简单实现
- 支持从 .txt 文件构建向量索引
- 支持查询检索并生成回答
- 所有代码集中在一个文件中，便于理解与调试
"""

import os
import glob
import chromadb
from dotenv import load_dotenv
from langchain_text_splitters import RecursiveCharacterTextSplitter
import dashscope
from dashscope import TextEmbedding
from openai import OpenAI

# 加载环境变量（假设 .env 在项目根目录）
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env'))

# ======================== 配置区域 ========================
# 请根据需要修改以下参数

# 知识库目录：存放 .txt 文件的文件夹路径（绝对或相对路径）
SOP_DIR = "data/sop"  # 相对于当前文件的目录

# ChromaDB 持久化目录
CHROMA_PERSIST_DIR = "./chroma_db"
COLLECTION_NAME = "sop_knowledge"

# 文本分块参数
CHUNK_SIZE = 500  # 每块最大字符数
CHUNK_OVERLAP = 50  # 块之间重叠字符数

# 检索参数
TOP_K = 3  # 返回最相关的段落数

# 模型配置
EMBEDDING_MODEL = "text-embedding-v4"  # 千问 embedding 模型
DEEPSEEK_MODEL = "deepseek-chat"  # DeepSeek 对话模型

# ======================== 初始化全局对象 ========================
# ChromaDB 客户端（延迟初始化）
_chroma_client = None
_collection = None

# DeepSeek 客户端
_deepseek_client = None

# 千问 API Key 设置
dashscope.api_key = os.getenv("DASHSCOPE_API_KEY")


# ======================== 辅助函数 ========================

def _get_chroma_collection():
    """获取 ChromaDB 集合（若不存在则创建）"""
    global _chroma_client, _collection
    if _chroma_client is None:
        _chroma_client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)
    if _collection is None:
        # get_or_create_collection 会自动创建不存在的集合
        _collection = _chroma_client.get_or_create_collection(name=COLLECTION_NAME)
    return _collection


def _get_embedding(text: str):
    """调用千问 embedding API 获取单个文本的向量"""
    resp = TextEmbedding.call(
        model=EMBEDDING_MODEL,
        input=text
    )
    if resp.status_code == 200:
        return resp.output["embeddings"][0]["embedding"]
    else:
        raise RuntimeError(f"Embedding 失败: {resp.message}")


def _get_embeddings_batch(texts: list):
    """批量获取向量（用于构建索引，效率更高）"""
    resp = TextEmbedding.call(
        model=EMBEDDING_MODEL,
        input=texts
    )
    if resp.status_code == 200:
        # 按原始顺序整理 embeddings
        embeds = [None] * len(texts)
        for item in resp.output["embeddings"]:
            embeds[item["text_index"]] = item["embedding"]
        return embeds
    else:
        raise RuntimeError(f"批量 Embedding 失败: {resp.message}")


def _get_deepseek_client():
    """获取 DeepSeek OpenAI 兼容客户端"""
    global _deepseek_client
    if _deepseek_client is None:
        api_key = os.getenv("DEEPSEEK_API_KEY")
        base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
        if not api_key:
            raise ValueError("请在 .env 中设置 DEEPSEEK_API_KEY")
        _deepseek_client = OpenAI(api_key=api_key, base_url=base_url)
    return _deepseek_client


# ======================== 索引构建 ========================

def build_index(force_rebuild=False):
    """
    读取 SOP_DIR 下的所有 .txt 文件，分块、向量化并存入 ChromaDB
    :param force_rebuild: 是否删除已有索引并重建
    """
    collection = _get_chroma_collection()

    # 如果要求强制重建，删除现有集合
    if force_rebuild:
        # ChromaDB 删除集合需要通过 client
        client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)
        if COLLECTION_NAME in [c.name for c in client.list_collections()]:
            client.delete_collection(COLLECTION_NAME)
            print(f"已删除旧集合 {COLLECTION_NAME}")
            # 重新获取新集合
            _collection = client.get_or_create_collection(COLLECTION_NAME)
        else:
            _collection = collection

    # 获取所有 txt 文件路径
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

    # 分块
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

    # 批量获取向量
    print(f"正在计算 {len(all_chunks)} 个文本块的向量（调用千问 API）...")
    embeddings = _get_embeddings_batch(all_chunks)

    # 存入 ChromaDB
    collection.add(
        ids=ids,
        documents=all_chunks,
        embeddings=embeddings
    )
    print(f"索引构建完成，共 {len(all_chunks)} 个片段")


# ======================== 检索函数 ========================

def retrieve(query: str, top_k: int = TOP_K):
    """
    根据用户问题，从向量库中检索最相关的 SOP 段落
    :param query: 用户输入的文本
    :param top_k: 返回结果数量
    :return: 列表，每个元素为字典包含 content 和 distance
    """
    collection = _get_chroma_collection()
    # 将问题转换为向量
    query_vec = _get_embedding(query)

    # 在 ChromaDB 中查询
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


# ======================== 生成回答 ========================

def generate_answer(question: str, retrieved_chunks: list) -> str:
    """
    基于检索到的知识块，调用 DeepSeek 生成最终回答
    :param question: 原始用户问题
    :param retrieved_chunks: retrieve() 返回的列表
    :return: 回答字符串
    """
    if not retrieved_chunks:
        context = "未找到相关的 SOP 知识。"
    else:
        # 将多个段落用换行分隔
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
        temperature=0.1,
        max_tokens=500
    )
    return response.choices[0].message.content


# ======================== 统一入口 ========================

def ask_sop(question: str) -> str:
    """
    主入口：输入用户问题，输出基于 SOP 知识库的回复
    """
    # 1. 检索
    chunks = retrieve(question)
    # 2. 生成
    answer = generate_answer(question, chunks)
    return answer