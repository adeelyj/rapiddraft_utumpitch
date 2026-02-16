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


def test_load_dfm_bundle_happy_path():
    bundle = load_dfm_bundle()
    assert bundle.manifest["expected_rule_count"] == len(bundle.rule_library["rules"])
    assert bundle.manifest["roles_count"] == len(bundle.roles["roles"])


def test_load_dfm_bundle_missing_required_file(tmp_path: Path):
    bundle_dir = _copy_bundle(tmp_path)
    (bundle_dir / "roles.json").unlink()

    with pytest.raises(DfmBundleValidationError, match="Required DFM file is missing"):
        load_dfm_bundle(bundle_dir=bundle_dir, repo_root=REPO_ROOT)


def test_load_dfm_bundle_invalid_json(tmp_path: Path):
    bundle_dir = _copy_bundle(tmp_path)
    (bundle_dir / "roles.json").write_text("{not-valid-json", encoding="utf-8")

    with pytest.raises(DfmBundleValidationError, match="Invalid JSON"):
        load_dfm_bundle(bundle_dir=bundle_dir, repo_root=REPO_ROOT)


def test_load_dfm_bundle_schema_validation_failure(tmp_path: Path):
    bundle_dir = _copy_bundle(tmp_path)
    roles_payload = json.loads((bundle_dir / "roles.json").read_text(encoding="utf-8"))
    roles_payload["roles"][0]["severity_weights"]["critical"] = "high"
    (bundle_dir / "roles.json").write_text(json.dumps(roles_payload, indent=2), encoding="utf-8")

    with pytest.raises(DfmBundleValidationError, match="Schema validation failed for 'roles.json'"):
        load_dfm_bundle(bundle_dir=bundle_dir, repo_root=REPO_ROOT)
