# backend/database.py
"""
数据库操作模块 (SQLite)
架构优化：WAL模式防锁表、json_extract查询下推、上下文管理器防泄漏、标准日志
"""
import sqlite3
import json
import os
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from contextlib import contextmanager

from config import DATABASE_PATH

logger = logging.getLogger(__name__)


def _ensure_dir(path: str) -> None:
    dirname = os.path.dirname(path)
    if dirname and not os.path.exists(dirname):
        os.makedirs(dirname, exist_ok=True)


@contextmanager
def get_db_connection():
    """
    使用上下文管理器确保数据库连接正确关闭。
    开启 WAL 模式与 busy_timeout，彻底解决 FastAPI 并发下的 "database is locked" 问题。
    """
    _ensure_dir(DATABASE_PATH)
    # 增加 timeout 参数防止瞬间锁表
    conn = sqlite3.connect(DATABASE_PATH, timeout=10.0)
    conn.row_factory = sqlite3.Row
    try:
        # 开启 WAL 模式，大幅提升并发读写性能
        conn.execute("PRAGMA journal_mode=WAL;")
        # 设置忙等待时间，遇到锁时等待 5 秒而不是立即报错
        conn.execute("PRAGMA busy_timeout=5000;")
        yield conn
    finally:
        conn.close()


def init_db() -> None:
    """初始化数据库表结构及索引"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                           CREATE TABLE IF NOT EXISTS tickets
                           (
                               id
                               INTEGER
                               PRIMARY
                               KEY
                               AUTOINCREMENT,
                               ticket_id
                               TEXT
                               UNIQUE
                               NOT
                               NULL,
                               raw_json
                               TEXT
                               NOT
                               NULL,
                               created_at
                               TEXT
                               NOT
                               NULL,
                               status
                               TEXT
                               DEFAULT
                               '未处理'
                           )
                           ''')

            # 兼容旧表：动态添加 status 列
            cursor.execute("PRAGMA table_info(tickets)")
            columns = [col[1] for col in cursor.fetchall()]
            if 'status' not in columns:
                cursor.execute("ALTER TABLE tickets ADD COLUMN status TEXT DEFAULT '未处理'")
                logger.info("[INFO] 已为 tickets 表动态添加 status 列")

            # 建立索引加速查询
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_ticket_id ON tickets(ticket_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_created_at ON tickets(created_at DESC)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_status ON tickets(status)')

            conn.commit()
            logger.info("[INFO] 数据库初始化完成 (含 WAL 模式、status 列及索引)")
    except sqlite3.Error as e:
        logger.error(f"[ERROR] 数据库初始化失败: {e}")
        raise


def save_ticket(ticket: Dict[str, Any]) -> None:
    """保存或更新工单 (UPSERT)"""
    ticket_id = ticket.get("ticket_id")
    if not ticket_id:
        raise ValueError("[ERROR] ticket_id 不能为空")

    raw_json = json.dumps(ticket, ensure_ascii=False)
    created_at = ticket.get("created_at", datetime.now().isoformat())
    status = ticket.get("status", "未处理")

    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                           INSERT INTO tickets (ticket_id, raw_json, created_at, status)
                           VALUES (?, ?, ?, ?) ON CONFLICT(ticket_id) DO
                           UPDATE SET
                               raw_json = excluded.raw_json,
                               status = excluded.status
                           ''', (ticket_id, raw_json, created_at, status))
            conn.commit()
            logger.info(f"[INFO] 工单 {ticket_id} 已保存，状态: {status}")
    except sqlite3.Error as e:
        logger.error(f"[ERROR] 保存工单 {ticket_id} 失败: {e}")
        raise


def update_ticket_status(ticket_id: str, new_status: str) -> bool:
    """更新工单状态，成功返回 True"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                           UPDATE tickets
                           SET status = ?
                           WHERE ticket_id = ?
                           ''', (new_status, ticket_id))
            affected = cursor.rowcount
            conn.commit()
            if affected:
                logger.info(f"[INFO] 工单 {ticket_id} 状态已更新为 {new_status}")
            else:
                logger.warning(f"[WARN] 尝试更新不存在的工单: {ticket_id}")
            return affected > 0
    except sqlite3.Error as e:
        logger.error(f"[ERROR] 更新工单状态失败 {ticket_id}: {e}")
        return False


def get_all_tickets(limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
    """获取工单列表 (支持分页，默认按时间倒序)"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                           SELECT raw_json, created_at, status
                           FROM tickets
                           ORDER BY created_at DESC LIMIT ?
                           OFFSET ?
                           ''', (limit, offset))
            rows = cursor.fetchall()

            tickets = []
            for row in rows:
                try:
                    ticket = json.loads(row["raw_json"])
                    if "created_at" not in ticket:
                        ticket["created_at"] = row["created_at"]
                    # 以数据库中的状态为准，覆盖 JSON 中可能不一致的状态
                    ticket["status"] = row["status"]
                    tickets.append(ticket)
                except json.JSONDecodeError as e:
                    logger.warning(f"[WARN] 解析工单 JSON 失败，跳过。错误: {e}")
                    continue
            return tickets
    except sqlite3.Error as e:
        logger.error(f"[ERROR] 获取工单列表失败: {e}")
        return []


def get_tickets_by_urgency(urgency_level: str) -> List[Dict[str, Any]]:
    """
    【性能优化】按紧急度过滤工单。
    使用 SQLite 的 json_extract 将过滤条件下推到数据库层，避免全表加载到 Python 内存。
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            # 直接从 JSON 字段中提取 urgency_level 进行 SQL 层面比对
            query = '''
                    SELECT raw_json, created_at, status
                    FROM tickets
                    WHERE json_extract(raw_json, '$.agent_business_assessment.urgency_level') = ?
                    ORDER BY created_at DESC \
                    '''
            cursor.execute(query, (urgency_level,))
            rows = cursor.fetchall()

            tickets = []
            for row in rows:
                try:
                    ticket = json.loads(row["raw_json"])
                    ticket["status"] = row["status"]
                    tickets.append(ticket)
                except json.JSONDecodeError:
                    continue
            return tickets
    except sqlite3.Error as e:
        logger.error(f"[ERROR] 按紧急度查询工单失败: {e}")
        return []


def get_ticket_by_id(ticket_id: str) -> Optional[Dict[str, Any]]:
    """根据 ID 获取单个工单详情"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT raw_json, status FROM tickets WHERE ticket_id = ?', (ticket_id,))
            row = cursor.fetchone()
            if row:
                ticket = json.loads(row["raw_json"])
                ticket["status"] = row["status"]
                return ticket
            return None
    except (sqlite3.Error, json.JSONDecodeError) as e:
        logger.error(f"[ERROR] 获取工单详情失败 {ticket_id}: {e}")
        return None


def get_tickets_count() -> int:
    """获取工单总数"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM tickets')
            return cursor.fetchone()[0]
    except sqlite3.Error as e:
        logger.error(f"[ERROR] 获取工单总数失败: {e}")
        return 0