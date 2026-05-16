# sop_matcher.py - RAG 检索模块
import os
os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'
from sentence_transformers import SentenceTransformer
import json
import chromadb
from langchain_text_splitters import RecursiveCharacterTextSplitter

# ========== 全局配置 ==========
EMBEDDING_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
CHROMA_PERSIST_DIR = "./chroma_db"
COLLECTION_NAME = "sop_knowledge"
# 获取当前文件所在目录，构建绝对路径
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(_BASE_DIR, "data", "sop_documents.json")

# 全局变量（只初始化一次）
_embedding_model = None
_chroma_client = None
_collection = None
_is_initialized = False


def _init_embedding_model():
    """初始化 Sentence Transformer 嵌入模型（懒加载）"""
    global _embedding_model
    if _embedding_model is None:
        print(f"正在加载嵌入模型: {EMBEDDING_MODEL_NAME}...")
        _embedding_model = SentenceTransformer(EMBEDDING_MODEL_NAME)
        print("嵌入模型加载完成")
    return _embedding_model


def _init_chroma():
    """初始化 ChromaDB 客户端和集合"""
    global _chroma_client, _collection, _is_initialized

    if _is_initialized:
        return

    # 初始化 Chroma 客户端（持久化模式）
    _chroma_client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)

    # 检查集合是否已存在
    existing_collections = [c.name for c in _chroma_client.list_collections()]

    if COLLECTION_NAME in existing_collections:
        # 已存在，直接获取
        _collection = _chroma_client.get_collection(COLLECTION_NAME)
        print(f"已加载现有集合: {COLLECTION_NAME}, 包含 {_collection.count()} 个文档片段")
    else:
        # 不存在，创建新集合并导入数据
        _collection = _chroma_client.create_collection(COLLECTION_NAME)
        print(f"创建新集合: {COLLECTION_NAME}")
        _import_documents_to_chroma()

    _is_initialized = True


def _import_documents_to_chroma():
    """读取 JSON 文档，分割并导入 ChromaDB"""
    model = _init_embedding_model()

    # 读取 JSON 文档
    if not os.path.exists(DATA_FILE):
        print(f"警告: 数据文件 {DATA_FILE} 不存在！请创建该文件并包含 SOP 数据。")
        return

    with open(DATA_FILE, "r", encoding="utf-8") as f:
        documents = json.load(f)

    # 准备要添加的数据
    all_documents = []
    all_metadata = []
    all_ids = []

    for doc in documents:
        # 使用 LangChain 文本分割器将长文档切分为小块
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=500,
            chunk_overlap=50,
            separators=["\n\n", "\n", "。", "！", "？", "；", " ", ""]
        )

        # 如果内容较短，直接作为一块
        if len(doc["content"]) <= 600:
            chunks = [doc["content"]]
        else:
            chunks = splitter.split_text(doc["content"])

        # 为每个 chunk 生成唯一 ID 和元数据
        for idx, chunk in enumerate(chunks):
            chunk_id = f"{doc['id']}_chunk_{idx}" if len(chunks) > 1 else doc['id']
            all_documents.append(chunk)
            all_metadata.append({
                "source_id": doc["id"],
                "title": doc.get("title", ""),
                "category": doc.get("category", ""),
                "urgency": doc.get("urgency", ""),
                "keywords": ", ".join(doc.get("keywords", []))
            })
            all_ids.append(chunk_id)

    # 批量计算向量
    print(f"正在计算 {len(all_documents)} 个文档片段的向量...")
    embeddings = model.encode(all_documents).tolist()

    # 批量添加到 Chroma
    _collection.add(
        ids=all_ids,
        documents=all_documents,
        metadatas=all_metadata,
        embeddings=embeddings
    )

    print(f"成功导入 {len(all_documents)} 个文档片段到 Chroma")


def rebuild_index():
    """
    重建整个向量索引：删除现有数据库，重新从 JSON 文件导入。
    当 SOP 文档更新时调用此函数。
    """
    global _chroma_client, _collection, _is_initialized
    import shutil

    # 关闭现有连接（如果有）
    _chroma_client = None
    _collection = None
    _is_initialized = False

    # 删除持久化目录
    if os.path.exists(CHROMA_PERSIST_DIR):
        shutil.rmtree(CHROMA_PERSIST_DIR)
        print(f"已删除旧的索引目录: {CHROMA_PERSIST_DIR}")

    # 重新初始化
    _init_chroma()
    print("索引重建完成")


def search_sop(query: str, top_k: int = 3, urgency_filter: str = None) -> list:
    """
    根据用户查询，从 SOP 知识库中检索最相关的段落

    参数:
        query: 用户的投诉原文
        top_k: 返回的最相关段落数量
        urgency_filter: 可选，按紧急度过滤（"High"/"Medium"/"Low"）

    返回:
        list of dict，每个 dict 包含:
            - content: SOP 段落原文
            - source_id: 来源章节 ID
            - title: 章节标题
            - urgency: 紧急度
            - distance: 相似度距离（越小越相关）
    """
    _init_chroma()  # 确保 Chroma 已初始化

    # 将查询转换为向量
    model = _init_embedding_model()
    query_embedding = model.encode([query]).tolist()

    # 构建查询条件
    where_filter = None
    if urgency_filter:
        where_filter = {"urgency": urgency_filter}

    # 在 Chroma 中进行相似度检索
    results = _collection.query(
        query_embeddings=query_embedding,
        n_results=top_k,
        where=where_filter
    )

    # 格式化返回结果
    formatted_results = []
    if results['documents'] and results['documents'][0]:
        for i, doc in enumerate(results['documents'][0]):
            formatted_results.append({
                "content": doc,
                "source_id": results['metadata'][0][i].get("source_id", ""),
                "title": results['metadata'][0][i].get("title", ""),
                "urgency": results['metadata'][0][i].get("urgency", ""),
                "distance": results['distances'][0][i] if results['distances'] else None
            })

    return formatted_results


def get_sop_guide_with_rag(user_query: str, urgency_level: str = None) -> str:
    """
    基于 RAG 检索的 SOP 匹配函数

    参数:
        user_query: 用户投诉原文
        urgency_level: 可选的大模型判定的紧急度，用于过滤

    返回:
        SOP 指导文本
    """
    similar_sops = search_sop(user_query, top_k=2, urgency_filter=urgency_level)

    if not similar_sops:
        return "感谢您的反馈，我们已经记录工单，人工客服将尽快联系您。"

    # 返回最相关的结果
    return similar_sops[0]["content"]


def get_sop_guide(issue_category: str, urgency_level: str) -> str:
    """
    兼容旧接口（当没有用户原文时使用）
    """
    return get_sop_guide_with_rag(
        user_query=f"类别: {issue_category}, 紧急度: {urgency_level}",
        urgency_level=urgency_level
    )