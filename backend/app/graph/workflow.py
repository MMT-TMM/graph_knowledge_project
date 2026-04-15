from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from app.graph.extractors import llm_extract, rule_based_extract
from app.graph.validators import validate_and_normalize
from app.services.ingestion import (
    extract_text_from_image_ocr,
    extract_text_from_image_vision,
    extract_text_from_pdf_bytes,
)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
OUTPUT_DIR = PROJECT_ROOT / "output"


class KGState(TypedDict, total=False):
    text: str
    image_bytes_list: list[bytes]
    pdf_bytes_list: list[bytes]
    model_name: str
    api_key: str | None
    base_url: str | None
    custom_prompt: str | None
    graph_name: str | None

    ingested_texts: list[str]
    combined_text: str
    raw_extraction: dict[str, Any]
    validated_output: dict[str, Any]

    warnings: list[str]
    output_path: str


def _sanitize_graph_name(name: str | None) -> str:
    raw = (name or "").strip()
    if not raw:
        return ""
    safe = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff_-]+", "_", raw)
    safe = safe.strip("_")
    return safe[:48]


def ingest_node(state: KGState) -> KGState:
    texts: list[str] = []
    warnings = list(state.get("warnings", []))

    text = (state.get("text") or "").strip()
    if text:
        texts.append(text)

    pdf_bytes_list = state.get("pdf_bytes_list", [])
    for idx, pdf_bytes in enumerate(pdf_bytes_list, start=1):
        if not pdf_bytes:
            continue
        try:
            pdf_text = extract_text_from_pdf_bytes(pdf_bytes)
            if pdf_text:
                texts.append(pdf_text)
            else:
                warnings.append(f"第{idx}个PDF未提取到有效文本")
        except Exception as exc:
            warnings.append(f"第{idx}个PDF解析失败: {exc}")

    image_bytes_list = state.get("image_bytes_list", [])
    for idx, image_bytes in enumerate(image_bytes_list, start=1):
        if not image_bytes:
            continue

        image_text = extract_text_from_image_ocr(image_bytes)
        if image_text:
            texts.append(image_text)
            continue

        api_key = (state.get("api_key") or "").strip()
        if api_key:
            try:
                vision_text = extract_text_from_image_vision(
                    image_bytes=image_bytes,
                    model_name=state.get("model_name", "gpt-4.1-mini"),
                    api_key=api_key,
                    base_url=state.get("base_url"),
                )
                if vision_text:
                    texts.append(vision_text)
                else:
                    warnings.append(f"第{idx}张图片视觉识别未提取到文本")
            except Exception as exc:
                warnings.append(f"第{idx}张图片视觉识别失败: {exc}")
        else:
            warnings.append(f"第{idx}张图片OCR不可用且未提供API Key，已跳过图片内容")

    return {
        "ingested_texts": texts,
        "warnings": warnings,
    }


def normalize_node(state: KGState) -> KGState:
    combined = "\n\n".join(t.strip() for t in state.get("ingested_texts", []) if t.strip())
    return {"combined_text": combined}


def extract_node(state: KGState) -> KGState:
    text = state.get("combined_text", "")
    warnings = list(state.get("warnings", []))

    if not text:
        warnings.append("无可用于抽取的文本内容")
        return {
            "raw_extraction": {"entities": [], "relations": []},
            "warnings": warnings,
        }

    api_key = (state.get("api_key") or "").strip()
    if api_key:
        try:
            raw = llm_extract(
                text=text,
                model_name=state.get("model_name", "gpt-4.1-mini"),
                api_key=api_key,
                base_url=state.get("base_url"),
                custom_prompt=state.get("custom_prompt"),
            )
            return {
                "raw_extraction": raw,
                "warnings": warnings,
            }
        except Exception as exc:
            warnings.append(f"LLM抽取失败，已回退规则抽取: {exc}")

    raw = rule_based_extract(text)
    return {
        "raw_extraction": raw,
        "warnings": warnings,
    }


def validate_node(state: KGState) -> KGState:
    validated = validate_and_normalize(state.get("raw_extraction", {}))
    merged_warnings = list(state.get("warnings", [])) + list(validated.get("warnings", []))
    validated["warnings"] = merged_warnings
    return {
        "validated_output": validated,
        "warnings": merged_warnings,
    }


def save_node(state: KGState) -> KGState:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    graph_name = _sanitize_graph_name(state.get("graph_name"))

    if graph_name:
        filename = f"kg_{graph_name}_{timestamp}.json"
    else:
        filename = f"kg_{timestamp}.json"

    path = OUTPUT_DIR / filename

    payload = dict(state.get("validated_output", {}))
    payload["__meta"] = {
        "graph_name": state.get("graph_name") or "",
        "model_name": state.get("model_name") or "",
        "base_url": state.get("base_url") or "",
        "custom_prompt": state.get("custom_prompt") or "",
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }

    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    return {"output_path": str(path)}


def build_workflow():
    graph = StateGraph(KGState)
    graph.add_node("ingest", ingest_node)
    graph.add_node("normalize", normalize_node)
    graph.add_node("extract", extract_node)
    graph.add_node("validate", validate_node)
    graph.add_node("save", save_node)

    graph.add_edge(START, "ingest")
    graph.add_edge("ingest", "normalize")
    graph.add_edge("normalize", "extract")
    graph.add_edge("extract", "validate")
    graph.add_edge("validate", "save")
    graph.add_edge("save", END)

    return graph.compile()


PIPELINE = build_workflow()


def run_kg_workflow(
    *,
    text: str,
    image_bytes_list: list[bytes],
    pdf_bytes_list: list[bytes],
    model_name: str,
    api_key: str | None,
    base_url: str | None,
    custom_prompt: str | None,
    graph_name: str | None,
) -> dict[str, Any]:
    final_state = PIPELINE.invoke(
        {
            "text": text,
            "image_bytes_list": image_bytes_list,
            "pdf_bytes_list": pdf_bytes_list,
            "model_name": model_name,
            "api_key": api_key,
            "base_url": base_url,
            "custom_prompt": custom_prompt,
            "graph_name": graph_name,
            "warnings": [],
        }
    )

    validated = final_state.get("validated_output", {})
    return {
        "entities": validated.get("entities", []),
        "relations": validated.get("relations", []),
        "triples": validated.get("triples", []),
        "warnings": validated.get("warnings", []),
        "json_output": final_state.get("output_path", ""),
        "combined_text": final_state.get("combined_text", ""),
    }
