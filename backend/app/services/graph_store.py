from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from app.graph.workflow import OUTPUT_DIR


def _resolve_within_output(path: Path) -> Path:
    resolved = path.resolve()
    output_resolved = OUTPUT_DIR.resolve()
    if output_resolved not in resolved.parents and resolved != output_resolved:
        raise ValueError("非法图谱路径")
    return resolved


def resolve_graph_path(graph_ref: str) -> Path:
    ref = (graph_ref or "").strip()
    if not ref:
        raise ValueError("图谱标识不能为空")

    if "/" in ref or "\\" in ref:
        candidate = Path(ref)
        if not candidate.is_absolute():
            candidate = OUTPUT_DIR.parent / candidate
    else:
        candidate = OUTPUT_DIR / ref

    return _resolve_within_output(candidate)


def list_graphs() -> list[dict[str, Any]]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    items: list[dict[str, Any]] = []

    for path in sorted(OUTPUT_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        stat = path.stat()
        model_name = ""
        try:
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                meta = data.get("__meta", {})
                if isinstance(meta, dict):
                    model_name = str(meta.get("model_name", "")).strip()
        except Exception:
            model_name = ""

        items.append(
            {
                "id": path.name,
                "name": path.stem,
                "json_output": str(Path("output") / path.name),
                "created_at": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
                "size": stat.st_size,
                "model_name": model_name,
            }
        )

    return items


def load_graph(graph_ref: str) -> dict[str, Any]:
    path = resolve_graph_path(graph_ref)
    if not path.exists() or not path.is_file():
        raise FileNotFoundError("图谱文件不存在")

    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, dict):
        raise ValueError("图谱文件格式非法")

    return data
