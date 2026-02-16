from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from server.dfm_bundle import load_dfm_bundle
from server.dfm_review_v2 import generate_dfm_review_v2


def _bundle():
    return load_dfm_bundle(bundle_dir=REPO_ROOT / "server" / "dfm", repo_root=REPO_ROOT)


def _all_required_facts(bundle, pack_ids: list[str]) -> dict[str, object]:
    facts: dict[str, object] = {}
    for rule in bundle.rule_library.get("rules", []):
        if rule.get("pack_id") not in pack_ids:
            continue
        for required_key in rule.get("inputs_required", []):
            facts[required_key] = True
    return facts


def test_review_v2_route_is_wired_in_main():
    source = (REPO_ROOT / "server" / "main.py").read_text(encoding="utf-8")
    assert '@app.post("/api/models/{model_id}/dfm/review-v2")' in source


def test_review_v2_run_both_returns_two_routes_on_mismatch():
    bundle = _bundle()
    response = generate_dfm_review_v2(
        bundle,
        model_id="model-review-v2",
        component_context={
            "component_node_name": "component_1",
            "component_display_name": "Part 1",
            "profile": {
                "material": "Aluminum",
                "manufacturingProcess": "Sheet Metal",
                "industry": "Medical",
            },
        },
        planning_inputs={
            "extracted_part_facts": {
                "bends_present": True,
                "constant_thickness": True,
                "sheet_thickness": 2.0,
            },
            "selected_process_override": "cnc_milling",
            "selected_overlay": "medical",
            "selected_role": "quality_engineer",
            "selected_template": "medical_design_review",
            "run_both_if_mismatch": True,
        },
        context_payload={},
    )

    assert response["mismatch"]["has_mismatch"] is True
    assert response["mismatch"]["run_both_executed"] is True
    assert response["route_count"] == 2

    first_route = response["routes"][0]
    second_route = response["routes"][1]
    assert first_route["process_id"] == "cnc_milling"
    assert second_route["process_id"] == "sheet_metal"

    reference_ids = set(bundle.references.keys())
    for route in response["routes"]:
        for finding in route["findings"]:
            assert set(finding["refs"]).issubset(reference_ids)


def test_review_v2_empty_findings_response_shape_is_stable():
    bundle = _bundle()
    context_payload = _all_required_facts(bundle, ["A_DRAWING"])
    response = generate_dfm_review_v2(
        bundle,
        model_id="model-empty-findings",
        component_context={
            "component_node_name": "component_1",
            "component_display_name": "Part 1",
            "profile": {},
        },
        execution_plans=[
            {
                "plan_id": "plan_1",
                "route_source": "selected",
                "process_id": "cnc_milling",
                "pack_ids": ["A_DRAWING"],
                "overlay_id": None,
                "role_id": "general_dfm",
                "template_id": "executive_1page",
            }
        ],
        context_payload=context_payload,
    )

    assert response["route_count"] == 1
    assert response["finding_count_total"] == 0
    assert response["standards_used_auto_union"] == []

    route = response["routes"][0]
    assert route["finding_count"] == 0
    assert route["findings"] == []
    assert route["standards_used_auto"] == []
    assert isinstance(route["report_skeleton"]["template_sections"], list)
