def init_db() -> None:
    """在应用启动时调用，创建 tickets 表（如果不存在）"""
    # TODO: 建立连接，执行 CREATE TABLE IF NOT EXISTS
    pass

def save_ticket(ticket: dict) -> None:
    """将完整工单 JSON 存入数据库，ticket 必须包含 'ticket_id' 字段"""
    # TODO: INSERT INTO tickets (ticket_id, raw_json, created_at) VALUES (?, ?, datetime('now'))
    pass

def get_all_tickets() -> list:
    """返回所有工单列表，按创建时间倒序，每个元素为 dict（原始工单 JSON）"""
    # TODO: SELECT raw_json FROM tickets ORDER BY created_at DESC
    pass