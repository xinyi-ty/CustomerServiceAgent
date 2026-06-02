# 大模型 Agent 路由分发与定级逻辑说明文档

> 版本：1.0  
> 适用项目：客诉自动回复与出单分发智能体  
> 最后更新：2026-06-02

---

## 一、系统架构总览

```
客户输入 (文本/图片/视频)
        │
        ▼
┌──────────────────┐
│  1. 多模态 OCR    │  ← PaddleOCR 提取图片/视频文字 + SN 码
│     预处理        │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  2. RAG 前置检索  │  ← 用客户原文检索 SOP 知识库 (ChromaDB + DashScope Embedding)
│  SOP 上下文获取   │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  3. LLM 推理      │  ← 注入 SOP 上下文，输出结构化 JSON 工单
│  意图识别 + 定级  │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  4. 安全硬规则拦截 │  ← 危险关键词强制 High 优先级
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  5. ERP 质保校验   │  ← SN 码 → 远程 ERP / 本地模拟
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  6. 工单生成入库   │  ← 数据库持久化 + 递增工单号
└──────────────────┘
```

---

## 二、紧急度定级规则（核心路由依据）

### 2.1 三级定级矩阵

定级摒弃主观情绪判断，完全基于**客观业务影响**进行硬性定级：

| 紧急度 | 触发条件 | 业务影响 | 路由目标 | 响应时限 |
|--------|---------|---------|---------|---------|
| **low** | 无安全风险，不影响基本使用 | Normal | 一线员工 (frontline_worker) | 24小时内 |
| **medium** | 影响部分功能，有潜在风险 | Production_Stop / Degraded | 部门经理 (manager_dashboard) | 4小时内 |
| **high** | 涉及人身/财产安全，群体性风险 | Safety_Hazard / Critical | 总经理看板 (general_manager_dashboard) | 30分钟内 |

### 2.2 具体分类规则

#### Low 紧急度（对应 `issue_category`）
| 类别 | 判定依据 | 示例 |
|------|---------|------|
| `Missing_Part` | 配件缺失、零件遗漏 | 少螺丝、缺少数据线 |
| `Cosmetic_Damage` | 外观轻微划痕、磕碰 | 外壳划痕、轻微掉漆 |
| `Operational_Error` | 客户操作失误、使用咨询 | 不会操作、设置问题 |
| `Documentation_Missing` | 说明书等文档丢失 | 没有说明书 |
| `Packaging_Damage` | 外包装损坏 | 包装压坏（不影响内部） |

#### Medium 紧急度
| 类别 | 判定依据 | 示例 |
|------|---------|------|
| `Damaged_Part` | 核心部件损坏 | 屏幕破碎、按键失灵 |
| `Functional_Failure` | 功能故障影响使用 | 无法开机、频繁死机 |
| `Batch_Defect` | 疑似批次缺陷 | 同一批次多起故障 |

#### High 紧急度
| 类别 | 判定依据 | 示例 |
|------|---------|------|
| `Hardware_Thermal_Runaway` | 设备过热/冒烟/起火 | 冒烟、烧焦味、火花 |
| `Safety_Hazard` | 漏电/触电 | 漏电、电击 |
| `Explosion_Injury` | 爆炸/严重伤人 | 爆炸、碎片飞溅 |
| `Mass_Complaint_Risk` | 群体性客诉风险/舆情 | 同一批次批量故障、媒体曝光 |

### 2.3 定级与业务影响对照

| urgency_level | business_impact | 对应关系 |
|---------------|----------------|---------|
| low | Normal | 不影响设备核心功能 |
| medium | Production_Stop | 核心故障影响生产/使用 |
| high | Safety_Hazard | 涉及人身财产安全 |

### 2.4 路由分发矩阵

| 紧急度 | routing_decision | 处理者 | 工单可见范围 |
|--------|-----------------|--------|-------------|
| low | `frontline_worker` | 一线客服员工 | 一线员工看板 |
| medium | `manager_dashboard` | 部门经理 | 经理看板 |
| high | `general_manager_dashboard` | 总经理/技术总监 | 总经理看板 |

路由决策与紧急度严格一一对应，无交叉路由。

---

## 三、安全护栏：硬规则优先级覆盖

尽管 LLM Agent 承担主要判断职责，系统设置了**不容逾越的安全硬规则**：

```python
danger_keywords = ["冒烟", "起火", "漏电", "爆炸", "冒火", "烧焦"]
```

**触发逻辑**：上述关键词出现在用户消息或 OCR 识别结果中任一位置 → **无论 LLM 判断结果如何**：
1. `urgency_level` 强制设为 `high`
2. `routing_decision` 强制设为 `general_manager_dashboard`
3. `business_impact` 强制设为 `Safety_Hazard`
4. 自动回复强制替换为紧急安全警示语

**设计原因**：硬件事故涉及人身安全，不允许依赖模型推理的准确性，必须执行最高级别响应。

---

## 四、LLM 智能分级机制

### 4.1 模型配置

- **模型**: Qwen/QwQ-32B (兼容 OpenAI API 格式，可替换为任意同类模型)
- **温度**: 0.2 (低温度确保输出一致性)
- **输出格式**: JSON Object（强制约束）
- **最大 token**: 1024

### 4.2 Prompt 工程设计

系统提示词（`prompt.txt`）包含以下结构化指令：

1. **角色定义**：面向客户的客诉自动回复与出单分发智能体
2. **定级规则**：逐条列出 low/medium/high 的判定标准和业务影响对照
3. **分类规则**：10 个问题类别（Hardware_Thermal_Runaway 等）的定义
4. **路由规则**：紧急度 → 路由目标的映射表
5. **工单格式**：严格 JSON Schema 约束
6. **回复规范**：按紧急度级别差异化要求（high 必须安全提醒优先）

### 4.3 信息抽取字段

| 字段 | 来源 | 说明 |
|------|------|------|
| `order_id` | 用户文本/OCR | 订单号 |
| `model_number` | 用户文本/OCR | 产品型号 |
| `batch_code` | 用户文本/OCR | 批次号 |
| `sn_code` | OCR 优先 > 用户文本 | 设备序列号 |

---

## 五、RAG 知识库增强

### 5.1 检索链路

```
客户问题 → DashScope Embedding 向量化 → ChromaDB 向量检索 → Top-3 SOP 片段
     ↓
注入 LLM 系统上下文 → LLM 基于 SOP 知识生成回复
```

### 5.2 SOP 知识库结构

源文档：`data/sop/sop_document.txt`，按故障场景分为十大类：
- 安全类故障（高紧急度）
- 核心部件损坏（中紧急度）
- 配件/外观问题（低紧急度）
- 软件/固件问题
- 物流与售后
- 群体性/舆情风险事件

### 5.3 前置检索设计

关键优化：在 LLM 调用**之前**执行 RAG 检索，将 SOP 上下文注入 LLM prompt，确保 Agent 的回复基于企业知识库而非模型自身知识。相比"先生成后补充"的传统 RAG 模式，本设计实现了：

- 知识库内容深度融入 Agent 推理过程
- 避免"通用回复 + 话术粘贴"的生硬拼接
- 紧急处置 SOP 直接内嵌于 LLM 回复逻辑

---

## 六、质保核验链路（加分项）

### 6.1 OCR 提取 SN 码

```
图片/视频 → PaddleOCR → 正则匹配（SN/S/N/序列号前缀）→ SN 码
```

### 6.2 质保判定优先级

1. **缓存查询**（TTL 1 小时，防止重复击穿）
2. **远程 ERP 接口**（若配置了 `ERP_API_URL`）
3. **本地模拟降级**（基于 SN 码中的生产日期 + 2 年质保期）

### 6.3 结果写入

质保状态 `warranty_status` 写入工单 JSON，可选值：`In_Warranty` / `Out_of_Warranty` / `Unknown`

---

## 七、工单数据结构

### 7.1 标准 JSON Schema

```json
{
  "ticket_id": "CS-20260602-0001",
  "extracted_data": {
    "order_id": "JD9988776655",
    "model_number": "Pro-Max-V2",
    "batch_code": "X11",
    "sn_code": "SN202501001",
    "evidence_images": ["uploads/abc123.jpg"],
    "ocr_text": "..."
  },
  "agent_business_assessment": {
    "issue_category": "Hardware_Thermal_Runaway",
    "business_impact": "Safety_Hazard",
    "urgency_level": "high",
    "warranty_status": "In_Warranty"
  },
  "routing_decision": "general_manager_dashboard",
  "auto_reply_sent": "您好，已收到您的故障反馈...",
  "status": "未处理",
  "created_at": "2026-06-02T10:30:00"
}
```

### 7.2 工单号生成规则

格式：`CS-YYYYMMDD-NNNN`
- `CS`：固定前缀（Customer Service）
- `YYYYMMDD`：创建日期
- `NNNN`：当日从 `0001` 递增的 4 位序号

使用 SQLite `ticket_sequences` 表 + 原子 UPSERT 保证并发安全。

---

## 八、验收场景映射

### 场景 A：简单配件缺失

**输入**："我收到的产品少了一个螺丝，怎么补发？"

**处理链路**：
1. RAG 检索 → 命中 SOP "2.3.1 配件缺失"
2. LLM 判定 → `issue_category: Missing_Part`, `urgency_level: low`, `business_impact: Normal`
3. 路由 → `frontline_worker`
4. 回复 → 配件补发链接 + 标准流程说明

### 场景 B：设备冒烟（带图片/视频）

**输入**："机器冒黑烟了！" + 图片附件

**处理链路**：
1. OCR 识别图片内容
2. RAG 检索 → 命中 SOP "2.1.1 设备冒烟、起火"
3. LLM 判定 → `issue_category: Hardware_Thermal_Runaway`, `urgency_level: high`
4. 安全硬规则覆盖 → 关键词"冒烟"触发最高优先级
5. 路由 → `general_manager_dashboard`
6. 回复 → 紧急断电指示 + 总监直接联系

---

## 九、故障降级机制

| 故障环节 | 降级策略 | 代码位置 |
|---------|---------|---------|
| LLM 调用失败/超时 | 使用默认工单模板（Low 优先级 + 人工客服兜底） | `chat_router.py` exception handler |
| LLM 返回格式异常 | `_clean_llm_response` 清洗 + Tenacity 重试 3 次 | `llm_client.py` |
| RAG 检索失败 | 跳过 SOP 注入，LLM 基于自身知识回复 | `chat_router.py` search_sop try/except |
| ERP 接口不可用 | 降级为本地 SN 码规则模拟校验 | `warranty.py` `_check_local_warranty` |
| 数据库写入失败 | 记录错误日志，不阻止回复 | `database.py` exception handler |
| 视频 OCR 失败 | 返回空文本，不影响后续流程 | `ocr_utils.py` try/except |
