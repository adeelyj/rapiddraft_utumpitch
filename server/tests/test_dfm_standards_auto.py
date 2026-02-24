from __future__ import annotations

import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from server.dfm_bundle import load_dfm_bundle
from server.dfm_review_v2 import (
    DfmReviewV2Body,
    DfmReviewV2Error,
    generate_dfm_review_v2,
)


def _bundle():
    return load_dfm_bundle(bundle_dir=REPO_ROOT / "server" / "dfm", repo_root=REPO_ROOT)


def _base_execution_plan() -> list[dict[str, object]]:
    return [
        {
            "plan_id": "plan_1",
            "route_source": "selected",
            "process_id": "cnc_milling",
            "pack_ids": ["A_DRAWING"],
            "overlay_id": None,
            "role_id": "general_dfm",
            "template_id": "executive_1page",
        }
    ]


def _all_required_facts(bundle, pack_ids: list[str]) -> dict[str, object]:
    facts: dict[str, object] = {}
    for rule in bundle.rule_library.get("rules", []):
        if rule.get("pack_id") not in pack_ids:
            continue
        for required_key in rule.get("inputs_required", []):
            facts[required_key] = True
    return facts


def test_standards_used_auto_is_sorted_unique_and_resolved():
    bundle = _bundle()
    response = generate_dfm_review_v2(
        bundle,
        model_id="model-standards",
        component_context={
            "component_node_name": "component_1",
            "component_display_name": "Part 1",
            "profile": {},
        },
        execution_plans=_base_execution_plan(),
        context_payload={},
    )

    standards = response["routes"][0]["standards_used_auto"]
    ref_ids = [entry["ref_id"] for entry in standards]
    assert ref_ids == sorted(ref_ids)
    assert len(ref_ids) == len(set(ref_ids))
    for entry in standards:
        assert entry["ref_id"] in bundle.references
        assert isinstance(entry.get("title"), str)


def test_standards_used_auto_changes_only_with_finding_refs():
    bundle = _bundle()
    response_with_findings = generate_dfm_review_v2(
        bundle,
        model_id="model-with-findings",
        component_context={
            "component_node_name": "component_1",
            "component_display_name": "Part 1",
            "profile": {},
        },
        execution_plans=_base_execution_plan(),
        context_payload={},
    )
    response_without_findings = generate_dfm_review_v2(
        bundle,
        model_id="model-without-findings",
        component_context={
            "component_node_name": "component_1",
            "component_display_name": "Part 1",
            "profile": {},
        },
        execution_plans=_base_execution_plan(),
        context_payload=_all_required_facts(bundle, ["A_DRAWING"]),
    )

    route_with_findings = response_with_findings["routes"][0]
    route_without_findings = response_without_findings["routes"][0]
    assert route_with_findings["finding_count"] > 0
    assert route_without_findings["finding_count"] == 0
    assert route_without_findings["standards_used_auto"] == []
    assert route_with_findings["standards_used_auto"] != route_without_findings["standards_used_auto"]


def test_manual_standards_injection_is_blocked():
    bundle = _bundle()
    with pytest.raises(DfmReviewV2Error, match="Manual standards injection is not allowed"):
        generate_dfm_review_v2(
            bundle,
            model_id="model-manual-standards",
            component_context={
                "component_node_name": "component_1",
                "component_display_name": "Part 1",
                "profile": {},
            },
            execution_plans=_base_execution_plan(),
            context_payload={"manual_standards": ["REF-GPS-1"]},
        )


def test_review_v2_request_model_forbids_manual_standards_field():
    with pytest.raises(ValidationError):
        DfmReviewV2Body.model_validate(
            {
                "planning_inputs": {
                    "selected_role": "quality_engineer",
                    "selected_template": "medical_design_review",
                },
                "manual_standards": ["REF-GPS-1"],
            }
        )


def test_pilot_overlay_emits_new_standards_from_findings():
    bundle = _bundle()
    response = generate_dfm_review_v2(
        bundle,
        model_id="model-pilot-standards",
        component_context={
            "component_node_name": "component_1",
            "component_display_name": "CombiCUT_FormatPart",
            "profile": {
                "material": "Stainless Steel 316L (1.4404)",
                "manufacturingProcess": "CNC Machining",
                "industry": "Prototype and Pilot Compliance (Food Portioning/Robotics)",
            },
        },
        execution_plans=[
            {
                "plan_id": "plan_1",
                "route_source": "selected",
                "process_id": "cnc_milling",
                "pack_ids": ["A_DRAWING", "F_OVERLAY"],
                "overlay_id": "pilot_prototype",
                "role_id": "general_dfm",
                "template_id": "executive_1page",
            }
        ],
        context_payload={},
    )

    ref_ids = {entry["ref_id"] for entry in response["standards_used_auto_union"]}
    assert "REF-FOOD-EN13870" in ref_ids
    assert "REF-FCM-EU-1935-2004" in ref_ids
    assert "REF-FIT-286" in ref_ids


def test_pilot_overlay_standards_trace_includes_all_overlay_refs():
    bundle = _bundle()
    pilot_overlay = next(
        overlay
        for overlay in bundle.overlays.get("overlays", [])
        if overlay.get("overlay_id") == "pilot_prototype"
    )
    expected_refs = {
        ref_id
        for ref_id in pilot_overlay.get("adds_refs", [])
        if isinstance(ref_id, str) and ref_id
    }

    response = generate_dfm_review_v2(
        bundle,
        model_id="model-pilot-trace",
        component_context={
            "component_node_name": "component_1",
            "component_display_name": "CombiCUT_FormatPart",
            "profile": {},
        },
        execution_plans=[
            {
                "plan_id": "plan_1",
                "route_source": "selected",
                "process_id": "cnc_milling",
                "pack_ids": ["A_DRAWING", "F_OVERLAY"],
                "overlay_id": "pilot_prototype",
                "role_id": "general_dfm",
                "template_id": "executive_1page",
            }
        ],
        context_payload={},
    )

    traced_refs = {
        entry["ref_id"]
        for entry in response.get("standards_trace_union", [])
        if isinstance(entry, dict) and isinstance(entry.get("ref_id"), str)
    }
    assert expected_refs.issubset(traced_refs)
