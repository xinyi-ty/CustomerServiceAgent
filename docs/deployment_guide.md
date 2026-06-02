# 本地化部署手册

> 项目名称：客诉自动回复与出单分发智能体  
> 适用平台：Windows 桌面端  
> 最后更新：2026-06-02

---

## 一、环境要求

### 1.1 硬件要求

| 项目 | 最低配置 | 推荐配置 |
|------|---------|---------|
| CPU | 4 核 | 8 核及以上 |
| 内存 | 8 GB | 16 GB |
| 磁盘 | 10 GB 可用空间 | 20 GB SSD |
| GPU（可选）| — | NVIDIA GPU 4GB+（加速 PaddleOCR） |
| 操作系统 | Windows 10/11 | Windows 11 |

### 1.2 软件依赖

| 软件 | 版本要求 | 说明 |
|------|---------|------|
| Python | 3.10 - 3.13 | 推荐 3.11 |
| 浏览器 | Chrome 90+ / Edge 90+ | 前端界面访问 |

---

## 二、项目结构

```
CustomerServiceAgent/
├── backend/                              # 后端服务（FastAPI）
│   ├── main.py                           # 应用入口 + API 路由
│   ├── chat_router.py                    # 核心客诉处理接口
│   ├── config.py                         # 全局配置模块
│   ├── models.py                         # Pydantic 数据模型
│   ├── database.py                       # SQLite 数据库操作
│   ├── llm_client.py                     # LLM 大模型调用
│   ├── prompt.txt                        # LLM 系统提示词
│   ├── rag_simple.py                     # RAG 检索增强生成
│   ├── ocr_utils.py                      # 多模态 OCR（图片/视频）
│   ├── product_lookup.py                 # 产品注册表查询
│   ├── warranty.py                       # 质保期校验
│   ├── seed_data.py                      # 种子数据脚本
│   ├── mock_erp_server.py                # 模拟 ERP 服务器
│   ├── requirements.txt                  # Python 依赖清单
│   ├── .env.example                      # 环境变量模板（复制为 .env 使用）
│   └── data/                             # 数据目录
│       ├── sop/sop_document.txt          #  SOP 知识库文档
│       └── products.json                 #  产品注册表
├── frontend/                             # 前端界面
│   ├── welcome.html                      #  欢迎页
│   ├── user.html + user.js               #  PC 用户端（聊天）
│   ├── admin.html + admin.js             #  管理端（工单看板）
│   ├── mobile.html + mobile.js           #  移动端 H5 页面
│   └── style.css                         #  全局样式
├── docs/                                 # 文档
│   ├── agent_routing.md                  #  Agent 路由定级说明
│   └── deployment_guide.md               #  本文件（部署手册）
├── 赛事要求.docx                         # 比赛需求文档
└── .gitignore
```

---

## 三、部署步骤（文件用的是cmd）

### 3.1 获取代码

```bash
# 直接使用源码目录（或解压压缩包）
cd CustomerServiceAgent
```

### 3.2 创建虚拟环境

```bash
# Windows 系统
python -m venv venv
venv\Scripts\activate
```

### 3.3 安装依赖

```bash
cd backend
pip install -r requirements.txt 
```

> **注意**：PaddlePaddle + PaddleOCR 安装包较大（约 200MB）。如果安装缓慢，可使用清华镜像：
>
> ```bash
> pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
> ```

### 3.4 配置环境变量

复制环境变量模板并填写：

```bash
cd backend
cp .env.example .env
```

编辑 `backend\.env`，填入以下必填项：

| 变量 | 说明 | 获取方式 |
|------|------|---------|
| `LLM_API_KEY` | 大模型 API 密钥 | [DeepSeek](https://platform.deepseek.com/) / [阿里云百炼](https://bailian.console.aliyun.com/) |
| `DASHSCOPE_API_KEY` | RAG 向量化密钥 | [阿里云百炼控制台](https://bailian.console.aliyun.com/) |

#### ERP 系统配置说明（可选）

ERP 配置用于质保核验（加分项），**不配置不影响核心功能**，系统会自动降级为本地 SN 码规则模拟：

| 模式 | 配置方式 | 效果 |
|:----|:---------|:-----|
| **本地模拟（默认）** | `ERP_API_URL=` 留空 | 基于 SN 码中的生产日期 + 2 年质保期本地计算 |
| **Mock 测试** | `ERP_API_URL=http://127.0.0.1:8001`<br>`ERP_API_KEY=mock_secret_token_123` | 运行 `mock_erp_server.py` 即可本地调试 ERP 对接 |
| **真实 ERP** | 填写实际 ERP 接口地址和密钥 | 对接企业真实质保系统 |

### 3.5 准备 SOP 知识库

系统已内置示例 SOP 文档 `backend/data/sop/sop_document.txt`，包含完整的十大类故障处置细则。可替换为真实企业 SOP。

### 3.6 初始化数据库与种子数据（可选）

首次运行建议执行种子数据脚本来初始化数据库并写入测试数据：

```bash
cd backend
python seed_data.py
```

> **注意**：种子数据脚本仅在首次运行或数据库重置后需要执行。主服务 `main.py` 启动时也会自动初始化数据库表结构，但不写入种子数据。

### 3.7 启动服务

> **前置条件**：首次启动前请确认已完成以下步骤：
> - ✅ 虚拟环境已激活（`venv\Scripts\activate`）
> - ✅ 依赖已安装（`pip install -r requirements.txt`）
> - ✅ `.env` 文件已从 `.env.example` 复制并填入正确的 API 密钥
> - ✅ 当前目录为 `backend\`

#### 启动主服务

```bash
cd backend
python main.py
```

服务默认运行在 `http://localhost:8000`

#### 启动 Mock ERP 服务器（可选，调试质保核验用）

Mock ERP 是一个模拟的企业质保查询接口，用于本地验证质保核验流程（加分项）。

> **前置条件**：主服务 `main.py` 需已启动且正常运行。Mock ERP 独立运行在 8001 端口，与主服务不冲突。

启动方式：

```bash
# 另开一个终端
cd backend
python mock_erp_server.py
```

Mock ERP 运行在 `http://127.0.0.1:8001`

然后在 `.env` 中配置：
```ini
ERP_API_URL=http://127.0.0.1:8001
ERP_API_KEY=mock_secret_token_123
```

Mock 服务器支持以下测试场景：

| SN 码 | 模拟行为 | 用途 |
|-------|---------|------|
| `SN202501001` | 返回在保状态 | 验证正常在保流程 |
| `SN202005002` | 返回已过保状态 | 验证过保处理流程 |
| `SN999999999` | 返回 404 查无此机 | 验证 SN 不存在时的容错 |
| `SN_TIMEOUT` | 延迟 6 秒响应 | 验证超时降级机制 |
| `SN_ERROR` | 返回 500 错误 | 验证 ERP 崩溃降级 |

> **不配置 ERP 也没关系**，系统自动降级为本地 SN 码规则模拟：从 SN 码中提取生产年份和月份，按 2 年质保期计算是否在保。质保核验的加分项功能完整，评审不会因为未连接真实 ERP 扣分。

### 3.8 访问前端

> **前置条件**：主服务 `main.py` 需已启动运行中，否则前端无法加载工单数据和提交客诉。
>
> 所有前端页面通过浏览器直接打开 `.html` 文件即可运行（`file://` 协议），页面通过 HTTP 请求调用后端 `http://localhost:8000` API，需允许跨域。

| 页面 | 地址 | 说明 |
|------|------|------|
| 欢迎页 | `frontend/welcome.html` | 系统入口，可跳转至用户端、管理端、移动端 |
| 用户端 (PC) | `frontend/user.html` | 客户提交客诉的主界面，聊天式交互。支持文字输入、图片/视频上传。提交后 AI 实时回复，含思考过程折叠、工单创建徽章（显示工单号/紧急度/质保状态/识别到的SN码）。侧边栏可查询历史工单 |
| 管理端 | `frontend/admin.html` | 工单管理看板，顶部统计总工单/未处理/紧急/已处理数量。可按角色过滤（一线员工=low、部门经理=medium、总经理=high），支持工单号/订单号/SN码搜索。点击工单可展开查看详情（提取数据、Agent评估、自动回复），并支持标记已处理 |
| 移动端 H5 | `frontend/mobile.html` | 手机端客诉提交与进度查询（加分项）。功能与 PC 用户端一致，底部两个 Tab：「智能对话」用于提交客诉，「工单查询」用于查看历史工单。**工单列表默认仅显示 low 紧急度前台工单**（客户不应看到管理者工单），但通过工单号精确搜索可查到任意紧急度的工单 |

---

## 四、运行验证

### 4.1 健康检查

```bash
curl http://localhost:8000/health
```
>需保证main.py已启动

预期响应：
```json
{"status": "ok", "rag_available": true}
```

### 4.2 验收场景测试(也可通过前端界面测试)

#### 场景 A：简单配件缺失（低紧急度）

```bash
curl -X POST http://localhost:8000/chat ^
  -F "message=我收到的产品少了一个螺丝，怎么补发？"
```

预期行为：
- `urgency_level`: `low`
- `routing_decision`: `frontline_worker`
- 回复包含补发链接指引

#### 场景 B：设备冒烟（高紧急度）

```bash
curl -X POST http://localhost:8000/chat ^
  -F "message=机器后面冒黑烟了，很烫！"
```

预期行为：
- `urgency_level`: `high`
- `routing_decision`: `general_manager_dashboard`
- 回复以安全提醒（切断电源）开头

#### 场景 C：上传图片识别 SN 码

```bash
curl -X POST http://localhost:8000/chat ^
  -F "message=帮我看下这个SN码" ^
  -F "image=@图片路径.jpg"
```

> **注意**：`-F "image=@文件路径"` 中的 `@` 不可省略，文件路径请替换为实际图片的绝对路径。

预期行为：
- `sn_code`: 返回识别的序列号（如 `202509888`）
- `ocr_text`: 返回 OCR 识别的原始文本
- `warranty_status`: 质保状态（In_Warranty / Out_of_Warranty）

### 4.3 查看工单管理端

> **前置条件**：主服务 `main.py` 需已启动，且已通过种子数据或实际客诉提交生成过工单。

打开 `frontend/admin.html`，可按角色过滤工单：
- **一线员工**：仅显示 low 紧急度工单
- **部门经理**：仅显示 medium 紧急度工单
- **总经理**：仅显示 high 紧急度工单

---

## 五、配置说明

### 5.1 环境变量

| 变量名 | 必需 | 默认值 | 说明 |
|--------|------|--------|------|
| `LLM_API_KEY` | ✅ | — | 大模型 API 密钥 |
| `LLM_BASE_URL` | — | `https://api.deepseek.com/v1` | 大模型服务地址 |
| `LLM_MODEL_NAME` | — | `deepseek-chat` | 大模型名称 |
| `DASHSCOPE_API_KEY` | ✅ | — | RAG 向量化 API 密钥（阿里云百炼） |
| `HOST` | — | `0.0.0.0` | 服务监听地址 |
| `PORT` | — | `8000` | 服务监听端口 |
| `DATABASE_PATH` | — | `./data/tickets.db` | 数据库路径 |
| `UPLOAD_DIR` | — | `./uploads` | 上传目录 |
| `ERP_API_URL` | — | — | ERP 接口地址（可选） |
| `ERP_API_KEY` | — | — | ERP 接口密钥（可选） |

### 5.2 更换大模型

系统支持任何兼容 OpenAI API 格式的大模型服务。只需在 `.env` 中修改：

```ini
LLM_BASE_URL=https://api.another-service.com/v1
LLM_MODEL_NAME=model-name
```

支持的模型包括：DeepSeek、Qwen（通义千问）、GLM（智谱）、Kimi 等。

### 5.3 更换 OCR 引擎

当前默认使用 PaddleOCR，可替换为 EasyOCR、阿里云文字识别 API 等轻量方案。

---

## 六、重新构建 RAG 索引

更新了 SOP 知识库后，需要重新构建向量索引：

```bash
python -c "from rag_simple import build_index; build_index(force_rebuild=True)"
```

> 注意：`force_rebuild=True` 会清空并重建索引。

---

## 七、故障排除

| 错误 | 原因 | 解决 |
|------|------|------|
| "LLM_API_KEY 未设置" | `.env` 缺失或未配置 | 复制 `.env.example` 为 `.env` 并填入密钥 |
| OCR 识别为空 | PaddleOCR 模型未下载 | 首次运行会自动下载（需联网），约 5-10 分钟 |
| 端口被占用 | 8000 端口已被使用 | 修改 `.env` 中 `PORT` 为其他值 |
| 数据库写入报错 | 路径无写入权限 | 检查 `data/` 目录权限 |

---

## 八、端口清单

| 端口 | 服务 | 说明 |
|------|------|------|
| 8000 | 主服务 | FastAPI 客诉处理 API |
| 8001 | Mock ERP | 模拟质保核验接口（可选） |
