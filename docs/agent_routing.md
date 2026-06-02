# 大模型 Agent 路由分发与定级逻辑说明文档

> 版本：2.0  
> 适用项目：客诉自动回复与出单分发智能体  
> 最后更新：2026-06-02

---

## 一、系统架构总览

```
客户输入 (文本 / 图片 / 视频)
        │
        ▼
┌──────────────────┐
│  1. 多模态 OCR    │  ← PaddleOCR 提取文字 + SN 码
│     图像预处理     │      灰度 + 高斯降噪 → OCR 识别 → 垃圾清洗
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  2. RAG 前置检索  │  ← ChromaDB + DashScope Embedding
│  SOP 上下文获取   │      用客户原文检索知识库 Top-3 片段
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  3. 产品注册表查询 │  ← 通过 SN/订单号查询产品信息
│     Product DB    │      注入 LLM 上下文
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  4. LLM 推理      │  ← 注入 SOP + 产品信息 → 输出结构化 JSON
│  意图识别 + 定级  │      字段：issue_category / business_impact
│                   │            urgency_level / routing_decision
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  5. 安全硬规则拦截 │  ← 危险关键词强制 High 优先级
│  Safety Override  │      冒烟/起火/漏电/爆炸 → 强制最高级
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  6. ERP 质保校验   │  ← SN 码 → 缓存查询 → 远程 ERP → 本地模拟
│   Warranty Check  │      三级降级：缓存(1h) → ERP API → 本地规则
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  7. 工单生成入库   │  ← SQLite 持久化 + 递增工单号 + 状态管理
│   Ticket Save     │      /history 接口支持按角色/ID 查询
└──────────────────┘
```

---

## 二、紧急度定级规则（核心路由依据）

### 2.1 三级定级矩阵

定级摒弃主观情绪判断，完全基于**客观业务影响**进行硬性定级：

| 紧急度 | 触发条件 | 业务影响 | 路由目标 |
|--------|---------|---------|---------|
| **low** | 无安全风险，不影响基本使用 | Normal | 一线员工 (frontline_worker) |
| **medium** | 影响部分功能，有潜在风险 | Production_Stop | 部门经理 (manager_dashboard) |
| **high** | 涉及人身/财产安全，群体性风险 | Safety_Hazard | 总经理看板 (general_manager_dashboard) |

### 2.2 具体分类规则

#### Low 紧急度
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
| `Mass_Complaint_Risk` | 群体性客诉风险/舆情 | 同一批次批量故障 |

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
4. 自动回复强制在开头插入紧急安全警示语

**设计原因**：硬件事故涉及人身安全，不允许依赖模型推理的准确性，必须执行最高级别响应。

---

## 四、LLM 智能分级机制

### 4.1 模型配置

- **模型**: DeepSeek-V4 / Qwen 等（兼容 OpenAI API 格式，可替换）
- **温度**: 0.5（平衡一致性与创造性）
- **输出格式**: JSON Object（结构化约束）
- **最大 token**: 3072

### 4.2 Prompt 工程设计

系统提示词（`prompt.txt`）包含以下结构化指令：

1. **角色定义**：面向客户的客诉自动回复与出单分发智能体
2. **定级规则**：逐条列出 low/medium/high 的判定标准和业务影响对照
3. **分类规则**：10 个问题类别的定义
4. **路由规则**：紧急度 → 路由目标的映射表
5. **工单格式**：严格 JSON Schema 约束
6. **回复规范**：按紧急度级别差异化要求

### 4.3 降级机制

| 故障环节 | 降级策略 |
|---------|---------|
| LLM 调用失败/超时 | 使用默认工单模板 + 人工客服兜底 |
| LLM 返回格式异常 | 正则提取 JSON + Tenacity 重试 3 次 |
| RAG 检索失败 | 跳过 SOP 注入，LLM 基于自身知识回复 |
| ERP 接口不可用 | 降级为本地 SN 码规则模拟校验 |

---

## 五、SN 码提取流程（加分项 - 质保核验）

### 5.1 提取链路

```
图片/视频 → PaddleOCR → 置信度过滤(>=0.6) → 垃圾清洗 → 正则提取 SN 码
                                                              │
                 ┌────────────────────────────────────────────┤
                 ▼                                            ▼
          产品注册表查询                                  质保期核验
          (product_lookup.py)                           (warranty.py)
                 │                                            │
                 ▼                                            ▼
         产品信息注入 LLM                               TTL 缓存(1h)
         上下文辅助回复                                 → ERP API
                                                      → 本地规则模拟
```

### 5.2 SN 码提取正则

```python
# 前缀匹配（优先）：SN:xxx、S/N xxx、序列号：xxx、出厂编号 xxx
prefix_pattern = r'(?:SN|S/N|序列号|出厂编号)[:\s\-]*([A-Za-z0-9]{9,20})'

# 兜底匹配（无前缀）：独立的 9-20 位字母+数字混合
fallback_pattern = r'\b(?=.*[A-Z])(?=.*[0-9])[A-Z0-9]{9,20}\b'
```

**设计要点**：
- 最小长度 9 位：避免将 8 位订单号（如 `JD123456`）误识别为 SN
- 双重前缀剥离：`S/N:SN202501001` → 提取 `202501001`
- OCR 识别的 SN 码优先级高于 LLM 从文本推断的结果

### 5.3 质保核验优先级

1. **TTL 缓存查询**（1 小时有效期，防止重复击穿）
2. **远程 ERP 接口**（若配置了 `ERP_API_URL`）
3. **本地模拟降级**（基于 SN 码中的生产日期 + 2 年质保期）

---

## 六、RAG 知识库增强

### 6.1 检索链路

```
客户问题 → DashScope Embedding 向量化 → ChromaDB 向量检索 → Top-3 SOP 片段
     ↓
注入 LLM 系统上下文 → LLM 基于 SOP 知识生成回复
```

### 6.2 SOP 知识库结构

源文档：`backend/data/sop/sop_document.txt`，按故障场景分为十大类：
- 安全类故障（高紧急度）
- 核心部件损坏（中紧急度）
- 配件/外观问题（低紧急度）
- 软件/固件问题
- 物流与售后
- 群体性/舆情风险事件

### 6.3 前置检索设计

关键优化：在 LLM 调用**之前**执行 RAG 检索，将 SOP 上下文注入 LLM prompt，确保 Agent 的回复基于企业知识库而非模型自身知识。

---

## 七、工单数据结构

### 7.1 标准 JSON Schema

```json
{
  "ticket_id": "CS-20260602-0001",
  "created_at": "2026-06-02T10:30:00",
  "extracted_data": {
    "order_id": "JD9988776655",
    "model_number": "Pro-Max-V2",
    "batch_code": "BATCH-A01",
    "sn_code": "202501001",
    "evidence_images": ["uploads/abc123.jpg"],
    "ocr_text": "SN:202501001 空调冒烟"
  },
  "agent_business_assessment": {
    "issue_category": "Hardware_Thermal_Runaway",
    "business_impact": "Safety_Hazard",
    "urgency_level": "high",
    "warranty_status": "In_Warranty"
  },
  "routing_decision": "general_manager_dashboard",
  "auto_reply_sent": "【紧急安全警告】请立即切断设备电源...",
  "status": "未处理"
}
```

### 7.2 工单号生成规则

格式：`CS-YYYYMMDD-NNNN`
- `CS`：固定前缀（Customer Service）
- `YYYYMMDD`：创建日期
- `NNNN`：当日从 0001 递增的 4 位序号

使用 SQLite `ticket_sequences` 表 + 原子 UPSERT 保证线程安全。

---

## 八、验收场景映射

### 场景 A：简单配件缺失

**输入**："我收到的产品少了一个螺丝，怎么补发？"

**预期处理链路**：
1. RAG 检索 → 命中 SOP "配件缺失"
2. LLM 判定 → `issue_category: Missing_Part`, `urgency_level: low`, `business_impact: Normal`
3. 路由 → `frontline_worker`
4. 回复 → 配件补发链接 + 标准流程说明

### 场景 B：设备冒烟（带图片/视频）

**输入**："机器冒黑烟了！" + 图片附件

**预期处理链路**：
1. OCR 识别图片内容 → 提取 SN 码
2. RAG 检索 → 命中 SOP "设备冒烟、起火"
3. LLM 判定 → `issue_category: Hardware_Thermal_Runaway`, `urgency_level: high`
4. 安全硬规则覆盖 → 关键词"冒烟"触发最高优先级
5. 路由 → `general_manager_dashboard`
6. 回复 → 紧急断电指示 + 总监直接联系

---

## 九、前端界面说明

| 界面 | 入口 | 功能 |
|------|------|------|
| 欢迎页 | `frontend/welcome.html` | 系统入口，导航至各端 |
| 用户端 (PC) | `frontend/user.html` | 聊天式客诉提交、工单追踪、文件上传 |
| 管理端 | `frontend/admin.html` | 工单看板、角色过滤、状态管理 |
| 移动端 H5 | `frontend/mobile.html` | 手机端客诉提交与进度查询（加分项） |

---

## 十、测试数据说明

系统内置了 10 条测试工单和 11 条产品注册记录（`backend/seed_data.py`），覆盖：
- 三种紧急度级别（low/medium/high）
- 三种路由目标
- 质保在保/过保/未知三种状态
- 含图片/视频附件场景
- SN 码格式异常场景

运行 `python seed_data.py` 即可初始化测试数据。
