from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]

EXPECTED_DETECTION_KEYS: dict[str, tuple[str, ...]] = {
    "turning_detection": (
        "rotational_symmetry",
        "turned_faces_present",
        "turned_face_count",
        "turned_diameter_faces_count",
        "turned_end_faces_count",
        "turned_profile_faces_count",
        "outer_diameter_groove_count",
        "end_face_groove_count",
    ),
    "hole_detection": (
        "hole_count",
        "through_hole_count",
        "partial_hole_count",
        "bore_count",
        "stepped_hole_count",
    ),
    "pocket_detection": (
        "pocket_count",
        "open_pocket_count",
        "closed_pocket_count",
    ),
    "boss_detection": ("boss_count",),
    "milled_face_detection": (
        "milled_face_count",
        "flat_milled_face_count",
        "flat_side_milled_face_count",
        "curved_milled_face_count",
        "circular_milled_face_count",
        "convex_profile_edge_milled_face_count",
        "concave_fillet_edge_milled_face_count",
    ),
}


def _derive_case_id(inspection_path: Path) -> str:
    stem = inspection_path.stem
    suffix = "_feature_inspection"
    if stem.endswith(suffix):
        return stem[: -len(suffix)]
    return stem


def _build_expected_detection(inspection_payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    expected_detection: dict[str, dict[str, Any]] = {}
    for section_name, keys in EXPECTED_DETECTION_KEYS.items():
        section_payload = inspection_payload.get(section_name)
        if not isinstance(section_payload, dict):
            raise ValueError(f"Inspection artifact is missing '{section_name}'.")
        expected_detection[section_name] = {
            key: section_payload.get(key)
            for key in keys
        }
    return expected_detection


def _portable_path(path: Path) -> str:
    try:
        return path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def build_fixture_payload(
    inspection_payload: dict[str, Any],
    *,
    case_id: str,
    inspection_path: Path,
) -> dict[str, Any]:
    face_inventory = inspection_payload.get("face_inventory")
    bbox_bounds = inspection_payload.get("bbox_bounds")
    if not isinstance(face_inventory, list):
        raise ValueError("Inspection artifact is missing a face_inventory list.")
    if not isinstance(bbox_bounds, list) or len(bbox_bounds) != 6:
        raise ValueError("Inspection artifact is missing bbox_bounds.")

    return {
        "case_id": case_id,
        "source_inspection": _portable_path(inspection_path),
        "source_part": inspection_payload.get("part_filename"),
        "bbox_bounds": bbox_bounds,
        "face_inventory": face_inventory,
        "expected_detection": _build_expected_detection(inspection_payload),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Reduce a feature-parity inspection artifact into a stable geometry "
            "fixture for cnc_geometry_occ regression tests."
        )
    )
    parser.add_argument("--inspection", required=True, help="Path to a feature inspection JSON artifact.")
    parser.add_argument("--out", required=True, help="Path to write the reduced fixture JSON.")
    parser.add_argument("--case-id", help="Optional explicit case id. Defaults to the inspection filename stem.")
    args = parser.parse_args()

    inspection_path = Path(args.inspection).resolve()
    out_path = Path(args.out).resolve()
    case_id = args.case_id or _derive_case_id(inspection_path)

    inspection_payload = json.loads(inspection_path.read_text(encoding="utf-8-sig"))
    fixture_payload = build_fixture_payload(
        inspection_payload,
        case_id=case_id,
        inspection_path=inspection_path,
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(fixture_payload, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote feature fixture for {case_id} -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
