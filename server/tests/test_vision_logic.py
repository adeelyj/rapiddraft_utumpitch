from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from server.vision_analysis import (  # noqa: E402
    _build_customer_output,
    _build_part_facts_prompt_context,
    _build_prompt,
    _filter_findings_by_criteria,
    _parse_model_output_as_json,
    VisionCriteria,
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


def test_normalize_provider_result_preserves_optional_structured_fields():
    normalized = normalize_provider_result(
        {
            "flagged_features": [
                {
                    "description": "Tight internal corner",
                    "severity": "warning",
                    "confidence": "high",
                    "refs": [" REF-CNC-2 ", "", "REF-CNC-2"],
                    "geometry_anchor": {"feature": " pocket ", "view": " x "},
                    "evidence_quality": "high",
                }
            ],
            "general_observations": "Structured fields present.",
            "confidence": "high",
        },
        fallback_view="x",
    )

    finding = normalized["flagged_features"][0]
    assert finding["refs"] == ["REF-CNC-2"]
    assert finding["geometry_anchor"] == {"feature": "pocket", "view": "x"}
    assert finding["evidence_quality"] == "high"


def test_merge_and_filter_keep_optional_structured_fields():
    merged = merge_view_results(
        [
            {
                "view_name": "x",
                "confidence": "high",
                "general_observations": "X notes.",
                "flagged_features": [
                    {
                        "description": "Deep pocket corner risk",
                        "severity": "warning",
                        "confidence": "high",
                        "refs": ["REF-CNC-2"],
                        "geometry_anchor": {"feature": "pocket", "view": "x"},
                        "evidence_quality": "high",
                    }
                ],
            },
            {
                "view_name": "y",
                "confidence": "high",
                "general_observations": "Y notes.",
                "flagged_features": [
                    {
                        "description": "Deep pocket corner risk",
                        "severity": "critical",
                        "confidence": "high",
                        "refs": ["REF-CNC-7"],
                        "evidence_quality": "medium",
                    }
                ],
            },
        ]
    )

    filtered = _filter_findings_by_criteria(
        findings=merged["flagged_features"],
        report_confidence=merged["confidence"],
        criteria=VisionCriteria(confidence_threshold="low"),
    )

    finding = filtered[0]
    assert finding["refs"] == ["REF-CNC-2", "REF-CNC-7"]
    assert finding["geometry_anchor"] == {"feature": "pocket", "view": "x"}
    assert finding["evidence_quality"] == "low"


def test_build_part_facts_prompt_context_extracts_core_signals():
    payload = {
        "overall_confidence": "medium",
        "coverage": {
            "full_rule_readiness_coverage": {
                "percent": 32.1,
            }
        },
        "sections": {
            "declared_context": {
                "material": {
                    "state": "declared",
                    "value": "Stainless Steel",
                    "unit": None,
                },
                "manufacturing_process": {
                    "state": "declared",
                    "value": "CNC Machining",
                    "unit": None,
                },
                "industry": {
                    "state": "declared",
                    "value": "Food Machinery and Hygienic Design",
                    "unit": None,
                },
            },
            "manufacturing_signals": {
                "min_internal_radius_mm": {
                    "state": "measured",
                    "value": 0.8,
                    "unit": "mm",
                },
                "max_depth_to_radius_ratio": {
                    "state": "measured",
                    "value": 4.2,
                    "unit": None,
                },
                "pockets_present": {
                    "state": "inferred",
                    "value": True,
                    "unit": None,
                },
            },
        },
    }

    lines = _build_part_facts_prompt_context(payload)

    assert any("Declared context:" in line for line in lines)
    assert any("min_internal_radius" in line for line in lines)
    assert any("PartFacts quality:" in line for line in lines)


def test_build_prompt_includes_selected_image_manifest_and_part_facts_context():
    prompt = _build_prompt(
        criteria=VisionCriteria(),
        component_node_name="component_1",
        selected_image_labels=["Mesh TOP", "Screenshot 1"],
        part_facts_context_lines=["Declared context: material=Stainless Steel"],
    )

    assert "Image labels provided for this run:" in prompt
    assert "- Mesh TOP" in prompt
    assert "- Screenshot 1" in prompt
    assert "PartFacts context (use as priors, not direct visual evidence):" in prompt
    assert "Declared context: material=Stainless Steel" in prompt


def test_build_customer_output_adds_customer_summary_and_actions():
    payload = _build_customer_output(
        findings=[
            {
                "feature_id": "V1",
                "description": "Sharp internal pocket corners without radius",
                "severity": "critical",
                "confidence": "medium",
                "source_views": ["x", "z"],
                "refs": ["REF-CNC-2"],
            }
        ],
        report_confidence="medium",
        general_observations="Visual evidence indicates sharp internal corners.",
    )

    summary = payload["summary"]
    finding = payload["findings"][0]

    assert summary["status"] == "critical"
    assert summary["confidence"] == "medium"
    assert summary["risk_counts"]["critical"] == 1
    assert "recommended_next_step" in summary

    assert finding["finding_id"] == "V1"
    assert finding["severity"] == "critical"
    assert finding["source_views"] == ["x", "z"]
    assert "recommended_action" in finding
    assert "why_it_matters" in finding
