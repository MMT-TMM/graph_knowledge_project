from __future__ import annotations

from collections import Counter
from typing import Any


def _tokenize_question(text: str) -> list[str]:
    text = (text or "").lower()
    tokens = set()

    current = []
    for ch in text:
        if ch.isalnum() or ch == "_":
            current.append(ch)
        else:
            if current:
                tokens.add("".join(current))
                current = []
    if current:
        tokens.add("".join(current))

    chinese_chars = [ch for ch in text if "\u4e00" <= ch <= "\u9fff"]
    for ch in chinese_chars:
        tokens.add(ch)
    for idx in range(len(chinese_chars) - 1):
        tokens.add(chinese_chars[idx] + chinese_chars[idx + 1])

    return sorted(tokens)


def retrieve_subgraph(
    *,
    index_data: dict[str, Any],
    question: str,
    max_edges: int = 60,
    max_entities: int = 80,
    hops: int = 2,
) -> dict[str, Any]:
    triples = index_data.get("triples", [])
    triple_texts = index_data.get("triple_texts", [])
    adjacency = index_data.get("adjacency", {})
    entity_types = index_data.get("entity_types", {})

    if not triples:
        return {
            "entities": [],
            "triples": [],
            "stats": {
                "selected_edges": 0,
                "candidate_edges": 0,
                "query_terms": [],
                "seed_entities": [],
            },
        }

    q = (question or "").strip().lower()
    terms = _tokenize_question(q)

    score_map: dict[int, float] = {}
    seed_entities: set[str] = set()

    for idx, triple in enumerate(triples):
        s = str(triple.get("subject", ""))
        p = str(triple.get("predicate", ""))
        o = str(triple.get("object", ""))
        text_blob = triple_texts[idx] if idx < len(triple_texts) else f"{s} {p} {o}".lower()

        score = 0.0
        s_lower, p_lower, o_lower = s.lower(), p.lower(), o.lower()

        if s_lower and s_lower in q:
            score += 8
            seed_entities.add(s)
        if o_lower and o_lower in q:
            score += 8
            seed_entities.add(o)
        if p_lower and p_lower in q:
            score += 5

        for term in terms:
            if len(term) >= 2 and term in text_blob:
                score += 1

        if score > 0:
            score_map[idx] = score

    if not seed_entities and score_map:
        for idx, _ in sorted(score_map.items(), key=lambda kv: kv[1], reverse=True)[:6]:
            seed_entities.add(str(triples[idx].get("subject", "")))
            seed_entities.add(str(triples[idx].get("object", "")))

    if not seed_entities:
        # 兜底选前几条，避免空上下文
        fallback_ids = list(range(min(6, len(triples))))
        for idx in fallback_ids:
            score_map[idx] = score_map.get(idx, 0.5)
            seed_entities.add(str(triples[idx].get("subject", "")))
            seed_entities.add(str(triples[idx].get("object", "")))

    expanded_ids: set[int] = set(score_map.keys())
    frontier = {e for e in seed_entities if e}
    visited_entities = set(frontier)

    for _ in range(max(1, hops)):
        if not frontier:
            break
        next_frontier: set[str] = set()
        for ent in frontier:
            for triple_idx in adjacency.get(ent, []):
                expanded_ids.add(triple_idx)
                triple = triples[triple_idx]
                s = str(triple.get("subject", ""))
                o = str(triple.get("object", ""))
                for other in (s, o):
                    if other and other not in visited_entities:
                        visited_entities.add(other)
                        next_frontier.add(other)
        frontier = next_frontier
        if len(expanded_ids) > max_edges * 6:
            break

    ranked_ids = sorted(
        expanded_ids,
        key=lambda idx: (score_map.get(idx, 0.0), -idx),
        reverse=True,
    )
    selected_ids = ranked_ids[:max_edges]

    selected_triples = [triples[idx] for idx in selected_ids]

    entity_counter: Counter[str] = Counter()
    for triple in selected_triples:
        entity_counter[str(triple.get("subject", ""))] += 1
        entity_counter[str(triple.get("object", ""))] += 1

    entities = []
    for name, _ in entity_counter.most_common(max_entities):
        if not name:
            continue
        entities.append(
            {
                "name": name,
                "type": entity_types.get(name, "Unknown"),
            }
        )

    return {
        "entities": entities,
        "triples": selected_triples,
        "stats": {
            "selected_edges": len(selected_triples),
            "candidate_edges": len(expanded_ids),
            "query_terms": terms[:20],
            "seed_entities": sorted([e for e in seed_entities if e])[:20],
        },
    }


def build_subgraph_context(subgraph: dict[str, Any], max_chars: int = 6500) -> str:
    entity_lines = []
    for entity in subgraph.get("entities", []):
        entity_lines.append(f"- {entity.get('name', '')} ({entity.get('type', '')})")

    triple_lines = []
    for triple in subgraph.get("triples", []):
        triple_lines.append(
            f"- ({triple.get('subject', '')}) -[{triple.get('predicate', '')}]-> ({triple.get('object', '')})"
        )

    entity_block = "\n".join(entity_lines) if entity_lines else "- 无"
    triple_block = "\n".join(triple_lines) if triple_lines else "- 无"

    context = f"实体(检索子图):\n{entity_block}\n\n关系/三元组(检索子图):\n{triple_block}"
    if len(context) > max_chars:
        context = context[:max_chars] + "\n...（上下文已截断）"
    return context
