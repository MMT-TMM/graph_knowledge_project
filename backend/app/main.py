from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from app.graph.workflow import run_kg_workflow
from app.schemas import (
    ExtractResponse,
    GraphDetailResponse,
    GraphItem,
    QARequest,
    QAResponse,
    SourceSummary,
)
from app.services.graph_store import list_graphs, load_graph
from app.services.qa import answer_with_graph

app = FastAPI(title="Heritage KG Builder", version="1.1.0")

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


@app.get("/api/graphs", response_model=list[GraphItem])
def get_graphs() -> list[GraphItem]:
    return [GraphItem(**item) for item in list_graphs()]


@app.get("/api/graphs/{graph_id}", response_model=GraphDetailResponse)
def get_graph_detail(graph_id: str) -> GraphDetailResponse:
    try:
        graph_data = load_graph(graph_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"读取图谱失败: {exc}") from exc

    item = next((g for g in list_graphs() if g["id"] == graph_id), None)
    if item is None:
        item = {
            "id": graph_id,
            "name": Path(graph_id).stem,
            "json_output": str(Path("output") / graph_id),
            "created_at": "",
            "size": 0,
        }

    return GraphDetailResponse(graph=GraphItem(**item), data=graph_data)


@app.post("/api/qa", response_model=QAResponse)
def qa_with_graph(req: QARequest) -> QAResponse:
    question = (req.question or "").strip()
    if not question:
        raise HTTPException(status_code=400, detail="问题不能为空")

    try:
        graph_data = load_graph(req.graph_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"读取图谱失败: {exc}") from exc

    try:
        qa_result = answer_with_graph(
            graph_data=graph_data,
            question=question,
            model_name=req.model_name,
            api_key=req.api_key,
            base_url=req.base_url,
            qa_prompt=req.qa_prompt,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"问答执行失败: {exc}") from exc

    return QAResponse(
        graph_id=req.graph_id,
        question=question,
        answer=qa_result["answer"],
        mode=qa_result["mode"],
        evidence=qa_result["evidence"],
        context_preview=qa_result.get("context_preview", ""),
    )


@app.post("/api/extract", response_model=ExtractResponse)
async def extract_knowledge_graph(
    text: str = Form(default=""),
    graph_name: str = Form(default=""),
    model_name: str = Form(default="gpt-4.1-mini"),
    api_key: str | None = Form(default=None),
    base_url: str | None = Form(default=None),
    custom_prompt: str | None = Form(default=None),
    image_files: list[UploadFile] | None = File(default=None),
    pdf_files: list[UploadFile] | None = File(default=None),
    image_file: UploadFile | None = File(default=None),
    pdf_file: UploadFile | None = File(default=None),
):
    image_bytes_list: list[bytes] = []
    pdf_bytes_list: list[bytes] = []

    for upload in image_files or []:
        content = await upload.read()
        if content:
            image_bytes_list.append(content)

    for upload in pdf_files or []:
        content = await upload.read()
        if content:
            pdf_bytes_list.append(content)

    if image_file is not None:
        content = await image_file.read()
        if content:
            image_bytes_list.append(content)

    if pdf_file is not None:
        content = await pdf_file.read()
        if content:
            pdf_bytes_list.append(content)

    if not text.strip() and not image_bytes_list and not pdf_bytes_list:
        raise HTTPException(status_code=400, detail="请至少提供文本、图片或PDF中的一种输入")

    result = run_kg_workflow(
        text=text,
        image_bytes_list=image_bytes_list,
        pdf_bytes_list=pdf_bytes_list,
        model_name=model_name.strip() or "gpt-4.1-mini",
        api_key=(api_key or "").strip() or None,
        base_url=(base_url or "").strip() or None,
        custom_prompt=(custom_prompt or "").strip() or None,
        graph_name=(graph_name or "").strip() or None,
    )

    output_path = Path(result["json_output"])
    graph_id = output_path.name

    try:
        relative_output_path = str(output_path.relative_to(Path.cwd().parent))
    except Exception:
        relative_output_path = str(output_path)

    resolved_graph_name = (graph_name or "").strip() or output_path.stem

    return ExtractResponse(
        request_id=uuid4().hex,
        graph_id=graph_id,
        graph_name=resolved_graph_name,
        model_used=model_name,
        entities=result["entities"],
        relations=result["relations"],
        triples=result["triples"],
        warnings=result["warnings"],
        json_output=relative_output_path,
        source_summary=SourceSummary(
            input_text_chars=len(text),
            image_provided=bool(image_bytes_list),
            pdf_provided=bool(pdf_bytes_list),
            image_count=len(image_bytes_list),
            pdf_count=len(pdf_bytes_list),
            combined_text_chars=len(result.get("combined_text", "")),
        ),
        debug={
            "entity_count": len(result["entities"]),
            "triple_count": len(result["triples"]),
        },
    )
