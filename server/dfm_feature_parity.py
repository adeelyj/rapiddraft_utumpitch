from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .dfm_benchmark import (
    extract_cadex_feature_reference,
    extract_feature_categories_from_facts,
    load_benchmark_manifest,
)
from .dfm_bundle import load_dfm_bundle
from .dfm_part_facts_bridge import build_extracted_facts_from_part_facts
from .part_facts import PartFactsService


def generate_feature_parity_report(
    manifest_path: Path,
    *,
    run_label: str | None = None,
) -> dict[str, Any]:
    manifest = load_benchmark_manifest(manifest_path)
    repo_root = manifest.manifest_path.parent.parent
    bundle = load_dfm_bundle(bundle_dir=repo_root / "server" / "dfm", repo_root=repo_root)

    timestamp = datetime.now(timezone.utc)
    run_id = run_label.strip() if isinstance(run_label, str) and run_label.strip() else timestamp.strftime("%Y%m%dT%H%M%SZ")
    output_root = repo_root / "output" / "dfm_feature_parity" / run_id
    output_root.mkdir(parents=True, exist_ok=True)
    part_facts_service = PartFactsService(root=output_root / "_runtime", bundle=bundle)

    cases: list[dict[str, Any]] = []
    for case in manifest.cases:
        cadex_payload = json.loads(case.cadex_features_file.read_text(encoding="utf-8"))
        cadex_reference = extract_cadex_feature_reference(cadex_payload)

        part_facts_payload = part_facts_service.get_or_create(
            model_id=f"feature_parity_{case.case_id}",
            step_path=case.step_file,
            component_node_name=case.component_node_name or "benchmark_root",
            component_display_name=case.label,
            component_profile={"material": "", "manufacturingProcess": "", "industry": ""},
            triangle_count=None,
            assembly_component_count=2 if case.component_node_name else 1,
            force_refresh=True,
        )
        extracted_facts = build_extracted_facts_from_part_facts(
            part_facts_payload=part_facts_payload,
            component_profile={},
            context_payload={},
        )
        inspection_payload = part_facts_service.geometry_analyzer.inspect_feature_inventory(
            step_path=case.step_file,
            component_node_name=case.component_node_name or "benchmark_root",
        )
        inspection_path = output_root / f"{case.case_id}_feature_inspection.json"
        inspection_path.write_text(
            json.dumps(inspection_payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        current_snapshot = summarize_current_detection(extracted_facts)
        group_assessments = [
            assess_feature_group(group, extracted_facts)
            for group in cadex_reference.get("feature_groups", [])
        ]
        case_summary = summarize_case_assessments(group_assessments)

        cases.append(
            {
                "case_id": case.case_id,
                "label": case.label,
                "step_file": str(case.step_file),
                "cadex_feature_reference": cadex_reference,
                "current_detection_snapshot": current_snapshot,
                "part_facts_errors": part_facts_payload.get("errors", []),
                "inspection_artifact": str(inspection_path),
                "group_assessments": group_assessments,
                "case_summary": case_summary,
            }
        )

    report = {
        "generated_at": timestamp.isoformat(),
        "manifest_path": str(manifest.manifest_path),
        "output_root": str(output_root),
        "cases": cases,
        "summary": summarize_feature_parity_report(cases),
    }
    (output_root / "summary.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (output_root / "summary.md").write_text(
        render_feature_parity_markdown(report),
        encoding="utf-8",
    )
    return report


def summarize_current_detection(extracted_facts: dict[str, Any]) -> dict[str, Any]:
    return {
        "detected_feature_families": extract_feature_categories_from_facts(extracted_facts),
        "key_facts": {
            key: extracted_facts.get(key)
            for key in (
                "hole_features",
                "hole_count",
                "pocket_count",
                "open_pocket_count",
                "closed_pocket_count",
                "through_hole_count",
                "partial_hole_count",
                "stepped_hole_count",
                "bore_count",
                "hole_diameter",
                "hole_depth",
                "pockets_present",
                "pocket_depth",
                "pocket_corner_radius",
                "min_internal_radius_mm",
                "bbox_x_mm",
                "bbox_y_mm",
                "bbox_z_mm",
                "feature_complexity_score",
                "boss_count",
                "milled_faces_present",
                "milled_face_count",
                "flat_milled_face_count",
                "flat_side_milled_face_count",
                "curved_milled_face_count",
                "convex_profile_edge_milled_face_count",
                "concave_fillet_edge_milled_face_count",
                "turned_faces_present",
                "rotational_symmetry",
                "turned_face_count",
                "turned_diameter_faces_count",
                "turned_end_faces_count",
                "turned_profile_faces_count",
            )
            if key in extracted_facts
        },
    }


def assess_feature_group(
    group: dict[str, Any],
    extracted_facts: dict[str, Any],
) -> dict[str, Any]:
    name = str(group.get("name") or "").strip()
    normalized = name.lower()
    categories = list(group.get("categories", []))
    reference_count = _safe_int(group.get("feature_count"))
    detected_count, detected_fact_key = _detected_count_for_group(name, extracted_facts)

    status = "not_detected"
    note = "No matching feature-specific detector is currently surfaced by part facts."
    recommended_hook = "Add an explicit detector for this Cadex feature family in OCC-based geometry extraction."

    if "open pocket" in normalized:
        specific_count = _safe_int(extracted_facts.get("open_pocket_count")) or 0
        if specific_count > 0:
            status = "partially_detected"
            note = (
                "Open-pocket geometry is surfaced with a dedicated subtype count, even though the product taxonomy is still broader than Cadex's."
            )
        elif extracted_facts.get("pockets_present"):
            status = "partially_detected"
            note = (
                "Pocket-family geometry is detected today, but this case is still inferred from generic pocket facts rather than an open-pocket subtype."
            )
        recommended_hook = (
            "Use recessed floor faces plus side-wall support counts to distinguish side-open pockets from enclosed ones."
        )
    elif "closed pocket" in normalized:
        specific_count = _safe_int(extracted_facts.get("closed_pocket_count")) or 0
        if specific_count > 0:
            status = "partially_detected"
            note = (
                "Closed-pocket geometry is surfaced with a dedicated subtype count, even though the product taxonomy is still broader than Cadex's."
            )
        elif extracted_facts.get("pockets_present"):
            status = "partially_detected"
            note = (
                "Pocket-family geometry is detected today, but this case is still inferred from generic pocket facts rather than a closed-pocket subtype."
            )
        recommended_hook = (
            "Use recessed floor faces plus side-wall support counts to distinguish enclosed pockets from open ones."
        )
    elif "pocket" in normalized:
        if extracted_facts.get("pockets_present"):
            status = "partially_detected"
            note = (
                "Pocket-like cavity geometry is detected today, and the product now surfaces open and closed pocket subtypes when the geometry supports it."
            )
        recommended_hook = (
            "Keep refining recessed floor and wall-support heuristics so more pockets land in explicit open or closed buckets."
        )
    elif "through hole" in normalized:
        specific_count = _safe_int(extracted_facts.get("through_hole_count")) or 0
        if specific_count > 0:
            status = "partially_detected"
            note = (
                "Through-hole geometry is surfaced with a dedicated subtype count, even though the product taxonomy is still broader than Cadex's."
            )
        elif extracted_facts.get("hole_features"):
            status = "partially_detected"
            note = (
                "Hole-family geometry is detected today, but this case is still inferred from generic hole facts rather than a through-hole subtype."
            )
        recommended_hook = (
            "Use cylindrical-face completeness plus coaxial grouping to distinguish full through holes from partial cylindrical cutouts."
        )
    elif "partial hole" in normalized:
        specific_count = _safe_int(extracted_facts.get("partial_hole_count")) or 0
        if specific_count > 0:
            status = "partially_detected"
            note = (
                "Partial-hole geometry is surfaced with a dedicated subtype count, even though the product taxonomy is still broader than Cadex's."
            )
        elif extracted_facts.get("hole_features"):
            status = "partially_detected"
            note = (
                "Hole-family geometry is detected today, but this case is still inferred from generic hole facts rather than a partial-hole subtype."
            )
        recommended_hook = (
            "Use cylindrical-face wall completeness and side-opening clues to separate partial holes from full through holes."
        )
    elif "stepped hole" in normalized:
        specific_count = _safe_int(extracted_facts.get("stepped_hole_count")) or 0
        if specific_count > 0:
            status = "partially_detected"
            note = (
                "Stepped-hole geometry is surfaced with a dedicated count, even though the product taxonomy is still broader than Cadex's."
            )
        elif extracted_facts.get("hole_features"):
            status = "partially_detected"
            note = (
                "Hole-family geometry is detected today, but this case is still inferred from generic hole facts rather than a stepped-hole subtype."
            )
        recommended_hook = (
            "Count nested coaxial cylinder stacks as one stepped-hole feature instead of treating each cylindrical segment as a separate hole."
        )
    elif "bore" in normalized:
        specific_count = _safe_int(extracted_facts.get("bore_count")) or 0
        if specific_count > 0:
            status = "partially_detected"
            note = (
                "Bore geometry is surfaced with a dedicated subtype count, even though the product taxonomy is still broader than Cadex's."
            )
        elif extracted_facts.get("hole_features"):
            status = "partially_detected"
            note = (
                "Hole-family geometry is detected today, but this case is still inferred from generic hole facts rather than a bore subtype."
            )
        recommended_hook = (
            "Use coaxial grouping and long-axis depth checks to separate bores from exterior turned cylinders."
        )
    elif "hole" in normalized:
        if extracted_facts.get("hole_features"):
            status = "partially_detected"
            note = (
                "Hole-family geometry is detected today, but bore, through-hole, and partial-hole subclasses are not explicit."
            )
        recommended_hook = (
            "Extend cylindrical-face analysis with entry/exit and blind-end classification to separate bore, through, and partial holes."
        )
    elif "turn" in normalized or "lathe" in normalized:
        specific_count = 0
        if "turn diameter" in normalized:
            specific_count = _safe_int(extracted_facts.get("turned_diameter_faces_count")) or 0
        elif "turn face" in normalized:
            specific_count = _safe_int(extracted_facts.get("turned_end_faces_count")) or 0
        elif "turn form" in normalized:
            specific_count = _safe_int(extracted_facts.get("turned_profile_faces_count")) or 0
        if specific_count > 0:
            status = "partially_detected"
            note = (
                "Turning-style geometry signals are surfaced with subtype counts, but the groups remain product-generic rather than Cadex-identical."
            )
        elif extracted_facts.get("turned_faces_present") or extracted_facts.get("rotational_symmetry"):
            status = "partially_detected"
            note = (
                "Turning-style geometry signals are present, but this Cadex subtype is still inferred from generic turning facts."
            )
        else:
            note = (
                "Turning-style feature groups are not surfaced yet, even though sample 2 suggests this is an important gap."
            )
        recommended_hook = (
            "Add a primary-axis and revolved-surface detector that marks rotational symmetry and groups cylindrical/conical turned faces."
        )
    elif "boss" in normalized:
        if extracted_facts.get("boss_features") or (_safe_int(extracted_facts.get("boss_count")) or 0) > 0:
            status = "partially_detected"
            note = (
                "Boss-like protrusion geometry is surfaced with a dedicated count, even though the product taxonomy is still broader than Cadex's."
            )
        recommended_hook = (
            "Keep refining the protrusion detector so more non-cylindrical bosses can be counted explicitly."
        )
    elif "convex profile edge" in normalized or "concave fillet edge" in normalized or "milled" in normalized or "milling" in normalized:
        if "convex profile edge" in normalized:
            specific_count = _safe_int(extracted_facts.get("convex_profile_edge_milled_face_count")) or 0
            if specific_count > 0:
                status = "partially_detected"
                note = (
                    "Convex edge-profile milling geometry is now surfaced with a dedicated count from exterior cylindrical profile segments."
                )
        elif "concave fillet edge" in normalized:
            specific_count = _safe_int(extracted_facts.get("concave_fillet_edge_milled_face_count")) or 0
            if specific_count > 0:
                status = "partially_detected"
                note = (
                    "Concave fillet edge milling geometry is surfaced with a dedicated count, even though the product taxonomy is still evolving."
                )
        elif "curved milled" in normalized:
            specific_count = _safe_int(extracted_facts.get("curved_milled_face_count")) or 0
            if specific_count > 0:
                status = "partially_detected"
                note = (
                    "Curved milled faces are surfaced with a dedicated count, even though the product taxonomy is still broader than Cadex's."
                )
        elif "flat side milled" in normalized:
            specific_count = _safe_int(extracted_facts.get("flat_side_milled_face_count")) or 0
            if specific_count > 0:
                status = "partially_detected"
                note = (
                    "Flat side milled faces are surfaced with a dedicated count, even though the product taxonomy is still broader than Cadex's."
                )
        else:
            specific_count = _safe_int(extracted_facts.get("flat_milled_face_count")) or 0
            if specific_count > 0:
                status = "partially_detected"
                note = (
                    "Flat milled faces are surfaced with a dedicated count, even though the product taxonomy is still broader than Cadex's."
                )
        if status == "not_detected" and extracted_facts.get("milled_faces_present"):
            status = "partially_detected"
            note = (
                "Milled-face geometry is detected today, but this Cadex subtype is still inferred from generic milled-face facts."
            )
        recommended_hook = (
            "Keep refining surface taxonomy over planar and curved accessible faces so milled-face groups can be counted explicitly."
        )

    count_comparison = _build_count_comparison(
        reference_count=reference_count,
        detected_count=detected_count,
        detected_fact_key=detected_fact_key,
    )
    if count_comparison["alignment"] == "exact_match":
        status = "matched"

    return {
        "name": name,
        "feature_count": reference_count,
        "categories": categories,
        "status": status,
        "note": note,
        "recommended_hook": recommended_hook,
        "count_comparison": count_comparison,
    }


def render_feature_parity_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# DFM Feature Parity",
        "",
        f"Generated at: {report.get('generated_at', '')}",
        "",
    ]
    summary = report.get("summary", {})
    if isinstance(summary, dict):
        lines.extend(
            [
                "## Report Summary",
                "",
                f"- Cases: {summary.get('case_count', 0)}",
                f"- Feature-family matches: {summary.get('family_matched_group_count', 0)}/{summary.get('feature_group_count', 0)}",
                f"- Exact count matches: {summary.get('exact_count_match_group_count', 0)}/{summary.get('countable_group_count', 0)} countable groups",
                f"- Exact milled-face count matches: {summary.get('milled_exact_count_match_group_count', 0)}/{summary.get('milled_group_count', 0)}",
            ]
        )
        count_drifts = summary.get("count_drifts", [])
        if isinstance(count_drifts, list) and count_drifts:
            lines.append("- Remaining count drifts:")
            for drift in count_drifts:
                if not isinstance(drift, dict):
                    continue
                lines.append(
                    "  - "
                    f"{drift.get('case_id', '')} / {drift.get('name', '')}: "
                    f"Cadex {drift.get('reference_count', '?')}, "
                    f"Product {drift.get('detected_count', '?')}, "
                    f"delta {drift.get('delta', '?'):+}"
                )
        lines.append("")
    for case in report.get("cases", []):
        if not isinstance(case, dict):
            continue
        case_summary = case.get("case_summary", {})
        lines.extend(
            [
                f"## {case.get('case_id', '')} - {case.get('label', '')}",
                "",
                f"STEP: `{case.get('step_file', '')}`",
                f"Inspection artifact: `{case.get('inspection_artifact', '')}`",
                "",
                "Case summary:",
                f"- Feature-family matches: {case_summary.get('family_matched_group_count', 0)}/{case_summary.get('feature_group_count', 0)}",
                f"- Exact count matches: {case_summary.get('exact_count_match_group_count', 0)}/{case_summary.get('countable_group_count', 0)} countable groups",
                f"- Exact milled-face count matches: {case_summary.get('milled_exact_count_match_group_count', 0)}/{case_summary.get('milled_group_count', 0)}",
                "",
                "Current product snapshot:",
                f"- Detected feature families: {', '.join(case.get('current_detection_snapshot', {}).get('detected_feature_families', [])) or 'none'}",
            ]
        )
        for group in case.get("group_assessments", []):
            if not isinstance(group, dict):
                continue
            count_comparison = group.get("count_comparison", {})
            lines.extend(
                [
                    f"- {group.get('name', '')}: {group.get('status', '')}",
                    f"  count: {_render_count_comparison(count_comparison)}",
                    f"  note: {group.get('note', '')}",
                    f"  hook: {group.get('recommended_hook', '')}",
                ]
            )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def summarize_case_assessments(group_assessments: list[dict[str, Any]]) -> dict[str, Any]:
    feature_group_count = len(group_assessments)
    family_matched_group_count = sum(
        1
        for group in group_assessments
        if _is_family_matched(group.get("status"))
    )
    countable_groups = [
        group
        for group in group_assessments
        if _count_alignment(group) != "not_applicable"
    ]
    exact_count_match_group_count = sum(
        1 for group in countable_groups if _count_alignment(group) == "exact_match"
    )
    milled_groups = [
        group
        for group in group_assessments
        if "milled" in str(group.get("name") or "").lower()
    ]
    milled_exact_count_match_group_count = sum(
        1 for group in milled_groups if _count_alignment(group) == "exact_match"
    )
    count_drifts = [
        {
            "name": group.get("name"),
            "reference_count": group.get("count_comparison", {}).get("reference_count"),
            "detected_count": group.get("count_comparison", {}).get("detected_count"),
            "delta": group.get("count_comparison", {}).get("delta"),
            "alignment": _count_alignment(group),
        }
        for group in countable_groups
        if _count_alignment(group) in {"under_detected", "over_detected"}
    ]
    return {
        "feature_group_count": feature_group_count,
        "family_matched_group_count": family_matched_group_count,
        "countable_group_count": len(countable_groups),
        "exact_count_match_group_count": exact_count_match_group_count,
        "milled_group_count": len(milled_groups),
        "milled_exact_count_match_group_count": milled_exact_count_match_group_count,
        "count_drifts": count_drifts,
    }


def summarize_feature_parity_report(cases: list[dict[str, Any]]) -> dict[str, Any]:
    summary = {
        "case_count": len(cases),
        "feature_group_count": 0,
        "family_matched_group_count": 0,
        "countable_group_count": 0,
        "exact_count_match_group_count": 0,
        "milled_group_count": 0,
        "milled_exact_count_match_group_count": 0,
        "count_drifts": [],
    }
    for case in cases:
        if not isinstance(case, dict):
            continue
        case_summary = case.get("case_summary", {})
        if not isinstance(case_summary, dict):
            continue
        summary["feature_group_count"] += int(case_summary.get("feature_group_count", 0))
        summary["family_matched_group_count"] += int(
            case_summary.get("family_matched_group_count", 0)
        )
        summary["countable_group_count"] += int(case_summary.get("countable_group_count", 0))
        summary["exact_count_match_group_count"] += int(
            case_summary.get("exact_count_match_group_count", 0)
        )
        summary["milled_group_count"] += int(case_summary.get("milled_group_count", 0))
        summary["milled_exact_count_match_group_count"] += int(
            case_summary.get("milled_exact_count_match_group_count", 0)
        )
        for drift in case_summary.get("count_drifts", []):
            if not isinstance(drift, dict):
                continue
            summary["count_drifts"].append(
                {
                    "case_id": case.get("case_id"),
                    "label": case.get("label"),
                    **drift,
                }
            )
    return summary


def _detected_count_for_group(
    group_name: str,
    extracted_facts: dict[str, Any],
) -> tuple[int | None, str | None]:
    normalized = group_name.lower()
    mappings = (
        ("open pocket", "open_pocket_count"),
        ("closed pocket", "closed_pocket_count"),
        ("through hole", "through_hole_count"),
        ("partial hole", "partial_hole_count"),
        ("stepped hole", "stepped_hole_count"),
        ("bore", "bore_count"),
        ("turn diameter", "turned_diameter_faces_count"),
        ("turn face", "turned_end_faces_count"),
        ("turn form", "turned_profile_faces_count"),
        ("convex profile edge", "convex_profile_edge_milled_face_count"),
        ("concave fillet edge", "concave_fillet_edge_milled_face_count"),
        ("flat side milled", "flat_side_milled_face_count"),
        ("curved milled", "curved_milled_face_count"),
    )
    for needle, fact_key in mappings:
        if needle in normalized:
            return _safe_int(extracted_facts.get(fact_key)), fact_key
    if "milled" in normalized and "flat" in normalized and "side" not in normalized:
        return _safe_int(extracted_facts.get("flat_milled_face_count")), "flat_milled_face_count"
    if "turn" in normalized or "lathe" in normalized:
        return _safe_int(extracted_facts.get("turned_face_count")), "turned_face_count"
    if "boss" in normalized:
        return _safe_int(extracted_facts.get("boss_count")), "boss_count"
    if "pocket" in normalized:
        return _safe_int(extracted_facts.get("pocket_count")), "pocket_count"
    if "hole" in normalized:
        return _safe_int(extracted_facts.get("hole_count")), "hole_count"
    if "milled" in normalized:
        return _safe_int(extracted_facts.get("milled_face_count")), "milled_face_count"
    return None, None


def _build_count_comparison(
    *,
    reference_count: int | None,
    detected_count: int | None,
    detected_fact_key: str | None,
) -> dict[str, Any]:
    if reference_count is None and detected_count is None:
        return {
            "reference_count": None,
            "detected_count": None,
            "delta": None,
            "alignment": "not_applicable",
            "detected_fact_key": detected_fact_key,
        }
    if reference_count is None or detected_count is None:
        return {
            "reference_count": reference_count,
            "detected_count": detected_count,
            "delta": None,
            "alignment": "count_unavailable",
            "detected_fact_key": detected_fact_key,
        }
    delta = detected_count - reference_count
    if delta == 0:
        alignment = "exact_match"
    elif delta < 0:
        alignment = "under_detected"
    else:
        alignment = "over_detected"
    return {
        "reference_count": reference_count,
        "detected_count": detected_count,
        "delta": delta,
        "alignment": alignment,
        "detected_fact_key": detected_fact_key,
    }


def _render_count_comparison(count_comparison: Any) -> str:
    if not isinstance(count_comparison, dict):
        return "not available"
    alignment = str(count_comparison.get("alignment") or "not_applicable")
    if alignment == "not_applicable":
        return "not applicable"
    reference_count = count_comparison.get("reference_count")
    detected_count = count_comparison.get("detected_count")
    delta = count_comparison.get("delta")
    if alignment == "count_unavailable":
        return f"Cadex {reference_count}, Product {detected_count}, delta unavailable"
    if isinstance(delta, int):
        return (
            f"Cadex {reference_count}, Product {detected_count}, "
            f"delta {delta:+} ({alignment})"
        )
    return f"Cadex {reference_count}, Product {detected_count}, {alignment}"


def _is_family_matched(status: Any) -> bool:
    return str(status or "") in {"matched", "partially_detected"}


def _count_alignment(group_assessment: dict[str, Any]) -> str:
    count_comparison = group_assessment.get("count_comparison", {})
    if not isinstance(count_comparison, dict):
        return "not_applicable"
    return str(count_comparison.get("alignment") or "not_applicable")


def _safe_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None
