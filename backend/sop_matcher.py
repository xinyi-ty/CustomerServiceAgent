# sop_matcher.py - RAG 检索模块

import json
import os
import chromadb
from sentence_transformers import SentenceTransformer
from langchain_text_splitters import RecursiveCharacterTextSplitter

# ========== 全局配置 ==========
EMBEDDING_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
CHROMA_PERSIST_DIR = "./chroma_db"
COLLECTION_NAME = "sop_knowledge"
DATA_FILE = "data/sop_documents.json"

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
    
    # 初始化 Chroma 客户端（持久化模式）[reference:3]
    _chroma_client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)
    
    # 检查集合是否已存在
    existing_collections = [c.name for c in _chroma_client.list_collections()]
    
    if COLLECTION_NAME in existing_collections:
        # 已存在，直接获取[reference:4]
        _collection = _chroma_client.get_collection(COLLECTION_NAME)
        print(f"已加载现有集合: {COLLECTION_NAME}")
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
        print(f"警告: 数据文件 {DATA_FILE} 不存在！")
        return
    
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        documents = json.load(f)
    
    # 准备要添加的数据
    all_documents = []
    all_metadatas = []
    all_ids = []
    
    for doc in documents:
        # 使用 LangChain 文本分割器将长文档切分为小块[reference:5]
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=500,           # 每块最大字符数
            chunk_overlap=50,         # 块之间的重叠字符数（保持上下文连续性）
            separators=["\n\n", "\n", "。", "！", "？", "；", " ", ""]
        )
        
        # 如果内容较短（<500字），直接作为一块
        if len(doc["content"]) <= 600:
            chunks = [doc["content"]]
        else:
            chunks = splitter.split_text(doc["content"])
        
        # 为每个 chunk 生成唯一 ID 和元数据
        for idx, chunk in enumerate(chunks):
            chunk_id = f"{doc['id']}_chunk_{idx}" if len(chunks) > 1 else doc['id']
            all_documents.append(chunk)
            all_metadatas.append({
                "source_id": doc["id"],
                "title": doc.get("title", ""),
                "category": doc.get("category", ""),
                "urgency": doc.get("urgency", ""),
                "keywords": ", ".join(doc.get("keywords", []))
            })
            all_ids.append(chunk_id)
    
    # 批量计算向量（更高效）
    print(f"正在计算 {len(all_documents)} 个文档片段的向量...")
    embeddings = model.encode(all_documents).tolist()
    
    # 批量添加到 Chroma
    _collection.add(
        ids=all_ids,
        documents=all_documents,
        metadatas=all_metadatas,
        embeddings=embeddings
    )
    
    print(f"成功导入 {len(all_documents)} 个文档片段到 Chroma")


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
    global _collection
    _init_chroma()  # 确保 Chroma 已初始化
    
    # 将查询转换为向量[reference:6]
    model = _init_embedding_model()
    query_embedding = model.encode([query]).tolist()
    
    # 构建查询条件
    where_filter = None
    if urgency_filter:
        where_filter = {"urgency": urgency_filter}
    
    # 在 Chroma 中进行相似度检索[reference:7]
    results = _collection.query(
        query_embeddings=query_embedding,
        n_results=top_k,
        where=where_filter  # 可选按元数据过滤
    )
    
    # 格式化返回结果
    formatted_results = []
    if results['documents'] and results['documents'][0]:
        for i, doc in enumerate(results['documents'][0]):
            formatted_results.append({
                "content": doc,
                "source_id": results['metadatas'][0][i].get("source_id", ""),
                "title": results['metadatas'][0][i].get("title", ""),
                "urgency": results['metadatas'][0][i].get("urgency", ""),
                "distance": results['distances'][0][i] if results['distances'] else None
            })
    
    return formatted_results


def get_sop_guide_with_rag(user_query: str, urgency_level: str = None) -> str:
    """
    基于 RAG 检索的 SOP 匹配函数（替代原有的字典匹配版本）
    
    参数:
        user_query: 用户投诉原文
        urgency_level: 可选的大模型判定的紧急度，用于过滤
    
    返回:
        SOP 指导文本
    """
    # 1. 检索最相关的 SOP 段落
    similar_sops = search_sop(user_query, top_k=2, urgency_filter=urgency_level)
    
    if not similar_sops:
        return "感谢您的反馈，我们已经记录工单，人工客服将尽快联系您。"
    
    # 2. 构建检索结果的上下文文本
    # 如果有多个匹配结果，合并它们
    if len(similar_sops) == 1:
        return similar_sops[0]["content"]
    else:
        # 合并多个结果，保留最相关的一个（第一个）作为主要回复
        # 可选的增强：如果第二个结果的相似度也非常高，可以合并
        return similar_sops[0]["content"]


# 为了兼容原有的字典匹配函数，保留旧函数名
def get_sop_guide(issue_category: str, urgency_level: str) -> str:
    """
    兼容旧接口（当没有用户原文时使用）
    建议后端优先调用 get_sop_guide_with_rag 并传入用户原文
    """
    # 这里只做简单处理，实际建议后端改造调用方式
    return get_sop_guide_with_rag(
        user_query=f"类别: {issue_category}, 紧急度: {urgency_level}",
        urgency_level=urgency_level
    )