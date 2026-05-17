"""
database.py - 数据库操作模块

负责 SQLite 数据库的初始化、工单的保存和查询。
提供统一的数据库接口，其他模块通过此模块操作数据库。
"""

import sqlite3
import json
from typing import List, Dict, Any, Optional
from datetime import datetime
from contextlib import contextmanager

# 导入配置
from backend.config import DATABASE_PATH, ensure_data_dir, DEBUG_MODE


# ====================
# 数据库连接管理
# ====================

@contextmanager
def get_db_connection():
    """
    获取数据库连接的上下文管理器
    
    自动处理连接的打开和关闭，确保资源正确释放。
    
    Usage:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM tickets")
    
    Yields:
        SQLite 连接对象
    """
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        conn.row_factory = sqlite3.Row  # 返回字典形式的行
        yield conn
    finally:
        if conn:
            conn.close()


def get_db_connection_simple():
    """
    获取数据库连接的简单函数（不使用上下文管理器）
    
    Returns:
        SQLite 连接对象
    """
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ====================
# 数据库初始化
# ====================

def init_db():
    """
    初始化数据库
    
    创建所有必需的表（如果不存在）：
    - tickets: 工单主表
    - sop_knowledge: SOP 知识库表（可选，供 RAG 同学使用）
    - warranty_db: 保修信息表（可选）
    
    在应用启动时调用。
    """
    # 确保数据库目录存在
    ensure_data_dir()
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # 1. 创建工单表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id TEXT UNIQUE NOT NULL,
                raw_json TEXT NOT NULL,
                urgency_level TEXT,
                routing_decision TEXT,
                issue_category TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 为工单表创建索引（提升查询性能）
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_tickets_ticket_id 
            ON tickets(ticket_id)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_tickets_created_at 
            ON tickets(created_at DESC)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_tickets_urgency 
            ON tickets(urgency_level)
        """)
        
        # 2. 创建 SOP 知识库表（可选，供 RAG 同学使用）
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sop_knowledge (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,
                urgency_level TEXT,
                guide_text TEXT NOT NULL,
                keywords TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 3. 创建保修信息表（可选）
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS warranty_info (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sn_code TEXT UNIQUE NOT NULL,
                product_model TEXT,
                manufacture_date TEXT,
                warranty_expire_date TEXT,
                status TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_warranty_sn_code 
            ON warranty_info(sn_code)
        """)
        
        # 4. 创建系统配置表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS system_config (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                description TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        conn.commit()
        
        if DEBUG_MODE:
            print(f"✅ 数据库初始化完成: {DATABASE_PATH}")
            print(f"   - tickets 表: 工单存储")
            print(f"   - sop_knowledge 表: SOP 知识库")
            print(f"   - warranty_info 表: 保修信息")
            print(f"   - system_config 表: 系统配置")


# ====================
# 工单操作
# ====================

def save_ticket(ticket: Dict[str, Any]) -> bool:
    """
    保存工单到数据库
    
    Args:
        ticket: 工单字典，必须包含 ticket_id 字段
        
    Returns:
        是否保存成功
    """
    try:
        ticket_id = ticket.get("ticket_id")
        if not ticket_id:
            raise ValueError("工单必须包含 ticket_id 字段")
        
        # 提取用于索引的字段（方便查询）
        urgency_level = ticket.get("agent_business_assessment", {}).get("urgency_level")
        routing_decision = ticket.get("routing_decision")
        issue_category = ticket.get("agent_business_assessment", {}).get("issue_category")
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # 检查是否已存在（避免重复）
            cursor.execute("SELECT id FROM tickets WHERE ticket_id = ?", (ticket_id,))
            existing = cursor.fetchone()
            
            if existing:
                # 更新现有工单
                cursor.execute("""
                    UPDATE tickets 
                    SET raw_json = ?,
                        urgency_level = ?,
                        routing_decision = ?,
                        issue_category = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE ticket_id = ?
                """, (
                    json.dumps(ticket, ensure_ascii=False),
                    urgency_level,
                    routing_decision,
                    issue_category,
                    ticket_id
                ))
                if DEBUG_MODE:
                    print(f"更新工单: {ticket_id}")
            else:
                # 插入新工单
                cursor.execute("""
                    INSERT INTO tickets (ticket_id, raw_json, urgency_level, routing_decision, issue_category)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    ticket_id,
                    json.dumps(ticket, ensure_ascii=False),
                    urgency_level,
                    routing_decision,
                    issue_category
                ))
                if DEBUG_MODE:
                    print(f"插入工单: {ticket_id}")
            
            conn.commit()
            return True
            
    except Exception as e:
        print(f"❌ 保存工单失败: {str(e)}")
        if DEBUG_MODE:
            import traceback
            traceback.print_exc()
        return False


def get_ticket_by_id(ticket_id: str) -> Optional[Dict[str, Any]]:
    """
    根据工单 ID 获取工单
    
    Args:
        ticket_id: 工单 ID
        
    Returns:
        工单字典，如果不存在返回 None
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT raw_json FROM tickets WHERE ticket_id = ?", (ticket_id,))
            row = cursor.fetchone()
            
            if row:
                return json.loads(row["raw_json"])
            return None
            
    except Exception as e:
        print(f"❌ 查询工单失败: {str(e)}")
        return None


def get_all_tickets(limit: Optional[int] = None, offset: int = 0) -> List[Dict[str, Any]]:
    """
    获取所有工单，按创建时间倒序
    
    Args:
        limit: 返回的最大记录数（可选）
        offset: 偏移量，用于分页（可选）
        
    Returns:
        工单字典列表
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            if limit:
                cursor.execute(
                    "SELECT raw_json FROM tickets ORDER BY created_at DESC LIMIT ? OFFSET ?",
                    (limit, offset)
                )
            else:
                cursor.execute("SELECT raw_json FROM tickets ORDER BY created_at DESC")
            
            rows = cursor.fetchall()
            tickets = []
            
            for row in rows:
                try:
                    tickets.append(json.loads(row["raw_json"]))
                except json.JSONDecodeError as e:
                    print(f"解析工单 JSON 失败: {e}")
                    continue
            
            return tickets
            
    except Exception as e:
        print(f"❌ 查询工单列表失败: {str(e)}")
        return []


def get_tickets_by_urgency(urgency_level: str, limit: int = 50) -> List[Dict[str, Any]]:
    """
    按紧急度筛选工单
    
    Args:
        urgency_level: 紧急度（Low/Medium/High）
        limit: 返回的最大记录数
        
    Returns:
        工单字典列表
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT raw_json FROM tickets 
                WHERE urgency_level = ? 
                ORDER BY created_at DESC 
                LIMIT ?
            """, (urgency_level, limit))
            
            rows = cursor.fetchall()
            tickets = []
            
            for row in rows:
                try:
                    tickets.append(json.loads(row["raw_json"]))
                except json.JSONDecodeError:
                    continue
            
            return tickets
            
    except Exception as e:
        print(f"❌ 按紧急度查询失败: {str(e)}")
        return []


def get_tickets_by_date(start_date: str, end_date: str) -> List[Dict[str, Any]]:
    """
    按日期范围查询工单
    
    Args:
        start_date: 开始日期（YYYY-MM-DD）
        end_date: 结束日期（YYYY-MM-DD）
        
    Returns:
        工单字典列表
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT raw_json FROM tickets 
                WHERE DATE(created_at) BETWEEN ? AND ?
                ORDER BY created_at DESC
            """, (start_date, end_date))
            
            rows = cursor.fetchall()
            tickets = []
            
            for row in rows:
                try:
                    tickets.append(json.loads(row["raw_json"]))
                except json.JSONDecodeError:
                    continue
            
            return tickets
            
    except Exception as e:
        print(f"❌ 按日期查询失败: {str(e)}")
        return []


def delete_ticket(ticket_id: str) -> bool:
    """
    删除工单
    
    Args:
        ticket_id: 工单 ID
        
    Returns:
        是否删除成功
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM tickets WHERE ticket_id = ?", (ticket_id,))
            conn.commit()
            
            success = cursor.rowcount > 0
            if success and DEBUG_MODE:
                print(f"删除工单: {ticket_id}")
            return success
            
    except Exception as e:
        print(f"❌ 删除工单失败: {str(e)}")
        return False


def count_tickets() -> int:
    """
    统计工单总数
    
    Returns:
        工单总数
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) as count FROM tickets")
            row = cursor.fetchone()
            return row["count"] if row else 0
            
    except Exception as e:
        print(f"❌ 统计工单失败: {str(e)}")
        return 0


def get_statistics() -> Dict[str, Any]:
    """
    获取工单统计信息
    
    Returns:
        统计数据字典
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # 总数
            cursor.execute("SELECT COUNT(*) as total FROM tickets")
            total = cursor.fetchone()["total"]
            
            # 按紧急度统计
            cursor.execute("""
                SELECT urgency_level, COUNT(*) as count 
                FROM tickets 
                GROUP BY urgency_level
            """)
            urgency_stats = {row["urgency_level"]: row["count"] for row in cursor.fetchall()}
            
            # 按路由统计
            cursor.execute("""
                SELECT routing_decision, COUNT(*) as count 
                FROM tickets 
                GROUP BY routing_decision
            """)
            routing_stats = {row["routing_decision"]: row["count"] for row in cursor.fetchall()}
            
            # 最近7天工单数
            cursor.execute("""
                SELECT COUNT(*) as recent 
                FROM tickets 
                WHERE created_at >= DATE('now', '-7 days')
            """)
            recent_7days = cursor.fetchone()["recent"]
            
            return {
                "total": total,
                "by_urgency": urgency_stats,
                "by_routing": routing_stats,
                "recent_7days": recent_7days,
                "last_updated": datetime.now().isoformat()
            }
            
    except Exception as e:
        print(f"❌ 获取统计信息失败: {str(e)}")
        return {
            "total": 0,
            "by_urgency": {},
            "by_routing": {},
            "recent_7days": 0,
            "error": str(e)
        }


# ====================
# SOP 知识库操作（可选）
# ====================

def insert_sop_knowledge(category: str, guide_text: str, urgency_level: str = None, keywords: str = None) -> bool:
    """
    插入 SOP 知识
    
    Args:
        category: 问题类别
        guide_text: 指导文本
        urgency_level: 适用紧急度（可选）
        keywords: 关键词（逗号分隔）
        
    Returns:
        是否插入成功
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO sop_knowledge (category, urgency_level, guide_text, keywords)
                VALUES (?, ?, ?, ?)
            """, (category, urgency_level, guide_text, keywords))
            conn.commit()
            return True
    except Exception as e:
        print(f"❌ 插入 SOP 知识失败: {str(e)}")
        return False


def get_sop_knowledge(category: str, urgency_level: str = None) -> Optional[str]:
    """
    获取 SOP 知识
    
    Args:
        category: 问题类别
        urgency_level: 紧急度（可选）
        
    Returns:
        指导文本，如果不存在返回 None
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            if urgency_level:
                cursor.execute("""
                    SELECT guide_text FROM sop_knowledge 
                    WHERE category = ? AND (urgency_level = ? OR urgency_level IS NULL)
                    ORDER BY urgency_level DESC
                    LIMIT 1
                """, (category, urgency_level))
            else:
                cursor.execute("""
                    SELECT guide_text FROM sop_knowledge 
                    WHERE category = ?
                    LIMIT 1
                """, (category,))
            
            row = cursor.fetchone()
            return row["guide_text"] if row else None
            
    except Exception as e:
        print(f"❌ 查询 SOP 知识失败: {str(e)}")
        return None


# ====================
# 保修信息操作（可选）
# ====================

def insert_warranty_info(sn_code: str, product_model: str, manufacture_date: str, warranty_years: int = 2) -> bool:
    """
    插入保修信息
    
    Args:
        sn_code: SN 码
        product_model: 产品型号
        manufacture_date: 生产日期（YYYY-MM-DD）
        warranty_years: 保修年限
        
    Returns:
        是否插入成功
    """
    try:
        from datetime import datetime, timedelta
        
        manufacture_dt = datetime.strptime(manufacture_date, "%Y-%m-%d")
        warranty_expire = manufacture_dt + timedelta(days=warranty_years * 365)
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO warranty_info 
                (sn_code, product_model, manufacture_date, warranty_expire_date, status)
                VALUES (?, ?, ?, ?, ?)
            """, (sn_code, product_model, manufacture_date, warranty_expire.strftime("%Y-%m-%d"), "active"))
            conn.commit()
            return True
    except Exception as e:
        print(f"❌ 插入保修信息失败: {str(e)}")
        return False


def get_warranty_info(sn_code: str) -> Optional[Dict[str, Any]]:
    """
    获取保修信息
    
    Args:
        sn_code: SN 码
        
    Returns:
        保修信息字典
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM warranty_info WHERE sn_code = ?", (sn_code,))
            row = cursor.fetchone()
            
            if row:
                return dict(row)
            return None
            
    except Exception as e:
        print(f"❌ 查询保修信息失败: {str(e)}")
        return None


# ====================
# 系统配置操作
# ====================

def set_config(key: str, value: str, description: str = None) -> bool:
    """
    设置系统配置
    
    Args:
        key: 配置键
        value: 配置值
        description: 配置描述（可选）
        
    Returns:
        是否设置成功
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO system_config (key, value, description, updated_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            """, (key, value, description))
            conn.commit()
            return True
    except Exception as e:
        print(f"❌ 设置配置失败: {str(e)}")
        return False


def get_config(key: str) -> Optional[str]:
    """
    获取系统配置
    
    Args:
        key: 配置键
        
    Returns:
        配置值，如果不存在返回 None
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM system_config WHERE key = ?", (key,))
            row = cursor.fetchone()
            return row["value"] if row else None
            
    except Exception as e:
        print(f"❌ 获取配置失败: {str(e)}")
        return None


# ====================
# 数据库维护
# ====================

def backup_database(backup_path: str = None) -> bool:
    """
    备份数据库
    
    Args:
        backup_path: 备份文件路径（可选，默认生成时间戳文件名）
        
    Returns:
        是否备份成功
    """
    import shutil
    
    try:
        if backup_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = f"{DATABASE_PATH}.backup_{timestamp}"
        
        shutil.copy2(DATABASE_PATH, backup_path)
        print(f"✅ 数据库备份成功: {backup_path}")
        return True
        
    except Exception as e:
        print(f"❌ 数据库备份失败: {str(e)}")
        return False


def vacuum_database():
    """清理数据库（回收空间）"""
    try:
        with get_db_connection() as conn:
            conn.execute("VACUUM")
            print("✅ 数据库清理完成")
    except Exception as e:
        print(f"❌ 数据库清理失败: {str(e)}")


def get_table_info() -> Dict[str, int]:
    """
    获取数据库表信息
    
    Returns:
        各表的记录数
    """
    tables = ["tickets", "sop_knowledge", "warranty_info", "system_config"]
    info = {}
    
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            for table in tables:
                cursor.execute(f"SELECT COUNT(*) as count FROM {table}")
                row = cursor.fetchone()
                info[table] = row["count"] if row else 0
    except Exception as e:
        print(f"❌ 获取表信息失败: {str(e)}")
    
    return info


# ====================
# 测试函数
# ====================

def test_database():
    """测试数据库功能"""
    print("\n" + "=" * 50)
    print("测试 database.py")
    print("=" * 50)
    
    # 初始化数据库
    init_db()
    print("✅ 数据库初始化")
    
    # 测试保存工单
    test_ticket = {
        "ticket_id": "TEST-001",
        "extracted_data": {"order_id": "TEST001"},
        "agent_business_assessment": {
            "issue_category": "Test",
            "urgency_level": "Low",
            "business_impact": "Normal",
            "warranty_status": "Unknown"
        },
        "routing_decision": "frontline_worker",
        "auto_reply_sent": "测试回复"
    }
    
    save_ticket(test_ticket)
    print("✅ 保存工单")
    
    # 测试查询
    ticket = get_ticket_by_id("TEST-001")
    print(f"✅ 查询工单: {ticket is not None}")
    
    # 测试统计
    stats = get_statistics()
    print(f"✅ 统计信息: {stats}")
    
    # 测试删除
    delete_ticket("TEST-001")
    print("✅ 删除工单")
    
    print("=" * 50)
    print("所有测试通过！")
    print("=" * 50 + "\n")


if __name__ == "__main__":
    test_database()
