from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.graph.prompts import QA_SYSTEM_PROMPT_TEMPLATE, QA_USER_PROMPT_TEMPLATE
from app.services.graph_store import QA_CACHE_DIR, ensure_graph_index
from app.services.retrieval import build_subgraph_context, retrieve_subgraph


def _to_triples(graph_data: dict[str, Any]) -> list[dict[str, str]]:
    triples = graph_data.get("triples", [])
    if triples:
        return [
            {
                "subject": str(t.get("subject", "")),
                "predicate": str(t.get("predicate", "")),
                "object": str(t.get("object", "")),
            }
            for t in triples
            if str(t.get("subject", "")).strip()
            and str(t.get("predicate", "")).strip()
            and str(t.get("object", "")).strip()
        ]

    return [
        {
            "subject": str(rel.get("source", "")),
            "predicate": str(rel.get("type", "")),
            "object": str(rel.get("target", "")),
        }
        for rel in graph_data.get("relations", [])
        if str(rel.get("source", "")).strip()
        and str(rel.get("type", "")).strip()
        and str(rel.get("target", "")).strip()
    ]


def _simple_qa_from_triples(triples: list[dict[str, str]], question: str) -> tuple[str, list[dict[str, str]]]:
    evidence: list[dict[str, str]] = []
    q = (question or "").strip()

    for triple in triples:
        s = triple["subject"]
        p = triple["predicate"]
        o = triple["object"]
        if s in q or o in q or p in q:
            evidence.append({"subject": s, "predicate": p, "object": o})
            if len(evidence) >= 10:
                break

    if not evidence:
        evidence = triples[:6]

    if evidence:
        lines = ["根据当前图谱检索结果，找到以下相关事实："]
        for item in evidence[:6]:
            lines.append(f"{item['subject']} - {item['predicate']} -> {item['object']}")
        return "\n".join(lines), evidence[:6]

    return "根据当前图谱数据，无法确定。", []


def _cache_path(cache_key: str) -> Path:
    QA_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return QA_CACHE_DIR / f"{cache_key}.json"


def _make_cache_key(
    *,
    graph_id: str,
    graph_version: str,
    question: str,
    used_model: str,
    qa_prompt: str,
) -> str:
    raw = "|".join(
        [
            graph_id,
            graph_version,
            question.strip(),
            used_model.strip(),
            qa_prompt.strip(),
        ]
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _load_cache(cache_key: str) -> dict[str, Any] | None:
    path = _cache_path(cache_key)
    if not path.exists():
        return None

    try:
        with path.open("r", encoding="utf-8") as f:
            payload = json.load(f)
        if isinstance(payload, dict):
            return payload
    except Exception:
        return None
    return None


def _save_cache(cache_key: str, payload: dict[str, Any]) -> None:
    path = _cache_path(cache_key)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def answer_with_graph(
    *,
    graph_id: str,
    graph_data: dict[str, Any],
    question: str,
    fallback_model_name: str,
    api_key: str | None,
    fallback_base_url: str | None,
    qa_prompt: str | None,
) -> dict[str, Any]:
    meta = graph_data.get("__meta", {}) if isinstance(graph_data, dict) else {}
    if not isinstance(meta, dict):
        meta = {}

    # 问答强制优先使用构建图谱时记录的模型配置
    used_model = str(meta.get("model_name", "")).strip() or fallback_model_name
    used_base_url = str(meta.get("base_url", "")).strip() or (fallback_base_url or None)

    index_data = ensure_graph_index(graph_id, graph_data=graph_data)
    subgraph = retrieve_subgraph(index_data=index_data, question=question, max_edges=60, max_entities=80, hops=2)
    subgraph_triples = subgraph.get("triples", [])

    context = build_subgraph_context(subgraph, max_chars=6500)
    context_preview = context[:1200]

    api_key_clean = (api_key or "").strip()
    user_prompt_extra = (qa_prompt or "").strip() or "请使用简洁、专业、可追溯的中文回答。"

    graph_version = str(meta.get("created_at", "")).strip() or str(index_data.get("built_at", ""))
    cache_key = _make_cache_key(
        graph_id=graph_id,
        graph_version=graph_version,
        question=question,
        used_model=used_model,
        qa_prompt=user_prompt_extra,
    )

    retrieval_stats = dict(subgraph.get("stats", {}))
    retrieval_stats["context_chars"] = len(context)

    if not api_key_clean:
        answer, evidence = _simple_qa_from_triples(subgraph_triples, question)
        return {
            "answer": answer,
            "evidence": evidence,
            "mode": "rule",
            "used_model": used_model,
            "retrieval_stats": retrieval_stats,
            "context_preview": context_preview,
        }

    cached = _load_cache(cache_key)
    if cached is not None:
        cached["mode"] = "llm_cache"
        cached["used_model"] = used_model
        cached["retrieval_stats"] = retrieval_stats
        cached["context_preview"] = context_preview
        return cached

    system_prompt = QA_SYSTEM_PROMPT_TEMPLATE.format(custom_prompt=user_prompt_extra)
    user_prompt = QA_USER_PROMPT_TEMPLATE.format(context=context, question=question)

    llm = ChatOpenAI(
        model=used_model,
        api_key=api_key_clean,
        base_url=used_base_url,
        temperature=0.2,
    )

    response = llm.invoke([SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)])
    answer = response.content if isinstance(response.content, str) else str(response.content)

    _, evidence = _simple_qa_from_triples(subgraph_triples, question)

    result = {
        "answer": answer.strip(),
        "evidence": evidence,
        "mode": "llm",
        "used_model": used_model,
        "retrieval_stats": retrieval_stats,
        "context_preview": context_preview,
    }

    _save_cache(cache_key, result)
    return result
