from __future__ import annotations

from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.graph.prompts import QA_SYSTEM_PROMPT_TEMPLATE, QA_USER_PROMPT_TEMPLATE


def build_graph_context(graph_data: dict[str, Any]) -> str:
    entities = graph_data.get("entities", [])
    relations = graph_data.get("relations", [])
    triples = graph_data.get("triples", [])

    entity_lines = []
    for entity in entities[:300]:
        entity_lines.append(f"- {entity.get('name', '')} ({entity.get('type', '')})")

    relation_lines = []
    if triples:
        for triple in triples[:400]:
            relation_lines.append(
                f"- ({triple.get('subject', '')}) -[{triple.get('predicate', '')}]-> ({triple.get('object', '')})"
            )
    else:
        for relation in relations[:400]:
            relation_lines.append(
                f"- ({relation.get('source', '')}) -[{relation.get('type', '')}]-> ({relation.get('target', '')})"
            )

    entity_block = "\n".join(entity_lines) if entity_lines else "- 无"
    relation_block = "\n".join(relation_lines) if relation_lines else "- 无"

    return f"实体:\n{entity_block}\n\n关系/三元组:\n{relation_block}"


def _simple_qa(graph_data: dict[str, Any], question: str) -> tuple[str, list[dict[str, str]]]:
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

    evidence: list[dict[str, str]] = []
    q = (question or "").strip()

    for triple in triples:
        s = str(triple.get("subject", ""))
        p = str(triple.get("predicate", ""))
        o = str(triple.get("object", ""))
        if not (s and p and o):
            continue
        if s in q or o in q or p in q:
            evidence.append({"subject": s, "predicate": p, "object": o})
            if len(evidence) >= 8:
                break

    if not evidence:
        for triple in triples[:5]:
            evidence.append(
                {
                    "subject": str(triple.get("subject", "")),
                    "predicate": str(triple.get("predicate", "")),
                    "object": str(triple.get("object", "")),
                }
            )

    if evidence:
        lines = ["根据当前图谱，找到以下相关事实："]
        for item in evidence[:5]:
            lines.append(f"{item['subject']} - {item['predicate']} -> {item['object']}")
        return "\n".join(lines), evidence

    return "根据当前图谱数据，无法确定。", []


def answer_with_graph(
    *,
    graph_data: dict[str, Any],
    question: str,
    model_name: str,
    api_key: str | None,
    base_url: str | None,
    qa_prompt: str | None,
) -> dict[str, Any]:
    context = build_graph_context(graph_data)
    api_key_clean = (api_key or "").strip()

    if not api_key_clean:
        answer, evidence = _simple_qa(graph_data, question)
        return {
            "answer": answer,
            "evidence": evidence,
            "mode": "rule",
            "context_preview": context[:1000],
        }

    system_prompt = QA_SYSTEM_PROMPT_TEMPLATE.format(custom_prompt=(qa_prompt or "").strip() or "请使用简洁、专业、可追溯的中文回答。")
    user_prompt = QA_USER_PROMPT_TEMPLATE.format(context=context, question=question)

    llm = ChatOpenAI(
        model=model_name,
        api_key=api_key_clean,
        base_url=base_url or None,
        temperature=0.2,
    )

    response = llm.invoke([SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)])
    answer = response.content if isinstance(response.content, str) else str(response.content)
    _, evidence = _simple_qa(graph_data, question)

    return {
        "answer": answer.strip(),
        "evidence": evidence,
        "mode": "llm",
        "context_preview": context[:1000],
    }
