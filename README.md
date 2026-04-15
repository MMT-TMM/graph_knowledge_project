# graph_konwledge_project

基于 `Vue + FastAPI + LangGraph` 的文化遗产多源异构数据知识图谱与问答系统。

## 功能概览

1. 多源异构抽取：文本、图片、PDF 同时输入。
2. 多文件支持：可一次上传多张图片和多个 PDF。
3. 图谱管理：左侧图谱列表支持新建、选择、查看已构建图谱。
4. 图谱问答：基于已构建图谱进行问答（LLM 或规则模式）。
5. API 可配置：自定义模型、API Key、Base URL，支持自定义抽取提示词。
6. 可视化与下载：右侧知识图谱预览，支持下载 PNG 和 JSON。

## 目录结构

```text
graph_konwledge_project/
├─ backend/
├─ frontend/
└─ output/
```

## 启动

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

访问：`http://127.0.0.1:5173`

## 关键接口

- `POST /api/extract`：构建图谱（支持多文件上传）
- `GET /api/graphs`：获取图谱列表
- `GET /api/graphs/{graph_id}`：获取图谱详情
- `POST /api/qa`：基于图谱问答
