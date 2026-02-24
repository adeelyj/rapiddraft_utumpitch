from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from server.vision_analysis import (  # noqa: E402
    _parse_model_output_as_json,
    merge_view_results,
    normalize_provider_result,
    parse_vision_criteria,
)


def test_parse_vision_criteria_normalizes_invalid_values():
    criteria = parse_vision_criteria(
        {
            "checks": {
                "internal_pocket_tight_corners": False,
                "tool_access_risk": True,
                "annotation_note_scan": "bad",
            },
            "sensitivity": "invalid",
            "max_flagged_features": 999,
            "confidence_threshold": "high",
        }
    )

    assert criteria.check_internal_pocket_tight_corners is False
    assert criteria.check_tool_access_risk is True
    assert criteria.check_annotation_note_scan is True
    assert criteria.sensitivity == "medium"
    assert criteria.max_flagged_features == 50
    assert criteria.confidence_threshold == "high"


def test_normalize_provider_result_assigns_view_and_defaults():
    normalized = normalize_provider_result(
        {
            "flagged_features": [
                "Sharp internal corner",
                {
                    "description": "Deep pocket access",
                    "severity": "critical",
                    "confidence": "high",
                },
            ],
            "general_observations": "Two concerns found.",
            "confidence": "medium",
        },
        fallback_view="x",
    )

    assert normalized["confidence"] == "medium"
    assert len(normalized["flagged_features"]) == 2
    assert normalized["flagged_features"][0]["source_views"] == ["x"]
    assert normalized["flagged_features"][1]["severity"] == "critical"


def test_merge_view_results_deduplicates_and_promotes_severity():
    merged = merge_view_results(
        [
            {
                "view_name": "x",
                "confidence": "high",
                "general_observations": "X view notes.",
                "flagged_features": [
                    {
                        "description": "Tight corner near pocket",
                        "severity": "warning",
                        "confidence": "high",
                    }
                ],
            },
            {
                "view_name": "y",
                "confidence": "medium",
                "general_observations": "Y view notes.",
                "flagged_features": [
                    {
                        "description": "Tight corner near pocket",
                        "severity": "critical",
                        "confidence": "medium",
                    },
                    {
                        "description": "Secondary narrow slot",
                        "severity": "caution",
                        "confidence": "medium",
                    },
                ],
            },
        ]
    )

    assert merged["confidence"] == "low"
    assert len(merged["flagged_features"]) == 2
    first = merged["flagged_features"][0]
    assert first["severity"] == "critical"
    assert first["confidence"] == "low"
    assert first["source_views"] == ["x", "y"]
    assert "[x]" in merged["general_observations"]
    assert "[y]" in merged["general_observations"]


def test_parse_model_output_prefers_schema_object_in_mixed_text():
    model_text = """
Reasoning before JSON.
Here is an inner object: {"feature_id": "V_tmp", "description": "not root schema"}.
<think>intermediate thoughts</think>
{
  "flagged_features": [
    {
      "feature_id": "V1",
      "description": "Internal slot corners appear sharp",
      "severity": "critical",
      "confidence": "medium",
      "source_views": ["x", "y"]
    }
  ],
  "general_observations": "Visible tight corners may need radius relief.",
  "confidence": "medium"
}
""".strip()

    parsed = _parse_model_output_as_json(model_text)
    assert isinstance(parsed.get("flagged_features"), list)
    assert len(parsed["flagged_features"]) == 1
    assert parsed["flagged_features"][0]["description"] == "Internal slot corners appear sharp"
    assert parsed["general_observations"] == "Visible tight corners may need radius relief."
    assert parsed["confidence"] == "medium"
