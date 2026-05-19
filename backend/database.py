import sqlite3
import json
from typing import List, Dict, Any,Optional
from datetime import datetime
from config import DATABASE_PATH

def get_db_connection():
    """获取数据库连接"""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db() -> None:
    """初始化数据库，创建 tickets 表"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id TEXT UNIQUE NOT NULL,
            raw_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    ''')
    
    conn.commit()
    conn.close()
    print("数据库初始化完成")

def save_ticket(ticket: Dict[str, Any]) -> None:
    """保存工单到数据库"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT OR REPLACE INTO tickets (ticket_id, raw_json, created_at)
        VALUES (?, ?, ?)
    ''', (
        ticket.get("ticket_id"),
        json.dumps(ticket, ensure_ascii=False),
        datetime.now().isoformat()
    ))
    
    conn.commit()
    conn.close()

def get_all_tickets() -> List[Dict[str, Any]]:
    """获取所有工单，按创建时间倒序"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT raw_json FROM tickets 
        ORDER BY created_at DESC
    ''')
    
    rows = cursor.fetchall()
    conn.close()
    
    tickets = []
    for row in rows:
        try:
            ticket = json.loads(row["raw_json"])
            tickets.append(ticket)
        except:
            continue
    
    return tickets

def get_ticket_by_id(ticket_id: str) -> Optional[Dict[str, Any]]:
    """根据ID获取单个工单"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT raw_json FROM tickets WHERE ticket_id = ?
    ''', (ticket_id,))
    
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return json.loads(row["raw_json"])
    return None
