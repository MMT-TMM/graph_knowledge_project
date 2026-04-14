# graph_konwledge_project

基于 `Vue + FastAPI + LangGraph` 的文化遗产多源异构数据知识图谱构建系统。

## 1. 优化后的实现流程

1. 数据接入：接收文本、图片、PDF 三类输入。
2. 模态归一化：PDF 抽取文本；图片优先 OCR，失败时可用视觉模型补充。
3. LangGraph 编排：`ingest -> normalize -> extract -> validate -> save`。
4. 抽取策略：优先 LLM（可自定义模型与 API Key），失败或未配置时回退规则抽取。
5. 本体约束校验：严格限制实体/关系类型，纠正或过滤非法项，输出标准三元组。
6. 结果交付：
   - 后端将 JSON 写入 `output/`
   - 前端将知识图谱可视化并支持在线下载图谱图片与 JSON

## 2. 目录结构

```text
graph_konwledge_project/
├─ backend/
│  ├─ app/
│  │  ├─ graph/
│  │  │  ├─ extractors.py
│  │  │  ├─ prompts.py
│  │  │  ├─ validators.py
│  │  │  └─ workflow.py
│  │  ├─ services/
│  │  │  └─ ingestion.py
│  │  ├─ main.py
│  │  └─ schemas.py
│  ├─ tests/
│  │  └─ test_workflow.py
│  └─ requirements.txt
├─ frontend/
│  ├─ src/
│  │  ├─ App.vue
│  │  ├─ main.js
│  │  └─ styles.css
│  ├─ index.html
│  ├─ package.json
│  └─ vite.config.js
└─ output/
```

## 3. 启动方式

### 3.1 后端

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 3.2 前端

```bash
cd frontend
npm install
npm run dev
```

浏览器访问：`http://127.0.0.1:5173`

## 4. 接口说明

`POST /api/extract`，`multipart/form-data` 参数：

- `text`：文本（可选）
- `image_file`：图片（可选）
- `pdf_file`：PDF（可选）
- `model_name`：模型名（可选，默认 `gpt-4.1-mini`）
- `api_key`：模型 API Key（可选）
- `base_url`：兼容网关地址（可选）

返回：实体、关系、三元组、警告信息及 `output/` 下 JSON 保存路径。
