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


def test_cost_model_schema_happy_path():
    bundle = load_dfm_bundle(bundle_dir=REPO_ROOT / "server" / "dfm", repo_root=REPO_ROOT)
    assert bundle.cost_model["currency"] == "USD"
    assert "process_models" in bundle.cost_model


def test_cost_model_schema_rejects_invalid_currency(tmp_path: Path):
    bundle_dir = _copy_bundle(tmp_path)
    payload = json.loads((bundle_dir / "cost_model.json").read_text(encoding="utf-8"))
    payload["currency"] = "usd"
    (bundle_dir / "cost_model.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")

    with pytest.raises(DfmBundleValidationError, match="Schema validation failed for 'cost_model.json'"):
        load_dfm_bundle(bundle_dir=bundle_dir, repo_root=REPO_ROOT)


def test_cost_model_schema_rejects_missing_process_field(tmp_path: Path):
    bundle_dir = _copy_bundle(tmp_path)
    payload = json.loads((bundle_dir / "cost_model.json").read_text(encoding="utf-8"))
    payload["process_models"]["cnc_milling"].pop("hourly_rate", None)
    (bundle_dir / "cost_model.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")

    with pytest.raises(DfmBundleValidationError, match="Schema validation failed for 'cost_model.json'"):
        load_dfm_bundle(bundle_dir=bundle_dir, repo_root=REPO_ROOT)
