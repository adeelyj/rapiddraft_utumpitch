from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

FIXTURE_ROOT = REPO_ROOT / "server" / "tests" / "fixtures" / "cnc_turning"
FEATURE_FIXTURE_ROOT = REPO_ROOT / "server" / "tests" / "fixtures" / "cnc_feature_detection"

from server.cnc_geometry_occ import (
    detect_boss_features_from_face_inventory,
    detect_hole_features_from_face_inventory,
    detect_milled_faces_from_face_inventory,
    detect_pocket_features_from_face_inventory,
    detect_turning_from_face_inventory,
)


def _load_turning_fixture(name: str) -> dict:
    return json.loads((FIXTURE_ROOT / name).read_text(encoding="utf-8-sig"))


def _load_feature_fixture(name: str) -> dict:
    return json.loads((FEATURE_FIXTURE_ROOT / name).read_text(encoding="utf-8-sig"))


def _run_feature_detection_stack(fixture: dict) -> dict[str, dict]:
    bbox_bounds = tuple(fixture["bbox_bounds"])
    face_inventory = fixture["face_inventory"]
    turning_detection = detect_turning_from_face_inventory(
        face_inventory,
        bbox_bounds=bbox_bounds,
    )
    hole_detection = detect_hole_features_from_face_inventory(
        face_inventory,
        bbox_bounds=bbox_bounds,
        turning_detection=turning_detection,
    )
    pocket_detection = detect_pocket_features_from_face_inventory(
        face_inventory,
        bbox_bounds=bbox_bounds,
    )
    boss_detection = detect_boss_features_from_face_inventory(
        face_inventory,
        bbox_bounds=bbox_bounds,
        turning_detection=turning_detection,
    )
    milled_face_detection = detect_milled_faces_from_face_inventory(
        face_inventory,
        bbox_bounds=bbox_bounds,
        turning_detection=turning_detection,
        pocket_detection=pocket_detection,
        hole_detection=hole_detection,
        boss_detection=boss_detection,
    )
    return {
        "turning_detection": turning_detection,
        "hole_detection": hole_detection,
        "pocket_detection": pocket_detection,
        "boss_detection": boss_detection,
        "milled_face_detection": milled_face_detection,
    }


def _assert_detection_counts_match_fixture(result: dict[str, dict], fixture: dict) -> None:
    expected_detection = fixture["expected_detection"]
    for section_name, expected_counts in expected_detection.items():
        actual_section = result[section_name]
        for key, expected_value in expected_counts.items():
            assert actual_section[key] == expected_value


FEATURE_FIXTURE_NAMES = sorted(path.name for path in FEATURE_FIXTURE_ROOT.glob("*.json"))


def test_detect_turning_from_face_inventory_accepts_long_axis_turning_cluster():
    face_inventory = [
        {
            "face_index": 1,
            "surface_type": "cylinder",
            "area_mm2": 28000.0,
            "axis_direction": [0.0, 0.0, 1.0],
            "bbox_bounds": [-18.0, -18.0, -163.0, 18.0, 18.0, 95.0],
            "is_exterior": True,
        },
        {
            "face_index": 2,
            "surface_type": "cylinder",
            "area_mm2": 12000.0,
            "axis_direction": [0.0, 0.0, -1.0],
            "bbox_bounds": [-39.0, -39.0, -60.0, 39.0, 39.0, 5.0],
            "is_exterior": True,
        },
        {
            "face_index": 3,
            "surface_type": "cone",
            "area_mm2": 2400.0,
            "axis_direction": [0.0, 0.0, 1.0],
            "bbox_bounds": [-45.0, -45.0, -15.0, 45.0, 45.0, 35.0],
            "is_exterior": True,
        },
        {
            "face_index": 4,
            "surface_type": "plane",
            "area_mm2": 2300.0,
            "sample_normal": [0.0, 0.0, -1.0],
            "bbox_bounds": [-40.0, -40.0, -163.0, 40.0, 40.0, -163.0],
            "is_exterior": True,
        },
        {
            "face_index": 5,
            "surface_type": "plane",
            "area_mm2": 2700.0,
            "sample_normal": [0.0, 0.0, 1.0],
            "bbox_bounds": [-50.0, -50.0, 95.0, 50.0, 50.0, 95.0],
            "is_exterior": True,
        },
        {
            "face_index": 6,
            "surface_type": "cylinder",
            "area_mm2": 500.0,
            "axis_direction": [1.0, 0.0, 0.0],
            "bbox_bounds": [-5.0, -5.0, -5.0, 5.0, 5.0, 5.0],
            "is_exterior": False,
        },
    ]

    result = detect_turning_from_face_inventory(
        face_inventory,
        bbox_bounds=(-85.0, -85.0, -163.0, 85.0, 85.0, 95.0),
    )

    assert result["rotational_symmetry"] is True
    assert result["turned_faces_present"] is True
    assert result["turned_diameter_faces_count"] == 2
    assert result["turned_profile_faces_count"] == 1
    assert result["turned_end_faces_count"] == 2
    assert result["primary_axis"] == (0.0, 0.0, 1.0)


def test_detect_turning_from_face_inventory_rejects_short_axis_milling_shape():
    face_inventory = [
        {
            "face_index": 1,
            "surface_type": "cylinder",
            "area_mm2": 1343.2,
            "axis_direction": [0.0, -1.0, 0.0],
            "bbox_bounds": [-132.0, 0.0, -24.0, -108.0, 20.0, 24.0],
            "is_exterior": True,
        },
        {
            "face_index": 2,
            "surface_type": "cylinder",
            "area_mm2": 942.4,
            "axis_direction": [0.0, 1.0, 0.0],
            "bbox_bounds": [-132.0, 0.0, -15.0, -108.0, 20.0, 15.0],
            "is_exterior": True,
        },
        {
            "face_index": 3,
            "surface_type": "cone",
            "area_mm2": 63.0,
            "axis_direction": [0.0, -1.0, 0.0],
            "bbox_bounds": [-15.0, 0.0, -6.0, -10.0, 20.0, 6.0],
            "is_exterior": True,
        },
    ]

    result = detect_turning_from_face_inventory(
        face_inventory,
        bbox_bounds=(-132.0, 0.0, -30.0, 0.0, 20.0, 30.0),
    )

    assert result["rotational_symmetry"] is False
    assert result["turned_faces_present"] is False
    assert result["turned_face_count"] == 0


def test_detect_turning_from_face_inventory_accepts_short_highly_revolved_part():
    face_inventory = [
        {
            "face_index": 1,
            "surface_type": "cylinder",
            "area_mm2": 4200.0,
            "axis_direction": [1.0, 0.0, 0.0],
            "bbox_bounds": [-22.0, -28.0, -28.0, -2.0, 28.0, 28.0],
            "is_exterior": True,
        },
        {
            "face_index": 2,
            "surface_type": "cylinder",
            "area_mm2": 4600.0,
            "axis_direction": [1.0, 0.0, 0.0],
            "bbox_bounds": [-2.0, -34.0, -34.0, 16.0, 34.0, 34.0],
            "is_exterior": True,
        },
        {
            "face_index": 3,
            "surface_type": "cone",
            "area_mm2": 2600.0,
            "axis_direction": [1.0, 0.0, 0.0],
            "bbox_bounds": [16.0, -39.0, -39.0, 22.0, 39.0, 39.0],
            "is_exterior": True,
        },
        {
            "face_index": 4,
            "surface_type": "plane",
            "area_mm2": 1800.0,
            "sample_normal": [1.0, 0.0, 0.0],
            "bbox_bounds": [22.0, -20.0, -20.0, 22.0, 20.0, 20.0],
            "is_exterior": True,
            "adjacent_face_indices": [3],
        },
    ]

    result = detect_turning_from_face_inventory(
        face_inventory,
        bbox_bounds=(-22.0, -40.0, -40.0, 22.0, 40.0, 40.0),
    )

    assert result["rotational_symmetry"] is True
    assert result["turned_faces_present"] is True
    assert result["primary_axis"] == (1.0, 0.0, 0.0)
    assert result["clusters"][0]["dominant_axis_ratio"] < 0.8
    assert result["clusters"][0]["exterior_revolved_area_ratio"] >= 0.75


def test_detect_turning_from_face_inventory_counts_torus_as_profile_face():
    face_inventory = [
        {
            "face_index": 1,
            "surface_type": "cylinder",
            "area_mm2": 6534.5,
            "axis_direction": [0.0, 0.0, 1.0],
            "bbox_bounds": [-32.5, -32.5, -163.0, 32.5, 32.5, -131.0],
            "is_exterior": True,
        },
        {
            "face_index": 2,
            "surface_type": "torus",
            "area_mm2": 6296.2,
            "axis_direction": [0.0, 0.0, 1.0],
            "bbox_bounds": [-47.4196, -47.4196, -83.0, 47.4196, 47.4196, -61.0],
            "is_exterior": True,
        },
        {
            "face_index": 3,
            "surface_type": "cylinder",
            "area_mm2": 11272.0,
            "axis_direction": [0.0, 0.0, 1.0],
            "bbox_bounds": [-39.0, -39.0, -51.0, 39.0, 39.0, -5.0],
            "is_exterior": True,
        },
        {
            "face_index": 4,
            "surface_type": "plane",
            "area_mm2": 4908.7,
            "sample_normal": [0.0, 0.0, 1.0],
            "bbox_bounds": [-39.0, -39.0, -5.0, 39.0, 39.0, -5.0],
            "is_exterior": True,
        },
        {
            "face_index": 5,
            "surface_type": "plane",
            "area_mm2": 3318.3,
            "sample_normal": [0.0, 0.0, -1.0],
            "bbox_bounds": [-32.5, -32.5, -163.0, 32.5, 32.5, -163.0],
            "is_exterior": True,
        },
    ]

    result = detect_turning_from_face_inventory(
        face_inventory,
        bbox_bounds=(-85.0, -85.0, -163.0, 85.0, 85.0, 95.0),
    )

    assert result["rotational_symmetry"] is True
    assert result["turned_diameter_faces_count"] == 2
    assert result["turned_profile_faces_count"] == 1
    assert result["turned_end_faces_count"] == 2


def test_detect_turning_from_face_inventory_groups_diameters_and_counts_axis_normal_planes():
    face_inventory = [
        {
            "face_index": 1,
            "surface_type": "cylinder",
            "area_mm2": 6534.5,
            "axis_direction": [0.0, 0.0, 1.0],
            "axis_origin": [0.0, 0.0, -163.0],
            "sample_point_mm": [32.5, 0.0, -147.0],
            "bbox_bounds": [-32.5, -32.5, -163.0, 32.5, 32.5, -131.0],
            "is_exterior": True,
            "adjacent_face_indices": [8, 9],
        },
        {
            "face_index": 2,
            "surface_type": "cylinder",
            "area_mm2": 353.6,
            "axis_direction": [0.0, 0.0, 1.0],
            "axis_origin": [0.0, 0.0, -163.0],
            "sample_point_mm": [36.0, 0.0, -107.0],
            "bbox_bounds": [34.0, -5.0, -131.0, 36.0, 5.0, -83.0],
            "is_exterior": True,
            "adjacent_face_indices": [9, 10, 15],
        },
        {
            "face_index": 3,
            "surface_type": "cylinder",
            "area_mm2": 353.6,
            "axis_direction": [0.0, 0.0, 1.0],
            "axis_origin": [0.0, 0.0, -163.0],
            "sample_point_mm": [0.0, 36.0, -107.0],
            "bbox_bounds": [-5.0, 34.0, -131.0, 5.0, 36.0, -83.0],
            "is_exterior": True,
            "adjacent_face_indices": [9, 10, 15],
        },
        {
            "face_index": 4,
            "surface_type": "torus",
            "area_mm2": 6296.2,
            "axis_direction": [0.0, 0.0, 1.0],
            "axis_origin": [0.0, 0.0, -72.0],
            "bbox_bounds": [-47.4, -47.4, -83.0, 47.4, 47.4, -61.0],
            "is_exterior": True,
            "adjacent_face_indices": [10, 11],
        },
        {
            "face_index": 5,
            "surface_type": "cylinder",
            "area_mm2": 2387.6,
            "axis_direction": [0.0, 0.0, 1.0],
            "axis_origin": [0.0, 0.0, -163.0],
            "sample_point_mm": [38.0, 0.0, -56.0],
            "bbox_bounds": [-38.0, -38.0, -61.0, 38.0, 38.0, -51.0],
            "is_exterior": True,
            "adjacent_face_indices": [11, 12],
        },
        {
            "face_index": 6,
            "surface_type": "cylinder",
            "area_mm2": 11272.0,
            "axis_direction": [0.0, 0.0, 1.0],
            "axis_origin": [0.0, 0.0, -163.0],
            "sample_point_mm": [39.0, 0.0, -28.0],
            "bbox_bounds": [-39.0, -39.0, -51.0, 39.0, 39.0, -5.0],
            "is_exterior": True,
            "adjacent_face_indices": [12, 13],
        },
        {
            "face_index": 7,
            "surface_type": "cylinder",
            "area_mm2": 1413.7,
            "axis_direction": [0.0, 0.0, 1.0],
            "axis_origin": [0.0, 0.0, -163.0],
            "sample_point_mm": [45.0, 0.0, -2.5],
            "bbox_bounds": [-45.0, -45.0, -5.0, 45.0, 45.0, 0.0],
            "is_exterior": True,
            "adjacent_face_indices": [13, 14],
        },
        {
            "face_index": 8,
            "surface_type": "plane",
            "area_mm2": 3318.3,
            "sample_normal": [0.0, 0.0, -1.0],
            "bbox_bounds": [-32.5, -32.5, -163.0, 32.5, 32.5, -163.0],
            "is_exterior": True,
            "adjacent_face_indices": [1],
        },
        {
            "face_index": 9,
            "surface_type": "plane",
            "area_mm2": 1418.3,
            "sample_normal": [0.0, 0.0, -1.0],
            "bbox_bounds": [-41.3, -41.0, -131.0, 41.3, 41.0, -131.0],
            "is_exterior": None,
            "adjacent_face_indices": [1, 2, 3],
        },
        {
            "face_index": 10,
            "surface_type": "plane",
            "area_mm2": 51.2,
            "sample_normal": [0.0, 0.0, -1.0],
            "bbox_bounds": [-10.0, -10.0, -83.0, 10.0, 10.0, -83.0],
            "is_exterior": False,
            "adjacent_face_indices": [2, 3, 4],
        },
        {
            "face_index": 11,
            "surface_type": "plane",
            "area_mm2": 465.0,
            "sample_normal": [0.0, 0.0, -1.0],
            "bbox_bounds": [-38.0, -38.0, -61.0, 38.0, 38.0, -61.0],
            "is_exterior": None,
            "adjacent_face_indices": [4, 5],
        },
        {
            "face_index": 12,
            "surface_type": "plane",
            "area_mm2": 241.9,
            "sample_normal": [0.0, 0.0, -1.0],
            "bbox_bounds": [-39.0, -39.0, -51.0, 39.0, 39.0, -51.0],
            "is_exterior": None,
            "adjacent_face_indices": [5, 6],
        },
        {
            "face_index": 13,
            "surface_type": "plane",
            "area_mm2": 1583.4,
            "sample_normal": [0.0, 0.0, -1.0],
            "bbox_bounds": [-45.0, -45.0, -5.0, 45.0, 45.0, -5.0],
            "is_exterior": None,
            "adjacent_face_indices": [6, 7],
        },
        {
            "face_index": 14,
            "surface_type": "plane",
            "area_mm2": 8538.4,
            "sample_normal": [0.0, 0.0, 1.0],
            "bbox_bounds": [-85.0, -85.0, 0.0, 85.0, 85.0, 0.0],
            "is_exterior": True,
            "adjacent_face_indices": [7],
        },
    ]

    result = detect_turning_from_face_inventory(
        face_inventory,
        bbox_bounds=(-85.0, -85.0, -163.0, 85.0, 85.0, 95.0),
    )

    assert result["rotational_symmetry"] is True
    assert result["turned_diameter_faces_count"] == 4
    assert result["turned_profile_faces_count"] == 1
    assert result["turned_end_faces_count"] == 7
    assert result["turned_face_count"] == 12
    assert result["turned_end_face_indices"] == [8, 9, 10, 11, 12, 13, 14]
    assert [group["face_indices"] for group in result["turned_diameter_groups"]] == [
        [1],
        [2, 3],
        [5, 6],
        [7],
    ]


def test_detect_turning_from_face_inventory_matches_sample_2_fixture():
    fixture = _load_turning_fixture("sample_2_turning_fixture.json")

    result = detect_turning_from_face_inventory(
        fixture["face_inventory"],
        bbox_bounds=tuple(fixture["bbox_bounds"]),
    )

    expected = fixture["expected_turning_detection"]
    assert result["rotational_symmetry"] is expected["rotational_symmetry"]
    assert result["turned_faces_present"] is expected["turned_faces_present"]
    assert result["turned_face_count"] == expected["turned_face_count"]
    assert result["turned_diameter_faces_count"] == expected["turned_diameter_faces_count"]
    assert result["turned_end_faces_count"] == expected["turned_end_faces_count"]
    assert result["turned_profile_faces_count"] == expected["turned_profile_faces_count"]
    assert 24 in result["turned_end_face_indices"]
    assert 25 in result["turned_end_face_indices"]


def test_detect_turning_from_face_inventory_rejects_sample_3_fixture():
    fixture = _load_turning_fixture("sample_3_turning_fixture.json")

    result = detect_turning_from_face_inventory(
        fixture["face_inventory"],
        bbox_bounds=tuple(fixture["bbox_bounds"]),
    )

    expected = fixture["expected_turning_detection"]
    assert result["rotational_symmetry"] is expected["rotational_symmetry"]
    assert result["turned_faces_present"] is expected["turned_faces_present"]
    assert result["turned_face_count"] == expected["turned_face_count"]
    assert result["turned_diameter_faces_count"] == expected["turned_diameter_faces_count"]
    assert result["turned_end_faces_count"] == expected["turned_end_faces_count"]
    assert result["turned_profile_faces_count"] == expected["turned_profile_faces_count"]


def test_detect_hole_features_from_face_inventory_separates_nested_holes_from_outer_cylinders():
    face_inventory = [
        {
            "face_index": 17,
            "surface_type": "cylinder",
            "area_mm2": 1343.2163,
            "bbox_bounds": [-132.0, 0.0, -12.0, -108.0, 20.0, 12.0],
            "axis_direction": [0.0, 1.0, 0.0],
            "axis_origin": [-120.0, 20.0, 0.0],
            "axial_span_mm": 20.0,
            "is_exterior": True,
        },
        {
            "face_index": 22,
            "surface_type": "cylinder",
            "area_mm2": 942.4778,
            "bbox_bounds": [-127.5, 0.0, -7.5, -112.5, 20.0, 7.5],
            "axis_direction": [0.0, 1.0, 0.0],
            "axis_origin": [-120.0, 20.0, 0.0],
            "axial_span_mm": 20.0,
            "is_exterior": False,
        },
        {
            "face_index": 21,
            "surface_type": "cylinder",
            "area_mm2": 1003.1317,
            "bbox_bounds": [-25.0, 0.0, -25.0, 0.0, 20.0, 25.0],
            "axis_direction": [0.0, 1.0, 0.0],
            "axis_origin": [0.0, 20.0, 0.0],
            "axial_span_mm": 20.0,
            "is_exterior": True,
        },
        {
            "face_index": 19,
            "surface_type": "cylinder",
            "area_mm2": 773.5725,
            "bbox_bounds": [-13.6798, 1.0, -13.6798, 0.0, 19.0, 13.6798],
            "axis_direction": [0.0, 1.0, 0.0],
            "axis_origin": [0.0, 20.0, 0.0],
            "axial_span_mm": 18.0,
            "is_exterior": True,
        },
        {
            "face_index": 33,
            "surface_type": "cylinder",
            "area_mm2": 271.1544,
            "bbox_bounds": [-13.5657, 6.0, -29.0, 0.0, 14.0, -21.0],
            "axis_direction": [1.0, 0.0, 0.0],
            "axis_origin": [-20.0, 10.0, -25.0],
            "axial_span_mm": 13.5657,
            "is_exterior": True,
        },
        {
            "face_index": 34,
            "surface_type": "cylinder",
            "area_mm2": 271.1542,
            "bbox_bounds": [-13.5647, 6.0, 21.0, 0.0, 14.0, 29.0],
            "axis_direction": [1.0, 0.0, 0.0],
            "axis_origin": [-20.0, 10.0, 25.0],
            "axial_span_mm": 13.5647,
            "is_exterior": False,
        },
    ]

    result = detect_hole_features_from_face_inventory(
        face_inventory,
        bbox_bounds=(-132.53, -0.53, -30.53, 0.53, 20.53, 30.53),
    )

    assert result["hole_count"] == 4
    assert result["through_hole_count"] == 3
    assert result["partial_hole_count"] == 1
    assert result["bore_count"] == 0


def test_detect_hole_features_from_face_inventory_counts_central_bore_without_turning_exteriors():
    face_inventory = [
        {
            "face_index": 14,
            "surface_type": "cylinder",
            "area_mm2": 6534.5127,
            "bbox_bounds": [-32.5, -32.5, -163.0, 32.5, 32.5, -131.0],
            "axis_direction": [0.0, 0.0, 1.0],
            "axis_origin": [0.0, 0.0, -163.0],
            "axial_span_mm": 32.0,
            "is_exterior": True,
        },
        {
            "face_index": 21,
            "surface_type": "cylinder",
            "area_mm2": 11272.0344,
            "bbox_bounds": [-39.0, -39.0, -51.0, 39.0, 39.0, -5.0],
            "axis_direction": [0.0, 0.0, 1.0],
            "axis_origin": [0.0, 0.0, -61.0],
            "axial_span_mm": 46.0,
            "is_exterior": True,
        },
        {
            "face_index": 110,
            "surface_type": "cylinder",
            "area_mm2": 28368.5817,
            "bbox_bounds": [-17.5, -17.5, -163.0, 17.5, 17.5, 95.0],
            "axis_direction": [0.0, 0.0, 1.0],
            "axis_origin": [0.0, 0.0, -163.0],
            "axial_span_mm": 258.0,
            "is_exterior": False,
        },
    ]

    result = detect_hole_features_from_face_inventory(
        face_inventory,
        bbox_bounds=(-85.0708, -85.0708, -163.0, 85.0708, 85.0708, 95.0),
        turning_detection={"primary_axis": [0.0, 0.0, 1.0]},
    )

    assert result["hole_count"] == 1
    assert result["through_hole_count"] == 0
    assert result["partial_hole_count"] == 0
    assert result["bore_count"] == 1


def test_detect_hole_features_from_face_inventory_treats_split_same_diameter_walls_as_through_hole():
    half_wall_area = math.pi * 4.0 * 10.0 * 0.5
    face_inventory = [
        {
            "face_index": 1,
            "surface_type": "cylinder",
            "area_mm2": half_wall_area,
            "bbox_bounds": [0.0, -2.0, -2.0, 10.0, 0.0, 2.0],
            "axis_direction": [1.0, 0.0, 0.0],
            "axis_origin": [0.0, 0.0, 0.0],
            "axial_span_mm": 10.0,
            "is_exterior": False,
        },
        {
            "face_index": 2,
            "surface_type": "cylinder",
            "area_mm2": half_wall_area,
            "bbox_bounds": [0.0, 0.0, -2.0, 10.0, 2.0, 2.0],
            "axis_direction": [1.0, 0.0, 0.0],
            "axis_origin": [0.0, 0.0, 0.0],
            "axial_span_mm": 10.0,
            "is_exterior": False,
        },
    ]

    result = detect_hole_features_from_face_inventory(
        face_inventory,
        bbox_bounds=(0.0, -5.0, -5.0, 10.0, 5.0, 5.0),
    )

    assert result["hole_count"] == 1
    assert result["through_hole_count"] == 1
    assert result["partial_hole_count"] == 0
    assert result["candidates"][0]["subtype"] == "through_hole"
    assert result["candidates"][0]["group_completeness_ratio"] == 1.0


def test_detect_hole_features_from_face_inventory_splits_same_axis_line_into_two_through_holes():
    face_inventory = [
        {
            "face_index": 1,
            "surface_type": "cylinder",
            "area_mm2": 40.84,
            "bbox_bounds": [0.0, -30.5, -4.0, 8.0, -24.0, 4.0],
            "axis_direction": [0.0, 1.0, 0.0],
            "axis_origin": [4.0, 0.0, 0.0],
            "axial_span_mm": 6.5,
            "is_exterior": False,
        },
        {
            "face_index": 2,
            "surface_type": "cylinder",
            "area_mm2": 40.84,
            "bbox_bounds": [8.0, -30.5, -4.0, 16.0, -24.0, 4.0],
            "axis_direction": [0.0, 1.0, 0.0],
            "axis_origin": [12.0, 0.0, 0.0],
            "axial_span_mm": 6.5,
            "is_exterior": False,
        },
        {
            "face_index": 3,
            "surface_type": "cylinder",
            "area_mm2": 40.84,
            "bbox_bounds": [0.0, 24.0, -4.0, 8.0, 30.5, 4.0],
            "axis_direction": [0.0, 1.0, 0.0],
            "axis_origin": [4.0, 0.0, 0.0],
            "axial_span_mm": 6.5,
            "is_exterior": False,
        },
        {
            "face_index": 4,
            "surface_type": "cylinder",
            "area_mm2": 40.84,
            "bbox_bounds": [8.0, 24.0, -4.0, 16.0, 30.5, 4.0],
            "axis_direction": [0.0, 1.0, 0.0],
            "axis_origin": [12.0, 0.0, 0.0],
            "axial_span_mm": 6.5,
            "is_exterior": False,
        },
    ]

    result = detect_hole_features_from_face_inventory(
        face_inventory,
        bbox_bounds=(0.0, -32.0, -8.0, 16.0, 32.0, 8.0),
    )

    assert result["hole_count"] == 2
    assert result["through_hole_count"] == 2
    assert result["partial_hole_count"] == 0


def test_detect_hole_features_from_face_inventory_rejects_same_diameter_exterior_profile_band():
    face_inventory = [
        {
            "face_index": 27,
            "surface_type": "cylinder",
            "area_mm2": 484.4357,
            "bbox_bounds": [-20.0, 20.0, -7.8564, -18.3923, 50.0, 7.8564],
            "axis_direction": [0.0, 1.0, 0.0],
            "axis_origin": [0.0, 50.0, 0.0],
            "axial_span_mm": 30.0,
            "is_exterior": True,
        },
        {
            "face_index": 31,
            "surface_type": "cylinder",
            "area_mm2": 484.4357,
            "bbox_bounds": [2.3923, 20.0, 12.0, 16.0, 50.0, 19.8564],
            "axis_direction": [0.0, 1.0, 0.0],
            "axis_origin": [0.0, 50.0, 0.0],
            "axial_span_mm": 30.0,
            "is_exterior": True,
        },
        {
            "face_index": 35,
            "surface_type": "cylinder",
            "area_mm2": 484.4357,
            "bbox_bounds": [2.3923, 20.0, -19.8564, 16.0, 50.0, -12.0],
            "axis_direction": [0.0, 1.0, 0.0],
            "axis_origin": [0.0, 50.0, 0.0],
            "axial_span_mm": 30.0,
            "is_exterior": True,
        },
    ]

    result = detect_hole_features_from_face_inventory(
        face_inventory,
        bbox_bounds=(-50.0, 0.0, -40.0, 50.0, 50.0, 40.0),
    )

    assert result["hole_count"] == 0
    assert result["through_hole_count"] == 0
    assert result["partial_hole_count"] == 0
    assert all(
        candidate["selection_reason"] == "exterior_profile_band"
        for candidate in result["rejected_candidates"]
    )


def test_detect_hole_features_from_face_inventory_counts_stepped_holes_and_rejects_shallow_nested_recess():
    face_inventory = [
        {
            "face_index": 1,
            "surface_type": "cylinder",
            "area_mm2": 691.1504,
            "bbox_bounds": [-5.0, 10.0, -5.0, 5.0, 32.0, 5.0],
            "axis_direction": [0.0, 1.0, 0.0],
            "axis_origin": [0.0, 40.0, 0.0],
            "axial_span_mm": 22.0,
            "is_exterior": False,
        },
        {
            "face_index": 2,
            "surface_type": "cylinder",
            "area_mm2": 376.9911,
            "bbox_bounds": [-7.5, 0.0, -7.5, 7.5, 8.0, 7.5],
            "axis_direction": [0.0, 1.0, 0.0],
            "axis_origin": [0.0, 40.0, 0.0],
            "axial_span_mm": 8.0,
            "is_exterior": False,
        },
        {
            "face_index": 3,
            "surface_type": "cylinder",
            "area_mm2": 1847.2565,
            "bbox_bounds": [-14.7, 0.0, -14.7, 14.7, 40.0, 14.7],
            "axis_direction": [0.0, 1.0, 0.0],
            "axis_origin": [0.0, 40.0, 0.0],
            "axial_span_mm": 40.0,
            "is_exterior": True,
        },
        {
            "face_index": 4,
            "surface_type": "cylinder",
            "area_mm2": 1884.9556,
            "bbox_bounds": [35.0, 10.0, -15.0, 65.0, 30.0, 15.0],
            "axis_direction": [0.0, 1.0, 0.0],
            "axis_origin": [50.0, 40.0, 0.0],
            "axial_span_mm": 20.0,
            "is_exterior": False,
        },
        {
            "face_index": 5,
            "surface_type": "cylinder",
            "area_mm2": 1087.4425,
            "bbox_bounds": [28.5, 0.0, -21.7, 71.5, 8.0, 21.7],
            "axis_direction": [0.0, 1.0, 0.0],
            "axis_origin": [50.0, 40.0, 0.0],
            "axial_span_mm": 8.0,
            "is_exterior": True,
        },
    ]

    result = detect_hole_features_from_face_inventory(
        face_inventory,
        bbox_bounds=(-20.0, 0.0, -30.0, 80.0, 40.0, 30.0),
    )

    assert result["hole_count"] == 1
    assert result["through_hole_count"] == 0
    assert result["partial_hole_count"] == 0
    assert result["stepped_hole_count"] == 1
    assert result["candidates"][0]["subtype"] == "stepped_hole"
    assert any(
        candidate["selection_reason"] == "shallow_nested_recess"
        for candidate in result["rejected_candidates"]
    )


def test_detect_pocket_features_from_face_inventory_separates_open_and_closed_pockets():
    open_pocket_inventory = [
        {
            "face_index": 61,
            "surface_type": "plane",
            "area_mm2": 51.1608,
            "bbox_bounds": [-5.0, 35.6511, -83.0, 5.0, 41.0, -83.0],
            "sample_normal": [0.0, 0.0, -1.0],
            "is_exterior": False,
            "adjacent_face_indices": [17, 58, 59, 60],
        },
        {
            "face_index": 17,
            "surface_type": "torus",
            "area_mm2": 6296.1958,
            "bbox_bounds": [-47.4196, -47.4196, -83.0, 47.4196, 47.4196, -61.0],
            "axis_direction": [0.0, 0.0, 1.0],
            "is_exterior": True,
            "adjacent_face_indices": [61],
        },
        {
            "face_index": 58,
            "surface_type": "plane",
            "area_mm2": 256.7478,
            "bbox_bounds": [-5.0, 35.6511, -131.0, -5.0, 41.0, -83.0],
            "sample_normal": [-1.0, 0.0, 0.0],
            "is_exterior": True,
            "adjacent_face_indices": [61],
        },
        {
            "face_index": 59,
            "surface_type": "plane",
            "area_mm2": 256.7478,
            "bbox_bounds": [5.0, 35.6511, -131.0, 5.0, 41.0, -83.0],
            "sample_normal": [1.0, 0.0, 0.0],
            "is_exterior": True,
            "adjacent_face_indices": [61],
        },
        {
            "face_index": 60,
            "surface_type": "plane",
            "area_mm2": 480.0,
            "bbox_bounds": [-5.0, 41.0, -131.0, 5.0, 41.0, -83.0],
            "sample_normal": [0.0, 1.0, 0.0],
            "is_exterior": True,
            "adjacent_face_indices": [61],
        },
    ]
    open_result = detect_pocket_features_from_face_inventory(
        open_pocket_inventory,
        bbox_bounds=(-85.0708, -85.0708, -163.0, 85.0708, 85.0708, 95.0),
    )

    assert open_result["pocket_count"] == 1
    assert open_result["open_pocket_count"] == 1
    assert open_result["closed_pocket_count"] == 0

    closed_pocket_inventory = [
        {
            "face_index": 25,
            "surface_type": "plane",
            "area_mm2": 968.2389,
            "bbox_bounds": [-108.0, 10.0, -7.0, -25.0, 10.0, 7.0],
            "sample_normal": [0.0, 1.0, 0.0],
            "is_exterior": True,
            "adjacent_face_indices": [8, 10, 11, 14, 15, 16],
        },
        {
            "face_index": 8,
            "surface_type": "cylinder",
            "area_mm2": 117.841,
            "bbox_bounds": [-32.3941, 5.0, -7.0, -25.0, 15.0, 7.0],
            "axis_direction": [0.0, 1.0, 0.0],
            "is_exterior": True,
            "adjacent_face_indices": [25],
        },
        {
            "face_index": 10,
            "surface_type": "plane",
            "area_mm2": 1.971,
            "bbox_bounds": [-32.3941, 5.0, -7.0, -32.0, 10.0, -6.9889],
            "sample_normal": [0.0, 0.0, -1.0],
            "is_exterior": None,
            "adjacent_face_indices": [25],
        },
        {
            "face_index": 11,
            "surface_type": "plane",
            "area_mm2": 1.971,
            "bbox_bounds": [-32.3941, 5.0, 6.9889, -32.0, 10.0, 7.0],
            "sample_normal": [0.0, 0.0, 1.0],
            "is_exterior": None,
            "adjacent_face_indices": [25],
        },
        {
            "face_index": 14,
            "surface_type": "plane",
            "area_mm2": 353.1698,
            "bbox_bounds": [-103.0, 10.0, 5.0, -32.3941, 15.0, 6.9889],
            "sample_normal": [0.0, 0.0, 1.0],
            "is_exterior": True,
            "adjacent_face_indices": [25],
        },
        {
            "face_index": 15,
            "surface_type": "cylinder",
            "area_mm2": 78.5398,
            "bbox_bounds": [-108.0, 10.0, -5.0, -103.0, 15.0, 5.0],
            "axis_direction": [0.0, 1.0, 0.0],
            "is_exterior": True,
            "adjacent_face_indices": [25],
        },
        {
            "face_index": 16,
            "surface_type": "plane",
            "area_mm2": 353.1698,
            "bbox_bounds": [-103.0, 10.0, -6.9889, -32.3941, 15.0, -5.0],
            "sample_normal": [0.0, 0.0, -1.0],
            "is_exterior": True,
            "adjacent_face_indices": [25],
        },
    ]

    closed_result = detect_pocket_features_from_face_inventory(
        closed_pocket_inventory,
        bbox_bounds=(-132.53, -0.53, -30.53, 0.53, 20.53, 30.53),
    )

    assert closed_result["pocket_count"] == 1
    assert closed_result["open_pocket_count"] == 0
    assert closed_result["closed_pocket_count"] == 1


def test_detect_pocket_features_from_face_inventory_accepts_exterior_open_floor_with_interior_walls():
    face_inventory = [
        {
            "face_index": 18,
            "surface_type": "plane",
            "area_mm2": 401.0973,
            "bbox_bounds": [-44.0, 10.0, -6.0, -32.0, 10.0, 6.0],
            "sample_normal": [0.0, 1.0, 0.0],
            "is_exterior": True,
            "adjacent_face_indices": [6, 11, 15, 16, 17],
        },
        {
            "face_index": 6,
            "surface_type": "cylinder",
            "area_mm2": 376.9911,
            "bbox_bounds": [-44.0, 0.0, -6.0, -32.0, 10.0, 6.0],
            "axis_direction": [0.0, 1.0, 0.0],
            "is_exterior": False,
            "adjacent_face_indices": [18],
        },
        {
            "face_index": 11,
            "surface_type": "plane",
            "area_mm2": 914.7005,
            "bbox_bounds": [-44.0, 0.0, -6.0, -32.0, 20.0, 6.0],
            "sample_normal": [1.0, 0.0, 0.0],
            "is_exterior": True,
            "adjacent_face_indices": [18],
        },
        {
            "face_index": 15,
            "surface_type": "cylinder",
            "area_mm2": 376.9911,
            "bbox_bounds": [-44.0, 10.0, -12.0, -32.0, 20.0, 12.0],
            "axis_direction": [0.0, 1.0, 0.0],
            "is_exterior": True,
            "adjacent_face_indices": [18],
        },
        {
            "face_index": 16,
            "surface_type": "plane",
            "area_mm2": 120.0,
            "bbox_bounds": [-38.0, 10.0, -6.0, -26.0, 10.0, 6.0],
            "sample_normal": [0.0, 0.0, 1.0],
            "is_exterior": False,
            "adjacent_face_indices": [18],
        },
        {
            "face_index": 17,
            "surface_type": "plane",
            "area_mm2": 120.0,
            "bbox_bounds": [-38.0, 10.0, -6.0, -26.0, 10.0, 6.0],
            "sample_normal": [0.0, 0.0, -1.0],
            "is_exterior": False,
            "adjacent_face_indices": [18],
        },
    ]

    result = detect_pocket_features_from_face_inventory(
        face_inventory,
        bbox_bounds=(-50.0, 0.0, -30.0, 50.0, 50.0, 30.0),
    )

    assert result["open_pocket_count"] == 1
    assert result["candidates"][0]["face_index"] == 18
    assert result["candidates"][0]["selection_reason"] == "exterior_open_recessed_floor"


def test_detect_pocket_features_from_face_inventory_accepts_curved_enclosed_floor():
    face_inventory = [
        {
            "face_index": 113,
            "surface_type": "plane",
            "area_mm2": 4005.5306,
            "bbox_bounds": [125.0, 20.0, -45.0, 175.0, 20.0, 45.0],
            "sample_normal": [0.0, 1.0, 0.0],
            "is_exterior": True,
            "adjacent_face_indices": [109, 110, 111, 112],
        },
        {
            "face_index": 109,
            "surface_type": "cylinder",
            "area_mm2": 3141.5927,
            "bbox_bounds": [150.0, 20.0, -50.0, 200.0, 40.0, 50.0],
            "axis_direction": [0.0, 1.0, 0.0],
            "is_exterior": True,
            "adjacent_face_indices": [113],
        },
        {
            "face_index": 110,
            "surface_type": "cylinder",
            "area_mm2": 942.4778,
            "bbox_bounds": [135.0, 20.0, 20.0, 165.0, 40.0, 50.0],
            "axis_direction": [0.0, 1.0, 0.0],
            "is_exterior": False,
            "adjacent_face_indices": [113],
        },
        {
            "face_index": 111,
            "surface_type": "cylinder",
            "area_mm2": 942.4778,
            "bbox_bounds": [135.0, 20.0, -50.0, 165.0, 40.0, -20.0],
            "axis_direction": [0.0, 1.0, 0.0],
            "is_exterior": False,
            "adjacent_face_indices": [113],
        },
        {
            "face_index": 112,
            "surface_type": "cylinder",
            "area_mm2": 942.4778,
            "bbox_bounds": [100.0, 20.0, -15.0, 130.0, 40.0, 15.0],
            "axis_direction": [0.0, 1.0, 0.0],
            "is_exterior": False,
            "adjacent_face_indices": [113],
        },
    ]

    result = detect_pocket_features_from_face_inventory(
        face_inventory,
        bbox_bounds=(0.0, 0.0, -90.0, 235.0, 40.0, 90.0),
    )

    assert result["closed_pocket_count"] == 1
    assert result["candidates"][0]["face_index"] == 113
    assert result["candidates"][0]["selection_reason"] == "curved_enclosed_floor"


def test_detect_boss_features_from_face_inventory_accepts_supported_exterior_group():
    face_inventory = [
        {
            "face_index": 19,
            "surface_type": "cylinder",
            "area_mm2": 773.5725,
            "bbox_bounds": [-13.6798, 1.0, -13.6798, 0.0, 19.0, 13.6798],
            "axis_direction": [0.0, 1.0, 0.0],
            "axis_origin": [0.0, 20.0, 0.0],
            "is_exterior": True,
        },
        {
            "face_index": 21,
            "surface_type": "cylinder",
            "area_mm2": 1003.1317,
            "bbox_bounds": [-25.0, 0.0, -25.0, 0.0, 20.0, 25.0],
            "axis_direction": [0.0, 1.0, 0.0],
            "axis_origin": [0.0, 20.0, 0.0],
            "is_exterior": True,
        },
        {
            "face_index": 35,
            "surface_type": "cone",
            "area_mm2": 62.999,
            "bbox_bounds": [-14.6798, 0.0, -14.6798, 0.0, 1.0, 14.6798],
            "axis_direction": [0.0, 1.0, 0.0],
            "axis_origin": [0.0, 0.0, 0.0],
            "is_exterior": True,
        },
        {
            "face_index": 36,
            "surface_type": "cone",
            "area_mm2": 62.999,
            "bbox_bounds": [-14.6798, 19.0, -14.6798, 0.0, 20.0, 14.6798],
            "axis_direction": [0.0, 1.0, 0.0],
            "axis_origin": [0.0, 20.0, 0.0],
            "is_exterior": True,
        },
        {
            "face_index": 23,
            "surface_type": "plane",
            "area_mm2": 643.2482,
            "bbox_bounds": [-25.0, 20.0, -25.0, 0.0, 20.0, 25.0],
            "sample_normal": [0.0, 1.0, 0.0],
            "is_exterior": True,
        },
        {
            "face_index": 24,
            "surface_type": "plane",
            "area_mm2": 643.2482,
            "bbox_bounds": [-25.0, 0.0, -25.0, 0.0, 0.0, 25.0],
            "sample_normal": [0.0, -1.0, 0.0],
            "is_exterior": True,
        },
        {
            "face_index": 17,
            "surface_type": "cylinder",
            "area_mm2": 1343.2163,
            "bbox_bounds": [-132.0, 0.0, -12.0, -108.0, 20.0, 12.0],
            "axis_direction": [0.0, 1.0, 0.0],
            "axis_origin": [-120.0, 20.0, 0.0],
            "is_exterior": True,
        },
        {
            "face_index": 22,
            "surface_type": "cylinder",
            "area_mm2": 942.4778,
            "bbox_bounds": [-127.5, 0.0, -7.5, -112.5, 20.0, 7.5],
            "axis_direction": [0.0, 1.0, 0.0],
            "axis_origin": [-120.0, 20.0, 0.0],
            "is_exterior": False,
        },
        {
            "face_index": 12,
            "surface_type": "plane",
            "area_mm2": 275.6748,
            "bbox_bounds": [-132.0, 0.0, -12.0, -108.0, 0.0, 12.0],
            "sample_normal": [0.0, -1.0, 0.0],
            "is_exterior": True,
        },
        {
            "face_index": 13,
            "surface_type": "plane",
            "area_mm2": 275.6748,
            "bbox_bounds": [-132.0, 20.0, -12.0, -108.0, 20.0, 12.0],
            "sample_normal": [0.0, 1.0, 0.0],
            "is_exterior": True,
        },
    ]

    result = detect_boss_features_from_face_inventory(
        face_inventory,
        bbox_bounds=(-132.53, -0.53, -30.53, 0.53, 20.53, 30.53),
    )

    assert result["boss_count"] == 1
    assert result["candidates"][0]["face_indices"] == [19, 21, 35, 36]


def test_detect_milled_faces_from_face_inventory_groups_milling_features_on_non_turning_part():
    face_inventory = [
        {
            "face_index": 1,
            "surface_type": "plane",
            "area_mm2": 40.0,
            "bbox_bounds": [-30.0, 0.0, -10.0, -20.0, 10.0, -10.0],
            "sample_normal": [0.0, 0.0, 1.0],
            "is_exterior": True,
            "adjacent_face_indices": [2],
        },
        {
            "face_index": 2,
            "surface_type": "plane",
            "area_mm2": 40.0,
            "bbox_bounds": [-20.0, 0.0, -10.0, -10.0, 10.0, -10.0],
            "sample_normal": [0.0, 0.0, 1.0],
            "is_exterior": True,
            "adjacent_face_indices": [1],
        },
        {
            "face_index": 3,
            "surface_type": "plane",
            "area_mm2": 50.0,
            "bbox_bounds": [-10.0, 0.0, -10.0, 0.0, 10.0, -10.0],
            "sample_normal": [0.0, 1.0, 0.0],
            "is_exterior": True,
            "adjacent_face_indices": [],
        },
        {
            "face_index": 4,
            "surface_type": "plane",
            "area_mm2": 12.0,
            "bbox_bounds": [0.0, 0.0, -10.0, 0.0, 10.0, 0.0],
            "sample_normal": [1.0, 0.0, 0.0],
            "is_exterior": True,
            "adjacent_face_indices": [],
        },
        {
            "face_index": 5,
            "surface_type": "plane",
            "area_mm2": 20.0,
            "bbox_bounds": [-40.0, 0.0, 0.0, -30.0, 10.0, 5.0],
            "sample_normal": [0.4, 0.0, 0.9165],
            "is_exterior": True,
            "adjacent_face_indices": [],
        },
        {
            "face_index": 6,
            "surface_type": "cone",
            "area_mm2": 18.0,
            "bbox_bounds": [-15.0, 0.0, 5.0, -5.0, 10.0, 15.0],
            "axis_direction": [0.0, 1.0, 0.0],
            "is_exterior": True,
            "adjacent_face_indices": [7],
        },
        {
            "face_index": 7,
            "surface_type": "cylinder",
            "area_mm2": 22.0,
            "bbox_bounds": [-5.0, 0.0, 5.0, 0.0, 10.0, 15.0],
            "axis_direction": [0.0, 1.0, 0.0],
            "is_exterior": True,
            "adjacent_face_indices": [6],
        },
        {
            "face_index": 8,
            "surface_type": "cone",
            "area_mm2": 18.0,
            "bbox_bounds": [5.0, 0.0, 5.0, 15.0, 10.0, 15.0],
            "axis_direction": [0.0, 1.0, 0.0],
            "is_exterior": True,
            "adjacent_face_indices": [],
        },
    ]

    result = detect_milled_faces_from_face_inventory(
        face_inventory,
        bbox_bounds=(-40.0, 0.0, -10.0, 15.0, 10.0, 15.0),
    )

    assert result["flat_milled_face_count"] == 2
    assert result["flat_side_milled_face_count"] == 2
    assert result["curved_milled_face_count"] == 2
    assert result["milled_face_count"] == 6
    assert result["count_strategy"]["flat"] == "connected_groups"
    assert len(result["flat_milled_feature_groups"]) == 2
    assert len(result["curved_milled_feature_groups"]) == 2


def test_detect_milled_faces_from_face_inventory_counts_off_axis_half_cylinder_as_curved():
    face_inventory = [
        {
            "face_index": 1,
            "surface_type": "cylinder",
            "area_mm2": math.pi * 2.0 * 40.0 * 0.5,
            "bbox_bounds": [0.0, 0.0, 0.0, 40.0, 2.0, 2.0],
            "axis_direction": [1.0, 0.0, 0.0],
            "axis_origin": [0.0, 1.0, 1.0],
            "is_exterior": True,
            "adjacent_face_indices": [2, 3, 4, 5],
        },
        {
            "face_index": 2,
            "surface_type": "torus",
            "area_mm2": 20.0,
            "bbox_bounds": [38.0, -1.0, -1.0, 42.0, 3.0, 3.0],
            "axis_direction": [1.0, 0.0, 0.0],
            "axis_origin": [40.0, 1.0, 1.0],
            "is_exterior": False,
            "adjacent_face_indices": [1],
        },
        {
            "face_index": 3,
            "surface_type": "torus",
            "area_mm2": 20.0,
            "bbox_bounds": [-2.0, -1.0, -1.0, 2.0, 3.0, 3.0],
            "axis_direction": [1.0, 0.0, 0.0],
            "axis_origin": [0.0, 1.0, 1.0],
            "is_exterior": False,
            "adjacent_face_indices": [1],
        },
        {
            "face_index": 4,
            "surface_type": "plane",
            "area_mm2": 40.0,
            "bbox_bounds": [0.0, 0.0, 0.0, 40.0, 0.0, 2.0],
            "sample_normal": [0.0, -1.0, 0.0],
            "is_exterior": False,
            "adjacent_face_indices": [1],
        },
        {
            "face_index": 5,
            "surface_type": "plane",
            "area_mm2": 40.0,
            "bbox_bounds": [0.0, 2.0, 0.0, 40.0, 2.0, 2.0],
            "sample_normal": [0.0, 1.0, 0.0],
            "is_exterior": False,
            "adjacent_face_indices": [1],
        },
    ]

    result = detect_milled_faces_from_face_inventory(
        face_inventory,
        bbox_bounds=(0.0, 0.0, 0.0, 100.0, 10.0, 10.0),
    )

    assert result["curved_milled_face_count"] == 1
    assert result["curved_milled_feature_groups"] == [[1]]


def test_detect_milled_faces_from_face_inventory_splits_asymmetric_cone_group():
    face_inventory = [
        {
            "face_index": 1,
            "surface_type": "cone",
            "area_mm2": 20.0,
            "bbox_bounds": [0.0, 0.0, 0.0, 8.0, 6.0, 8.0],
            "axis_direction": [0.0, 1.0, 0.0],
            "axis_origin": [4.0, 0.0, 4.0],
            "is_exterior": True,
            "adjacent_face_indices": [2],
        },
        {
            "face_index": 2,
            "surface_type": "cone",
            "area_mm2": 220.0,
            "bbox_bounds": [8.0, 0.0, 0.0, 28.0, 6.0, 20.0],
            "axis_direction": [0.0, 1.0, 0.0],
            "axis_origin": [18.0, 0.0, 10.0],
            "is_exterior": True,
            "adjacent_face_indices": [1],
        },
    ]

    result = detect_milled_faces_from_face_inventory(
        face_inventory,
        bbox_bounds=(0.0, 0.0, 0.0, 30.0, 10.0, 20.0),
    )

    assert result["curved_milled_face_count"] == 2
    assert result["curved_milled_feature_groups"] == [[1], [2]]


def test_detect_milled_faces_from_face_inventory_uses_hybrid_counting_on_turning_part():
    face_inventory = [
        {
            "face_index": 1,
            "surface_type": "plane",
            "area_mm2": 80.0,
            "bbox_bounds": [-10.0, -10.0, -60.0, 10.0, 10.0, -60.0],
            "sample_normal": [0.0, 0.0, -1.0],
            "is_exterior": True,
            "adjacent_face_indices": [],
        },
        {
            "face_index": 2,
            "surface_type": "plane",
            "area_mm2": 80.0,
            "bbox_bounds": [-10.0, -10.0, 60.0, 10.0, 10.0, 60.0],
            "sample_normal": [0.0, 0.0, 1.0],
            "is_exterior": True,
            "adjacent_face_indices": [],
        },
        {
            "face_index": 3,
            "surface_type": "plane",
            "area_mm2": 25.0,
            "bbox_bounds": [12.0, 5.0, -15.0, 22.0, 15.0, -15.0],
            "sample_normal": [0.8, 0.6, 0.0],
            "is_exterior": True,
            "adjacent_face_indices": [4],
        },
        {
            "face_index": 4,
            "surface_type": "plane",
            "area_mm2": 25.0,
            "bbox_bounds": [22.0, 5.0, -15.0, 32.0, 15.0, -15.0],
            "sample_normal": [0.8, 0.6, 0.0],
            "is_exterior": True,
            "adjacent_face_indices": [3],
        },
        {
            "face_index": 5,
            "surface_type": "plane",
            "area_mm2": 200.0,
            "bbox_bounds": [-30.0, -30.0, 0.0, 30.0, 30.0, 0.0],
            "sample_normal": [0.0, 0.0, 1.0],
            "is_exterior": True,
            "adjacent_face_indices": [6, 7, 8, 9, 10, 11, 12, 13],
        },
        {
            "face_index": 6,
            "surface_type": "bspline",
            "area_mm2": 120.0,
            "bbox_bounds": [-40.0, -10.0, -5.0, -20.0, 10.0, 20.0],
            "sample_normal": [-0.7, -0.6, 0.1],
            "is_exterior": True,
            "adjacent_face_indices": [],
        },
        {
            "face_index": 7,
            "surface_type": "bspline",
            "area_mm2": 118.0,
            "bbox_bounds": [-20.0, -10.0, -5.0, 0.0, 10.0, 20.0],
            "sample_normal": [-0.2, -0.97, 0.1],
            "is_exterior": True,
            "adjacent_face_indices": [],
        },
        {
            "face_index": 8,
            "surface_type": "bspline",
            "area_mm2": 30.0,
            "bbox_bounds": [0.0, -10.0, -5.0, 20.0, 10.0, 20.0],
            "sample_normal": [0.4, -0.9, 0.2],
            "is_exterior": True,
            "adjacent_face_indices": [],
        },
        {
            "face_index": 9,
            "surface_type": "bspline",
            "area_mm2": 28.0,
            "bbox_bounds": [20.0, -10.0, -5.0, 40.0, 10.0, 20.0],
            "sample_normal": [0.8, -0.4, 0.2],
            "is_exterior": True,
            "adjacent_face_indices": [],
        },
        {
            "face_index": 10,
            "surface_type": "bspline",
            "area_mm2": 122.0,
            "bbox_bounds": [-40.0, 10.0, -5.0, -20.0, 30.0, 20.0],
            "sample_normal": [-0.7, 0.6, 0.1],
            "is_exterior": True,
            "adjacent_face_indices": [],
        },
        {
            "face_index": 11,
            "surface_type": "bspline",
            "area_mm2": 121.0,
            "bbox_bounds": [-20.0, 10.0, -5.0, 0.0, 30.0, 20.0],
            "sample_normal": [-0.2, 0.97, 0.1],
            "is_exterior": True,
            "adjacent_face_indices": [],
        },
        {
            "face_index": 12,
            "surface_type": "bspline",
            "area_mm2": 27.0,
            "bbox_bounds": [0.0, 10.0, -5.0, 20.0, 30.0, 20.0],
            "sample_normal": [0.4, 0.9, 0.2],
            "is_exterior": True,
            "adjacent_face_indices": [],
        },
        {
            "face_index": 13,
            "surface_type": "bspline",
            "area_mm2": 29.0,
            "bbox_bounds": [20.0, 10.0, -5.0, 40.0, 30.0, 20.0],
            "sample_normal": [0.8, 0.4, 0.2],
            "is_exterior": True,
            "adjacent_face_indices": [],
        },
    ]

    result = detect_milled_faces_from_face_inventory(
        face_inventory,
        bbox_bounds=(-40.0, -30.0, -60.0, 40.0, 30.0, 60.0),
        turning_detection={
            "primary_axis": [0.0, 0.0, 1.0],
            "primary_cluster": {"face_indices": [20, 21]},
        },
    )

    assert result["flat_milled_face_count"] == 4
    assert result["flat_side_milled_face_count"] == 0
    assert result["curved_milled_face_count"] == 4
    assert result["excluded_turning_deck_faces"] == []
    assert result["count_strategy"]["flat"] == "raw_faces_plus_moderate_groups"


def test_detect_milled_faces_from_face_inventory_counts_short_turning_exceptions():
    face_inventory = [
        {
            "face_index": 1,
            "surface_type": "cone",
            "area_mm2": 80.0,
            "bbox_bounds": [10.0, -25.0, -25.0, 12.0, 0.0, 25.0],
            "axis_direction": [1.0, 0.0, 0.0],
            "axis_origin": [0.0, 0.0, 0.0],
            "sample_point_mm": [11.0, 24.5, 0.0],
            "is_exterior": True,
            "adjacent_face_indices": [],
        },
        {
            "face_index": 2,
            "surface_type": "cone",
            "area_mm2": 80.0,
            "bbox_bounds": [10.0, 0.0, -25.0, 12.0, 25.0, 25.0],
            "axis_direction": [1.0, 0.0, 0.0],
            "axis_origin": [0.0, 0.0, 0.0],
            "sample_point_mm": [11.0, 24.5, 0.0],
            "is_exterior": True,
            "adjacent_face_indices": [],
        },
        {
            "face_index": 3,
            "surface_type": "cone",
            "area_mm2": 80.0,
            "bbox_bounds": [32.0, -25.0, -25.0, 34.0, 0.0, 25.0],
            "axis_direction": [1.0, 0.0, 0.0],
            "axis_origin": [0.0, 0.0, 0.0],
            "sample_point_mm": [33.0, 24.5, 0.0],
            "is_exterior": True,
            "adjacent_face_indices": [],
        },
        {
            "face_index": 4,
            "surface_type": "cone",
            "area_mm2": 80.0,
            "bbox_bounds": [32.0, 0.0, -25.0, 34.0, 25.0, 25.0],
            "axis_direction": [1.0, 0.0, 0.0],
            "axis_origin": [0.0, 0.0, 0.0],
            "sample_point_mm": [33.0, 24.5, 0.0],
            "is_exterior": True,
            "adjacent_face_indices": [],
        },
        {
            "face_index": 5,
            "surface_type": "torus",
            "area_mm2": 100.0,
            "bbox_bounds": [33.5, -36.0, -36.0, 34.5, 0.0, 36.0],
            "axis_direction": [1.0, 0.0, 0.0],
            "axis_origin": [34.0, 0.0, 0.0],
            "sample_point_mm": [34.0, 31.8, 0.0],
            "is_exterior": True,
            "adjacent_face_indices": [],
        },
        {
            "face_index": 6,
            "surface_type": "torus",
            "area_mm2": 100.0,
            "bbox_bounds": [33.5, 0.0, -36.0, 34.5, 36.0, 36.0],
            "axis_direction": [1.0, 0.0, 0.0],
            "axis_origin": [34.0, 0.0, 0.0],
            "sample_point_mm": [34.0, 31.8, 0.0],
            "is_exterior": True,
            "adjacent_face_indices": [],
        },
    ]

    result = detect_milled_faces_from_face_inventory(
        face_inventory,
        bbox_bounds=(0.0, -40.0, -40.0, 44.0, 40.0, 40.0),
        turning_detection={
            "primary_axis": [1.0, 0.0, 0.0],
            "primary_cluster": {
                "dominant_axis_ratio": 0.55,
                "exterior_revolved_area_ratio": 0.85,
                "face_indices": [1, 2, 3, 4, 5, 6],
            },
            "turned_diameter_groups": [{"radius_mm": 39.75}],
        },
        pocket_detection={"candidates": [], "rejected_candidates": []},
        hole_detection={"candidates": [], "rejected_candidates": []},
        boss_detection={"candidates": [], "rejected_candidates": []},
    )

    assert result["circular_milled_face_count"] == 4
    assert result["curved_milled_face_count"] == 2


def test_detect_milled_faces_from_face_inventory_counts_convex_profile_edge_cylinders():
    face_inventory = [
        {
            "face_index": 1,
            "surface_type": "plane",
            "area_mm2": 1200.0,
            "bbox_bounds": [-20.0, 20.0, -20.0, 20.0, 50.0, -20.0],
            "sample_normal": [0.0, 1.0, 0.0],
            "is_exterior": True,
            "adjacent_face_indices": [27, 31, 35],
        },
        {
            "face_index": 7,
            "surface_type": "plane",
            "area_mm2": 1200.0,
            "bbox_bounds": [-20.0, 20.0, 20.0, 20.0, 50.0, 20.0],
            "sample_normal": [0.0, 1.0, 0.0],
            "is_exterior": True,
            "adjacent_face_indices": [27, 31, 35],
        },
        {
            "face_index": 30,
            "surface_type": "plane",
            "area_mm2": 600.0,
            "bbox_bounds": [0.0, 20.0, 12.0, 16.0, 50.0, 20.0],
            "sample_normal": [-0.866025, 0.0, -0.5],
            "is_exterior": True,
            "adjacent_face_indices": [31],
        },
        {
            "face_index": 32,
            "surface_type": "plane",
            "area_mm2": 600.0,
            "bbox_bounds": [0.0, 20.0, 12.0, 16.0, 50.0, 20.0],
            "sample_normal": [0.0, 0.0, -1.0],
            "is_exterior": True,
            "adjacent_face_indices": [31],
        },
        {
            "face_index": 34,
            "surface_type": "plane",
            "area_mm2": 600.0,
            "bbox_bounds": [0.0, 20.0, -20.0, 16.0, 50.0, -12.0],
            "sample_normal": [0.0, 0.0, 1.0],
            "is_exterior": True,
            "adjacent_face_indices": [35],
        },
        {
            "face_index": 36,
            "surface_type": "plane",
            "area_mm2": 600.0,
            "bbox_bounds": [0.0, 20.0, -20.0, 16.0, 50.0, -12.0],
            "sample_normal": [-0.866025, 0.0, 0.5],
            "is_exterior": True,
            "adjacent_face_indices": [35],
        },
        {
            "face_index": 38,
            "surface_type": "plane",
            "area_mm2": 600.0,
            "bbox_bounds": [-20.0, 20.0, -8.0, -18.0, 50.0, 8.0],
            "sample_normal": [0.866025, 0.0, -0.5],
            "is_exterior": True,
            "adjacent_face_indices": [27],
        },
        {
            "face_index": 27,
            "surface_type": "cylinder",
            "area_mm2": 484.4357,
            "bbox_bounds": [-20.0, 20.0, -7.8564, -18.3923, 50.0, 7.8564],
            "axis_direction": [0.0, 1.0, 0.0],
            "axis_origin": [0.0, 50.0, 0.0],
            "axial_span_mm": 30.0,
            "is_exterior": True,
            "adjacent_face_indices": [1, 7, 38],
        },
        {
            "face_index": 31,
            "surface_type": "cylinder",
            "area_mm2": 484.4357,
            "bbox_bounds": [2.3923, 20.0, 12.0, 16.0, 50.0, 19.8564],
            "axis_direction": [0.0, 1.0, 0.0],
            "axis_origin": [0.0, 50.0, 0.0],
            "axial_span_mm": 30.0,
            "is_exterior": True,
            "adjacent_face_indices": [1, 7, 30, 32],
        },
        {
            "face_index": 35,
            "surface_type": "cylinder",
            "area_mm2": 484.4357,
            "bbox_bounds": [2.3923, 20.0, -19.8564, 16.0, 50.0, -12.0],
            "axis_direction": [0.0, 1.0, 0.0],
            "axis_origin": [0.0, 50.0, 0.0],
            "axial_span_mm": 30.0,
            "is_exterior": True,
            "adjacent_face_indices": [1, 7, 34, 36],
        },
    ]

    result = detect_milled_faces_from_face_inventory(
        face_inventory,
        bbox_bounds=(-20.0, 0.0, -25.0, 20.0, 50.0, 25.0),
    )

    assert result["convex_profile_edge_milled_face_count"] == 3
    assert result["convex_profile_edge_milled_face_indices"] == [27, 31, 35]


def test_detect_milled_faces_from_face_inventory_counts_open_pocket_side_walls_and_splits_recessed_flat():
    face_inventory = [
        {
            "face_index": 1,
            "surface_type": "plane",
            "area_mm2": 1636.705,
            "bbox_bounds": [-50.0, 0.0, -20.0, 50.0, 0.0, 20.0],
            "sample_normal": [0.0, 1.0, 0.0],
            "is_exterior": True,
            "adjacent_face_indices": [],
        },
        {
            "face_index": 8,
            "surface_type": "plane",
            "area_mm2": 7981.67,
            "bbox_bounds": [-50.0, 0.0, -20.0, 50.0, 0.0, 20.0],
            "sample_normal": [0.0, 1.0, 0.0],
            "is_exterior": True,
            "adjacent_face_indices": [11, 14],
        },
        {
            "face_index": 11,
            "surface_type": "plane",
            "area_mm2": 914.7005,
            "bbox_bounds": [-50.0, 0.0, -20.0, -40.0, 20.0, 20.0],
            "sample_normal": [1.0, 0.0, 0.0],
            "is_exterior": True,
            "adjacent_face_indices": [8, 18, 16, 17],
        },
        {
            "face_index": 14,
            "surface_type": "plane",
            "area_mm2": 1154.7005,
            "bbox_bounds": [40.0, 0.0, -20.0, 50.0, 20.0, 20.0],
            "sample_normal": [-1.0, 0.0, 0.0],
            "is_exterior": True,
            "adjacent_face_indices": [8],
        },
        {
            "face_index": 18,
            "surface_type": "plane",
            "area_mm2": 401.0973,
            "bbox_bounds": [-44.0, 10.0, -6.0, -32.0, 10.0, 6.0],
            "sample_normal": [0.0, 1.0, 0.0],
            "is_exterior": True,
            "adjacent_face_indices": [11, 16, 17],
        },
        {
            "face_index": 22,
            "surface_type": "plane",
            "area_mm2": 401.0973,
            "bbox_bounds": [-10.0, 10.0, -6.0, 2.0, 10.0, 6.0],
            "sample_normal": [0.0, 1.0, 0.0],
            "is_exterior": True,
            "adjacent_face_indices": [19, 21],
        },
        {
            "face_index": 26,
            "surface_type": "plane",
            "area_mm2": 401.0973,
            "bbox_bounds": [10.0, 10.0, -6.0, 22.0, 10.0, 6.0],
            "sample_normal": [0.0, 1.0, 0.0],
            "is_exterior": True,
            "adjacent_face_indices": [24, 25],
        },
        {
            "face_index": 16,
            "surface_type": "plane",
            "area_mm2": 120.0,
            "bbox_bounds": [-38.0, 10.0, -6.0, -26.0, 10.0, 6.0],
            "sample_normal": [0.0, 0.0, 1.0],
            "is_exterior": False,
            "adjacent_face_indices": [11, 18],
        },
        {
            "face_index": 17,
            "surface_type": "plane",
            "area_mm2": 120.0,
            "bbox_bounds": [-38.0, 10.0, -6.0, -26.0, 10.0, 6.0],
            "sample_normal": [0.0, 0.0, -1.0],
            "is_exterior": False,
            "adjacent_face_indices": [11, 18],
        },
        {
            "face_index": 19,
            "surface_type": "plane",
            "area_mm2": 120.0,
            "bbox_bounds": [-10.0, 10.0, -6.0, 2.0, 10.0, 6.0],
            "sample_normal": [-0.866025, 0.0, 0.5],
            "is_exterior": False,
            "adjacent_face_indices": [22],
        },
        {
            "face_index": 21,
            "surface_type": "plane",
            "area_mm2": 120.0,
            "bbox_bounds": [-10.0, 10.0, -6.0, 2.0, 10.0, 6.0],
            "sample_normal": [0.866025, 0.0, -0.5],
            "is_exterior": False,
            "adjacent_face_indices": [22],
        },
        {
            "face_index": 24,
            "surface_type": "plane",
            "area_mm2": 120.0,
            "bbox_bounds": [10.0, 10.0, -6.0, 22.0, 10.0, 6.0],
            "sample_normal": [-0.866025, 0.0, -0.5],
            "is_exterior": False,
            "adjacent_face_indices": [26],
        },
        {
            "face_index": 25,
            "surface_type": "plane",
            "area_mm2": 120.0,
            "bbox_bounds": [10.0, 10.0, -6.0, 22.0, 10.0, 6.0],
            "sample_normal": [0.866025, 0.0, 0.5],
            "is_exterior": False,
            "adjacent_face_indices": [26],
        },
    ]

    pocket_detection = {
        "candidates": [
            {"face_index": 18, "subtype": "open_pocket", "is_exterior": True},
            {"face_index": 22, "subtype": "open_pocket", "is_exterior": True},
            {"face_index": 26, "subtype": "open_pocket", "is_exterior": True},
        ]
    }

    result = detect_milled_faces_from_face_inventory(
        face_inventory,
        bbox_bounds=(-50.0, 0.0, -30.0, 50.0, 50.0, 30.0),
        pocket_detection=pocket_detection,
    )

    assert result["flat_milled_face_count"] == 5
    assert result["flat_side_milled_face_count"] == 6
    assert result["flat_side_milled_face_indices"] == [11, 14, 19, 21, 24, 25]


@pytest.mark.parametrize("fixture_name", FEATURE_FIXTURE_NAMES)
def test_feature_detection_stack_matches_real_feature_fixture_counts(fixture_name: str):
    fixture = _load_feature_fixture(fixture_name)

    result = _run_feature_detection_stack(fixture)

    _assert_detection_counts_match_fixture(result, fixture)
    case_id = fixture["case_id"]
    if case_id == "sample_4":
        assert result["hole_detection"]["threaded_holes_count"] == 6
        assert result["turning_detection"]["primary_axis"] is None
    if case_id == "sample_8":
        assert result["hole_detection"]["threaded_holes_count"] == 7
        assert result["milled_face_detection"]["concave_fillet_edge_milled_face_indices"]
