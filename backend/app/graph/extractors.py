from __future__ import annotations

import json
import re
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.graph.prompts import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE

COMPONENTS = [
    "地基",
    "墙体",
    "柱子",
    "梁",
    "屋顶",
    "斗拱",
    "台基",
    "檩条",
    "木构架",
    "廊柱",
]
MATERIALS = ["木材", "砖", "石材", "夯土", "青砖", "灰浆"]
DEFECTS = ["裂缝", "倾斜", "风化", "潮湿", "生物侵蚀", "腐朽", "剥落"]
EVENT_PATTERNS = {
    "建造事件": ["建造", "修建", "始建", "营造"],
    "修缮事件": ["修缮", "修复", "重修", "加固"],
    "破坏事件": ["破坏", "损毁", "毁坏", "坍塌", "火灾", "地震"],
}
DYNASTIES = ["唐", "宋", "元", "明", "清", "唐代", "宋代", "元代", "明代", "清代"]


def _extract_json_block(text: str) -> dict[str, Any]:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    fenced_match = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", text)
    if fenced_match:
        return json.loads(fenced_match.group(1))

    brace_match = re.search(r"(\{[\s\S]*\})", text)
    if brace_match:
        return json.loads(brace_match.group(1))

    raise ValueError("Model output is not valid JSON")


def llm_extract(
    text: str,
    model_name: str,
    api_key: str,
    base_url: str | None = None,
) -> dict[str, Any]:
    llm = ChatOpenAI(
        model=model_name,
        api_key=api_key,
        base_url=base_url or None,
        temperature=0,
    ).bind(response_format={"type": "json_object"})

    response = llm.invoke(
        [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=USER_PROMPT_TEMPLATE.format(text=text)),
        ]
    )

    content = response.content if isinstance(response.content, str) else str(response.content)
    return _extract_json_block(content)


def _split_sentences(text: str) -> list[str]:
    parts = re.split(r"[。！？!?.；;\n]+", text)
    return [p.strip() for p in parts if p.strip()]


def _add_entity(entities: dict[str, str], name: str, etype: str) -> None:
    if not name:
        return
    if name not in entities:
        entities[name] = etype


def _add_relation(relations: set[tuple[str, str, str]], source: str, rtype: str, target: str) -> None:
    if source and target and source != target:
        relations.add((source, rtype, target))


def rule_based_extract(text: str) -> dict[str, Any]:
    entities: dict[str, str] = {}
    relations: set[tuple[str, str, str]] = set()
    sentences = _split_sentences(text)

    for sentence in sentences:
        present_components = [c for c in COMPONENTS if c in sentence]
        present_materials = [m for m in MATERIALS if m in sentence]
        present_defects = [d for d in DEFECTS if d in sentence]

        for comp in present_components:
            _add_entity(entities, comp, "ArchitecturalComponent")
        for mat in present_materials:
            _add_entity(entities, mat, "Material")
        for defect in present_defects:
            _add_entity(entities, defect, "Defect")

        for comp in present_components:
            for mat in present_materials:
                _add_relation(relations, comp, "hasMaterial", mat)
            for defect in present_defects:
                _add_relation(relations, comp, "hasDefect", defect)

        for event_name, keywords in EVENT_PATTERNS.items():
            if any(keyword in sentence for keyword in keywords):
                _add_entity(entities, event_name, "Event")
                for comp in present_components:
                    _add_relation(relations, event_name, "affected", comp)

                dynasty_found = [d for d in DYNASTIES if d in sentence]
                year_found = re.findall(r"\d{3,4}年", sentence)
                time_targets = dynasty_found + year_found
                for target in time_targets:
                    if target in DYNASTIES:
                        _add_entity(entities, target, "Dynasty")
                    _add_relation(relations, event_name, "occurredAt", target)

        if len(present_defects) >= 2 and re.search(r"导致|引发|造成", sentence):
            for i in range(len(present_defects) - 1):
                _add_relation(relations, present_defects[i], "causedBy", present_defects[i + 1])

    return {
        "entities": [{"name": name, "type": etype} for name, etype in entities.items()],
        "relations": [
            {"source": src, "type": rtype, "target": tgt}
            for src, rtype, tgt in sorted(relations)
        ],
    }
