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
- `GET /api/graphs`：图谱文件列表
- `GET /api/graphs/{graph_id}`：图谱详情
- `POST /api/qa`：基于图谱问答
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

JSON output will be written to `../output`.
