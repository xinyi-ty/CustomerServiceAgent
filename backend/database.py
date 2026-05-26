import sqlite3
import json
import os
from typing import List, Dict, Any, Optional
from datetime import datetime
from config import DATABASE_PATH


def _ensure_dir(path: str) -> None:
    """确保数据库文件所在目录存在"""
    dirname = os.path.dirname(path)
    if dirname and not os.path.exists(dirname):
        os.makedirs(dirname, exist_ok=True)


def get_db_connection():
    """获取数据库连接"""
    _ensure_dir(DATABASE_PATH)
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """初始化数据库，创建 tickets 表和索引"""
    conn = get_db_connection()
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
                       NULL
                   )
                   ''')

    # 创建索引以加速查询
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_ticket_id ON tickets(ticket_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_created_at ON tickets(created_at DESC)')

    conn.commit()
    conn.close()
    print("数据库初始化完成（含索引）")


def save_ticket(ticket: Dict[str, Any]) -> None:
    """
    保存或更新工单（基于 ticket_id 唯一约束）
    如果工单已存在，则更新其内容和时间戳
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    ticket_id = ticket.get("ticket_id")
    if not ticket_id:
        raise ValueError("ticket_id 不能为空")

    raw_json = json.dumps(ticket, ensure_ascii=False)
    created_at = datetime.now().isoformat()

    # INSERT OR REPLACE 会根据 UNIQUE 约束覆盖已有记录
    cursor.execute('''
        INSERT OR REPLACE INTO tickets (ticket_id, raw_json, created_at)
        VALUES (?, ?, ?)
    ''', (ticket_id, raw_json, created_at))

    conn.commit()
    conn.close()
    print(f"工单 {ticket_id} 已保存/更新")


def get_all_tickets() -> List[Dict[str, Any]]:
    """获取所有工单，按创建时间倒序，并确保每条工单都有 created_at 字段"""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
                   SELECT raw_json, created_at
                   FROM tickets
                   ORDER BY created_at DESC
                   ''')

    rows = cursor.fetchall()
    conn.close()

    tickets = []
    for row in rows:
        try:
            ticket = json.loads(row["raw_json"])
            # 如果工单内部没有 created_at，则从表字段补充（向下兼容）
            if "created_at" not in ticket:
                ticket["created_at"] = row["created_at"]
            tickets.append(ticket)
        except json.JSONDecodeError as e:
            print(f"警告: 解析工单 JSON 失败，跳过该记录。错误: {e}")
            continue

    return tickets


def get_ticket_by_id(ticket_id: str) -> Optional[Dict[str, Any]]:
    """根据ID获取单个工单"""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
                   SELECT raw_json
                   FROM tickets
                   WHERE ticket_id = ?
                   ''', (ticket_id,))

    row = cursor.fetchone()
    conn.close()

    if row:
        try:
            ticket = json.loads(row["raw_json"])
            return ticket
        except json.JSONDecodeError as e:
            print(f"警告: 解析工单 {ticket_id} 的 JSON 失败: {e}")
            return None
    return None


def get_tickets_count() -> int:
    """返回工单总数（辅助函数）"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM tickets')
    count = cursor.fetchone()[0]
    conn.close()
    return count