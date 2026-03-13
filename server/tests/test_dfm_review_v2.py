from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from server.dfm_benchmark import adapt_cadex_features_to_facts
from server.dfm_bundle import load_dfm_bundle
from server.dfm_part_facts_bridge import NOT_APPLICABLE_INPUTS_KEY
from server.dfm_review_v2 import (
    RULE_VIOLATION_EVALUATORS,
    _evaluate_rule_violation,
    _missing_required_inputs,
    generate_dfm_review_v2,
)


def _bundle():
    return load_dfm_bundle(bundle_dir=REPO_ROOT / "server" / "dfm", repo_root=REPO_ROOT)


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


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


def test_review_v2_route_auto_injects_part_facts_when_extracted_is_empty():
    source = (REPO_ROOT / "server" / "main.py").read_text(encoding="utf-8")

    assert "part_facts_service.get_or_create(" in source
    assert "build_extracted_facts_from_part_facts(" in source
    assert "if not isinstance(extracted_facts, dict) or not extracted_facts:" in source


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
            "process_selection_mode": "override",
            "overlay_selection_mode": "profile",
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


def test_review_v2_ignores_ui_mode_fields_when_planning():
    bundle = _bundle()
    response = generate_dfm_review_v2(
        bundle,
        model_id="model-review-v2-mode-fields",
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
            "selected_process_override": None,
            "selected_overlay": "medical",
            "process_selection_mode": "auto",
            "overlay_selection_mode": "profile",
            "selected_role": "quality_engineer",
            "selected_template": "medical_design_review",
            "run_both_if_mismatch": True,
        },
        context_payload={},
    )

    assert response["route_count"] >= 1


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
    assert response["geometry_evidence"]["process_summary"]["effective_process_label"] == "CNC Milling"
    assert response["geometry_evidence"]["feature_groups"] == []
    assert response["geometry_evidence"]["detail_metrics"] == []

    route = response["routes"][0]
    assert route["finding_count"] == 0
    assert route["findings"] == []
    assert route["standards_used_auto"] == []
    assert isinstance(route["report_skeleton"]["template_sections"], list)


def test_missing_required_inputs_skips_not_applicable_keys():
    rule = {
        "inputs_required": ["drawing_title_block", "drawing_notes"],
    }
    review_facts = {
        "drawing_title_block": True,
        NOT_APPLICABLE_INPUTS_KEY: ["drawing_notes"],
    }

    assert _missing_required_inputs(rule, review_facts) == []


def test_review_v2_findings_are_classified_as_evidence_gaps():
    bundle = _bundle()
    response = generate_dfm_review_v2(
        bundle,
        model_id="model-finding-type",
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
        context_payload={},
    )

    findings = response["routes"][0]["findings"]
    assert findings, "Expected findings for evidence-gap classification test."
    assert all(finding.get("finding_type") == "evidence_gap" for finding in findings)
    assert all(isinstance(finding.get("recommended_action"), str) and finding.get("recommended_action") for finding in findings)
    assert all(isinstance(finding.get("expected_impact"), dict) for finding in findings)


def test_review_v2_can_emit_rule_violation_findings():
    bundle = _bundle()
    context_payload = _all_required_facts(bundle, ["A_DRAWING"])
    context_payload.update(
        {
            "wall_thickness_map": True,
            "material_spec": "Aluminum 6061",
            "min_wall_thickness": 0.6,
            "pocket_depth": True,
            "pocket_corner_radius": True,
            "max_pocket_depth_mm": 16.0,
            "min_internal_radius_mm": 1.0,
            "part_bounding_box": True,
            "bbox_x_mm": 1400.0,
            "bbox_y_mm": 800.0,
            "bbox_z_mm": 620.0,
        }
    )
    response = generate_dfm_review_v2(
        bundle,
        model_id="model-rule-violation",
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
                "pack_ids": ["A_DRAWING", "B_CNC"],
                "overlay_id": None,
                "role_id": "general_dfm",
                "template_id": "executive_1page",
            }
        ],
        context_payload=context_payload,
    )

    findings = response["routes"][0]["findings"]
    rule_violations = [finding for finding in findings if finding.get("finding_type") == "rule_violation"]
    assert rule_violations, "Expected at least one deterministic rule violation."
    assert any(finding.get("rule_id") == "CNC-001" for finding in rule_violations)
    assert any("evaluation" in finding.get("evidence", {}) for finding in rule_violations)
    assert all(isinstance(finding.get("recommended_action"), str) and finding.get("recommended_action") for finding in rule_violations)
    assert all(isinstance(finding.get("expected_impact"), dict) for finding in rule_violations)


def test_review_v2_small_radius_findings_can_emit_violating_instances():
    bundle = _bundle()
    context_payload = _all_required_facts(bundle, ["A_DRAWING", "B_CNC"])
    context_payload.update(
        {
            "material_spec": "Aluminum 6061",
            "pocket_depth": True,
            "pocket_corner_radius": True,
            "max_pocket_depth_mm": 25.0,
            "min_internal_radius_mm": 1.2,
            "count_radius_below_3_0_mm": 2,
            "internal_radius_instances": [
                {
                    "instance_id": "C1",
                    "edge_index": 11,
                    "location_description": "front-left pocket corner",
                    "radius_mm": 1.2,
                    "status": "WARNING",
                    "recommendation": "Increase radius",
                    "pocket_depth_mm": 12.0,
                    "depth_to_radius_ratio": 10.0,
                    "aggravating_factor": True,
                    "position_mm": [10.0, 20.0, 30.0],
                    "bbox_bounds_mm": [9.0, 19.0, 29.0, 11.0, 21.0, 31.0],
                },
                {
                    "instance_id": "C2",
                    "edge_index": 12,
                    "location_description": "rear-right pocket corner",
                    "radius_mm": 2.5,
                    "status": "CAUTION",
                    "recommendation": "Increase radius",
                    "pocket_depth_mm": 17.5,
                    "depth_to_radius_ratio": 7.0,
                    "aggravating_factor": True,
                    "position_mm": [40.0, 50.0, 60.0],
                    "bbox_bounds_mm": [38.5, 48.5, 58.5, 41.5, 51.5, 61.5],
                },
                {
                    "instance_id": "C3",
                    "edge_index": 13,
                    "location_description": "large blend",
                    "radius_mm": 4.0,
                    "status": "OK",
                    "recommendation": "No action",
                    "pocket_depth_mm": 8.0,
                    "depth_to_radius_ratio": 2.0,
                    "aggravating_factor": False,
                    "position_mm": [70.0, 80.0, 90.0],
                    "bbox_bounds_mm": [68.0, 78.0, 88.0, 72.0, 82.0, 92.0],
                },
            ],
        }
    )
    response = generate_dfm_review_v2(
        bundle,
        model_id="model-small-radius-instances",
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
                "pack_ids": ["A_DRAWING", "B_CNC"],
                "overlay_id": None,
                "role_id": "general_dfm",
                "template_id": "executive_1page",
            }
        ],
        context_payload=context_payload,
    )

    violations = [
        finding
        for finding in response["routes"][0]["findings"]
        if finding.get("finding_type") == "rule_violation"
    ]
    cnc_006 = next(finding for finding in violations if finding.get("rule_id") == "CNC-006")
    food_004 = next((finding for finding in violations if finding.get("rule_id") == "FOOD-004"), None)

    cnc_006_instances = cnc_006["evidence"]["violating_instances"]
    assert [instance["instance_id"] for instance in cnc_006_instances] == ["C1", "C2"]
    assert cnc_006_instances[0]["violation_reasons"] == [
        "radius_below_3.0_mm",
        "depth_to_radius_ratio_above_6.0",
    ]
    assert cnc_006_instances[0]["bbox_bounds_mm"] == [9.0, 19.0, 29.0, 11.0, 21.0, 31.0]
    assert cnc_006_instances[1]["violation_reasons"] == [
        "radius_below_3.0_mm",
        "depth_to_radius_ratio_above_6.0",
    ]
    assert cnc_006_instances[1]["bbox_bounds_mm"] == [38.5, 48.5, 58.5, 41.5, 51.5, 61.5]

    if food_004 is not None:
        food_004_instances = food_004["evidence"]["violating_instances"]
        assert [instance["instance_id"] for instance in food_004_instances] == ["C1", "C2"]
        assert food_004_instances[0]["bbox_bounds_mm"] == [9.0, 19.0, 29.0, 11.0, 21.0, 31.0]


def test_review_v2_deep_pocket_and_long_reach_findings_can_emit_violating_instances():
    bundle = _bundle()
    context_payload = _all_required_facts(bundle, ["A_DRAWING", "B_CNC"])
    context_payload.update(
        {
            "material_spec": "Aluminum 6061",
            "pocket_depth": True,
            "pocket_corner_radius": True,
            "max_pocket_depth_mm": 22.0,
            "min_internal_radius_mm": 1.5,
            "long_reach_tool_risk_count": 2,
            "max_depth_to_radius_ratio": 14.6667,
            "internal_radius_instances": [
                {
                    "instance_id": "P1",
                    "edge_index": 21,
                    "location_description": "deep rib pocket corner",
                    "radius_mm": 1.5,
                    "status": "WARNING",
                    "recommendation": "Increase radius",
                    "pocket_depth_mm": 22.0,
                    "depth_to_radius_ratio": 14.6667,
                    "aggravating_factor": True,
                    "position_mm": [15.0, 25.0, 35.0],
                    "bbox_bounds_mm": [13.5, 23.5, 33.5, 16.5, 26.5, 36.5],
                },
                {
                    "instance_id": "P2",
                    "edge_index": 22,
                    "location_description": "long-reach corner",
                    "radius_mm": 2.8,
                    "status": "CAUTION",
                    "recommendation": "Reduce pocket depth",
                    "pocket_depth_mm": 11.0,
                    "depth_to_radius_ratio": 3.9286,
                    "aggravating_factor": True,
                    "position_mm": [45.0, 55.0, 65.0],
                    "bbox_bounds_mm": [43.5, 53.5, 63.5, 46.5, 56.5, 66.5],
                },
                {
                    "instance_id": "P3",
                    "edge_index": 23,
                    "location_description": "deep finishing corner",
                    "radius_mm": 3.5,
                    "status": "WARNING",
                    "recommendation": "Open up pocket",
                    "pocket_depth_mm": 40.0,
                    "depth_to_radius_ratio": 11.4286,
                    "aggravating_factor": False,
                    "position_mm": [75.0, 85.0, 95.0],
                    "bbox_bounds_mm": [73.0, 83.0, 93.0, 77.0, 87.0, 97.0],
                },
            ],
        }
    )
    response = generate_dfm_review_v2(
        bundle,
        model_id="model-deep-pocket-long-reach-instances",
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
                "pack_ids": ["A_DRAWING", "B_CNC"],
                "overlay_id": None,
                "role_id": "general_dfm",
                "template_id": "executive_1page",
            }
        ],
        context_payload=context_payload,
    )

    violations = {
        finding["rule_id"]: finding
        for finding in response["routes"][0]["findings"]
        if finding.get("finding_type") == "rule_violation"
    }
    cnc_013_instances = violations["CNC-013"]["evidence"]["violating_instances"]
    cnc_024_instances = violations["CNC-024"]["evidence"]["violating_instances"]

    assert [instance["instance_id"] for instance in cnc_013_instances] == ["P1", "P2", "P3"]
    assert cnc_013_instances[0]["violation_reasons"] == [
        "depth_to_radius_ratio_above_8.0",
        "long_reach_tool_risk",
    ]
    assert cnc_013_instances[1]["violation_reasons"] == ["long_reach_tool_risk"]
    assert cnc_013_instances[2]["violation_reasons"] == ["depth_to_radius_ratio_above_8.0"]
    assert cnc_013_instances[0]["bbox_bounds_mm"] == [13.5, 23.5, 33.5, 16.5, 26.5, 36.5]

    assert [instance["instance_id"] for instance in cnc_024_instances] == ["P1", "P3"]
    assert cnc_024_instances[0]["violation_reasons"] == [
        "pocket_depth_above_12.0_mm",
        "depth_to_radius_ratio_above_10.0",
    ]
    assert cnc_024_instances[1]["violation_reasons"] == [
        "pocket_depth_above_12.0_mm",
        "depth_to_radius_ratio_above_10.0",
    ]
    assert cnc_024_instances[1]["bbox_bounds_mm"] == [73.0, 83.0, 93.0, 77.0, 87.0, 97.0]


def test_review_v2_hole_findings_can_emit_violating_instances():
    bundle = _bundle()
    context_payload = _all_required_facts(bundle, ["A_DRAWING", "B_CNC"])
    context_payload.update(
        {
            "hole_features": True,
            "hole_depth": True,
            "hole_diameter": True,
            "hole_depth_mm": 18.0,
            "hole_diameter_mm": 1.3,
            "min_hole_diameter_mm": 1.3,
            "hole_instances": [
                {
                    "instance_id": "H1",
                    "subtype": "through_hole",
                    "location_description": "small deep pilot hole",
                    "diameter_mm": 1.3,
                    "depth_mm": 18.0,
                    "depth_to_diameter_ratio": 13.8462,
                    "position_mm": [15.0, 25.0, 35.0],
                    "bbox_bounds_mm": [14.0, 24.0, 34.0, 16.0, 26.0, 36.0],
                    "face_indices": [7, 8],
                },
                {
                    "instance_id": "H2",
                    "subtype": "through_hole",
                    "location_description": "clearance hole",
                    "diameter_mm": 4.0,
                    "depth_mm": 8.0,
                    "depth_to_diameter_ratio": 2.0,
                    "position_mm": [45.0, 55.0, 65.0],
                    "bbox_bounds_mm": [43.0, 53.0, 63.0, 47.0, 57.0, 67.0],
                    "face_indices": [17],
                },
            ],
        }
    )
    response = generate_dfm_review_v2(
        bundle,
        model_id="model-hole-instances",
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
                "pack_ids": ["A_DRAWING", "B_CNC"],
                "overlay_id": None,
                "role_id": "general_dfm",
                "template_id": "executive_1page",
            }
        ],
        context_payload=context_payload,
    )

    violations = {
        finding["rule_id"]: finding
        for finding in response["routes"][0]["findings"]
        if finding.get("finding_type") == "rule_violation"
    }
    cnc_002_instances = violations["CNC-002"]["evidence"]["violating_instances"]
    cnc_003_instances = violations["CNC-003"]["evidence"]["violating_instances"]

    assert [instance["instance_id"] for instance in cnc_002_instances] == ["H1"]
    assert cnc_002_instances[0]["violation_reasons"] == ["depth_to_diameter_ratio_above_10.0"]
    assert cnc_002_instances[0]["bbox_bounds_mm"] == [14.0, 24.0, 34.0, 16.0, 26.0, 36.0]

    assert [instance["instance_id"] for instance in cnc_003_instances] == ["H1"]
    assert cnc_003_instances[0]["violation_reasons"] == ["non_standard_hole_diameter"]


def test_review_v2_wall_findings_can_emit_violating_instances():
    bundle = _bundle()
    context_payload = _all_required_facts(bundle, ["A_DRAWING", "B_CNC"])
    context_payload.update(
        {
            "wall_thickness_map": True,
            "min_wall_thickness": 0.6,
            "material_spec": "Aluminum 6061",
            "tight_tolerance_flag": True,
            "wall_thickness_instances": [
                {
                    "instance_id": "W1",
                    "location_description": "thin clamp wall",
                    "thickness_mm": 0.6,
                    "position_mm": [5.0, 6.0, 7.0],
                    "bbox_bounds_mm": [4.0, 5.0, 6.0, 6.0, 7.0, 8.0],
                    "face_indices": [21, 22],
                }
            ],
        }
    )
    response = generate_dfm_review_v2(
        bundle,
        model_id="model-wall-instances",
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
                "pack_ids": ["A_DRAWING", "B_CNC"],
                "overlay_id": None,
                "role_id": "general_dfm",
                "template_id": "executive_1page",
            }
        ],
        context_payload=context_payload,
    )

    violations = {
        finding["rule_id"]: finding
        for finding in response["routes"][0]["findings"]
        if finding.get("finding_type") == "rule_violation"
    }
    cnc_001_instances = violations["CNC-001"]["evidence"]["violating_instances"]
    cnc_020_instances = violations["CNC-020"]["evidence"]["violating_instances"]

    assert [instance["instance_id"] for instance in cnc_001_instances] == ["W1"]
    assert cnc_001_instances[0]["violation_reasons"] == ["wall_thickness_below_1.0_mm"]
    assert cnc_001_instances[0]["bbox_bounds_mm"] == [4.0, 5.0, 6.0, 6.0, 7.0, 8.0]

    assert [instance["instance_id"] for instance in cnc_020_instances] == ["W1"]
    assert cnc_020_instances[0]["violation_reasons"] == ["wall_thickness_below_1.2_mm"]


def test_review_v2_geometry_evidence_surfaces_sample_2_turning_signals():
    bundle = _bundle()
    adapted = adapt_cadex_features_to_facts(
        _load_json(
            REPO_ROOT / "benchmark_data" / "dfm_mtk" / "cases" / "sample 2" / "sample2_features.json"
        ),
        component_profile={"material": "Aluminum", "manufacturingProcess": "", "industry": ""},
    )

    response = generate_dfm_review_v2(
        bundle,
        model_id="sample-2-geometry-evidence",
        component_context={
            "component_node_name": "component_1",
            "component_display_name": "Sample 2",
            "profile": {
                "material": "Aluminum",
                "manufacturingProcess": "CNC Machining",
                "industry": "All standards (non-pilot)",
            },
        },
        planning_inputs={
            "extracted_part_facts": adapted["extracted_part_facts"],
            "analysis_mode": "geometry_dfm",
            "selected_process_override": None,
            "selected_overlay": None,
            "process_selection_mode": "auto",
            "overlay_selection_mode": "none",
            "selected_role": "general_dfm",
            "selected_template": "executive_1page",
            "run_both_if_mismatch": False,
        },
        context_payload={},
    )

    geometry_evidence = response["geometry_evidence"]
    assert geometry_evidence["process_summary"]["ai_process_label"] == "CNC Turning"
    assert "Rotational symmetry detected" in geometry_evidence["process_summary"]["reason_tags"]
    assert "25 turned faces detected" in geometry_evidence["process_summary"]["reason_tags"]

    groups = {entry["group_id"]: entry for entry in geometry_evidence["feature_groups"]}
    turning_metrics = {metric["key"]: metric["value"] for metric in groups["turning"]["metrics"]}
    hole_metrics = {metric["key"]: metric["value"] for metric in groups["holes"]["metrics"]}
    pocket_metrics = {metric["key"]: metric["value"] for metric in groups["pockets"]["metrics"]}
    milled_metrics = {metric["key"]: metric["value"] for metric in groups["milled_faces"]["metrics"]}

    assert turning_metrics["rotational_symmetry"] is True
    assert turning_metrics["turned_face_count"] == 25
    assert hole_metrics["hole_count"] == 1
    assert hole_metrics["bore_count"] == 1
    assert pocket_metrics["pocket_count"] == 13
    assert milled_metrics["milled_face_count"] == 45

    detail_metrics = {metric["key"]: metric["value"] for metric in geometry_evidence["detail_metrics"]}
    assert detail_metrics["turned_diameter_faces_count"] == 4
    assert detail_metrics["turned_end_faces_count"] == 20
    assert detail_metrics["turned_profile_faces_count"] == 1


def test_review_v2_geometry_evidence_surfaces_sample_6_turning_and_groove_signals():
    bundle = _bundle()
    adapted = adapt_cadex_features_to_facts(
        _load_json(
            REPO_ROOT / "benchmark_data" / "dfm_mtk" / "cases" / "sample 6" / "sample6_features.json"
        ),
        component_profile={"material": "Aluminum", "manufacturingProcess": "", "industry": ""},
    )

    response = generate_dfm_review_v2(
        bundle,
        model_id="sample-6-geometry-evidence",
        component_context={
            "component_node_name": "component_1",
            "component_display_name": "Sample 6",
            "profile": {
                "material": "Aluminum",
                "manufacturingProcess": "CNC Machining",
                "industry": "All standards (non-pilot)",
            },
        },
        planning_inputs={
            "extracted_part_facts": adapted["extracted_part_facts"],
            "analysis_mode": "geometry_dfm",
            "selected_process_override": None,
            "selected_overlay": None,
            "process_selection_mode": "auto",
            "overlay_selection_mode": "none",
            "selected_role": "general_dfm",
            "selected_template": "executive_1page",
            "run_both_if_mismatch": False,
        },
        context_payload={},
    )

    geometry_evidence = response["geometry_evidence"]
    assert geometry_evidence["process_summary"]["ai_process_label"] == "CNC Turning"
    assert "Rotational symmetry detected" in geometry_evidence["process_summary"]["reason_tags"]
    assert "26 turned faces detected" in geometry_evidence["process_summary"]["reason_tags"]

    groups = {entry["group_id"]: entry for entry in geometry_evidence["feature_groups"]}
    groove_metrics = {metric["key"]: metric["value"] for metric in groups["grooves"]["metrics"]}
    milled_metrics = {metric["key"]: metric["value"] for metric in groups["milled_faces"]["metrics"]}
    hole_metrics = {metric["key"]: metric["value"] for metric in groups["holes"]["metrics"]}

    assert groove_metrics["outer_diameter_groove_count"] == 1
    assert groove_metrics["end_face_groove_count"] == 1
    assert milled_metrics["circular_milled_face_count"] == 4
    assert hole_metrics["bore_count"] == 3

    detail_metrics = {metric["key"]: metric["value"] for metric in geometry_evidence["detail_metrics"]}
    assert detail_metrics["turned_diameter_faces_count"] == 18
    assert detail_metrics["turned_end_faces_count"] == 4
    assert detail_metrics["turned_profile_faces_count"] == 4


def test_review_v2_geometry_evidence_can_emit_feature_anchors():
    bundle = _bundle()

    response = generate_dfm_review_v2(
        bundle,
        model_id="geometry-evidence-anchor-test",
        component_context={
            "component_node_name": "component_1",
            "component_display_name": "Anchor Part",
            "profile": {
                "material": "Aluminum",
                "manufacturingProcess": "CNC Machining",
                "industry": "Aerospace",
            },
            "geometry_feature_inventory": {
                "face_inventory": [
                    {
                        "face_index": 7,
                        "centroid_mm": [10.0, 20.0, 30.0],
                        "bbox_bounds": [8.0, 18.0, 28.0, 12.0, 22.0, 32.0],
                        "sample_point_mm": [10.0, 20.0, 30.0],
                        "sample_normal": [0.0, 0.0, 1.0],
                    },
                    {
                        "face_index": 8,
                        "centroid_mm": [40.0, 25.0, 15.0],
                        "bbox_bounds": [38.0, 23.0, 13.0, 42.0, 27.0, 17.0],
                        "sample_point_mm": [40.0, 25.0, 15.0],
                        "sample_normal": [1.0, 0.0, 0.0],
                    },
                ],
                "turning_detection": {
                    "primary_cluster": {"face_indices": [8]},
                    "turned_diameter_groups": [{"face_indices": [8]}],
                    "turned_end_face_indices": [8],
                    "outer_diameter_groove_groups": [],
                    "end_face_groove_groups": [],
                },
                "hole_detection": {
                    "candidates": [
                        {
                            "face_index": 7,
                            "group_face_indices": [7],
                            "bbox_bounds": [8.0, 18.0, 28.0, 12.0, 22.0, 32.0],
                            "subtype": "bore",
                        }
                    ]
                },
                "pocket_detection": {
                    "open_pocket_feature_groups": [],
                    "closed_pocket_feature_groups": [],
                },
                "boss_detection": {"candidates": []},
                "milled_face_detection": {"face_indices": []},
            },
        },
        planning_inputs={
            "extracted_part_facts": {
                "rotational_symmetry": True,
                "turned_face_count": 1,
                "turned_diameter_faces_count": 1,
                "hole_count": 1,
                "bore_count": 1,
            },
            "analysis_mode": "geometry_dfm",
            "selected_process_override": None,
            "selected_overlay": None,
            "process_selection_mode": "auto",
            "overlay_selection_mode": "none",
            "selected_role": "general_dfm",
            "selected_template": "executive_1page",
            "run_both_if_mismatch": False,
        },
        context_payload={},
    )

    geometry_evidence = response["geometry_evidence"]
    groups = {entry["group_id"]: entry for entry in geometry_evidence["feature_groups"]}

    turning_anchor = next(
        metric["geometry_anchor"]
        for metric in groups["turning"]["metrics"]
        if metric["key"] == "turned_face_count"
    )
    bore_anchor = next(
        metric["geometry_anchor"]
        for metric in groups["holes"]["metrics"]
        if metric["key"] == "bore_count"
    )

    assert turning_anchor["component_node_name"] == "component_1"
    assert turning_anchor["face_indices"] == [8]
    assert turning_anchor["position_mm"] == [40.0, 25.0, 15.0]

    assert bore_anchor["component_node_name"] == "component_1"
    assert bore_anchor["face_indices"] == [7]
    assert bore_anchor["bbox_bounds_mm"] == [8.0, 18.0, 28.0, 12.0, 22.0, 32.0]


def test_review_v2_response_includes_effective_context_when_provided():
    bundle = _bundle()
    response = generate_dfm_review_v2(
        bundle,
        model_id="model-effective-context",
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
        context_payload={},
        effective_context={
            "process": {"source": "profile_mapped"},
            "overlay": {"source": "profile_mapped"},
        },
    )

    assert response["effective_context"] == {
        "analysis_mode": {
            "selected_mode": "full",
            "source": "execution_plans_default",
        },
        "process": {"source": "profile_mapped"},
        "overlay": {"source": "profile_mapped"},
    }


def test_review_v2_geometry_mode_filters_drawing_spec_rules():
    bundle = _bundle()
    response = generate_dfm_review_v2(
        bundle,
        model_id="model-geometry-mode",
        component_context={
            "component_node_name": "component_1",
            "component_display_name": "Part 1",
            "profile": {
                "material": "Aluminum",
                "manufacturingProcess": "CNC Milling",
                "industry": "Food Machinery and Hygienic Design",
            },
        },
        planning_inputs={
            "analysis_mode": "geometry_dfm",
            "extracted_part_facts": {
                "material_spec": "Aluminum",
                "part_bounding_box": True,
                "bbox_x_mm": 200.0,
                "bbox_y_mm": 120.0,
                "bbox_z_mm": 60.0,
                "pocket_depth": True,
                "pocket_corner_radius": True,
                "max_pocket_depth_mm": 25.0,
                "min_internal_radius_mm": 0.0,
                "radii_set": True,
                "geometry_features": True,
            },
            "selected_process_override": "cnc_milling",
            "selected_overlay": "food",
            "selected_role": "general_dfm",
            "selected_template": "executive_1page",
            "run_both_if_mismatch": False,
        },
        context_payload={},
    )

    route = response["routes"][0]
    assert route["analysis_mode"] == "geometry_dfm"
    assert all(not finding["rule_id"].startswith("SPEC-") for finding in route["findings"])
    assert all(
        "drawing_" not in ",".join(finding.get("evidence", {}).get("missing_inputs", []))
        for finding in route["findings"]
    )
    trace = {entry["ref_id"]: entry for entry in response.get("standards_trace_union", [])}
    assert "REF-HYG-1" in trace
    assert trace["REF-HYG-1"]["active_in_mode"] is True
    assert trace["REF-HYG-1"]["design_risk_findings"] >= 1
    assert "REF-FOOD-EN" in trace
    assert trace["REF-FOOD-EN"]["active_in_mode"] is False


def test_review_v2_zero_corner_radius_is_reported_as_violation():
    bundle = _bundle()
    context_payload = _all_required_facts(bundle, ["A_DRAWING", "B_CNC"])
    context_payload.update(
        {
            "wall_thickness_map": True,
            "material_spec": "Aluminum",
            "min_wall_thickness": 2.0,
            "pocket_depth": True,
            "pocket_corner_radius": True,
            "max_pocket_depth_mm": 25.0,
            "min_internal_radius_mm": 0.0,
            "part_bounding_box": True,
            "bbox_x_mm": 150.0,
            "bbox_y_mm": 80.0,
            "bbox_z_mm": 40.0,
            "hole_features": True,
            "hole_depth": 8.0,
            "hole_diameter": 4.0,
            "radii_set": True,
            "unique_internal_radius_count": 2,
            "radius_variation_ratio": 1.2,
            "long_reach_tool_risk_count": 1,
            "max_depth_to_radius_ratio": 9.0,
        }
    )

    response = generate_dfm_review_v2(
        bundle,
        model_id="model-radius-zero",
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
                "pack_ids": ["A_DRAWING", "B_CNC"],
                "overlay_id": None,
                "role_id": "general_dfm",
                "template_id": "executive_1page",
            }
        ],
        context_payload=context_payload,
    )

    violations = [
        finding
        for finding in response["routes"][0]["findings"]
        if finding.get("finding_type") == "rule_violation"
    ]
    assert any(finding.get("rule_id") == "CNC-005" for finding in violations)


def test_review_v2_pilot_findings_include_traceable_source_fields():
    bundle = _bundle()
    response = generate_dfm_review_v2(
        bundle,
        model_id="model-pilot-trace-fields",
        component_context={
            "component_node_name": "component_1",
            "component_display_name": "Part 1",
            "profile": {
                "material": "Aluminum",
                "manufacturingProcess": "CNC Milling",
                "industry": "Aerospace",
            },
        },
        planning_inputs={
            "extracted_part_facts": {},
            "analysis_mode": "geometry_dfm",
            "selected_process_override": "cnc_milling",
            "selected_overlay": "pilot_prototype",
            "process_selection_mode": "override",
            "overlay_selection_mode": "override",
            "selected_role": "general_dfm",
            "selected_template": "executive_1page",
            "run_both_if_mismatch": False,
        },
        context_payload={},
    )

    pilot_findings = [
        finding
        for finding in response["routes"][0]["findings"]
        if str(finding.get("rule_id", "")).startswith("PSTD-")
    ]
    assert pilot_findings, "Expected pilot findings from the pilot overlay."
    assert any(
        str(finding.get("source_rule_id", "")).startswith("PILOTSTD-")
        for finding in pilot_findings
    )


def test_review_v2_pilot_geometry_rules_emit_rule_violations_when_inputs_present():
    bundle = _bundle()
    response = generate_dfm_review_v2(
        bundle,
        model_id="model-pilot-geometry-violations",
        component_context={
            "component_node_name": "component_1",
            "component_display_name": "Part 1",
            "profile": {
                "material": "Aluminum",
                "manufacturingProcess": "CNC Milling",
                "industry": "Food Machinery and Hygienic Design",
            },
        },
        planning_inputs={
            "extracted_part_facts": {
                "geometry_features": True,
                "hole_features": True,
                "cad.robot_interface.conformance_flag": False,
                "cad.fits.all_pairs_intended_fit_type_met": False,
                "cad.threads.iso228_all_conformant": False,
                "cad.hygienic_design.enclosed_voids_in_product_zone_count": 2,
                "cad.hygienic_design.trapped_volume_count": 1,
                "cad.hygienic_design.crevice_count": 3,
            },
            "analysis_mode": "geometry_dfm",
            "selected_process_override": "cnc_milling",
            "selected_overlay": "pilot_prototype",
            "process_selection_mode": "override",
            "overlay_selection_mode": "override",
            "selected_role": "general_dfm",
            "selected_template": "executive_1page",
            "run_both_if_mismatch": False,
        },
        context_payload={},
    )

    violations = [
        finding
        for finding in response["routes"][0]["findings"]
        if finding.get("finding_type") == "rule_violation"
    ]
    violation_ids = {finding.get("rule_id") for finding in violations}
    assert {"PSTD-001", "PSTD-004", "PSTD-008", "PSTD-009", "PSTD-012", "PSTD-019"}.issubset(
        violation_ids
    )


def test_review_v2_evaluator_registry_includes_phase2_targets():
    expected_targets = {"CNC-004", "CNC-020", "TURN-001", "TURN-004", "PSTD-016"}
    assert expected_targets.issubset(set(RULE_VIOLATION_EVALUATORS.keys()))
    assert len(RULE_VIOLATION_EVALUATORS) >= 24
    pilot_evaluator_count = sum(
        1 for rule_id in RULE_VIOLATION_EVALUATORS.keys() if rule_id.startswith("PSTD-")
    )
    assert pilot_evaluator_count >= 7


def test_phase2_rule_evaluators_return_expected_outcomes():
    cnc_004 = _evaluate_rule_violation(
        {"rule_id": "CNC-004"},
        {"hole_features": True, "blind_hole_flat_bottom_functional": True},
    )
    assert cnc_004 is not None
    assert cnc_004["violated"] is True

    cnc_020 = _evaluate_rule_violation(
        {"rule_id": "CNC-020"},
        {"wall_thickness_map": True, "min_wall_thickness": 0.6, "tight_tolerance_flag": True},
    )
    assert cnc_020 is not None
    assert cnc_020["violated"] is True

    turn_001 = _evaluate_rule_violation(
        {"rule_id": "TURN-001"},
        {"wall_thickness_map": True, "min_wall_thickness": 0.6, "material_spec": "Aluminum 6061"},
    )
    assert turn_001 is not None
    assert turn_001["violated"] is True

    turn_004 = _evaluate_rule_violation(
        {"rule_id": "TURN-004"},
        {"hole_features": True, "hole_diameter": 1.0},
    )
    assert turn_004 is not None
    assert turn_004["violated"] is True

    pstd_016_violation = _evaluate_rule_violation(
        {"rule_id": "PSTD-016"},
        {"material_spec": "Stainless Steel 316L"},
    )
    assert pstd_016_violation is not None
    assert pstd_016_violation["violated"] is True

    pstd_016_pass = _evaluate_rule_violation(
        {"rule_id": "PSTD-016"},
        {"material_spec": "Stainless Steel EN 10088-3 1.4404"},
    )
    assert pstd_016_pass is not None
    assert pstd_016_pass["violated"] is False


def test_review_v2_phase2_geometry_route_emits_new_violations_and_coverage_summary():
    bundle = _bundle()
    response = generate_dfm_review_v2(
        bundle,
        model_id="model-phase2-coverage",
        component_context={
            "component_node_name": "component_1",
            "component_display_name": "Part 1",
            "profile": {
                "material": "Stainless Steel 316L",
                "manufacturingProcess": "CNC Milling",
                "industry": "Food Machinery and Hygienic Design",
            },
        },
        planning_inputs={
            "analysis_mode": "geometry_dfm",
            "extracted_part_facts": {
                "hole_features": True,
                "hole_diameter": 1.0,
                "wall_thickness_map": True,
                "min_wall_thickness": 0.6,
                "material_spec": "Stainless Steel 316L",
                "sheet_thickness": 1.0,
                "blind_hole_flat_bottom_functional": True,
            },
            "selected_process_override": "cnc_milling",
            "selected_overlay": "pilot_prototype",
            "selected_role": "general_dfm",
            "selected_template": "executive_1page",
            "run_both_if_mismatch": False,
        },
        context_payload={},
    )

    route = response["routes"][0]
    violations = {
        finding.get("rule_id")
        for finding in route["findings"]
        if finding.get("finding_type") == "rule_violation"
    }
    assert {"CNC-004", "CNC-020", "TURN-001", "TURN-004", "PSTD-016"}.issubset(violations)

    coverage = route.get("coverage_summary")
    assert isinstance(coverage, dict)
    assert coverage["rules_considered"] >= coverage["checks_evaluated"]
    assert coverage["checks_evaluated"] == coverage["checks_passed"] + coverage["design_risk_findings"]
    assert coverage["rules_considered"] == (
        coverage["checks_evaluated"] + coverage["blocked_by_missing_inputs"] + coverage["checks_unresolved"]
    )
    assert coverage["checks_no_evaluator"] <= coverage["checks_unresolved"]
