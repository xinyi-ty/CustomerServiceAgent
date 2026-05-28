# backend/database.py
import sqlite3
import json
import os
from typing import List, Dict, Any, Optional
from datetime import datetime
from config import DATABASE_PATH


def _ensure_dir(path: str) -> None:
    dirname = os.path.dirname(path)
    if dirname and not os.path.exists(dirname):
        os.makedirs(dirname, exist_ok=True)


def get_db_connection():
    _ensure_dir(DATABASE_PATH)
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tickets
        (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id TEXT UNIQUE NOT NULL,
            raw_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            status TEXT DEFAULT '未处理'
        )
    ''')
    # 为旧表添加 status 列（如果不存在）
    cursor.execute("PRAGMA table_info(tickets)")
    columns = [col[1] for col in cursor.fetchall()]
    if 'status' not in columns:
        cursor.execute("ALTER TABLE tickets ADD COLUMN status TEXT DEFAULT '未处理'")
        print("已为 tickets 表添加 status 列")

    cursor.execute('CREATE INDEX IF NOT EXISTS idx_ticket_id ON tickets(ticket_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_created_at ON tickets(created_at DESC)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_status ON tickets(status)')
    conn.commit()
    conn.close()
    print("数据库初始化完成（含 status 列及索引）")


def save_ticket(ticket: Dict[str, Any]) -> None:
    conn = get_db_connection()
    cursor = conn.cursor()
    ticket_id = ticket.get("ticket_id")
    if not ticket_id:
        raise ValueError("ticket_id 不能为空")
    raw_json = json.dumps(ticket, ensure_ascii=False)
    created_at = ticket.get("created_at", datetime.now().isoformat())
    # 默认状态为“未处理”
    status = ticket.get("status", "未处理")
    cursor.execute('''
        INSERT OR REPLACE INTO tickets (ticket_id, raw_json, created_at, status)
        VALUES (?, ?, ?, ?)
    ''', (ticket_id, raw_json, created_at, status))
    conn.commit()
    conn.close()
    print(f"工单 {ticket_id} 已保存，状态: {status}")


def update_ticket_status(ticket_id: str, new_status: str) -> bool:
    """更新工单状态，成功返回 True"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE tickets SET status = ? WHERE ticket_id = ?
    ''', (new_status, ticket_id))
    affected = cursor.rowcount
    conn.commit()
    conn.close()
    if affected:
        print(f"工单 {ticket_id} 状态已更新为 {new_status}")
    return affected > 0


def get_all_tickets() -> List[Dict[str, Any]]:
    """获取所有工单，同时返回 status 字段"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT raw_json, created_at, status FROM tickets ORDER BY created_at DESC')
    rows = cursor.fetchall()
    conn.close()

    tickets = []
    for row in rows:
        try:
            ticket = json.loads(row["raw_json"])
            if "created_at" not in ticket:
                ticket["created_at"] = row["created_at"]
            # 从数据库读取状态，覆盖工单内可能不一致的状态
            ticket["status"] = row["status"]
            tickets.append(ticket)
        except json.JSONDecodeError as e:
            print(f"警告: 解析工单 JSON 失败，跳过。错误: {e}")
            continue
    return tickets


def get_tickets_by_urgency(urgency_level: str) -> List[Dict[str, Any]]:
    all_tickets = get_all_tickets()
    filtered = []
    for ticket in all_tickets:
        assessment = ticket.get("agent_business_assessment", {})
        ticket_urgency = assessment.get("urgency_level", "")
        if ticket_urgency.lower() == urgency_level.lower():
            filtered.append(ticket)
    return filtered


def get_ticket_by_id(ticket_id: str) -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT raw_json, status FROM tickets WHERE ticket_id = ?', (ticket_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        try:
            ticket = json.loads(row["raw_json"])
            ticket["status"] = row["status"]
            return ticket
        except json.JSONDecodeError:
            return None
    return None


def get_tickets_count() -> int:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM tickets')
    count = cursor.fetchone()[0]
    conn.close()
    return count