"""
测试数据种子脚本
================
1. 初始化数据库表结构
2. 写入产品注册表（SN 码 → 产品信息映射）
3. 写入测试工单

运行方式：python backend/seed_data.py
"""
import sys
import os
import json
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import init_db, save_ticket, seed_product_registry, get_all_products, get_all_tickets

# ============================
# 产品注册表数据 — 从外部 JSON 文件读取
# 替换真实数据时只需修改 data/products.json，无需改动代码
# ============================
PRODUCTS_JSON_PATH = os.path.join(os.path.dirname(__file__), "data", "products.json")

def load_product_registry() -> list:
    if not os.path.exists(PRODUCTS_JSON_PATH):
        print(f"[WARN] 未找到产品数据文件: {PRODUCTS_JSON_PATH}")
        print(f"[WARN] 请创建该文件或放入真实产品数据")
        return []
    with open(PRODUCTS_JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    print(f"[INFO] 从 {PRODUCTS_JSON_PATH} 加载了 {len(data)} 条产品记录")
    return data


# ============================
# 测试工单数据
# ============================
TEST_TICKETS = [
    # 场景 1：高紧急度 - 设备冒烟（SN 在保）→ 路由总经理
    {
        "ticket_id": "CS-20260602-0001",
        "created_at": "2026-06-02T08:30:00",
        "extracted_data": {
            "order_id": "JD202606010001",
            "model_number": "Pro-Max-V2",
            "batch_code": "BATCH-A01",
            "sn_code": "SN202501001",
            "evidence_images": ["uploads/burn_01.jpg"],
            "ocr_text": "SN: SN202501001 空调冒烟了"
        },
        "agent_business_assessment": {
            "issue_category": "Hardware_Thermal_Runaway",
            "business_impact": "Safety_Hazard",
            "urgency_level": "high",
            "warranty_status": "In_Warranty"
        },
        "routing_decision": "general_manager_dashboard",
        "auto_reply_sent": "[紧急安全警告] 请立即切断设备电源，并远离设备至少2米。我们的技术总监将在 15 分钟内直接与您联系。",
        "status": "未处理"
    },
    # 场景 2：高紧急度 - 漏电（SN 过保）→ 路由总经理
    {
        "ticket_id": "CS-20260602-0002",
        "created_at": "2026-06-02T09:15:00",
        "extracted_data": {
            "order_id": "TMALL20260515003",
            "model_number": "X-Basic-100",
            "batch_code": "BATCH-B03",
            "sn_code": "SN202301015",
            "evidence_images": [],
            "ocr_text": "S/N: SN202301015"
        },
        "agent_business_assessment": {
            "issue_category": "Hardware_Thermal_Runaway",
            "business_impact": "Safety_Hazard",
            "urgency_level": "high",
            "warranty_status": "Out_of_Warranty"
        },
        "routing_decision": "general_manager_dashboard",
        "auto_reply_sent": "[紧急] 请立即停止使用设备并拔掉电源插头。不要接触金属部分。我们的安全工程师会立刻联系您。",
        "status": "未处理"
    },
    # 场景 3：中紧急度 - 电机故障（SN 在保）→ 路由部门经理
    {
        "ticket_id": "CS-20260602-0003",
        "created_at": "2026-06-01T14:20:00",
        "extracted_data": {
            "order_id": "JD202605280010",
            "model_number": "Pro-Max-V2",
            "batch_code": "BATCH-A01",
            "sn_code": "SN202509888",
            "evidence_images": ["uploads/motor_fault.mp4"],
            "ocr_text": "Pro-Max-V2 电机不转 SN202509888"
        },
        "agent_business_assessment": {
            "issue_category": "Functional_Failure",
            "business_impact": "Production_Stop",
            "urgency_level": "medium",
            "warranty_status": "In_Warranty"
        },
        "routing_decision": "manager_dashboard",
        "auto_reply_sent": "非常抱歉给您带来不便。您反馈的设备核心部件问题已引起我们重视。我们将安排资深工程师与您预约远程诊断，请保持电话畅通。",
        "status": "未处理"
    },
    # 场景 4：中紧急度 - 批次缺陷（SN 在保）→ 路由部门经理
    {
        "ticket_id": "CS-20260602-0004",
        "created_at": "2026-06-02T10:00:00",
        "extracted_data": {
            "order_id": "PDD202605310020",
            "model_number": "Eco-Wash-P3",
            "batch_code": "BATCH-C07",
            "sn_code": "SN202607100",
            "evidence_images": [],
            "ocr_text": ""
        },
        "agent_business_assessment": {
            "issue_category": "Batch_Defect",
            "business_impact": "Production_Stop",
            "urgency_level": "medium",
            "warranty_status": "In_Warranty"
        },
        "routing_decision": "manager_dashboard",
        "auto_reply_sent": "我们已经注意到该批次可能存在共性质量问题，工程团队已介入调查。请您提供批次号和购买凭证，我们将优先为您换货。",
        "status": "未处理"
    },
    # 场景 5：低紧急度 - 配件缺失（SN 在保）→ 路由一线员工
    {
        "ticket_id": "CS-20260602-0005",
        "created_at": "2026-06-01T11:30:00",
        "extracted_data": {
            "order_id": "JD202605200101",
            "model_number": "SmartCook-M1",
            "batch_code": "BATCH-D02",
            "sn_code": "SN202512345",
            "evidence_images": [],
            "ocr_text": ""
        },
        "agent_business_assessment": {
            "issue_category": "Missing_Part",
            "business_impact": "Normal",
            "urgency_level": "low",
            "warranty_status": "In_Warranty"
        },
        "routing_decision": "frontline_worker",
        "auto_reply_sent": "您好，我们很重视您提到的配件缺失问题。请访问链接填写补发申请：https://example.com/replacement，通常 3 个工作日内免费寄出。",
        "status": "未处理"
    },
    # 场景 6：低紧急度 - 操作咨询（过保设备）→ 路由一线员工
    {
        "ticket_id": "CS-20260602-0006",
        "created_at": "2026-06-02T07:45:00",
        "extracted_data": {
            "order_id": "TMALL202203151234",
            "model_number": "X-Basic-100",
            "batch_code": "BATCH-B01",
            "sn_code": "SN202205678",
            "evidence_images": [],
            "ocr_text": ""
        },
        "agent_business_assessment": {
            "issue_category": "Operational_Error",
            "business_impact": "Normal",
            "urgency_level": "low",
            "warranty_status": "Out_of_Warranty"
        },
        "routing_decision": "frontline_worker",
        "auto_reply_sent": "您可访问说明书电子版：https://example.com/manual 或观看教学视频获取操作指引。",
        "status": "已处理"
    },
    # 场景 7：中紧急度 - 运输损坏（SN 格式异常）→ 路由部门经理
    {
        "ticket_id": "CS-20260602-0007",
        "created_at": "2026-05-31T16:00:00",
        "extracted_data": {
            "order_id": "SF202605300888",
            "model_number": "Pro-Max-V2",
            "batch_code": "BATCH-A02",
            "sn_code": "SN_BAD00",
            "evidence_images": ["uploads/package_damage.png"],
            "ocr_text": "包装破损 SN_BAD00"
        },
        "agent_business_assessment": {
            "issue_category": "Damaged_Part",
            "business_impact": "Production_Stop",
            "urgency_level": "medium",
            "warranty_status": "Unknown"
        },
        "routing_decision": "manager_dashboard",
        "auto_reply_sent": "很遗憾听到您的商品在运输中受损。请您保留原包装并拍摄破损照片，我们会联系物流公司理赔并为您安排换货。",
        "status": "未处理"
    },
    # 场景 8：高紧急度 - 群体性投诉（无 SN）→ 路由总经理
    {
        "ticket_id": "CS-20260602-0008",
        "created_at": "2026-06-02T06:30:00",
        "extracted_data": {
            "order_id": "ONLINE202606001",
            "model_number": "Eco-Wash-P3",
            "batch_code": "BATCH-C07",
            "sn_code": "",
            "evidence_images": [],
            "ocr_text": ""
        },
        "agent_business_assessment": {
            "issue_category": "Batch_Defect",
            "business_impact": "Safety_Hazard",
            "urgency_level": "high",
            "warranty_status": "Unknown"
        },
        "routing_decision": "general_manager_dashboard",
        "auto_reply_sent": "我们已经关注到您反馈的问题，并已成立专项小组进行调查。我们会尽快公布解决方案。",
        "status": "未处理"
    },
    # 场景 9：低紧急度 - 外观划痕（SN 在保）→ 路由一线员工
    {
        "ticket_id": "CS-20260602-0009",
        "created_at": "2026-06-01T09:10:00",
        "extracted_data": {
            "order_id": "JD202605220066",
            "model_number": "SmartCook-M1",
            "batch_code": "BATCH-D01",
            "sn_code": "SN202603001",
            "evidence_images": ["uploads/scratch.jpg"],
            "ocr_text": ""
        },
        "agent_business_assessment": {
            "issue_category": "Cosmetic_Damage",
            "business_impact": "Normal",
            "urgency_level": "low",
            "warranty_status": "In_Warranty"
        },
        "routing_decision": "frontline_worker",
        "auto_reply_sent": "对于外观损伤我们深表歉意。若确属出厂问题，我们将免费为您更换外壳。",
        "status": "已处理"
    },
    # 场景 10：中紧急度 - 刚过保故障 → 路由部门经理
    {
        "ticket_id": "CS-20260602-0010",
        "created_at": "2026-06-01T17:20:00",
        "extracted_data": {
            "order_id": "TMALL20240420000",
            "model_number": "X-Basic-100",
            "batch_code": "BATCH-B05",
            "sn_code": "SN202404020",
            "evidence_images": [],
            "ocr_text": "SN202404020"
        },
        "agent_business_assessment": {
            "issue_category": "Functional_Failure",
            "business_impact": "Production_Stop",
            "urgency_level": "medium",
            "warranty_status": "Out_of_Warranty"
        },
        "routing_decision": "manager_dashboard",
        "auto_reply_sent": "我们正在分析您的主板问题。请尝试断电重启。如果无效，我们提供付费维修服务。",
        "status": "未处理"
    },
]


def main():
    print("=" * 60)
    print("测试数据种子脚本")
    print("=" * 60)

    # 1. 初始化数据库
    init_db()

    # 2. 从 JSON 文件加载并写入产品注册表
    print(f"\n[1/3] 写入产品注册表...")
    product_data = load_product_registry()
    if not product_data:
        print("  [WARN] 无产品数据，跳过注册表写入")
    else:
        n = seed_product_registry(product_data)
        print(f"  [OK] 产品注册表写入 {n} 条记录")

    # 验证产品注册表
    products = get_all_products()
    print(f"\n  产品注册表内容 ({len(products)} 条):")
    for p in products:
        warranty = ""
        if p["production_year"] and p["production_year"] > 2000:
            from datetime import datetime
            from dateutil.relativedelta import relativedelta
            try:
                prod = datetime(int(p["production_year"]), int(p["production_month"] or 1), 1)
                exp = prod + relativedelta(years=2)
                status = "在保" if datetime.now() < exp else "过保"
                warranty = f" ({p['production_year']}-{str(p['production_month'] or 0).zfill(2)} 生产, {status})"
            except:
                pass
        print(f"    {p['sn_code']:>15s} → {p['model_number']:>15s} | 订单 {p['order_id']}{warranty}")

    # 3. 写入测试工单
    print(f"\n[2/3] 写入测试工单...")
    success = 0
    for ticket in TEST_TICKETS:
        try:
            save_ticket(ticket)
            print(f"  [OK] {ticket['ticket_id']} | "
                  f"{ticket['agent_business_assessment']['urgency_level'].upper():>5} | "
                  f"{ticket['extracted_data']['model_number']:>15s} | "
                  f"SN:{ticket['extracted_data']['sn_code'] or '(空)':>12s}")
            success += 1
        except Exception as e:
            print(f"  [FAIL] {ticket.get('ticket_id')}: {e}")
    print(f"\n  [SUMMARY] 工单写入 {success}/{len(TEST_TICKETS)}")

    # 4. 最终验证
    print(f"\n[3/3] 验证数据一致性...")
    all_tickets = get_all_tickets(limit=100)
    print(f"  数据库工单总数: {len(all_tickets)}")
    print(f"  产品注册记录数: {len(products)}")

    print(f"\n{'=' * 60}")
    print("种子数据写入完成。现在您可以：")
    print('  1. 在 chat 界面输入 "我的 SN 是 SN202501001，空调冒烟了" 来测试产品查询')
    print("  2. 在 admin 界面查看工单路由和保修状态")
    print("  3. OCR 识别图片/视频中的 SN 码后自动关联产品信息")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
