from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from server.dfm_bundle import load_dfm_bundle
from server.dfm_planning import DfmPlanningError, plan_dfm_execution


def _bundle():
    return load_dfm_bundle(bundle_dir=REPO_ROOT / "server" / "dfm", repo_root=REPO_ROOT)


def _base_request_payload() -> dict:
    return {
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
    }


def test_plan_contract_is_deterministic_for_same_inputs():
    bundle = _bundle()
    payload = _base_request_payload()

    first = plan_dfm_execution(bundle, **payload)
    second = plan_dfm_execution(bundle, **payload)

    assert first == second
    assert first["ai_recommendation"]["process_id"] == "sheet_metal"
    assert first["mismatch"]["has_mismatch"] is False
    assert len(first["execution_plans"]) == 1
    assert first["selected_packs"] == ["A_DRAWING", "C_SHEET", "E_ASSEMBLY", "F_OVERLAY"]


def test_plan_contract_runs_both_routes_when_mismatch_enabled():
    bundle = _bundle()
    payload = _base_request_payload()
    payload["selected_process_override"] = "cnc_milling"
    payload["run_both_if_mismatch"] = True

    response_payload = plan_dfm_execution(bundle, **payload)

    assert response_payload["mismatch"]["has_mismatch"] is True
    assert response_payload["mismatch"]["run_both_executed"] is True
    assert len(response_payload["execution_plans"]) == 2
    assert response_payload["execution_plans"][0]["process_id"] == "cnc_milling"
    assert response_payload["execution_plans"][1]["process_id"] == "sheet_metal"


def test_plan_contract_uses_single_route_when_run_both_disabled():
    bundle = _bundle()
    payload = _base_request_payload()
    payload["selected_process_override"] = "cnc_milling"
    payload["run_both_if_mismatch"] = False

    response_payload = plan_dfm_execution(bundle, **payload)

    assert response_payload["mismatch"]["has_mismatch"] is True
    assert response_payload["mismatch"]["run_both_executed"] is False
    assert len(response_payload["execution_plans"]) == 1
    assert response_payload["execution_plans"][0]["process_id"] == "cnc_milling"
    assert response_payload["selected_process"]["selected_via"] == "user_override"


def test_plan_contract_only_adds_overlay_pack_when_overlay_selected():
    bundle = _bundle()
    payload = _base_request_payload()
    payload["selected_overlay"] = None

    response_payload = plan_dfm_execution(bundle, **payload)
    assert "F_OVERLAY" not in response_payload["selected_packs"]
    assert response_payload["selected_packs"] == ["A_DRAWING", "C_SHEET", "E_ASSEMBLY"]


def test_plan_contract_rejects_unknown_overlay_id():
    bundle = _bundle()
    payload = copy.deepcopy(_base_request_payload())
    payload["selected_overlay"] = "unknown_overlay"

    with pytest.raises(DfmPlanningError, match="Unknown selected_overlay"):
        plan_dfm_execution(bundle, **payload)
