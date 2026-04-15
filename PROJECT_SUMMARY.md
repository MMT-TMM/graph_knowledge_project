# graph_konwledge_project 项目总结

## 1. 项目定位

本项目是一个基于 `Vue + FastAPI + LangGraph` 的文化遗产知识图谱系统，支持多源异构输入（文本、图片、PDF），完成三元组抽取、知识图谱可视化、图谱管理与图谱问答。

---

## 2. 技术框架

### 2.1 前端框架

- `Vue 3`（组合式 API）
- `Vite`（构建与开发服务器）
- `Axios`（HTTP 请求）
- `ECharts`（知识图谱渲染）

### 2.2 后端框架

- `FastAPI`（REST API 服务）
- `LangGraph`（抽取流程编排）
- `LangChain + ChatOpenAI`（模型调用）

### 2.3 文档解析与预处理

- `pypdf`：PDF 文本提取
- `pytesseract + Pillow`：图片 OCR
- 视觉模型回退：OCR 失败时可用多模态模型提取图片文本

---

## 3. 项目目录结构

```text
graph_konwledge_project/
├─ backend/
│  ├─ app/
│  │  ├─ graph/
│  │  │  ├─ prompts.py
│  │  │  ├─ extractors.py
│  │  │  ├─ validators.py
│  │  │  └─ workflow.py
│  │  ├─ services/
│  │  │  ├─ ingestion.py
│  │  │  ├─ graph_store.py
│  │  │  └─ qa.py
│  │  ├─ schemas.py
│  │  └─ main.py
│  └─ tests/
│     └─ test_workflow.py
├─ frontend/
│  ├─ src/
│  │  ├─ App.vue
│  │  ├─ main.js
│  │  └─ styles.css
│  ├─ package.json
│  └─ vite.config.js
├─ output/
└─ README.md
```

---

## 4. 核心流程设计

### 4.1 图谱构建流程（LangGraph）

`ingest -> normalize -> extract -> validate -> save`

1. `ingest`：接收文本、多个图片、多个 PDF，并抽取可用文本。
2. `normalize`：合并多源文本为统一上下文。
3. `extract`：优先使用 LLM 抽取实体关系；失败时回退规则抽取。
4. `validate`：本体约束校验（实体/关系类型白名单 + 关系约束校正）。
5. `save`：输出标准 JSON 到 `output/`，并写入图谱元数据（构建模型、base_url、提示词等）。

### 4.2 图谱问答流程

1. 前端选择某个已构建图谱并提问。
2. 后端读取图谱 JSON 与三元组上下文。
3. 问答优先使用该图谱构建时记录的模型（`__meta.model_name`）。
4. 有 API Key 时走 LLM 问答，无 API Key 走规则问答回退。
5. 返回答案、证据片段、实际使用模型（`used_model`）。

---

## 5. 使用到的主要工具

### 5.1 开发与运行工具

- Python 3.12+
- Node.js 24+
- npm 11+
- Uvicorn（FastAPI 启动）

### 5.2 后端依赖（核心）

- fastapi
- langgraph
- langchain
- langchain-openai
- pydantic
- python-multipart
- pypdf
- pillow
- pytesseract

### 5.3 前端依赖（核心）

- vue
- vite
- axios
- echarts

---

## 6. 功能实现清单

### 6.1 图谱构建

- 支持文本、图片、PDF 混合输入。
- 支持多图片并存上传。
- 支持多 PDF 上传。
- 可自定义模型名、API Key、Base URL。
- 可自定义抽取提示词（覆盖默认抽取提示词）。

### 6.2 图谱管理

- 左侧 `图谱` 标签页可新建图谱工作区。
- 可查看本地图谱列表和服务器图谱列表。
- 可导入历史图谱并加载详情。
- 显示实体数、三元组数、图谱构建状态。

### 6.3 图谱可视化与下载

- 右侧渲染知识图谱（ECharts force graph）。
- 支持在线预览。
- 支持下载图谱 PNG。
- 支持下载 JSON。

### 6.4 文件预览

- 预览区域在左侧上传模块内。
- 仅当已上传图片/PDF时显示对应预览区。
- 未上传时不显示对应预览模块。

### 6.5 图谱问答

- 左侧 `问答` 标签页提供对话框。
- 基于当前选中图谱问答。
- 问答优先使用图谱构建模型。
- 返回证据与答案，支持规则回退。

### 6.6 API 模块

- 保留模型/API Key/Base URL 配置。
- 增加抽取自定义提示词。
- 增加问答补充提示词。

---

## 7. 后端 API 概览

- `GET /api/health`：健康检查
- `POST /api/extract`：构建图谱（支持多文件上传）
- `GET /api/graphs`：图谱列表
- `GET /api/graphs/{graph_id}`：图谱详情
- `POST /api/qa`：图谱问答

---

## 8. 本体约束（抽取规则）

### 实体类型

- ArchitecturalComponent
- Material
- Defect
- Event
- Dynasty

### 关系类型

- hasDefect
- hasMaterial
- occurredAt
- affected
- causedBy

系统在 `validate` 阶段会对非法类型进行过滤/修正，并生成标准化三元组。

---

## 9. 运行方式

### 后端

```bash
cd backend
python -m pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 前端

```bash
cd frontend
npm install
npm run dev
```

访问地址：`http://127.0.0.1:5173`

---

## 10. 当前项目特点总结

- 从“多源数据抽取”到“图谱问答”形成闭环。
- LangGraph 流程清晰，可扩展到更多文档类型或领域本体。
- 前端采用模块化交互（图谱/上传/问答/API）便于后续迭代。
- 在无模型或模型失败场景下提供规则回退，提高可用性与鲁棒性。
