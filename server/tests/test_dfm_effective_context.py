from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from server.dfm_bundle import load_dfm_bundle
from server.dfm_effective_context import resolve_effective_planning_inputs


def _bundle():
    return load_dfm_bundle(bundle_dir=REPO_ROOT / "server" / "dfm", repo_root=REPO_ROOT)


def test_effective_context_defaults_preserve_backward_compatibility():
    bundle = _bundle()
    resolved, effective = resolve_effective_planning_inputs(
        bundle,
        planning_inputs={
            "extracted_part_facts": {},
            "selected_process_override": None,
            "selected_overlay": None,
            "selected_role": "general_dfm",
            "selected_template": "executive_1page",
            "run_both_if_mismatch": True,
        },
        component_profile={
            "material": "Aluminum",
            "manufacturingProcess": "CNC Milling",
            "industry": "Medical Devices",
        },
    )

    assert resolved["process_selection_mode"] == "auto"
    assert resolved["overlay_selection_mode"] == "none"
    assert resolved["analysis_mode"] == "full"
    assert resolved["selected_process_override"] is None
    assert resolved["selected_overlay"] is None
    assert effective["process"]["source"] == "auto_ai"
    assert effective["overlay"]["source"] == "none"
    assert effective["analysis_mode"]["selected_mode"] == "full"


def test_effective_context_profile_modes_map_profile_values():
    bundle = _bundle()
    resolved, effective = resolve_effective_planning_inputs(
        bundle,
        planning_inputs={
            "extracted_part_facts": {},
            "selected_process_override": None,
            "selected_overlay": None,
            "process_selection_mode": "profile",
            "overlay_selection_mode": "profile",
            "analysis_mode": "geometry_dfm",
            "selected_role": "general_dfm",
            "selected_template": "executive_1page",
            "run_both_if_mismatch": True,
        },
        component_profile={
            "material": "Aluminum",
            "manufacturingProcess": "CNC Milling",
            "industry": "Medical Devices",
        },
    )

    assert resolved["selected_process_override"] == "cnc_milling"
    assert resolved["selected_overlay"] == "medical"
    assert resolved["analysis_mode"] == "geometry_dfm"
    assert effective["process"]["source"] == "profile_mapped"
    assert effective["overlay"]["source"] == "profile_mapped"
    assert effective["analysis_mode"]["source"] == "user_selection"


def test_effective_context_override_modes_use_explicit_selection():
    bundle = _bundle()
    resolved, effective = resolve_effective_planning_inputs(
        bundle,
        planning_inputs={
            "extracted_part_facts": {},
            "selected_process_override": "sheet_metal",
            "selected_overlay": "food",
            "process_selection_mode": "override",
            "overlay_selection_mode": "override",
            "analysis_mode": "drawing_spec",
            "selected_role": "general_dfm",
            "selected_template": "executive_1page",
            "run_both_if_mismatch": True,
        },
        component_profile={
            "material": "Aluminum",
            "manufacturingProcess": "CNC Milling",
            "industry": "Medical Devices",
        },
    )

    assert resolved["selected_process_override"] == "sheet_metal"
    assert resolved["selected_overlay"] == "food"
    assert resolved["analysis_mode"] == "drawing_spec"
    assert effective["process"]["source"] == "user_override"
    assert effective["overlay"]["source"] == "user_override"
