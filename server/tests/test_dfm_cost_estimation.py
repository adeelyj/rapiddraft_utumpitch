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


def _component_context():
    return {
        "component_node_name": "component_1",
        "component_display_name": "Part 1",
        "profile": {
            "material": "Aluminum",
            "manufacturingProcess": "Sheet Metal Fabrication",
            "industry": "Medical Devices",
        },
        "triangle_count": 2800,
    }


def test_review_v2_single_route_contains_cost_estimate():
    bundle = _bundle()
    response = generate_dfm_review_v2(
        bundle,
        model_id="model-cost-single",
        component_context=_component_context(),
        planning_inputs={
            "extracted_part_facts": {
                "bends_present": True,
                "constant_thickness": True,
                "sheet_thickness": 2.0,
            },
            "selected_process_override": None,
            "selected_overlay": "medical",
            "selected_role": "quality_engineer",
            "selected_template": "medical_design_review",
            "run_both_if_mismatch": True,
        },
        context_payload={"quantity": 5},
    )

    assert response["cost_estimate"] is not None
    assert response["cost_estimate"]["unit_cost"] > 0
    assert response["cost_estimate"]["total_cost"] > 0
    assert len(response["cost_estimate_by_route"]) == 1
    assert response["routes"][0]["cost_estimate"] is not None
    assert response["routes"][0]["report_skeleton"]["cost_summary"] is not None
    assert isinstance(response["routes"][0]["report_skeleton"]["cost_drivers"], list)


def test_review_v2_run_both_includes_route_cost_delta():
    bundle = _bundle()
    response = generate_dfm_review_v2(
        bundle,
        model_id="model-cost-run-both",
        component_context=_component_context(),
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
        context_payload={"quantity": 3},
    )

    assert response["mismatch"]["run_both_executed"] is True
    assert len(response["cost_estimate_by_route"]) == 2
    assert response["cost_compare_routes"] is not None
    assert response["cost_compare_routes"]["baseline_plan_id"] == response["cost_estimate_by_route"][0]["plan_id"]
    assert response["cost_compare_routes"]["compare_plan_id"] == response["cost_estimate_by_route"][1]["plan_id"]


def test_missing_supplier_rates_and_geometry_degrade_confidence_without_failure():
    bundle = _bundle()
    with_supplier = generate_dfm_review_v2(
        bundle,
        model_id="model-cost-with-supplier",
        component_context=_component_context(),
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
        context_payload={
            "quantity": 1,
            "supplier_cost_profile": {
                "process_overrides": {
                    "cnc_milling": {
                        "hourly_rate": 92.0,
                        "setup_cost": 110.0,
                        "scrap_factor": 0.03,
                    }
                }
            },
        },
    )
    degraded = generate_dfm_review_v2(
        bundle,
        model_id="model-cost-degraded",
        component_context={
            "component_node_name": "component_1",
            "component_display_name": "Part 1",
            "profile": {},
            "triangle_count": None,
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
        context_payload={},
    )

    assert degraded["cost_estimate"] is not None
    assert degraded["cost_estimate"]["unit_cost"] > 0
    assert degraded["cost_estimate"]["confidence"] < with_supplier["cost_estimate"]["confidence"]
    assert degraded["cost_estimate"]["assumptions"]
