from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .dfm_bundle import load_dfm_bundle
from .dfm_effective_context import resolve_effective_planning_inputs
from .dfm_part_facts_bridge import build_extracted_facts_from_part_facts
from .dfm_review_v2 import generate_dfm_review_v2
from .part_facts import PartFactsError, PartFactsService


class DfmBenchmarkError(ValueError):
    pass


@dataclass(frozen=True)
class BenchmarkCaseConfig:
    case_id: str
    label: str
    step_file: Path
    cadex_features_file: Path
    cadex_dfm_file: Path
    component_node_name: str | None
    component_profile: dict[str, str]
    context_overrides: dict[str, Any]


@dataclass(frozen=True)
class BenchmarkDefaults:
    selected_role: str
    selected_template: str
    selected_overlay: str | None
    run_both_if_mismatch: bool
    analysis_mode_for_logic_only: str
    analysis_mode_for_end_to_end: str


@dataclass(frozen=True)
class BenchmarkManifest:
    manifest_path: Path
    benchmark_name: str
    benchmark_version: str
    dataset_root: Path
    cases_root: Path
    output_root: Path
    defaults: BenchmarkDefaults
    modes: dict[str, bool]
    normalization: dict[str, Any]
    cases: list[BenchmarkCaseConfig]


@dataclass(frozen=True)
class SeverityNormalizer:
    alias_to_bucket: dict[str, str]

    @classmethod
    def from_manifest(cls, payload: dict[str, Any]) -> "SeverityNormalizer":
        alias_to_bucket: dict[str, str] = {}
        normalization = payload.get("normalization", {})
        if not isinstance(normalization, dict):
            normalization = {}
        severity_map = normalization.get("severity_map", {})
        if not isinstance(severity_map, dict):
            severity_map = {}
        for bucket, aliases in severity_map.items():
            if not isinstance(bucket, str) or not bucket.strip():
                continue
            normalized_bucket = bucket.strip().lower()
            alias_to_bucket[normalized_bucket] = normalized_bucket
            if not isinstance(aliases, list):
                continue
            for alias in aliases:
                if not isinstance(alias, str) or not alias.strip():
                    continue
                alias_to_bucket[alias.strip().lower()] = normalized_bucket
        return cls(alias_to_bucket=alias_to_bucket)

    def normalize(self, severity: Any) -> str | None:
        if not isinstance(severity, str):
            return None
        normalized = severity.strip().lower()
        if not normalized:
            return None
        return self.alias_to_bucket.get(normalized, normalized)


def load_benchmark_manifest(manifest_path: Path) -> BenchmarkManifest:
    manifest_path = manifest_path.resolve()
    if not manifest_path.exists():
        raise DfmBenchmarkError(f"Manifest not found: {manifest_path}")

    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise DfmBenchmarkError(f"Failed to read manifest: {exc}") from exc

    if not isinstance(payload, dict):
        raise DfmBenchmarkError("Benchmark manifest must be a JSON object.")

    repo_root = manifest_path.parent.parent
    defaults_payload = payload.get("defaults", {})
    if not isinstance(defaults_payload, dict):
        raise DfmBenchmarkError("Manifest.defaults must be an object.")

    defaults = BenchmarkDefaults(
        selected_role=_required_string(defaults_payload, "selected_role"),
        selected_template=_required_string(defaults_payload, "selected_template"),
        selected_overlay=_optional_string(defaults_payload.get("selected_overlay")),
        run_both_if_mismatch=bool(defaults_payload.get("run_both_if_mismatch", True)),
        analysis_mode_for_logic_only=_optional_string(
            defaults_payload.get("analysis_mode_for_logic_only")
        )
        or "full",
        analysis_mode_for_end_to_end=_optional_string(
            defaults_payload.get("analysis_mode_for_end_to_end")
        )
        or "full",
    )

    cases_payload = payload.get("cases", [])
    if not isinstance(cases_payload, list) or not cases_payload:
        raise DfmBenchmarkError("Manifest must contain at least one case.")

    cases: list[BenchmarkCaseConfig] = []
    for raw_case in cases_payload:
        if not isinstance(raw_case, dict):
            raise DfmBenchmarkError("Each case entry must be an object.")
        component_profile = raw_case.get("component_profile", {})
        if not isinstance(component_profile, dict):
            component_profile = {}
        context_overrides = raw_case.get("context_overrides", {})
        if not isinstance(context_overrides, dict):
            context_overrides = {}
        cases.append(
            BenchmarkCaseConfig(
                case_id=_required_string(raw_case, "case_id"),
                label=_required_string(raw_case, "label"),
                step_file=_resolve_repo_path(repo_root, _required_string(raw_case, "step_file")),
                cadex_features_file=_resolve_repo_path(
                    repo_root, _required_string(raw_case, "cadex_features_file")
                ),
                cadex_dfm_file=_resolve_repo_path(
                    repo_root, _required_string(raw_case, "cadex_dfm_file")
                ),
                component_node_name=_optional_string(raw_case.get("component_node_name")),
                component_profile={
                    "material": _optional_string(component_profile.get("material")) or "",
                    "manufacturingProcess": _optional_string(
                        component_profile.get("manufacturingProcess")
                    )
                    or "",
                    "industry": _optional_string(component_profile.get("industry")) or "",
                },
                context_overrides=context_overrides,
            )
        )

    modes = payload.get("modes", {})
    if not isinstance(modes, dict):
        modes = {}

    normalization = payload.get("normalization", {})
    if not isinstance(normalization, dict):
        normalization = {}

    return BenchmarkManifest(
        manifest_path=manifest_path,
        benchmark_name=_required_string(payload, "benchmark_name"),
        benchmark_version=_required_string(payload, "benchmark_version"),
        dataset_root=_resolve_repo_path(repo_root, _required_string(payload, "dataset_root")),
        cases_root=_resolve_repo_path(repo_root, _required_string(payload, "cases_root")),
        output_root=_resolve_repo_path(repo_root, _required_string(payload, "output_root")),
        defaults=defaults,
        modes={
            "run_logic_only": bool(modes.get("run_logic_only", True)),
            "run_end_to_end": bool(modes.get("run_end_to_end", True)),
        },
        normalization=normalization,
        cases=cases,
    )


def run_benchmark(
    manifest_path: Path,
    *,
    run_label: str | None = None,
) -> dict[str, Any]:
    manifest = load_benchmark_manifest(manifest_path)
    normalizer = SeverityNormalizer.from_manifest(
        {"normalization": manifest.normalization}
    )
    repo_root = manifest.manifest_path.parent.parent
    bundle = load_dfm_bundle(bundle_dir=repo_root / "server" / "dfm", repo_root=repo_root)

    timestamp = datetime.now(timezone.utc)
    run_id = (
        _slugify(run_label)
        if isinstance(run_label, str) and run_label.strip()
        else timestamp.strftime("%Y%m%dT%H%M%SZ")
    )
    run_root = manifest.output_root / run_id
    run_root.mkdir(parents=True, exist_ok=True)
    runtime_root = run_root / "_runtime"
    runtime_root.mkdir(parents=True, exist_ok=True)

    part_facts_service = PartFactsService(root=runtime_root / "models", bundle=bundle)

    validation_cases = [validate_case_contract(case) for case in manifest.cases]
    results = [
        _run_case(
            manifest=manifest,
            case=case,
            bundle=bundle,
            normalizer=normalizer,
            part_facts_service=part_facts_service,
        )
        for case in manifest.cases
    ]

    summary = {
        "generated_at": timestamp.isoformat(),
        "benchmark_name": manifest.benchmark_name,
        "benchmark_version": manifest.benchmark_version,
        "manifest_path": _relative_to_repo(manifest.manifest_path, repo_root),
        "dataset_root": _relative_to_repo(manifest.dataset_root, repo_root),
        "output_root": _relative_to_repo(run_root, repo_root),
        "modes": manifest.modes,
        "dataset_validation": {
            "all_cases_valid": all(item.get("is_valid") for item in validation_cases),
            "cases": validation_cases,
        },
        "cases": results,
        "summary": _summarize_run(results),
    }

    (run_root / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (run_root / "summary.md").write_text(
        render_benchmark_markdown(summary),
        encoding="utf-8",
    )
    return summary


def validate_case_contract(case: BenchmarkCaseConfig) -> dict[str, Any]:
    case_dir = case.step_file.parent
    files = list(case_dir.iterdir()) if case_dir.exists() else []
    step_files = [
        path.name
        for path in files
        if path.is_file() and path.suffix.lower() in {".stp", ".step"}
    ]
    json_files = [
        path.name for path in files if path.is_file() and path.suffix.lower() == ".json"
    ]
    issues: list[str] = []
    for expected_path in (case.step_file, case.cadex_features_file, case.cadex_dfm_file):
        if not expected_path.exists():
            issues.append(f"Missing file: {expected_path}")
    if len(step_files) != 1:
        issues.append(
            f"Expected exactly one STEP file in case folder, found {len(step_files)}."
        )
    if len(json_files) < 2:
        issues.append(
            f"Expected at least two JSON files in case folder, found {len(json_files)}."
        )
    return {
        "case_id": case.case_id,
        "label": case.label,
        "case_directory": str(case_dir),
        "step_files_present": step_files,
        "json_files_present": json_files,
        "is_valid": not issues,
        "issues": issues,
    }


def adapt_cadex_features_to_facts(
    cadex_features_payload: dict[str, Any],
    *,
    component_profile: dict[str, str] | None = None,
) -> dict[str, Any]:
    component_profile = component_profile or {}
    part = _first_part(cadex_features_payload)
    feature_groups = _feature_groups(part.get("featureRecognition"))
    categories = sorted(
        {
            category
            for group in feature_groups
            for category in _cadex_feature_categories(group.get("name"))
        }
    )
    unmapped_groups = [
        group.get("name")
        for group in feature_groups
        if _cadex_feature_categories(group.get("name")) == []
    ]

    extracted_facts: dict[str, Any] = {}
    open_pocket_count = 0
    closed_pocket_count = 0
    through_hole_count = 0
    partial_hole_count = 0
    stepped_hole_count = 0
    bore_count = 0
    turned_diameter_faces_count = 0
    turned_end_faces_count = 0
    turned_profile_faces_count = 0
    boss_count = 0
    flat_milled_face_count = 0
    flat_side_milled_face_count = 0
    curved_milled_face_count = 0
    convex_profile_edge_milled_face_count = 0
    concave_fillet_edge_milled_face_count = 0
    for group in feature_groups:
        group_name = _optional_string(group.get("name")) or ""
        feature_count = _group_feature_count(group) or 0
        normalized_name = group_name.lower()
        if "open pocket" in normalized_name:
            open_pocket_count += feature_count
        elif "closed pocket" in normalized_name:
            closed_pocket_count += feature_count
        elif "through hole" in normalized_name:
            through_hole_count += feature_count
        elif "partial hole" in normalized_name:
            partial_hole_count += feature_count
        elif "stepped hole" in normalized_name:
            stepped_hole_count += feature_count
        elif "bore" in normalized_name:
            bore_count += feature_count
        elif "flat side milled" in normalized_name:
            flat_side_milled_face_count += feature_count
        elif "convex profile edge" in normalized_name:
            convex_profile_edge_milled_face_count += feature_count
        elif "concave fillet edge" in normalized_name:
            concave_fillet_edge_milled_face_count += feature_count
        elif "curved milled" in normalized_name:
            curved_milled_face_count += feature_count
        elif "milled" in normalized_name and "flat" in normalized_name:
            flat_milled_face_count += feature_count
        elif "turn diameter" in normalized_name:
            turned_diameter_faces_count += feature_count
        elif "turn face" in normalized_name:
            turned_end_faces_count += feature_count
        elif "turn form" in normalized_name:
            turned_profile_faces_count += feature_count
        elif "boss" in normalized_name:
            boss_count += feature_count

    if "hole_features" in categories:
        extracted_facts["hole_features"] = True
    pocket_count = open_pocket_count + closed_pocket_count
    if "pockets_present" in categories:
        extracted_facts["pockets_present"] = True
    if open_pocket_count > 0 or "open_pocket_features" in categories:
        extracted_facts["open_pocket_count"] = open_pocket_count or 1
        extracted_facts["open_pocket_features"] = True
    if closed_pocket_count > 0 or "closed_pocket_features" in categories:
        extracted_facts["closed_pocket_count"] = closed_pocket_count or 1
        extracted_facts["closed_pocket_features"] = True
    if pocket_count > 0:
        extracted_facts["pocket_count"] = pocket_count
    if through_hole_count > 0 or "through_hole_features" in categories:
        extracted_facts["through_hole_count"] = through_hole_count or 1
        extracted_facts["through_hole_features"] = True
    if partial_hole_count > 0 or "partial_hole_features" in categories:
        extracted_facts["partial_hole_count"] = partial_hole_count or 1
        extracted_facts["partial_hole_features"] = True
    if stepped_hole_count > 0 or "stepped_hole_features" in categories:
        extracted_facts["stepped_hole_count"] = stepped_hole_count or 1
        extracted_facts["stepped_hole_features"] = True
    if bore_count > 0 or "bore_features" in categories:
        extracted_facts["bore_count"] = bore_count or 1
        extracted_facts["bore_features"] = True
    subtype_hole_count = through_hole_count + partial_hole_count + stepped_hole_count + bore_count
    if subtype_hole_count > 0:
        extracted_facts["hole_count"] = subtype_hole_count
    if "turned_faces_present" in categories:
        extracted_facts["turned_faces_present"] = True
    if "rotational_symmetry" in categories:
        extracted_facts["rotational_symmetry"] = True
    milled_face_count = (
        flat_milled_face_count
        + flat_side_milled_face_count
        + curved_milled_face_count
    )
    if "milled_faces_present" in categories or milled_face_count > 0:
        extracted_facts["milled_faces_present"] = True
    if flat_milled_face_count > 0 or "flat_milled_faces_present" in categories:
        extracted_facts["flat_milled_face_count"] = flat_milled_face_count or 1
        extracted_facts["flat_milled_faces_present"] = True
    if flat_side_milled_face_count > 0 or "flat_side_milled_faces_present" in categories:
        extracted_facts["flat_side_milled_face_count"] = flat_side_milled_face_count or 1
        extracted_facts["flat_side_milled_faces_present"] = True
    if curved_milled_face_count > 0 or "curved_milled_faces_present" in categories:
        extracted_facts["curved_milled_face_count"] = curved_milled_face_count or 1
        extracted_facts["curved_milled_faces_present"] = True
    if (
        convex_profile_edge_milled_face_count > 0
        or "convex_profile_edge_milled_faces_present" in categories
    ):
        extracted_facts["convex_profile_edge_milled_face_count"] = (
            convex_profile_edge_milled_face_count or 1
        )
        extracted_facts["convex_profile_edge_milled_faces_present"] = True
    if (
        concave_fillet_edge_milled_face_count > 0
        or "concave_fillet_edge_milled_faces_present" in categories
    ):
        extracted_facts["concave_fillet_edge_milled_face_count"] = (
            concave_fillet_edge_milled_face_count or 1
        )
        extracted_facts["concave_fillet_edge_milled_faces_present"] = True
    if milled_face_count > 0:
        extracted_facts["milled_face_count"] = milled_face_count
    if boss_count > 0 or "boss_features" in categories:
        extracted_facts["boss_count"] = boss_count or 1
        extracted_facts["boss_features"] = True
    turned_face_count = (
        turned_diameter_faces_count
        + turned_end_faces_count
        + turned_profile_faces_count
    )
    if turned_face_count > 0:
        extracted_facts["turned_face_count"] = turned_face_count
        extracted_facts["turned_diameter_faces_count"] = turned_diameter_faces_count
        extracted_facts["turned_end_faces_count"] = turned_end_faces_count
        extracted_facts["turned_profile_faces_count"] = turned_profile_faces_count

    total_feature_count = _safe_int(
        part.get("featureRecognition", {}).get("totalFeatureCount")
        if isinstance(part.get("featureRecognition"), dict)
        else None
    )
    if total_feature_count is not None and total_feature_count > 0:
        extracted_facts["feature_complexity_score"] = min(total_feature_count, 100)

    bbox = _bbox_dimensions(part)
    if bbox:
        extracted_facts["part_bounding_box"] = True
        extracted_facts["bbox_x_mm"] = bbox["bbox_x_mm"]
        extracted_facts["bbox_y_mm"] = bbox["bbox_y_mm"]
        extracted_facts["bbox_z_mm"] = bbox["bbox_z_mm"]
        extracted_facts["bbox_dimensions"] = True

    material = _optional_string(component_profile.get("material"))
    if material:
        extracted_facts["material_spec"] = material

    return {
        "extracted_part_facts": extracted_facts,
        "cadex_part_name": _optional_string(part.get("partName")),
        "cadex_process_label": _optional_string(part.get("process")),
        "cadex_feature_categories": categories,
        "adapted_feature_categories": extract_feature_categories_from_facts(extracted_facts),
        "unmapped_feature_groups": [name for name in unmapped_groups if isinstance(name, str)],
        "total_feature_count": total_feature_count,
    }


def extract_cadex_feature_reference(cadex_features_payload: dict[str, Any]) -> dict[str, Any]:
    part = _first_part(cadex_features_payload)
    feature_groups = _feature_groups(part.get("featureRecognition"))
    groups = []
    for group in feature_groups:
        group_name = _optional_string(group.get("name")) or "unnamed_group"
        groups.append(
            {
                "name": group_name,
                "feature_count": _group_feature_count(group),
                "categories": _cadex_feature_categories(group_name),
            }
        )
    return {
        "part_name": _optional_string(part.get("partName")),
        "process_label": _optional_string(part.get("process")),
        "feature_categories": sorted(
            {
                category
                for item in groups
                for category in item.get("categories", [])
            }
        ),
        "feature_groups": groups,
    }


def extract_cadex_dfm_reference(
    cadex_dfm_payload: dict[str, Any],
    *,
    normalizer: SeverityNormalizer | None = None,
) -> dict[str, Any]:
    del normalizer
    part = _first_part(cadex_dfm_payload)
    issue_groups = _feature_groups(part.get("dfm"))
    issues = []
    for group in issue_groups:
        group_name = _optional_string(group.get("name")) or "unnamed_issue_group"
        issues.append(
            {
                "name": group_name,
                "category": _cadex_dfm_category(group_name),
                "feature_count": _group_feature_count(group),
                "parameters": _group_parameters(group),
            }
        )
    return {
        "part_name": _optional_string(part.get("partName")),
        "process_label": _optional_string(part.get("process")),
        "issues": issues,
        "issue_categories": sorted(
            {issue["category"] for issue in issues if issue.get("category")}
        ),
        "severity_available": False,
        "severity_note": "Cadex DFM reference JSON does not expose severity labels in the sampled files.",
    }


def extract_rapiddraft_review_reference(
    review_payload: dict[str, Any],
    *,
    normalizer: SeverityNormalizer,
) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    for route in review_payload.get("routes", []):
        if not isinstance(route, dict):
            continue
        route_source = _optional_string(route.get("route_source")) or "selected"
        process_id = _optional_string(route.get("process_id"))
        for finding in route.get("findings", []):
            if not isinstance(finding, dict):
                continue
            findings.append(
                {
                    "route_source": route_source,
                    "process_id": process_id,
                    "finding_type": _optional_string(finding.get("finding_type")) or "unknown",
                    "rule_id": _optional_string(finding.get("rule_id")),
                    "title": _optional_string(finding.get("title")),
                    "severity_raw": _optional_string(finding.get("severity")),
                    "severity_normalized": normalizer.normalize(finding.get("severity")),
                    "category": _rapiddraft_finding_category(finding),
                }
            )

    any_categories = sorted({item["category"] for item in findings if item.get("category")})
    violation_categories = sorted(
        {
            item["category"]
            for item in findings
            if item.get("category") and item.get("finding_type") == "rule_violation"
        }
    )
    evidence_gap_categories = sorted(
        {
            item["category"]
            for item in findings
            if item.get("category") and item.get("finding_type") == "evidence_gap"
        }
    )
    return {
        "finding_count_total": len(findings),
        "findings": findings,
        "categories_any": any_categories,
        "categories_rule_violations": violation_categories,
        "categories_evidence_gaps": evidence_gap_categories,
    }


def extract_feature_categories_from_facts(extracted_facts: dict[str, Any]) -> list[str]:
    categories: set[str] = set()
    if any(
        _truthy(extracted_facts.get(key))
        for key in (
            "hole_features",
            "hole_count",
            "through_hole_count",
            "partial_hole_count",
            "stepped_hole_count",
            "bore_count",
        )
    ):
        categories.add("hole_features")
    if any(
        _truthy(extracted_facts.get(key))
        for key in ("through_hole_features", "through_hole_count")
    ):
        categories.add("through_hole_features")
    if any(
        _truthy(extracted_facts.get(key))
        for key in ("partial_hole_features", "partial_hole_count")
    ):
        categories.add("partial_hole_features")
    if any(
        _truthy(extracted_facts.get(key))
        for key in ("stepped_hole_features", "stepped_hole_count")
    ):
        categories.add("stepped_hole_features")
    if any(
        _truthy(extracted_facts.get(key))
        for key in ("bore_features", "bore_count")
    ):
        categories.add("bore_features")
    if _truthy(extracted_facts.get("pockets_present")):
        categories.add("pockets_present")
    if any(
        _truthy(extracted_facts.get(key))
        for key in ("open_pocket_features", "open_pocket_count")
    ):
        categories.add("open_pocket_features")
    if any(
        _truthy(extracted_facts.get(key))
        for key in ("closed_pocket_features", "closed_pocket_count")
    ):
        categories.add("closed_pocket_features")
    if any(
        _truthy(extracted_facts.get(key))
        for key in (
            "milled_faces_present",
            "milled_face_count",
            "flat_milled_face_count",
            "flat_side_milled_face_count",
            "curved_milled_face_count",
            "convex_profile_edge_milled_face_count",
            "concave_fillet_edge_milled_face_count",
        )
    ):
        categories.add("milled_faces_present")
    if any(
        _truthy(extracted_facts.get(key))
        for key in ("flat_milled_faces_present", "flat_milled_face_count")
    ):
        categories.add("flat_milled_faces_present")
    if any(
        _truthy(extracted_facts.get(key))
        for key in ("flat_side_milled_faces_present", "flat_side_milled_face_count")
    ):
        categories.add("flat_side_milled_faces_present")
    if any(
        _truthy(extracted_facts.get(key))
        for key in ("curved_milled_faces_present", "curved_milled_face_count")
    ):
        categories.add("curved_milled_faces_present")
    if any(
        _truthy(extracted_facts.get(key))
        for key in (
            "convex_profile_edge_milled_faces_present",
            "convex_profile_edge_milled_face_count",
        )
    ):
        categories.add("convex_profile_edge_milled_faces_present")
    if any(
        _truthy(extracted_facts.get(key))
        for key in (
            "concave_fillet_edge_milled_faces_present",
            "concave_fillet_edge_milled_face_count",
        )
    ):
        categories.add("concave_fillet_edge_milled_faces_present")
    if any(
        _truthy(extracted_facts.get(key))
        for key in ("boss_features", "boss_count")
    ):
        categories.add("boss_features")
    if any(
        _truthy(extracted_facts.get(key))
        for key in (
            "turned_faces_present",
            "turned_face_count",
            "turned_diameter_faces_count",
            "turned_end_faces_count",
            "turned_profile_faces_count",
        )
    ):
        categories.add("turned_faces_present")
    if any(
        _truthy(extracted_facts.get(key))
        for key in (
            "rotational_symmetry",
            "turned_face_count",
            "turned_diameter_faces_count",
            "turned_end_faces_count",
            "turned_profile_faces_count",
        )
    ):
        categories.add("rotational_symmetry")
    return sorted(categories)


def compare_feature_signals(
    cadex_categories: list[str],
    rapiddraft_categories: list[str],
) -> dict[str, Any]:
    cadex_set = set(cadex_categories)
    rapiddraft_set = set(rapiddraft_categories)
    matched = sorted(cadex_set & rapiddraft_set)
    return {
        "cadex_categories": sorted(cadex_set),
        "rapiddraft_categories": sorted(rapiddraft_set),
        "matched_categories": matched,
        "cadex_only_categories": sorted(cadex_set - rapiddraft_set),
        "rapiddraft_only_categories": sorted(rapiddraft_set - cadex_set),
        "matched_count": len(matched),
        "cadex_category_count": len(cadex_set),
        "rapiddraft_category_count": len(rapiddraft_set),
        "recall_against_cadex": _ratio(len(matched), len(cadex_set)),
    }


def compare_reasoning_reference(
    cadex_reference: dict[str, Any],
    rapiddraft_reference: dict[str, Any],
) -> dict[str, Any]:
    cadex_categories = set(cadex_reference.get("issue_categories", []))
    any_categories = set(rapiddraft_reference.get("categories_any", []))
    violation_categories = set(rapiddraft_reference.get("categories_rule_violations", []))
    matched_any = sorted(cadex_categories & any_categories)
    matched_violations = sorted(cadex_categories & violation_categories)
    return {
        "cadex_issue_categories": sorted(cadex_categories),
        "rapiddraft_any_finding_categories": sorted(any_categories),
        "rapiddraft_rule_violation_categories": sorted(violation_categories),
        "matched_any_categories": matched_any,
        "matched_rule_violation_categories": matched_violations,
        "cadex_only_categories": sorted(cadex_categories - any_categories),
        "rapiddraft_only_categories": sorted(any_categories - cadex_categories),
        "any_category_recall_against_cadex": _ratio(len(matched_any), len(cadex_categories)),
        "rule_violation_category_recall_against_cadex": _ratio(
            len(matched_violations), len(cadex_categories)
        ),
        "severity_note": cadex_reference.get("severity_note"),
    }


def render_benchmark_markdown(summary: dict[str, Any]) -> str:
    lines = [
        f"# {summary.get('benchmark_name', 'DFM Benchmark')}",
        "",
        f"Generated at: {summary.get('generated_at', '')}",
        f"Manifest: `{summary.get('manifest_path', '')}`",
        f"Output: `{summary.get('output_root', '')}`",
        "",
        "## Run Summary",
        "",
        f"- Cases: {summary.get('summary', {}).get('case_count', 0)}",
        f"- Logic-only succeeded: {summary.get('summary', {}).get('logic_only_completed', 0)}",
        f"- Logic-only with warnings: {summary.get('summary', {}).get('logic_only_with_warnings', 0)}",
        f"- End-to-end succeeded: {summary.get('summary', {}).get('end_to_end_completed', 0)}",
        f"- End-to-end with warnings: {summary.get('summary', {}).get('end_to_end_with_warnings', 0)}",
        "",
    ]
    for case in summary.get("cases", []):
        if not isinstance(case, dict):
            continue
        case_id = case.get("case_id", "")
        label = case.get("label", "")
        lines.extend([f"## {case_id} - {label}", ""])
        dataset_contract = case.get("dataset_contract", {})
        if isinstance(dataset_contract, dict) and dataset_contract.get("issues"):
            lines.append("Dataset issues:")
            for issue in dataset_contract.get("issues", []):
                lines.append(f"- {issue}")
            lines.append("")
        for mode_key in ("logic_only", "end_to_end"):
            mode_payload = case.get(mode_key, {})
            if not isinstance(mode_payload, dict):
                continue
            lines.append(f"### {mode_key.replace('_', ' ').title()}")
            lines.append("")
            lines.append(f"- Status: {mode_payload.get('status', 'unknown')}")
            if mode_payload.get("error"):
                lines.append(f"- Error: {mode_payload.get('error')}")
            for warning in mode_payload.get("warnings", []):
                lines.append(f"- Warning: {warning}")
            feature_comparison = mode_payload.get("feature_signal_comparison", {})
            if isinstance(feature_comparison, dict):
                lines.append(
                    f"- Feature signal recall vs Cadex: {feature_comparison.get('recall_against_cadex', 0.0):.2f}"
                )
            reasoning = mode_payload.get("reasoning_comparison", {})
            if isinstance(reasoning, dict):
                lines.append(
                    f"- Reasoning category recall (any finding): {reasoning.get('any_category_recall_against_cadex', 0.0):.2f}"
                )
                lines.append(
                    f"- Reasoning category recall (rule violation): {reasoning.get('rule_violation_category_recall_against_cadex', 0.0):.2f}"
                )
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _run_case(
    *,
    manifest: BenchmarkManifest,
    case: BenchmarkCaseConfig,
    bundle: Any,
    normalizer: SeverityNormalizer,
    part_facts_service: PartFactsService,
) -> dict[str, Any]:
    cadex_features_payload = _read_json(case.cadex_features_file)
    cadex_dfm_payload = _read_json(case.cadex_dfm_file)
    cadex_feature_reference = extract_cadex_feature_reference(cadex_features_payload)
    cadex_dfm_reference = extract_cadex_dfm_reference(
        cadex_dfm_payload,
        normalizer=normalizer,
    )
    adapter = adapt_cadex_features_to_facts(
        cadex_features_payload,
        component_profile=case.component_profile,
    )

    return {
        "case_id": case.case_id,
        "label": case.label,
        "dataset_contract": validate_case_contract(case),
        "cadex_reference": {
            "feature_reference": cadex_feature_reference,
            "dfm_reference": cadex_dfm_reference,
        },
        "logic_only": _run_logic_only_case(
            manifest=manifest,
            case=case,
            bundle=bundle,
            normalizer=normalizer,
            cadex_dfm_reference=cadex_dfm_reference,
            cadex_feature_reference=cadex_feature_reference,
            adapter=adapter,
        )
        if manifest.modes.get("run_logic_only")
        else {"status": "skipped"},
        "end_to_end": _run_end_to_end_case(
            manifest=manifest,
            case=case,
            bundle=bundle,
            normalizer=normalizer,
            cadex_dfm_reference=cadex_dfm_reference,
            cadex_feature_reference=cadex_feature_reference,
            part_facts_service=part_facts_service,
        )
        if manifest.modes.get("run_end_to_end")
        else {"status": "skipped"},
    }


def _run_logic_only_case(
    *,
    manifest: BenchmarkManifest,
    case: BenchmarkCaseConfig,
    bundle: Any,
    normalizer: SeverityNormalizer,
    cadex_dfm_reference: dict[str, Any],
    cadex_feature_reference: dict[str, Any],
    adapter: dict[str, Any],
) -> dict[str, Any]:
    extracted_facts = dict(adapter.get("extracted_part_facts", {}))
    try:
        planning_inputs, review_payload = _generate_review_from_facts(
            manifest=manifest,
            case=case,
            bundle=bundle,
            extracted_facts=extracted_facts,
            analysis_mode=manifest.defaults.analysis_mode_for_logic_only,
            component_display_name=adapter.get("cadex_part_name") or case.label,
        )
    except Exception as exc:
        return {
            "status": "error",
            "error": f"{exc.__class__.__name__}: {exc}",
            "adapter": adapter,
        }

    rapiddraft_reference = extract_rapiddraft_review_reference(
        review_payload,
        normalizer=normalizer,
    )
    return {
        "status": "completed",
        "adapter": adapter,
        "planning_inputs": planning_inputs,
        "feature_signal_comparison": compare_feature_signals(
            cadex_feature_reference.get("feature_categories", []),
            adapter.get("adapted_feature_categories", []),
        ),
        "review": review_payload,
        "rapiddraft_reference": rapiddraft_reference,
        "reasoning_comparison": compare_reasoning_reference(
            cadex_dfm_reference,
            rapiddraft_reference,
        ),
    }


def _run_end_to_end_case(
    *,
    manifest: BenchmarkManifest,
    case: BenchmarkCaseConfig,
    bundle: Any,
    normalizer: SeverityNormalizer,
    cadex_dfm_reference: dict[str, Any],
    cadex_feature_reference: dict[str, Any],
    part_facts_service: PartFactsService,
) -> dict[str, Any]:
    component_node_name = case.component_node_name or "benchmark_root"
    assembly_component_count = 2 if case.component_node_name else 1
    try:
        part_facts_payload = part_facts_service.get_or_create(
            model_id=f"benchmark_{case.case_id}",
            step_path=case.step_file,
            component_node_name=component_node_name,
            component_display_name=case.label,
            component_profile=case.component_profile,
            triangle_count=None,
            assembly_component_count=assembly_component_count,
            force_refresh=True,
        )
        extracted_facts = build_extracted_facts_from_part_facts(
            part_facts_payload=part_facts_payload,
            component_profile=case.component_profile,
            context_payload=_context_payload(case.context_overrides),
        )
        planning_inputs, review_payload = _generate_review_from_facts(
            manifest=manifest,
            case=case,
            bundle=bundle,
            extracted_facts=extracted_facts,
            analysis_mode=manifest.defaults.analysis_mode_for_end_to_end,
            component_display_name=case.label,
        )
    except (PartFactsError, FileNotFoundError) as exc:
        return {"status": "error", "error": f"{exc.__class__.__name__}: {exc}"}
    except Exception as exc:
        return {"status": "error", "error": f"{exc.__class__.__name__}: {exc}"}

    rapiddraft_reference = extract_rapiddraft_review_reference(
        review_payload,
        normalizer=normalizer,
    )
    warnings = _part_facts_warnings(part_facts_payload)
    return {
        "status": "completed_with_warnings" if warnings else "completed",
        "warnings": warnings,
        "part_facts": part_facts_payload,
        "extracted_part_facts": extracted_facts,
        "planning_inputs": planning_inputs,
        "feature_signal_comparison": compare_feature_signals(
            cadex_feature_reference.get("feature_categories", []),
            extract_feature_categories_from_facts(extracted_facts),
        ),
        "review": review_payload,
        "rapiddraft_reference": rapiddraft_reference,
        "reasoning_comparison": compare_reasoning_reference(
            cadex_dfm_reference,
            rapiddraft_reference,
        ),
    }


def _generate_review_from_facts(
    *,
    manifest: BenchmarkManifest,
    case: BenchmarkCaseConfig,
    bundle: Any,
    extracted_facts: dict[str, Any],
    analysis_mode: str,
    component_display_name: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    planning_inputs = {
        "extracted_part_facts": extracted_facts,
        "analysis_mode": analysis_mode,
        "selected_process_override": _optional_string(
            case.context_overrides.get("selected_process_override")
        ),
        "selected_overlay": _optional_string(case.context_overrides.get("selected_overlay"))
        or manifest.defaults.selected_overlay,
        "selected_role": _optional_string(case.context_overrides.get("selected_role"))
        or manifest.defaults.selected_role,
        "selected_template": _optional_string(case.context_overrides.get("selected_template"))
        or manifest.defaults.selected_template,
        "run_both_if_mismatch": bool(
            case.context_overrides.get(
                "run_both_if_mismatch", manifest.defaults.run_both_if_mismatch
            )
        ),
    }
    planning_inputs, effective_context = resolve_effective_planning_inputs(
        bundle,
        planning_inputs=planning_inputs,
        component_profile=case.component_profile,
    )
    review_payload = generate_dfm_review_v2(
        bundle,
        model_id=f"benchmark_{case.case_id}",
        component_context={
            "component_node_name": case.component_node_name,
            "component_display_name": component_display_name,
            "profile": case.component_profile,
            "triangle_count": None,
        },
        planning_inputs=planning_inputs,
        context_payload=_context_payload(case.context_overrides),
        effective_context=effective_context,
    )
    return planning_inputs, review_payload


def _context_payload(context_overrides: dict[str, Any]) -> dict[str, Any]:
    payload = context_overrides.get("context_payload", {})
    if not isinstance(payload, dict):
        payload = {}
    return dict(payload)


def _summarize_run(results: list[dict[str, Any]]) -> dict[str, Any]:
    logic_only_completed = 0
    logic_only_with_warnings = 0
    end_to_end_completed = 0
    end_to_end_with_warnings = 0
    for case in results:
        if not isinstance(case, dict):
            continue
        logic_payload = case.get("logic_only", {})
        end_payload = case.get("end_to_end", {})
        if isinstance(logic_payload, dict):
            logic_status = logic_payload.get("status")
            if logic_status in {"completed", "completed_with_warnings"}:
                logic_only_completed += 1
            if logic_status == "completed_with_warnings":
                logic_only_with_warnings += 1
        if isinstance(end_payload, dict):
            end_status = end_payload.get("status")
            if end_status in {"completed", "completed_with_warnings"}:
                end_to_end_completed += 1
            if end_status == "completed_with_warnings":
                end_to_end_with_warnings += 1
    return {
        "case_count": len(results),
        "logic_only_completed": logic_only_completed,
        "logic_only_with_warnings": logic_only_with_warnings,
        "end_to_end_completed": end_to_end_completed,
        "end_to_end_with_warnings": end_to_end_with_warnings,
    }


def _part_facts_warnings(part_facts_payload: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    errors = part_facts_payload.get("errors", [])
    if isinstance(errors, list):
        for error in errors:
            if isinstance(error, str) and error:
                warnings.append(error)
    coverage = part_facts_payload.get("coverage", {})
    if isinstance(coverage, dict):
        core = coverage.get("core_extraction_coverage", {})
        if isinstance(core, dict):
            percent = core.get("percent")
            if isinstance(percent, (int, float)) and float(percent) == 0.0:
                warnings.append(
                    "No geometry-derived facts were extracted, so end-to-end comparisons are degraded."
                )
    overall_confidence = _optional_string(part_facts_payload.get("overall_confidence"))
    if overall_confidence == "low":
        warnings.append(
            "Part-facts overall confidence is low, so feature-recognition comparisons should be interpreted cautiously."
        )
    deduped: list[str] = []
    seen: set[str] = set()
    for warning in warnings:
        if warning in seen:
            continue
        seen.add(warning)
        deduped.append(warning)
    return deduped


def _cadex_feature_categories(group_name: Any) -> list[str]:
    normalized = _normalize_token(group_name)
    categories: list[str] = []
    if not normalized:
        return categories
    if "pocket" in normalized:
        categories.append("pockets_present")
    if "open pocket" in normalized:
        categories.append("open_pocket_features")
    if "closed pocket" in normalized:
        categories.append("closed_pocket_features")
    if any(token in normalized for token in ("hole", "bore")):
        categories.append("hole_features")
    if "through hole" in normalized:
        categories.append("through_hole_features")
    if "partial hole" in normalized:
        categories.append("partial_hole_features")
    if "stepped hole" in normalized:
        categories.append("stepped_hole_features")
    if "bore" in normalized:
        categories.append("bore_features")
    if "turn" in normalized or "lathe" in normalized:
        categories.append("turned_faces_present")
        categories.append("rotational_symmetry")
    if "boss" in normalized:
        categories.append("boss_features")
    if "milled" in normalized or "milling" in normalized:
        categories.append("milled_faces_present")
    if "convex profile edge" in normalized:
        categories.append("convex_profile_edge_milled_faces_present")
    if "concave fillet edge" in normalized:
        categories.append("concave_fillet_edge_milled_faces_present")
    if "curved milled" in normalized:
        categories.append("curved_milled_faces_present")
    if "flat side milled" in normalized:
        categories.append("flat_side_milled_faces_present")
    if "milled" in normalized and "flat" in normalized and "side" not in normalized:
        categories.append("flat_milled_faces_present")
    return sorted(set(categories))


def _cadex_dfm_category(group_name: Any) -> str | None:
    normalized = _normalize_token(group_name)
    if not normalized:
        return None
    if "non standard" in normalized and "hole" in normalized:
        return "non_standard_hole_diameter"
    if "partial hole" in normalized:
        return "partial_hole"
    if "non perpendicular hole" in normalized:
        return "non_perpendicular_hole"
    if "high boss" in normalized:
        return "high_boss"
    if "small radius" in normalized and "corner" in normalized:
        return "small_internal_radius"
    if "deep hole" in normalized:
        return "deep_hole"
    return _slugify(normalized)


def _rapiddraft_finding_category(finding: dict[str, Any]) -> str | None:
    rule_id = _optional_string(finding.get("rule_id"))
    if rule_id:
        rule_id = rule_id.upper()
    title = _normalize_token(finding.get("title"))
    rule_map = {
        "CNC-001": "thin_wall",
        "CNC-002": "deep_hole",
        "CNC-003": "non_standard_hole_diameter",
        "CNC-004": "blind_hole_bottom",
        "CNC-005": "small_internal_radius",
        "CNC-006": "small_internal_radius",
        "CNC-007": "high_boss",
        "CNC-008": "high_boss",
        "CNC-010": "small_internal_radius",
        "CNC-011": "small_internal_radius",
        "CNC-012": "high_boss",
        "CNC-013": "small_internal_radius",
        "CNC-020": "thin_wall",
        "CNC-024": "small_internal_radius",
        "CNC-025": "oversized_part",
        "TURN-001": "thin_wall",
        "TURN-002": "small_internal_radius",
        "TURN-004": "hole_diameter_limit",
        "FOOD-002": "small_internal_radius",
        "FOOD-004": "small_internal_radius",
        "PSTD-019": "small_internal_radius",
    }
    if rule_id and rule_id in rule_map:
        return rule_map[rule_id]
    if "boss" in title:
        return "high_boss"
    if "non standard" in title and "hole" in title:
        return "non_standard_hole_diameter"
    if "corner" in title or "radius" in title:
        return "small_internal_radius"
    if "thin wall" in title:
        return "thin_wall"
    if "hole" in title and "depth" in title:
        return "deep_hole"
    return None


def _feature_groups(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    groups = payload.get("featureGroups", [])
    if not isinstance(groups, list):
        return []
    return [item for item in groups if isinstance(item, dict)]


def _group_feature_count(group: dict[str, Any]) -> int | None:
    for key in ("featureCount", "totalGroupFeatureCount"):
        value = _safe_int(group.get(key))
        if value is not None:
            return value
    features = group.get("features")
    if isinstance(features, list):
        return len(features)
    subgroups = group.get("subGroups")
    if isinstance(subgroups, list):
        total = 0
        for item in subgroups:
            if not isinstance(item, dict):
                continue
            total += _safe_int(item.get("featureCount")) or len(item.get("features", []))
        return total
    return None


def _group_parameters(group: dict[str, Any]) -> list[dict[str, Any]]:
    parameter_groups: list[dict[str, Any]] = []
    for subgroup in group.get("subGroups", []):
        if not isinstance(subgroup, dict):
            continue
        parameters = subgroup.get("parameters", [])
        if not isinstance(parameters, list):
            continue
        cleaned = []
        for parameter in parameters:
            if not isinstance(parameter, dict):
                continue
            cleaned.append(
                {
                    "name": _optional_string(parameter.get("name")),
                    "units": _optional_string(parameter.get("units")),
                    "value": parameter.get("value"),
                }
            )
        if cleaned:
            parameter_groups.append(
                {
                    "parameters": cleaned,
                    "feature_count": _safe_int(subgroup.get("featureCount"))
                    or len(subgroup.get("features", [])),
                }
            )
    return parameter_groups


def _bbox_dimensions(part: dict[str, Any]) -> dict[str, float] | None:
    geometric = part.get("geometricProperties", {})
    if not isinstance(geometric, dict):
        return None
    aabb = geometric.get("AABB", {})
    if not isinstance(aabb, dict):
        return None
    dimensions = aabb.get("dimensions", {})
    if not isinstance(dimensions, dict):
        return None
    x = _safe_float(dimensions.get("x"))
    y = _safe_float(dimensions.get("y"))
    z = _safe_float(dimensions.get("z"))
    if x is None or y is None or z is None:
        return None
    return {
        "bbox_x_mm": x,
        "bbox_y_mm": y,
        "bbox_z_mm": z,
    }


def _first_part(payload: dict[str, Any]) -> dict[str, Any]:
    parts = payload.get("parts", [])
    if not isinstance(parts, list) or not parts:
        raise DfmBenchmarkError("Cadex payload must contain a non-empty 'parts' list.")
    part = parts[0]
    if not isinstance(part, dict):
        raise DfmBenchmarkError("Cadex payload parts[0] must be an object.")
    return part


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise DfmBenchmarkError(f"Failed to read JSON file {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise DfmBenchmarkError(f"Expected JSON object in {path}")
    return payload


def _required_string(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise DfmBenchmarkError(f"Missing required string field '{key}'.")
    return value.strip()


def _optional_string(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned or None


def _resolve_repo_path(repo_root: Path, raw_path: str) -> Path:
    path = Path(raw_path)
    if path.is_absolute():
        return path
    return (repo_root / path).resolve()


def _safe_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and float(value).is_integer():
        return int(value)
    if isinstance(value, str):
        try:
            return int(float(value.strip()))
        except Exception:
            return None
    return None


def _safe_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except Exception:
            return None
    return None


def _ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round(numerator / denominator, 4)


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, (int, float)):
        return value > 0
    if isinstance(value, str):
        normalized = value.strip().lower()
        return bool(normalized and normalized not in {"0", "false", "none", "null", "no"})
    if isinstance(value, (list, tuple, set, dict)):
        return len(value) > 0
    return bool(value)


def _normalize_token(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return re.sub(r"\s+", " ", value.strip().lower())


def _slugify(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip().lower())
    normalized = normalized.strip("_")
    return normalized or "run"


def _relative_to_repo(path: Path, repo_root: Path) -> str:
    try:
        return str(path.resolve().relative_to(repo_root.resolve()))
    except Exception:
        return str(path)
