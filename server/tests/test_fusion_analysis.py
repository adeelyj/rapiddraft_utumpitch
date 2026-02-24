from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from server.fusion_analysis import build_fusion_payload  # noqa: E402


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
