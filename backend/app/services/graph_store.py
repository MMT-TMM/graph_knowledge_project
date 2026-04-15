from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[3]
OUTPUT_DIR = PROJECT_ROOT / "output"
INDEX_DIR = OUTPUT_DIR / ".index"
QA_CACHE_DIR = OUTPUT_DIR / ".qa_cache"


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


def resolve_index_path(graph_ref: str) -> Path:
    graph_path = resolve_graph_path(graph_ref)
    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    return INDEX_DIR / f"{graph_path.name}.index.json"


def _tokenize(text: str) -> list[str]:
    text_lower = (text or "").lower()
    tokens: set[str] = set()

    for word in re.findall(r"[a-z0-9_]+", text_lower):
        if word:
            tokens.add(word)

    chinese_chars = re.findall(r"[\u4e00-\u9fff]", text_lower)
    for ch in chinese_chars:
        tokens.add(ch)
    for i in range(len(chinese_chars) - 1):
        tokens.add(chinese_chars[i] + chinese_chars[i + 1])

    return sorted(tokens)


def _canonical_triples(graph_data: dict[str, Any]) -> list[dict[str, str]]:
    triples = graph_data.get("triples", [])
    if not triples:
        triples = [
            {
                "subject": rel.get("source", ""),
                "predicate": rel.get("type", ""),
                "object": rel.get("target", ""),
            }
            for rel in graph_data.get("relations", [])
        ]

    dedup: set[tuple[str, str, str]] = set()
    cleaned: list[dict[str, str]] = []

    for triple in triples:
        s = str(triple.get("subject", "")).strip()
        p = str(triple.get("predicate", "")).strip()
        o = str(triple.get("object", "")).strip()
        if not (s and p and o):
            continue
        key = (s, p, o)
        if key in dedup:
            continue
        dedup.add(key)
        cleaned.append({"subject": s, "predicate": p, "object": o})

    return cleaned


def build_graph_index_payload(graph_id: str, graph_data: dict[str, Any]) -> dict[str, Any]:
    triples = _canonical_triples(graph_data)

    entity_types: dict[str, str] = {}
    for entity in graph_data.get("entities", []):
        name = str(entity.get("name", "")).strip()
        etype = str(entity.get("type", "")).strip()
        if name:
            entity_types[name] = etype

    adjacency: dict[str, list[int]] = {}
    triple_terms: list[list[str]] = []
    triple_texts: list[str] = []

    for idx, triple in enumerate(triples):
        s = triple["subject"]
        p = triple["predicate"]
        o = triple["object"]

        adjacency.setdefault(s, []).append(idx)
        adjacency.setdefault(o, []).append(idx)

        text_blob = f"{s} {p} {o}"
        triple_texts.append(text_blob.lower())
        triple_terms.append(_tokenize(text_blob))

    return {
        "graph_id": graph_id,
        "built_at": datetime.now().isoformat(timespec="seconds"),
        "meta": graph_data.get("__meta", {}),
        "entity_types": entity_types,
        "adjacency": adjacency,
        "triples": triples,
        "triple_texts": triple_texts,
        "triple_terms": triple_terms,
    }


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


def load_graph_index(graph_ref: str) -> dict[str, Any] | None:
    path = resolve_index_path(graph_ref)
    if not path.exists():
        return None

    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, dict):
        return None

    return data


def save_graph_index(graph_ref: str, payload: dict[str, Any]) -> Path:
    index_path = resolve_index_path(graph_ref)
    with index_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return index_path


def ensure_graph_index(graph_ref: str, graph_data: dict[str, Any] | None = None, force: bool = False) -> dict[str, Any]:
    graph_path = resolve_graph_path(graph_ref)
    index_path = resolve_index_path(graph_ref)

    if not force and index_path.exists() and index_path.stat().st_mtime >= graph_path.stat().st_mtime:
        loaded = load_graph_index(graph_ref)
        if loaded is not None:
            return loaded

    data = graph_data if graph_data is not None else load_graph(graph_ref)
    payload = build_graph_index_payload(graph_path.name, data)
    save_graph_index(graph_ref, payload)
    return payload
