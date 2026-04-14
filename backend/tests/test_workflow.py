from app.graph.workflow import run_kg_workflow


def test_pipeline_rule_based_extract_and_validate():
    text = "明代修缮事件中，柱子出现裂缝并使用木材加固，裂缝导致潮湿。"

    result = run_kg_workflow(
        text=text,
        image_bytes=None,
        pdf_bytes=None,
        model_name="gpt-4.1-mini",
        api_key=None,
        base_url=None,
    )

    assert result["entities"]
    assert result["relations"]
    relation_types = {r["type"] for r in result["relations"]}
    assert relation_types.issubset({"hasDefect", "hasMaterial", "occurredAt", "affected", "causedBy"})
