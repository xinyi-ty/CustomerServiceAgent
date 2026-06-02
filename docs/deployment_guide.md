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
| Python | 3.10 - 3.12 | 推荐 3.11 |
| Git | 最新稳定版 | 用于版本管理（可选） |
| 浏览器 | Chrome 90+ / Edge 90+ | 前端界面访问 |

---

## 二、项目结构

```
CustomerServiceAgent/
├── backend/                 # 后端服务（FastAPI）
│   ├── main.py              # 应用入口 + API 路由
│   ├── chat_router.py       # 核心客诉处理接口
│   ├── llm_client.py        # LLM 大模型调用客户端
│   ├── rag_simple.py        # RAG 检索增强生成模块
│   ├── ocr_utils.py         # 多模态 OCR 处理（图片/视频）
│   ├── warranty.py          # 质保期校验模块（ERP + 本地模拟）
│   ├── database.py          # SQLite 数据库操作
│   ├── models.py            # Pydantic 数据模型定义
│   ├── config.py            # 全局配置模块
│   ├── prompt.txt           # LLM 系统提示词
│   ├── mock_erp_server.py   # 模拟 ERP 服务器（仅开发调试用）
│   ├── data/
│   │   ├── sop/
│   │   │   └── sop_document.txt   # SOP 知识库文档
│   │   └── tickets.db              # SQLite 数据库（运行时生成）
│   ├── uploads/             # 上传文件存储目录（运行时生成）
│   ├── chroma_db/           # ChromaDB 向量数据库（运行时生成）
│   └── .env                 # 环境变量配置文件
├── frontend/                # 前端界面
│   ├── welcome.html         # 欢迎页/入口
│   ├── user.html            # 客户端聊天页面
│   ├── user.js              # 客户端逻辑
│   ├── mobile.html          # 移动端 H5 页面（加分项）
│   ├── mobile.js            # 移动端逻辑
│   ├── admin.html           # 管理者看板
│   └── admin.js             # 管理者看板逻辑
├── docs/                    # 文档目录
│   ├── agent_routing.md     # Agent 路由分发与定级逻辑说明
│   └── deployment_guide.md  # 本文件（部署手册）
├── requirements.txt         # Python 依赖清单
└── .gitignore               # Git 忽略配置
```

---

## 三、部署步骤

### 3.1 克隆 / 获取代码

```bash
# 如果使用 Git
git clone <仓库地址>
cd CustomerServiceAgent

# 或者直接解压源码包
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
pip install -r requirements.txt
```

> **注意**：PaddleOCR + PaddlePaddle 安装包较大（约 200MB），首次安装可能需要较长时间。  
> 如果不需要 OCR 功能，可移除此两项依赖，系统仍可处理纯文本客诉。

### 3.4 配置文件

复制环境变量模板并填写：

```bash
# backend/.env 文件内容
ENV=development

# ========== 阿里云千问 API（用于 Embedding / RAG 向量检索）==========
DASHSCOPE_API_KEY=your_dashscope_api_key_here

# ========== 大模型 API（用于对话生成）==========
# 支持任何兼容 OpenAI API 格式的服务（Qwen、DeepSeek、GLM 等）
LLM_API_KEY=your_llm_api_key_here
LLM_BASE_URL=https://your-llm-service.com/v1
LLM_MODEL_NAME=your-model-name

# ========== 数据库与存储 ==========
DATABASE_PATH=./data/tickets.db
UPLOAD_DIR=./uploads

# ========== ERP 系统配置（可选，用于质保核验）==========
# 留空则降级为本地 SN 码规则模拟
ERP_API_URL=http://127.0.0.1:8001
ERP_API_KEY=mock_secret_token_123

# ========== 服务配置 ==========
HOST=0.0.0.0
PORT=8000
```

#### API 密钥获取指南

| 服务 | 用途 | 获取方式 |
|------|------|---------|
| DashScope API Key | SOP 知识库向量化（Embedding） | [阿里云百炼控制台](https://bailian.console.aliyun.com/) |
| LLM API Key | 客诉分析与回复生成 | [通义千问](https://tongyi.aliyun.com/) / [DeepSeek](https://platform.deepseek.com/) 等 |

### 3.5 准备 SOP 知识库

将企业 SOP 文档以 UTF-8 编码的 `.txt` 格式放入 `backend/data/sop/` 目录。

系统已内置示例 SOP 文档 `sop_document.txt`，包含完整的十大类故障处置细则。**可替换为真实企业 SOP**。

SOP 文件格式要求：
- UTF-8 编码
- `.txt` 后缀
- 建议按章节组织，系统会自动分块索引

### 3.6 启动服务

#### 启动主服务

```bash
cd backend
python main.py
```

服务默认运行在 `http://localhost:8000`

查看启动日志确认：
```
[INFO] 数据库初始化完成 (含 WAL 模式、ticket_sequences 序列表、status 列及索引)
[INFO] RAG 向量库已就绪，共 N 个片段
[INFO] AI 售后主服务启动完成
```

#### 启动 Mock ERP 服务器（可选）

```bash
# 另开一个终端
cd backend
python mock_erp_server.py
```

Mock ERP 运行在 `http://127.0.0.1:8001`

> 仅在 .env 中配置了 `ERP_API_URL=http://127.0.0.1:8001` 时使用。
> 未配置则自动降级为本地 SN 码规则模拟。

### 3.7 访问前端

| 页面 | 地址 | 说明 |
|------|------|------|
| 欢迎页 | `frontend/welcome.html` | 系统入口，可跳转用户端和管理端 |
| 用户端 | `frontend/user.html` | 客户提交客诉的主界面 |
| 管理端 | `frontend/admin.html` | 工单看板（按角色过滤） |
| 移动端 | `frontend/mobile.html` | 移动端 H5 页面 |

> 前端页面通过 HTTP 协议访问后端 API，需确保 `http://localhost:8000` 可访问。
> 可直接在浏览器中打开 HTML 文件，或用任意 HTTP 服务器托管。

---

## 四、运行验证

### 4.1 健康检查

```bash
curl http://localhost:8000/health
```

预期响应：
```json
{"status": "ok", "rag_available": true}
```

### 4.2 验收场景测试

#### 场景 A：简单配件缺失（低紧急度）

```bash
curl -X POST http://localhost:8000/chat \
  -F "message=我收到的产品少了一个螺丝，怎么补发？"
```

预期行为：
- `urgency_level`: `low`
- `routing_decision`: `frontline_worker`
- 回复包含补发链接指引

#### 场景 B：设备冒烟（高紧急度）

```bash
curl -X POST http://localhost:8000/chat \
  -F "message=机器后面冒黑烟了，很烫！"
```

预期行为：
- `urgency_level`: `high`
- `routing_decision`: `general_manager_dashboard`
- 回复以安全提醒（切断电源）开头

### 4.3 查看工单管理端

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
| `LLM_BASE_URL` | — | 见 config.py | 大模型服务地址 |
| `LLM_MODEL_NAME` | — | 见 config.py | 大模型名称 |
| `DASHSCOPE_API_KEY` | ✅ | — | RAG 向量化 API 密钥 |
| `HOST` | — | 0.0.0.0 | 服务监听地址 |
| `PORT` | — | 8000 | 服务监听端口 |
| `DATABASE_PATH` | — | ./data/tickets.db | 数据库路径 |
| `UPLOAD_DIR` | — | ./uploads | 上传目录 |
| `ERP_API_URL` | — | — | ERP 接口地址（可选） |
| `ERP_API_KEY` | — | — | ERP 接口密钥（可选） |

### 5.2 更换大模型

系统支持任何兼容 OpenAI API 格式的大模型服务。只需在 `.env` 中修改：

```ini
LLM_BASE_URL=https://api.another-service.com/v1
LLM_MODEL_NAME=model-name
```

支持的服务包括但不限于：
- 通义千问 (Qwen)
- DeepSeek
- Kimi
- 智谱 GLM
- OpenAI GPT（需海外网络）

### 5.3 更换 OCR 引擎

`ocr_utils.py` 当前使用 PaddleOCR，可替换为：
- EasyOCR（更轻量）
- 云 API（如阿里云文字识别）
- Tesseract OCR

---

## 六、故障排除

### 6.1 启动失败

| 错误信息 | 可能原因 | 解决方案 |
|---------|---------|---------|
| "LLM_API_KEY 未设置" | .env 文件缺失或未配置 | 创建 .env 文件并填入 API Key |
| "DASHSCOPE_API_KEY 未设置" | RAG 密钥未配置 | 同上 |
| "ImportError: No module named 'paddleocr'" | OCR 依赖未安装 | `pip install paddlepaddle paddleocr` |
| "Address already in use" | 端口被占用 | 修改 .env 中 PORT 为其他值 |

### 6.2 运行时问题

| 问题 | 可能原因 | 解决方案 |
|------|---------|---------|
| LLM 返回空结果 | API Key 失效 / 模型不可用 | 检查 API Key 额度，更换模型 |
| RAG 索引为空 | SOP 文件缺失 | 确认 `data/sop/` 目录下有 `.txt` 文件 |
| 图片 OCR 失败 | PaddlePaddle 未正确安装 | `pip install paddlepaddle -i https://mirror.baidu.com/pypi/simple` |
| 视频 OCR 未安装 | opencv-python 缺失 | `pip install opencv-python` |
| 数据库写入报错 | 路径无写入权限 | 检查 `data/` 目录权限 |

### 6.3 日志查看

系统使用 Python `logging` 模块输出标准日志，在服务终端可见。日志级别：

```
启动时：INFO 级别显示配置状态
运行时：ERROR 级别显示故障信息
调试时：将 config.py 中日志级别改为 DEBUG
```

---

## 七、重新构建 RAG 索引

如果更新了 SOP 知识库文件，需要重新构建向量索引：

```python
# 方式 1：服务启动时自动检测（向量库为空时自动构建）
# 启动 main.py 即可

# 方式 2：手动调用
python -c "
from rag_simple import build_index
build_index(force_rebuild=True)
"
```

> 注意：`force_rebuild=True` 会清空并重建索引。生产环境中建议仅在 SOP 更新时执行。

---

## 八、附录

### 8.1 依赖清单

核心依赖及用途：

| 包名 | 用途 |
|------|------|
| `fastapi` | Web 框架 |
| `openai` | LLM API 客户端 |
| `chromadb` | 向量数据库 |
| `dashscope` | 阿里云 Embedding API |
| `paddleocr` | 图片/视频文字识别 |
| `paddlepaddle` | PaddleOCR 深度学习框架 |
| `opencv-python` | 视频帧提取与图像预处理 |
| `httpx` | ERP 异步 HTTP 客户端 |
| `tenacity` | API 调用重试机制 |
| `pydantic` | 数据模型校验 |
| `python-dateutil` | 质保期日期计算 |
| `uvicorn` | ASGI 服务器 |

### 8.2 端口清单

| 端口 | 服务 | 说明 |
|------|------|------|
| 8000 | 主服务 | FastAPI 客诉处理 API |
| 8001 | Mock ERP | 模拟质保核验接口 |

---
