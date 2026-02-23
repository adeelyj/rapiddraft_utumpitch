from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from server.dfm_bundle import load_dfm_bundle
from server.dfm_planning import build_dfm_config


def test_dfm_config_contract_from_bundle():
    bundle = load_dfm_bundle(bundle_dir=REPO_ROOT / "server" / "dfm", repo_root=REPO_ROOT)
    payload = build_dfm_config(bundle)

    assert isinstance(payload.get("bundle"), dict)
    assert isinstance(payload["bundle"].get("version"), str)
    assert isinstance(payload["bundle"].get("generated_at"), str)

    assert isinstance(payload.get("processes"), list) and payload["processes"]
    assert isinstance(payload.get("overlays"), list) and payload["overlays"]
    assert isinstance(payload.get("roles"), list) and payload["roles"]
    assert isinstance(payload.get("templates"), list) and payload["templates"]
    assert isinstance(payload.get("packs"), list) and payload["packs"]
    assert isinstance(payload.get("profile_options"), dict)
    assert isinstance(payload["profile_options"].get("materials"), list) and payload["profile_options"]["materials"]
    assert isinstance(payload["profile_options"].get("manufacturingProcesses"), list)
    assert isinstance(payload["profile_options"].get("industries"), list)

    process_ids = {item["process_id"] for item in payload["processes"]}
    assert "cnc_milling" in process_ids
    assert "sheet_metal" in process_ids

    overlay_ids = {item["overlay_id"] for item in payload["overlays"]}
    assert "medical" in overlay_ids
    assert "automotive" in overlay_ids


def test_dfm_config_has_expected_ui_flow_order():
    bundle = load_dfm_bundle(bundle_dir=REPO_ROOT / "server" / "dfm", repo_root=REPO_ROOT)
    payload = build_dfm_config(bundle)

    review_panel = payload["ui_bindings"]["screens"]["dfm_review_panel"]
    flow_order = review_panel["flow_order"]
    assert isinstance(flow_order, list) and flow_order
    assert flow_order[0] == "analysis_mode"
    assert "manufacturing_process" in flow_order
    assert "run_both_if_mismatch" in flow_order
    assert flow_order[-1] == "generate_review"

    controls = review_panel["controls"]
    analysis_control = next(
        (control for control in controls if control.get("control_id") == "analysis_mode"),
        None,
    )
    assert analysis_control is not None
    assert analysis_control.get("default") == "geometry_dfm"


def test_dfm_primary_routes_present_and_legacy_routes_removed():
    main_source = (REPO_ROOT / "server" / "main.py").read_text(encoding="utf-8")

    assert '@app.get("/api/dfm/config")' in main_source
    assert '@app.post("/api/dfm/plan")' in main_source
    assert '@app.post("/api/models/{model_id}/dfm/review-v2")' in main_source

    assert '@app.get("/api/dfm/profile-options")' not in main_source
    assert '@app.get("/api/dfm/rule-sets")' not in main_source
    assert '@app.post("/api/models/{model_id}/dfm/review")' not in main_source
    assert '@app.post("/api/dfm/review")' not in main_source
    assert "dfm_profile_options.json" not in main_source
    assert "from .dfm_review import" not in main_source


def test_legacy_dfm_module_is_removed():
    assert not (REPO_ROOT / "server" / "dfm_review.py").exists()
