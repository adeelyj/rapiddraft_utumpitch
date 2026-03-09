from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from server.dfm_feature_parity import assess_feature_group, render_feature_parity_markdown


def test_assess_feature_group_marks_pockets_as_partial_when_family_signal_exists():
    assessment = assess_feature_group(
        {
            "name": "Open Pocket(s)",
            "feature_count": 13,
            "categories": ["pockets_present", "open_pocket_features"],
        },
        {"pockets_present": True, "open_pocket_count": 13},
    )

    assert assessment["status"] == "matched"
    assert "dedicated subtype count" in assessment["note"]
    assert assessment["count_comparison"]["detected_count"] == 13
    assert assessment["count_comparison"]["delta"] == 0
    assert assessment["count_comparison"]["alignment"] == "exact_match"


def test_assess_feature_group_marks_turning_as_missing_without_turning_signals():
    assessment = assess_feature_group(
        {
            "name": "Turn Diameter Face(s)",
            "feature_count": 4,
            "categories": ["rotational_symmetry", "turned_faces_present"],
        },
        {},
    )

    assert assessment["status"] == "not_detected"
    assert "primary-axis and revolved-surface detector" in assessment["recommended_hook"]


def test_assess_feature_group_marks_turning_as_partial_with_generic_turning_signals():
    assessment = assess_feature_group(
        {
            "name": "Turn Form Face(s)",
            "feature_count": 1,
            "categories": ["rotational_symmetry", "turned_faces_present"],
        },
        {"turned_faces_present": True, "rotational_symmetry": True},
    )

    assert assessment["status"] == "partially_detected"
    assert "generic turning facts" in assessment["note"]
    assert assessment["count_comparison"]["alignment"] == "count_unavailable"


def test_assess_feature_group_marks_through_holes_from_specific_count():
    assessment = assess_feature_group(
        {
            "name": "Through Hole(s)",
            "feature_count": 3,
            "categories": ["hole_features", "through_hole_features"],
        },
        {"through_hole_count": 3, "hole_features": True},
    )

    assert assessment["status"] == "matched"
    assert "dedicated subtype count" in assessment["note"]
    assert assessment["count_comparison"]["alignment"] == "exact_match"


def test_assess_feature_group_marks_bores_from_specific_count():
    assessment = assess_feature_group(
        {
            "name": "Bore(s)",
            "feature_count": 1,
            "categories": ["hole_features", "bore_features"],
        },
        {"bore_count": 1, "hole_features": True},
    )

    assert assessment["status"] == "matched"
    assert "bore geometry is surfaced" in assessment["note"].lower()
    assert assessment["count_comparison"]["alignment"] == "exact_match"


def test_assess_feature_group_marks_stepped_holes_from_specific_count():
    assessment = assess_feature_group(
        {
            "name": "Stepped Hole(s)",
            "feature_count": 7,
            "categories": ["hole_features", "stepped_hole_features"],
        },
        {"stepped_hole_count": 7, "hole_features": True},
    )

    assert assessment["status"] == "matched"
    assert "stepped-hole geometry is surfaced" in assessment["note"].lower()
    assert assessment["count_comparison"]["alignment"] == "exact_match"


def test_assess_feature_group_marks_bosses_from_specific_count():
    assessment = assess_feature_group(
        {
            "name": "Boss(es)",
            "feature_count": 1,
            "categories": ["boss_features"],
        },
        {"boss_count": 1, "boss_features": True},
    )

    assert assessment["status"] == "matched"
    assert "boss-like protrusion geometry" in assessment["note"].lower()
    assert assessment["count_comparison"]["alignment"] == "exact_match"


def test_assess_feature_group_marks_curved_milled_faces_from_specific_count():
    assessment = assess_feature_group(
        {
            "name": "Curved Milled Face(s)",
            "feature_count": 3,
            "categories": ["milled_faces_present", "curved_milled_faces_present"],
        },
        {"curved_milled_face_count": 3, "milled_faces_present": True},
    )

    assert assessment["status"] == "matched"
    assert "curved milled faces are surfaced" in assessment["note"].lower()
    assert assessment["count_comparison"]["alignment"] == "exact_match"


def test_assess_feature_group_marks_convex_profile_edges_from_specific_count():
    assessment = assess_feature_group(
        {
            "name": "Convex Profile Edge Milling Face(s)",
            "feature_count": 6,
            "categories": ["milled_faces_present", "convex_profile_edge_milled_faces_present"],
        },
        {
            "convex_profile_edge_milled_face_count": 6,
            "milled_faces_present": True,
        },
    )

    assert assessment["status"] == "matched"
    assert "convex edge-profile milling geometry" in assessment["note"].lower()
    assert assessment["count_comparison"]["alignment"] == "exact_match"


def test_assess_feature_group_reports_count_delta_for_turning_mismatch():
    assessment = assess_feature_group(
        {
            "name": "Turn Diameter Face(s)",
            "feature_count": 4,
            "categories": ["rotational_symmetry", "turned_faces_present"],
        },
        {"turned_diameter_faces_count": 17, "turned_faces_present": True},
    )

    assert assessment["status"] == "partially_detected"
    assert assessment["count_comparison"]["detected_count"] == 17
    assert assessment["count_comparison"]["delta"] == 13
    assert assessment["count_comparison"]["alignment"] == "over_detected"


def test_render_feature_parity_markdown_surfaces_exact_matches_and_drifts():
    markdown = render_feature_parity_markdown(
        {
            "generated_at": "2026-03-09T00:00:00+00:00",
            "summary": {
                "case_count": 1,
                "feature_group_count": 2,
                "family_matched_group_count": 2,
                "countable_group_count": 2,
                "exact_count_match_group_count": 1,
                "milled_group_count": 1,
                "milled_exact_count_match_group_count": 1,
                "count_drifts": [
                    {
                        "case_id": "sample_2",
                        "name": "Turn Diameter Face(s)",
                        "reference_count": 4,
                        "detected_count": 17,
                        "delta": 13,
                    }
                ],
            },
            "cases": [
                {
                    "case_id": "sample_2",
                    "label": "sample 2",
                    "step_file": "sample2.stp",
                    "inspection_artifact": "sample2.json",
                    "current_detection_snapshot": {
                        "detected_feature_families": ["flat_milled_faces_present"]
                    },
                    "case_summary": {
                        "feature_group_count": 2,
                        "family_matched_group_count": 2,
                        "countable_group_count": 2,
                        "exact_count_match_group_count": 1,
                        "milled_group_count": 1,
                        "milled_exact_count_match_group_count": 1,
                    },
                    "group_assessments": [
                        {
                            "name": "Flat Milled Face(s)",
                            "status": "matched",
                            "note": "Aligned",
                            "recommended_hook": "Keep it stable.",
                            "count_comparison": {
                                "reference_count": 29,
                                "detected_count": 29,
                                "delta": 0,
                                "alignment": "exact_match",
                            },
                        },
                        {
                            "name": "Turn Diameter Face(s)",
                            "status": "partially_detected",
                            "note": "Broader family only.",
                            "recommended_hook": "Refine turning taxonomy.",
                            "count_comparison": {
                                "reference_count": 4,
                                "detected_count": 17,
                                "delta": 13,
                                "alignment": "over_detected",
                            },
                        },
                    ],
                }
            ],
        }
    )

    assert "Exact count matches: 1/2 countable groups" in markdown
    assert "sample_2 / Turn Diameter Face(s): Cadex 4, Product 17, delta +13" in markdown
    assert "count: Cadex 29, Product 29, delta +0 (exact_match)" in markdown
