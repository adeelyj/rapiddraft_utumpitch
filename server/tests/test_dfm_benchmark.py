from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from server.dfm_benchmark import (
    SeverityNormalizer,
    _part_facts_warnings,
    adapt_cadex_features_to_facts,
    compare_reasoning_reference,
    extract_cadex_dfm_reference,
    extract_rapiddraft_review_reference,
)


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_adapt_cadex_features_sample_2_maps_core_signals():
    payload = _load_json(
        REPO_ROOT / "benchmark_data" / "dfm_mtk" / "cases" / "sample 2" / "sample2_features.json"
    )

    adapted = adapt_cadex_features_to_facts(
        payload,
        component_profile={"material": "Aluminum", "manufacturingProcess": "", "industry": ""},
    )

    facts = adapted["extracted_part_facts"]
    assert facts["hole_features"] is True
    assert facts["bore_count"] == 1
    assert facts["bore_features"] is True
    assert facts["pockets_present"] is True
    assert facts["open_pocket_count"] == 13
    assert facts["open_pocket_features"] is True
    assert facts["turned_faces_present"] is True
    assert facts["rotational_symmetry"] is True
    assert facts["milled_faces_present"] is True
    assert facts["flat_milled_face_count"] == 29
    assert facts["curved_milled_face_count"] == 16
    assert facts["turned_diameter_faces_count"] == 4
    assert facts["turned_end_faces_count"] == 20
    assert facts["turned_profile_faces_count"] == 1
    assert facts["turned_face_count"] == 25
    assert facts["part_bounding_box"] is True
    assert facts["bbox_x_mm"] == 171.64
    assert facts["bbox_y_mm"] == 171.64
    assert facts["bbox_z_mm"] == 260.06
    assert facts["feature_complexity_score"] == 84
    assert facts["material_spec"] == "Aluminum"


def test_adapt_cadex_features_sample_3_maps_hole_subtypes():
    payload = _load_json(
        REPO_ROOT / "benchmark_data" / "dfm_mtk" / "cases" / "sample 3" / "sample3_features.json"
    )

    adapted = adapt_cadex_features_to_facts(payload)

    facts = adapted["extracted_part_facts"]
    assert facts["hole_features"] is True
    assert facts["through_hole_count"] == 3
    assert facts["partial_hole_count"] == 1
    assert facts["through_hole_features"] is True
    assert facts["partial_hole_features"] is True
    assert facts["closed_pocket_count"] == 1
    assert facts["closed_pocket_features"] is True
    assert facts["boss_count"] == 1
    assert facts["boss_features"] is True
    assert facts["flat_milled_face_count"] == 7
    assert facts["flat_side_milled_face_count"] == 6
    assert facts["curved_milled_face_count"] == 3


def test_adapt_cadex_features_sample_4_maps_convex_profile_edges():
    payload = _load_json(
        REPO_ROOT / "benchmark_data" / "dfm_mtk" / "cases" / "sample 4" / "sample4_features.json"
    )

    adapted = adapt_cadex_features_to_facts(payload)

    facts = adapted["extracted_part_facts"]
    assert facts["convex_profile_edge_milled_face_count"] == 6
    assert facts["convex_profile_edge_milled_faces_present"] is True


def test_adapt_cadex_features_sample_8_maps_stepped_holes_and_edge_taxonomy():
    payload = _load_json(
        REPO_ROOT / "benchmark_data" / "dfm_mtk" / "cases" / "sample 8" / "sample8_features.json"
    )

    adapted = adapt_cadex_features_to_facts(payload)

    facts = adapted["extracted_part_facts"]
    assert facts["through_hole_count"] == 1
    assert facts["stepped_hole_count"] == 7
    assert facts["closed_pocket_count"] == 4
    assert facts["convex_profile_edge_milled_face_count"] == 7
    assert facts["concave_fillet_edge_milled_face_count"] == 14
    assert facts["stepped_hole_features"] is True
    assert facts["concave_fillet_edge_milled_faces_present"] is True


def test_adapt_cadex_features_sample_6_maps_lathe_grooves_and_bores():
    payload = _load_json(
        REPO_ROOT / "benchmark_data" / "dfm_mtk" / "cases" / "sample 6" / "sample6_features.json"
    )

    adapted = adapt_cadex_features_to_facts(payload)

    facts = adapted["extracted_part_facts"]
    assert facts["outer_diameter_groove_count"] == 1
    assert facts["outer_diameter_groove_features"] is True
    assert facts["end_face_groove_count"] == 1
    assert facts["end_face_groove_features"] is True
    assert facts["bore_count"] == 3
    assert facts["turned_diameter_faces_count"] == 18
    assert facts["turned_end_faces_count"] == 4
    assert facts["turned_profile_faces_count"] == 4


def test_extract_cadex_dfm_reference_sample_3_maps_issue_categories():
    payload = _load_json(
        REPO_ROOT / "benchmark_data" / "dfm_mtk" / "cases" / "sample 3" / "sample3_dfm.json"
    )

    reference = extract_cadex_dfm_reference(payload)

    assert reference["severity_available"] is False
    assert set(reference["issue_categories"]) == {
        "high_boss",
        "non_perpendicular_hole",
        "non_standard_hole_diameter",
        "partial_hole",
        "small_internal_radius",
    }


def test_compare_reasoning_reference_separates_any_findings_from_rule_violations():
    normalizer = SeverityNormalizer.from_manifest(
        {
            "normalization": {
                "severity_map": {
                    "critical": ["critical"],
                    "major": ["major", "high"],
                    "minor": ["minor", "low", "info"],
                }
            }
        }
    )
    rapiddraft_reference = extract_rapiddraft_review_reference(
        {
            "routes": [
                {
                    "route_source": "selected",
                    "process_id": "cnc_milling",
                    "findings": [
                        {
                            "finding_type": "rule_violation",
                            "rule_id": "CNC-003",
                            "title": "Prefer standard drill diameters",
                            "severity": "major",
                        },
                        {
                            "finding_type": "evidence_gap",
                            "rule_id": "CNC-007",
                            "title": "Avoid raised islands/bosses",
                            "severity": "major",
                        },
                    ],
                }
            ]
        },
        normalizer=normalizer,
    )

    comparison = compare_reasoning_reference(
        {
            "issue_categories": [
                "non_standard_hole_diameter",
                "high_boss",
            ]
        },
        rapiddraft_reference,
    )

    assert comparison["matched_any_categories"] == [
        "high_boss",
        "non_standard_hole_diameter",
    ]
    assert comparison["matched_rule_violation_categories"] == [
        "non_standard_hole_diameter",
    ]
    assert comparison["any_category_recall_against_cadex"] == 1.0
    assert comparison["rule_violation_category_recall_against_cadex"] == 0.5


def test_part_facts_warnings_surface_environment_and_coverage_limits():
    warnings = _part_facts_warnings(
        {
            "errors": ["pythonOCC is required for CNC geometry analysis."],
            "overall_confidence": "low",
            "coverage": {
                "core_extraction_coverage": {
                    "percent": 0.0,
                }
            },
        }
    )

    assert any("pythonOCC" in warning for warning in warnings)
    assert any("No geometry-derived facts were extracted" in warning for warning in warnings)
    assert any("overall confidence is low" in warning for warning in warnings)
