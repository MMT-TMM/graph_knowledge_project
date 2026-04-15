# Backend (FastAPI + LangGraph)

## Install

```bash
cd backend
python -m pip install -r requirements.txt
```

## Run

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## API

- `GET /api/health`
- `GET /api/graphs`：图谱文件列表（含构建模型）
- `GET /api/graphs/{graph_id}`：图谱详情
- `POST /api/qa`：基于图谱问答（Graph-RAG 检索后问答）
- `POST /api/extract` (`multipart/form-data`)
  - fields:
    - `graph_name` (optional)
    - `text` (optional)
    - `image_files` (optional, supports multiple)
    - `pdf_files` (optional, supports multiple)
    - `model_name` (optional)
    - `api_key` (optional)
    - `base_url` (optional)
    - `custom_prompt` (optional, extraction prompt override)

## QA 性能优化（已实现）

1. 构建索引：图谱问答前自动生成/复用本地索引（`output/.index/`）。
2. 子图检索：按问题提取相关实体与关系，限制边数（默认 60）。
3. 上下文压缩：仅将检索子图传给模型，避免全量 JSON 消耗 token。
4. 问答缓存：LLM 问答按图谱版本 + 问题缓存到 `output/.qa_cache/`。
5. 模型一致性：问答优先使用图谱构建时记录的模型与 base_url。

JSON output will be written to `../output`.
