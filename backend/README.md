# Backend (FastAPI + LangGraph)

## Install

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Run

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## API

- `GET /api/health`
- `POST /api/extract` (`multipart/form-data`)
  - fields:
    - `text` (optional)
    - `image_file` (optional)
    - `pdf_file` (optional)
    - `model_name` (optional)
    - `api_key` (optional)
    - `base_url` (optional)

JSON output will be written to `../output`.
