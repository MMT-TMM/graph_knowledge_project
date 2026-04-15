from app.graph.workflow import run_kg_workflow
from app.services.qa import answer_with_graph


def test_pipeline_rule_based_extract_and_validate():
    text = "明代修缮事件中，柱子出现裂缝并使用木材加固，裂缝导致潮湿。"

    result = run_kg_workflow(
        text=text,
        image_bytes_list=[],
        pdf_bytes_list=[],
        model_name="gpt-4.1-mini",
        api_key=None,
        base_url=None,
        custom_prompt=None,
        graph_name="",
    )

    assert result["entities"]
    assert result["relations"]
    relation_types = {r["type"] for r in result["relations"]}
    assert relation_types.issubset({"hasDefect", "hasMaterial", "occurredAt", "affected", "causedBy"})


def test_qa_rule_mode():
    graph_data = {
        "__meta": {
            "model_name": "qwen-max",
            "created_at": "2026-04-15T12:00:00",
        },
        "entities": [
            {"id": "E001", "name": "柱子", "type": "ArchitecturalComponent"},
            {"id": "E002", "name": "裂缝", "type": "Defect"},
        ],
        "triples": [
            {"subject": "柱子", "predicate": "hasDefect", "object": "裂缝"},
        ],
    }

    result = answer_with_graph(
        graph_id="test_graph.json",
        graph_data=graph_data,
        question="柱子有什么病害？",
        fallback_model_name="gpt-4.1-mini",
        api_key=None,
        fallback_base_url=None,
        qa_prompt=None,
    )

    assert result["mode"] == "rule"
    assert result["used_model"] == "qwen-max"
    assert result["retrieval_stats"]["selected_edges"] >= 1
    assert "柱子" in result["answer"]
