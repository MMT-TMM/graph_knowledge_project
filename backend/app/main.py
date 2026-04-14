from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from app.graph.workflow import run_kg_workflow
from app.schemas import ExtractResponse, SourceSummary

app = FastAPI(title="Heritage KG Builder", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/extract", response_model=ExtractResponse)
async def extract_knowledge_graph(
    text: str = Form(default=""),
    model_name: str = Form(default="gpt-4.1-mini"),
    api_key: str | None = Form(default=None),
    base_url: str | None = Form(default=None),
    image_file: UploadFile | None = File(default=None),
    pdf_file: UploadFile | None = File(default=None),
):
    image_bytes: bytes | None = None
    pdf_bytes: bytes | None = None

    if image_file is not None:
        image_bytes = await image_file.read()
        if not image_bytes:
            image_bytes = None

    if pdf_file is not None:
        pdf_bytes = await pdf_file.read()
        if not pdf_bytes:
            pdf_bytes = None

    if not text.strip() and image_bytes is None and pdf_bytes is None:
        raise HTTPException(status_code=400, detail="请至少提供文本、图片或PDF中的一种输入")

    result = run_kg_workflow(
        text=text,
        image_bytes=image_bytes,
        pdf_bytes=pdf_bytes,
        model_name=model_name.strip() or "gpt-4.1-mini",
        api_key=(api_key or "").strip() or None,
        base_url=(base_url or "").strip() or None,
    )

    output_path = Path(result["json_output"])
    try:
        relative_output_path = str(output_path.relative_to(Path.cwd().parent))
    except Exception:
        relative_output_path = str(output_path)

    return ExtractResponse(
        request_id=uuid4().hex,
        model_used=model_name,
        entities=result["entities"],
        relations=result["relations"],
        triples=result["triples"],
        warnings=result["warnings"],
        json_output=relative_output_path,
        source_summary=SourceSummary(
            input_text_chars=len(text),
            image_provided=image_bytes is not None,
            pdf_provided=pdf_bytes is not None,
            combined_text_chars=len(result.get("combined_text", "")),
        ),
        debug={
            "entity_count": len(result["entities"]),
            "triple_count": len(result["triples"]),
        },
    )
