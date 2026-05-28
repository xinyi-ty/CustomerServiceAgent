# rag_simple.py
"""
RAG (检索增强生成) 核心模块 - 企业级生产版
=======================================================================
功能：
1. 自动读取 data/sop 目录下的 .txt 文件并进行智能分块。
2. 使用多线程并发调用阿里云百炼 Embedding API 构建 ChromaDB 向量索引。
3. 根据用户问题和工单标签，检索最相关的 SOP 片段。
4. 结合系统 Prompt 调用大模型生成专业回复，并内置高危故障熔断机制。
"""

import os
import re
import time
from typing import List, Dict, Any, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

import chromadb
import dashscope
from dashscope import TextEmbedding
from openai import OpenAI

# ================= 1. 配置与初始化 =================
try:
    from config import (
        CHROMA_PERSIST_DIRECTORY,
        DASHSCOPE_API_KEY,
        LLM_API_KEY,
        LLM_BASE_URL,
        LLM_MODEL_NAME
    )
except ImportError:
    CHROMA_PERSIST_DIRECTORY = "./data/chroma_db"
    DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "")
    LLM_API_KEY = os.getenv("LLM_API_KEY", "sk-xxx")
    LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
    LLM_MODEL_NAME = os.getenv("LLM_MODEL_NAME", "qwen-plus")

# 核心常量
SOP_DIR = "./data/sop"
COLLECTION_NAME = "sop_knowledge"
EMBEDDING_MODEL = "text-embedding-v2"
CHUNK_SIZE = 600
CHUNK_OVERLAP = 100

# 初始化 API Keys
dashscope.api_key = DASHSCOPE_API_KEY

# 初始化 ChromaDB 客户端
chroma_client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIRECTORY)

# 初始化 LLM 客户端
llm_client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)


# ================= 2. 文本处理与向量化核心 =================

def _chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[str]:
    """将长文本按固定窗口和重叠度切分为多个小块"""
    if not text:
        return []

    chunks: List[str] = []
    start = 0
    text_len = len(text)

    while start < text_len:
        end = start + chunk_size
        chunk = text[start:end]
        chunks.append(chunk.strip())

        if end >= text_len:
            break

        start += (chunk_size - overlap)

    return chunks


def _get_embedding(text: str) -> List[float]:
    """获取单条文本的向量 (用于用户查询时的实时向量化)"""
    if not dashscope.api_key:
        raise RuntimeError("DashScope API Key 未设置。")

    resp = TextEmbedding.call(model=EMBEDDING_MODEL, input=text)
    if resp.status_code == 200:
        return resp.output["embeddings"][0]["embedding"]
    else:
        raise RuntimeError(f"单条 Embedding 失败: {resp.message}")


def _get_embeddings_batch(texts: List[str]) -> List[List[float]]:
    """批量获取向量（多线程高并发优化版）"""
    if not dashscope.api_key:
        raise RuntimeError("DashScope API Key 未设置，无法进行向量化。")

    BATCH_SIZE = 10
    MAX_WORKERS = 5

    batches: List[List[str]] = [texts[i: i + BATCH_SIZE] for i in range(0, len(texts), BATCH_SIZE)]
    total_batches = len(batches)
    all_embeddings: List[Optional[List[float]]] = [None] * len(texts)

    print(f"[INFO] |-- 启动多线程并发向量化 (共 {total_batches} 批, 最大并发数 {MAX_WORKERS})")

    def fetch_batch(batch_idx: int, batch_texts: List[str]) -> Tuple[int, List[Dict[str, Any]]]:
        try:
            resp = TextEmbedding.call(model=EMBEDDING_MODEL, input=batch_texts)
            if resp.status_code == 200:
                return batch_idx, resp.output["embeddings"]
            else:
                raise RuntimeError(f"API 返回错误: {resp.message}")
        except Exception as e:
            print(f"[ERROR] 批次 {batch_idx + 1} 请求失败: {e}")
            raise e

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_idx = {
            executor.submit(fetch_batch, idx, batch): idx
            for idx, batch in enumerate(batches)
        }

        for future in as_completed(future_to_idx):
            batch_idx, embeddings_data = future.result()
            offset = batch_idx * BATCH_SIZE

            for item in embeddings_data:
                global_index = offset + item["text_index"]
                all_embeddings[global_index] = item["embedding"]

            print(f"[INFO] |-- 批次 {batch_idx + 1}/{total_batches} 处理完成 ({len(batches[batch_idx])} items)")

    return [emb for emb in all_embeddings if emb is not None]


# ================= 3. 索引构建 =================

def build_index(force_rebuild: bool = False) -> None:
    """读取 data/sop 目录下的文件，构建或更新 ChromaDB 向量索引"""
    print("\n" + "=" * 60)
    print("[INFO] RAG Engine: 开始构建知识库向量索引")
    print("=" * 60)

    if not os.path.exists(SOP_DIR):
        print(f"[ERROR] 未找到知识库目录: {SOP_DIR}")
        return

    if force_rebuild:
        try:
            existing_collections = [col.name for col in chroma_client.list_collections()]
            if COLLECTION_NAME in existing_collections:
                chroma_client.delete_collection(COLLECTION_NAME)
                print(f"[INFO] 已清理历史集合: {COLLECTION_NAME}")
            else:
                print(f"[INFO] 集合 {COLLECTION_NAME} 尚未创建，跳过清理。")
        except Exception as e:
            print(f"[WARN] 清理旧集合时出现异常 (不影响后续构建): {e}")

    collection = chroma_client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"}
    )

    all_chunks: List[str] = []
    all_metadatas: List[Dict[str, str]] = []
    all_ids: List[str] = []

    txt_files = [f for f in os.listdir(SOP_DIR) if f.endswith('.txt')]
    if not txt_files:
        print(f"[WARN] {SOP_DIR} 目录下未发现 .txt 文件。")
        return

    for filename in txt_files:
        filepath = os.path.join(SOP_DIR, filename)
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            print(f"[INFO] |-- 读取文档: {filename} ({len(content)} chars)")

            chunks = _chunk_text(content)
            for i, chunk in enumerate(chunks):
                chunk_id = f"{filename}_chunk_{i}"
                all_ids.append(chunk_id)
                all_chunks.append(chunk)
                all_metadatas.append({"source": filename, "chunk_index": str(i)})

    if not all_chunks:
        print("[WARN] 未提取到任何有效文本块。")
        return

    print(f"[INFO] 正在计算 {len(all_chunks)} 个文本块的向量 (Batch API)...")
    embeddings = _get_embeddings_batch(all_chunks)

    collection.add(
        ids=all_ids,
        embeddings=embeddings,
        documents=all_chunks,
        metadatas=all_metadatas
    )

    print(f"[SUCCESS] 索引构建完成，共入库 {len(all_ids)} 个知识片段。")


# ================= 4. RAG 检索与生成 =================

def get_sop_guide(
        issue_category: str,
        urgency_level: str,
        user_message: str
) -> str:
    """核心 RAG 接口：根据用户问题和标签，检索 SOP 并生成回复"""
    query_text = f"故障类别: {issue_category}, 紧急程度: {urgency_level}。用户描述: {user_message}"

    try:
        query_embedding = _get_embedding(query_text)
    except Exception as e:
        return f"[ERROR] 检索向量化失败: {e}"

    collection = chroma_client.get_or_create_collection(name=COLLECTION_NAME)

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=3,
        include=["documents", "metadatas"]
    )

    context_text = ""
    if results and results['documents'] and results['documents'][0]:
        for i, doc in enumerate(results['documents'][0]):
            source = results['metadatas'][0][i].get('source', 'Unknown')
            context_text += f"\n[参考片段 {i + 1} (来源: {source})]:\n{doc}\n"
    else:
        context_text = "未在知识库中找到直接相关的 SOP 记录。"

    system_prompt = """你是一个专业的智能售后客服助手。请严格基于以下提供的 [SOP 知识库片段] 来回答用户的问题。

【核心回复原则】：
1. 必须完全基于提供的 SOP 片段回答，禁止编造 SOP 中没有的技术参数或承诺。
2. 语气要专业、同理心强、条理清晰。
3. 如果 SOP 中没有相关信息，请明确告知用户需要转交人工工程师，并安抚情绪。
"""

    if urgency_level.strip().lower() == "high":
        system_prompt += "\n\n[紧急处置协议]：检测到高危故障（如冒烟、起火、漏电等）！你的回复**第一句话必须是**：\n'[紧急处置] 请立即切断设备电源，远离设备至少2米，确保人身安全！'\n然后再提供 SOP 中的后续上报流程。"

    user_prompt = f"""
[SOP 知识库片段]:
{context_text}

[用户当前问题]:
{user_message}

请根据上述 SOP 片段，给出专业、准确的指导回复：
"""

    # 调用 LLM (带限流自动重试与思考标签深度清洗)
    max_retries = 3

    for attempt in range(max_retries):
        try:
            response = llm_client.chat.completions.create(
                model=LLM_MODEL_NAME,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,
                max_tokens=1024
            )
            sop_response = response.choices[0].message.content

            # [核心修复] 深度清洗 QwQ 等推理模型的思考过程
            # 痛点：API 网关有时会吞掉开头的 <think>，只保留结尾的 </think>
            # 方案：直接以 </think> 为界，截取其后的最终回复
            if '</think>' in sop_response:
                sop_response = sop_response.split('</think>')[-1].strip()
            else:
                # 兜底：尝试正则匹配完整的 <think>...</think> (以防万一)
                sop_response = re.sub(r'(?s).*?</think>', '', sop_response).strip()

            # 极端情况兜底：如果清洗后为空，说明模型全在思考没输出结果
            if not sop_response:
                sop_response = "[系统提示] 模型正在深度推理中，请稍后重新发起请求。"

            return sop_response

        except Exception as e:
            error_msg = str(e).lower()
            if "rate limit" in error_msg and attempt < max_retries - 1:
                # [优化] 延长重试等待时间，适配严格的 API 网关冷却机制
                wait_time = 10 * (attempt + 1)  # 递增等待：10s, 20s
                print(f"[WARN] 触发 LLM API 限流 (Rate Limit)，{wait_time}s 后重试 ({attempt + 1}/{max_retries})...")
                time.sleep(wait_time)
            else:
                return f"[ERROR] LLM 生成回复失败: {e}"

    return "[ERROR] LLM 生成回复失败：超过最大重试次数。"