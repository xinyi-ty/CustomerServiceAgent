"""
database.py 测试脚本
运行方式：python test_database.py
"""

import os
import json
from database import init_db, save_ticket, get_all_tickets, get_ticket_by_id

# 1. 设置测试数据库路径
os.environ["DATABASE_PATH"] = "./test_data/test_tickets.db"

def test_init_db():
    """测试数据库初始化"""
    print("=" * 50)
    print("测试1: 初始化数据库")
    try:
        init_db()
        print("✅ 数据库初始化成功")
        print("   检查文件是否存在:", os.path.exists("./test_data/test_tickets.db"))
        return True
    except Exception as e:
        print(f"❌ 初始化失败: {e}")
        return False

def test_save_ticket():
    """测试保存工单"""
    print("\n" + "=" * 50)
    print("测试2: 保存工单")
    
    ticket = {
        "ticket_id": "CS-20260519-TEST001",
        "extracted_data": {
            "order_id": "JD9988776655",
            "model_number": "Pro-Max-V2",
            "batch_code": "X11"
        },
        "agent_business_assessment": {
            "issue_category": "Missing_Part",
            "business_impact": "Normal",
            "urgency_level": "Low",
            "warranty_status": "In_Warranty"
        },
        "routing_decision": "frontline_worker",
        "auto_reply_sent": "您好，配件已安排补发"
    }
    
    try:
        save_ticket(ticket)
        print("✅ 工单保存成功")
        print(f"   工单ID: {ticket['ticket_id']}")
        return True
    except Exception as e:
        print(f"❌ 保存失败: {e}")
        return False

def test_save_multiple_tickets():
    """测试保存多个工单"""
    print("\n" + "=" * 50)
    print("测试3: 保存多个工单")
    
    tickets = [
        {
            "ticket_id": "CS-20260519-TEST002",
            "agent_business_assessment": {"urgency_level": "Medium"},
            "auto_reply_sent": "核心部件损坏，已转交部门经理"
        },
        {
            "ticket_id": "CS-20260519-TEST003",
            "agent_business_assessment": {"urgency_level": "High"},
            "auto_reply_sent": "安全风险，已通知总经理"
        }
    ]
    
    for ticket in tickets:
        try:
            save_ticket(ticket)
            print(f"✅ 工单 {ticket['ticket_id']} 保存成功")
        except Exception as e:
            print(f"❌ 工单 {ticket['ticket_id']} 保存失败: {e}")
            return False
    return True

def test_get_all_tickets():
    """测试获取所有工单"""
    print("\n" + "=" * 50)
    print("测试4: 获取所有工单")
    
    try:
        tickets = get_all_tickets()
        print(f"✅ 查询成功，共 {len(tickets)} 个工单")
        for i, ticket in enumerate(tickets):
            print(f"   工单{i+1}: {ticket.get('ticket_id')} - 紧急度: {ticket.get('agent_business_assessment', {}).get('urgency_level', 'Unknown')}")
        return True
    except Exception as e:
        print(f"❌ 查询失败: {e}")
        return False

def test_get_ticket_by_id():
    """测试按ID查询工单"""
    print("\n" + "=" * 50)
    print("测试5: 按ID查询工单")
    
    test_id = "CS-20260519-TEST001"
    
    try:
        ticket = get_ticket_by_id(test_id)
        if ticket:
            print(f"✅ 查询成功，找到工单: {test_id}")
            print(f"   完整内容: {json.dumps(ticket, ensure_ascii=False, indent=2)}")
        else:
            print(f"⚠️ 未找到工单: {test_id}")
        return ticket is not None
    except Exception as e:
        print(f"❌ 查询失败: {e}")
        return False

def test_update_ticket():
    """测试更新工单（INSERT OR REPLACE）"""
    print("\n" + "=" * 50)
    print("测试6: 更新已存在的工单")
    
    updated_ticket = {
        "ticket_id": "CS-20260519-TEST001",
        "extracted_data": {
            "order_id": "UPDATED_ORDER_ID",
            "model_number": "Updated-Model",
            "batch_code": "UPDATED"
        },
        "agent_business_assessment": {
            "issue_category": "Updated_Category",
            "business_impact": "Updated_Impact",
            "urgency_level": "Updated_High",
            "warranty_status": "Unknown"
        },
        "routing_decision": "updated_routing",
        "auto_reply_sent": "这是更新后的回复内容"
    }
    
    try:
        save_ticket(updated_ticket)
        print("✅ 工单更新成功")
        
        # 验证更新
        saved = get_ticket_by_id("CS-20260519-TEST001")
        if saved and saved.get("extracted_data", {}).get("order_id") == "UPDATED_ORDER_ID":
            print("✅ 验证通过：工单内容已更新")
        else:
            print("⚠️ 验证失败：工单内容未正确更新")
        return True
    except Exception as e:
        print(f"❌ 更新失败: {e}")
        return False

def test_invalid_ticket_id():
    """测试查询不存在的工单"""
    print("\n" + "=" * 50)
    print("测试7: 查询不存在的工单ID")
    
    result = get_ticket_by_id("NON_EXISTENT_ID")
    if result is None:
        print("✅ 正确返回 None（未找到工单）")
        return True
    else:
        print("❌ 应返回 None，但实际返回了数据")
        return False

def cleanup():
    """清理测试数据"""
    print("\n" + "=" * 50)
    print("清理测试数据")
    import shutil
    if os.path.exists("./test_data"):
        shutil.rmtree("./test_data")
        print("✅ 测试数据已清理")

def run_all_tests():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("开始测试 database.py 模块")
    print("=" * 60)
    
    tests = [
        ("初始化数据库", test_init_db),
        ("保存工单", test_save_ticket),
        ("保存多个工单", test_save_multiple_tickets),
        ("获取所有工单", test_get_all_tickets),
        ("按ID查询工单", test_get_ticket_by_id),
        ("更新工单", test_update_ticket),
        ("查询不存在的ID", test_invalid_ticket_id),
    ]
    
    results = []
    for name, test_func in tests:
        result = test_func()
        results.append((name, result))
    
    # 输出测试总结
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    
    passed = sum(1 for _, r in results if r)
    total = len(results)
    
    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{status} - {name}")
    
    print(f"\n总计: {passed}/{total} 测试通过")
    
    # 询问是否清理测试数据
    print("\n是否清理测试数据？(y/n)")
    if input().lower() == 'y':
        cleanup()
    
    return passed == total

if __name__ == "__main__":
    run_all_tests()