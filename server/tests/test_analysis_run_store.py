from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from server.analysis_runs import AnalysisRunNotFoundError, AnalysisRunStore  # noqa: E402


def _sample_dfm_review() -> dict:
    return {
        "route_count": 1,
        "finding_count_total": 2,
        "created_at": "2026-02-24T10:00:00Z",
        "routes": [],
    }


def _sample_fusion_report() -> dict:
    return {
        "report_id": "fusion_rpt_20260224_001",
        "created_at": "2026-02-24T10:01:00Z",
    }


def test_create_and_get_manifest_persists_dfm_snapshot(tmp_path: Path):
    store = AnalysisRunStore(root=tmp_path)
    model_id = "model_1"
    analysis_run_id = "analysis_run_20260224_001"

    manifest = store.create_manifest(
        model_id=model_id,
        analysis_run_id=analysis_run_id,
        component_node_name="component_1",
        dfm_review=_sample_dfm_review(),
        vision_report_id="vision_rpt_20260224_003",
        vision_report={"created_at": "2026-02-24T09:59:00Z"},
        fusion_report=_sample_fusion_report(),
    )

    assert manifest["analysis_run_id"] == analysis_run_id
    assert manifest["artifacts"]["dfm"]["report_id"] == f"dfm_snapshot_{analysis_run_id}"
    assert manifest["artifacts"]["vision"]["report_id"] == "vision_rpt_20260224_003"
    assert manifest["artifacts"]["fusion"]["report_id"] == "fusion_rpt_20260224_001"

    run_dir = tmp_path / model_id / "analysis_runs" / analysis_run_id
    assert (run_dir / "manifest.json").exists()
    assert (run_dir / "dfm_review.json").exists()

    loaded = store.get_manifest(model_id=model_id, analysis_run_id=analysis_run_id)
    assert loaded["api_links"]["analysis_run"] == f"/api/models/{model_id}/analysis-runs/{analysis_run_id}"
    assert loaded["artifacts"]["dfm"]["finding_count_total"] == 2


def test_next_analysis_run_id_increments(tmp_path: Path):
    store = AnalysisRunStore(root=tmp_path)
    model_id = "model_1"

    first_id = store.next_analysis_run_id(model_id)
    assert re.match(r"^analysis_run_\d{8}_001$", first_id)

    store.create_manifest(
        model_id=model_id,
        analysis_run_id=first_id,
        component_node_name="component_1",
        dfm_review=_sample_dfm_review(),
        vision_report_id=None,
        vision_report=None,
        fusion_report=_sample_fusion_report(),
    )
    second_id = store.next_analysis_run_id(model_id)
    assert second_id.endswith("_002")


def test_get_manifest_raises_when_missing(tmp_path: Path):
    store = AnalysisRunStore(root=tmp_path)
    with pytest.raises(AnalysisRunNotFoundError):
        store.get_manifest(model_id="model_1", analysis_run_id="analysis_run_20260224_999")

