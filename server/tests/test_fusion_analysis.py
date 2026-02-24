from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from server.fusion_analysis import (  # noqa: E402
    FusionAnalysisError,
    FusionAnalysisService,
    build_fusion_payload,
    vision_report_matches_component,
)


def _sample_dfm_review() -> dict:
    return {
        "route_count": 1,
        "finding_count_total": 1,
        "standards_trace_union": [{"ref_id": "REF-CNC-2", "title": "CNC guide"}],
        "routes": [
            {
                "plan_id": "plan_1",
                "route_source": "selected",
                "process_id": "cnc_milling",
                "process_label": "CNC Milling",
                "findings": [
                    {
                        "rule_id": "CNC-005",
                        "title": "Pocket internal corners are too sharp",
                        "description": "Small internal radius increases tool length risk.",
                        "severity": "major",
                        "finding_type": "rule_violation",
                        "refs": ["REF-CNC-2"],
                        "recommended_action": "Increase pocket internal radius.",
                    }
                ],
            }
        ],
    }


def _write_vision_report(
    *,
    root: Path,
    model_id: str,
    report_id: str,
    component_node_name: str | None,
) -> None:
    report_dir = root / model_id / "vision_reports" / report_id
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "result.json").write_text(
        json.dumps(
            {
                "report_id": report_id,
                "model_id": model_id,
                "component_node_name": component_node_name,
                "summary": {"flagged_count": 0},
                "findings": [],
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def test_fusion_payload_confirms_overlap_between_dfm_and_vision():
    payload = build_fusion_payload(
        model_id="model_1",
        component_node_name="component_1",
        report_id="fusion_rpt_20260224_001",
        dfm_review=_sample_dfm_review(),
        vision_report={
            "report_id": "vision_rpt_20260224_001",
            "summary": {"flagged_count": 1},
            "findings": [
                {
                    "feature_id": "V1",
                    "description": "Pocket internal corners are too sharp and small internal radius increases tool risk.",
                    "severity": "warning",
                    "confidence": "high",
                    "source_views": ["x", "z"],
                }
            ],
        },
        vision_report_id="vision_rpt_20260224_001",
    )

    assert payload["priority_summary"]["confirmed_count"] == 1
    assert len(payload["confirmed_by_both"]) == 1
    confirmed = payload["confirmed_by_both"][0]
    assert "match_signals" in confirmed
    assert "match_rationale" in confirmed
    assert confirmed["match_signals"]["overall_match_score"] >= confirmed["match_signals"]["threshold"]
    assert payload["source_status"]["vision"] == "available"
    assert payload["standards_trace_union"] == [{"ref_id": "REF-CNC-2", "title": "CNC guide"}]


def test_fusion_payload_handles_missing_vision_report():
    payload = build_fusion_payload(
        model_id="model_1",
        component_node_name="component_1",
        report_id="fusion_rpt_20260224_001",
        dfm_review=_sample_dfm_review(),
        vision_report={},
        vision_report_id=None,
    )

    assert payload["priority_summary"]["confirmed_count"] == 0
    assert payload["priority_summary"]["dfm_only_count"] == 1
    assert payload["priority_summary"]["vision_only_count"] == 0
    assert payload["source_status"]["vision"] == "missing"
    assert payload["source_reports"]["vision_report_id"] is None


def test_fusion_payload_respects_custom_tuning_threshold():
    payload = build_fusion_payload(
        model_id="model_1",
        component_node_name="component_1",
        report_id="fusion_rpt_20260224_001",
        dfm_review=_sample_dfm_review(),
        vision_report={
            "report_id": "vision_rpt_20260224_001",
            "summary": {"flagged_count": 1},
            "findings": [
                {
                    "feature_id": "V1",
                    "description": "Pocket internal corners are too sharp and small internal radius increases tool risk.",
                    "severity": "warning",
                    "confidence": "high",
                    "source_views": ["x", "z"],
                }
            ],
        },
        vision_report_id="vision_rpt_20260224_001",
        fusion_tuning={
            "threshold": 0.95,
            "weight_semantic": 0.6,
            "weight_refs": 0.25,
            "weight_geometry": 0.15,
        },
    )

    assert payload["tuning_applied"]["threshold"] == 0.95
    assert payload["priority_summary"]["confirmed_count"] == 0
    assert payload["priority_summary"]["dfm_only_count"] == 1
    assert payload["dfm_only"][0]["match_signals"]["threshold"] == 0.95


def test_fusion_payload_rejects_invalid_tuning():
    with pytest.raises(FusionAnalysisError):
        build_fusion_payload(
            model_id="model_1",
            component_node_name="component_1",
            report_id="fusion_rpt_20260224_001",
            dfm_review=_sample_dfm_review(),
            vision_report={},
            vision_report_id=None,
            fusion_tuning={
                "threshold": 1.2,
            },
        )


def test_fusion_payload_includes_analysis_run_id_when_provided():
    payload = build_fusion_payload(
        model_id="model_1",
        component_node_name="component_1",
        report_id="fusion_rpt_20260224_099",
        dfm_review=_sample_dfm_review(),
        vision_report={},
        vision_report_id=None,
        analysis_run_id="analysis_run_20260224_001",
    )

    assert payload["analysis_run_id"] == "analysis_run_20260224_001"


def test_fusion_payload_uses_refs_and_geometry_anchor_signals_for_confirmed_matching():
    payload = build_fusion_payload(
        model_id="model_1",
        component_node_name="component_1",
        report_id="fusion_rpt_20260224_001",
        dfm_review=_sample_dfm_review(),
        vision_report={
            "report_id": "vision_rpt_20260224_002",
            "summary": {"flagged_count": 1},
            "findings": [
                {
                    "feature_id": "V2",
                    "description": "General manufacturability concern.",
                    "severity": "warning",
                    "confidence": "medium",
                    "refs": ["REF-CNC-2"],
                    "source_views": ["x"],
                    "geometry_anchor": {"feature": "pocket", "view": "x"},
                }
            ],
        },
        vision_report_id="vision_rpt_20260224_002",
    )

    assert payload["priority_summary"]["confirmed_count"] == 1
    confirmed = payload["confirmed_by_both"][0]
    assert confirmed["match_signals"]["refs_overlap_count"] == 1
    assert confirmed["match_signals"]["geometry_anchor_score"] > 0
    assert "shared refs" in confirmed["match_rationale"].lower()


def test_fusion_payload_dfm_only_emits_partial_match_rationale_when_below_threshold():
    payload = build_fusion_payload(
        model_id="model_1",
        component_node_name="component_1",
        report_id="fusion_rpt_20260224_003",
        dfm_review=_sample_dfm_review(),
        vision_report={
            "report_id": "vision_rpt_20260224_003",
            "summary": {"flagged_count": 1},
            "findings": [
                {
                    "feature_id": "V3",
                    "description": "Visual scratch on non-critical exterior face.",
                    "severity": "info",
                    "confidence": "low",
                    "source_views": ["z"],
                }
            ],
        },
        vision_report_id="vision_rpt_20260224_003",
    )

    assert payload["priority_summary"]["confirmed_count"] == 0
    assert payload["priority_summary"]["dfm_only_count"] == 1
    dfm_only_entry = payload["dfm_only"][0]
    assert dfm_only_entry["match_signals"]["overall_match_score"] < dfm_only_entry["match_signals"]["threshold"]
    assert "exceeded threshold" in dfm_only_entry["match_rationale"].lower()


def test_fusion_payload_vision_only_emits_partial_match_rationale_when_unmatched():
    payload = build_fusion_payload(
        model_id="model_1",
        component_node_name="component_1",
        report_id="fusion_rpt_20260224_004",
        dfm_review={
            "route_count": 0,
            "finding_count_total": 0,
            "standards_trace_union": [],
            "routes": [],
        },
        vision_report={
            "report_id": "vision_rpt_20260224_004",
            "summary": {"flagged_count": 1},
            "findings": [
                {
                    "feature_id": "V4",
                    "description": "Potential burr near edge.",
                    "severity": "warning",
                    "confidence": "medium",
                    "source_views": ["x"],
                }
            ],
        },
        vision_report_id="vision_rpt_20260224_004",
    )

    assert payload["priority_summary"]["vision_only_count"] == 1
    vision_only_entry = payload["vision_only"][0]
    assert vision_only_entry["match_signals"]["overall_match_score"] == 0
    assert "exceeded threshold" in vision_only_entry["match_rationale"].lower()


def test_latest_vision_report_id_is_component_scoped(tmp_path: Path):
    service = FusionAnalysisService(root=tmp_path)
    model_id = "model_1"
    _write_vision_report(
        root=tmp_path,
        model_id=model_id,
        report_id="vision_rpt_20260224_001",
        component_node_name="component_a",
    )
    _write_vision_report(
        root=tmp_path,
        model_id=model_id,
        report_id="vision_rpt_20260224_002",
        component_node_name="component_b",
    )
    _write_vision_report(
        root=tmp_path,
        model_id=model_id,
        report_id="vision_rpt_20260224_003",
        component_node_name="component_a",
    )

    assert service.latest_vision_report_id(model_id) == "vision_rpt_20260224_003"
    assert service.latest_vision_report_id(model_id, component_node_name="component_a") == "vision_rpt_20260224_003"
    assert service.latest_vision_report_id(model_id, component_node_name="component_b") == "vision_rpt_20260224_002"
    assert service.latest_vision_report_id(model_id, component_node_name="component_c") is None


def test_latest_vision_report_id_skips_invalid_payloads(tmp_path: Path):
    service = FusionAnalysisService(root=tmp_path)
    model_id = "model_1"
    _write_vision_report(
        root=tmp_path,
        model_id=model_id,
        report_id="vision_rpt_20260224_001",
        component_node_name="component_a",
    )
    invalid_report_dir = tmp_path / model_id / "vision_reports" / "vision_rpt_20260224_002"
    invalid_report_dir.mkdir(parents=True, exist_ok=True)
    (invalid_report_dir / "result.json").write_text("{ not-json", encoding="utf-8")

    assert service.latest_vision_report_id(model_id, component_node_name="component_a") == "vision_rpt_20260224_001"


def test_fusion_service_persists_analysis_run_id_in_report_artifacts(tmp_path: Path):
    service = FusionAnalysisService(root=tmp_path)

    payload = service.create_report(
        model_id="model_1",
        component_node_name="component_1",
        dfm_review=_sample_dfm_review(),
        vision_report={},
        vision_report_id=None,
        analysis_run_id="analysis_run_20260224_007",
    )

    assert payload["analysis_run_id"] == "analysis_run_20260224_007"
    report_dir = tmp_path / "model_1" / "fusion_reports" / payload["report_id"]
    persisted_result = json.loads((report_dir / "result.json").read_text(encoding="utf-8"))
    persisted_request = json.loads((report_dir / "request.json").read_text(encoding="utf-8"))
    assert persisted_result["analysis_run_id"] == "analysis_run_20260224_007"
    assert persisted_request["analysis_run_id"] == "analysis_run_20260224_007"


def test_vision_report_matches_component_requires_explicit_scope_for_component_queries():
    assert vision_report_matches_component(
        vision_report={"component_node_name": "component_1"},
        component_node_name="component_1",
    )
    assert not vision_report_matches_component(
        vision_report={},
        component_node_name="component_1",
    )
    assert vision_report_matches_component(
        vision_report={},
        component_node_name=None,
    )
