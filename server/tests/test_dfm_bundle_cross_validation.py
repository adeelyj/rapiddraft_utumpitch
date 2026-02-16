from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from server.dfm_bundle import (  # noqa: E402
    DEFAULT_BUNDLE_DIR,
    DfmBundleValidationError,
    load_dfm_bundle,
)


def _copy_bundle(tmp_path: Path) -> Path:
    destination = tmp_path / "dfm"
    shutil.copytree(DEFAULT_BUNDLE_DIR, destination)
    return destination


def test_cross_validation_detects_missing_reference(tmp_path: Path):
    bundle_dir = _copy_bundle(tmp_path)
    payload = json.loads((bundle_dir / "rule_library.json").read_text(encoding="utf-8"))
    payload["rules"][0]["refs"].append("REF-DOES-NOT-EXIST")
    (bundle_dir / "rule_library.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")

    with pytest.raises(DfmBundleValidationError, match="references missing ref 'REF-DOES-NOT-EXIST'"):
        load_dfm_bundle(bundle_dir=bundle_dir, repo_root=REPO_ROOT)


def test_cross_validation_detects_manifest_count_mismatch(tmp_path: Path):
    bundle_dir = _copy_bundle(tmp_path)
    payload = json.loads((bundle_dir / "manifest.json").read_text(encoding="utf-8"))
    payload["expected_rule_count"] = 999
    (bundle_dir / "manifest.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")

    with pytest.raises(DfmBundleValidationError, match="expected_rule_count=999"):
        load_dfm_bundle(bundle_dir=bundle_dir, repo_root=REPO_ROOT)


def test_cross_validation_detects_process_default_pack_mismatch(tmp_path: Path):
    bundle_dir = _copy_bundle(tmp_path)
    payload = json.loads((bundle_dir / "process_classifier.json").read_text(encoding="utf-8"))
    payload["process_families"][0]["default_packs"].append("Z_UNKNOWN")
    (bundle_dir / "process_classifier.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )

    with pytest.raises(DfmBundleValidationError, match="default pack 'Z_UNKNOWN' does not exist"):
        load_dfm_bundle(bundle_dir=bundle_dir, repo_root=REPO_ROOT)


def test_cross_validation_detects_overlay_requirement_not_present(tmp_path: Path):
    bundle_dir = _copy_bundle(tmp_path)
    overlays_payload = json.loads((bundle_dir / "overlays.json").read_text(encoding="utf-8"))
    overlays_payload["overlays"] = [
        entry for entry in overlays_payload["overlays"] if entry.get("overlay_id") != "automotive"
    ]
    (bundle_dir / "overlays.json").write_text(
        json.dumps(overlays_payload, indent=2), encoding="utf-8"
    )

    with pytest.raises(DfmBundleValidationError, match="requires unknown overlay 'automotive'"):
        load_dfm_bundle(bundle_dir=bundle_dir, repo_root=REPO_ROOT)
