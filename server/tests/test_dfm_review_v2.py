from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

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
