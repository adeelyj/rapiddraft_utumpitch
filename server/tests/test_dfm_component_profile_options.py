from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from server.dfm_bundle import load_dfm_bundle
from server.dfm_planning import build_component_profile_options


def test_component_profile_options_are_derived_from_bundle():
    bundle = load_dfm_bundle(bundle_dir=REPO_ROOT / "server" / "dfm", repo_root=REPO_ROOT)
    options = build_component_profile_options(bundle)

    materials = options.get("materials", [])
    manufacturing_processes = options.get("manufacturingProcesses", [])
    industries = options.get("industries", [])

    assert isinstance(materials, list) and materials
    assert isinstance(manufacturing_processes, list) and manufacturing_processes
    assert isinstance(industries, list) and industries

    process_ids = {entry["id"] for entry in manufacturing_processes}
    assert "cnc_milling" in process_ids
    assert "sheet_metal" in process_ids

    industry_ids = {entry["id"] for entry in industries}
    assert "none" in industry_ids
    assert "medical" in industry_ids
    assert "automotive" in industry_ids


def test_component_profile_industries_include_reference_titles():
    bundle = load_dfm_bundle(bundle_dir=REPO_ROOT / "server" / "dfm", repo_root=REPO_ROOT)
    options = build_component_profile_options(bundle)

    by_id = {entry["id"]: entry for entry in options["industries"]}
    medical = by_id["medical"]
    assert isinstance(medical["standards"], list)
    assert medical["standards"]


def test_component_profile_options_include_legacy_compat_labels():
    bundle = load_dfm_bundle(bundle_dir=REPO_ROOT / "server" / "dfm", repo_root=REPO_ROOT)
    options = build_component_profile_options(bundle)

    process_labels = {entry["label"] for entry in options["manufacturingProcesses"]}
    assert "Sheet Metal Fabrication" in process_labels
    assert "Welding & Fabrication" in process_labels

    material_labels = {entry["label"] for entry in options["materials"]}
    assert "Aluminum" in material_labels
    assert "Stainless Steel" in material_labels
