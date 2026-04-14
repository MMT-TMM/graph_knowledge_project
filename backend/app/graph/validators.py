from __future__ import annotations

from typing import Any

ALLOWED_ENTITY_TYPES = {
    "ArchitecturalComponent",
    "Material",
    "Defect",
    "Event",
    "Dynasty",
}

ALLOWED_RELATION_TYPES = {
    "hasDefect",
    "hasMaterial",
    "occurredAt",
    "affected",
    "causedBy",
}

RELATION_CONSTRAINTS: dict[str, tuple[str, str | None]] = {
    "hasDefect": ("ArchitecturalComponent", "Defect"),
    "hasMaterial": ("ArchitecturalComponent", "Material"),
    "occurredAt": ("Event", None),
    "affected": ("Event", "ArchitecturalComponent"),
    "causedBy": ("Defect", "Defect"),
}

DYNASTY_CANDIDATES = {"唐", "宋", "元", "明", "清", "唐代", "宋代", "元代", "明代", "清代"}


def _safe(value: Any) -> str:
    return str(value).strip()


def validate_and_normalize(raw: dict[str, Any]) -> dict[str, Any]:
    warnings: list[str] = []

    entity_type_by_name: dict[str, str] = {}
    for entity in raw.get("entities", []):
        name = _safe(entity.get("name", ""))
        etype = _safe(entity.get("type", ""))
        if not name:
            continue
        if etype not in ALLOWED_ENTITY_TYPES:
            warnings.append(f"实体类型非法，已忽略: {name} -> {etype}")
            continue
        entity_type_by_name[name] = etype

    valid_relations: list[dict[str, str]] = []
    seen_relations: set[tuple[str, str, str]] = set()

    for relation in raw.get("relations", []):
        source = _safe(relation.get("source", ""))
        rtype = _safe(relation.get("type", ""))
        target = _safe(relation.get("target", ""))

        if not source or not target:
            continue
        if rtype not in ALLOWED_RELATION_TYPES:
            warnings.append(f"关系类型非法，已忽略: {source} - {rtype} -> {target}")
            continue

        expected_source_type, expected_target_type = RELATION_CONSTRAINTS[rtype]

        source_type = entity_type_by_name.get(source)
        if source_type is None:
            entity_type_by_name[source] = expected_source_type
            source_type = expected_source_type
        if source_type != expected_source_type:
            warnings.append(f"关系源实体类型不匹配，已忽略: {source}({source_type}) - {rtype}")
            continue

        if expected_target_type is not None:
            target_type = entity_type_by_name.get(target)
            if target_type is None:
                entity_type_by_name[target] = expected_target_type
                target_type = expected_target_type
            if target_type != expected_target_type:
                warnings.append(f"关系目标实体类型不匹配，已忽略: {source} - {rtype} -> {target}({target_type})")
                continue
        else:
            if target in DYNASTY_CANDIDATES and target not in entity_type_by_name:
                entity_type_by_name[target] = "Dynasty"

        key = (source, rtype, target)
        if key in seen_relations:
            continue
        seen_relations.add(key)
        valid_relations.append({"source": source, "type": rtype, "target": target})

    entities = []
    for idx, (name, etype) in enumerate(sorted(entity_type_by_name.items()), start=1):
        entities.append(
            {
                "id": f"E{idx:03d}",
                "name": name,
                "type": etype,
            }
        )

    triples = [
        {
            "subject": rel["source"],
            "predicate": rel["type"],
            "object": rel["target"],
        }
        for rel in valid_relations
    ]

    return {
        "entities": entities,
        "relations": valid_relations,
        "triples": triples,
        "warnings": warnings,
    }
