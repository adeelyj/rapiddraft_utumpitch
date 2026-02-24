from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
DFM_DIR = REPO_ROOT / "server" / "dfm"
RULE_SCHEMA_PATH = DFM_DIR / "schemas" / "rule_library.schema.json"

SOURCE_RULE_ID_PATTERN = re.compile(r"^PILOTSTD-(\d+)$")
RUNTIME_RULE_ID_PATTERN = re.compile(r"^[A-Z]{2,6}-[0-9]{3}$")
CITE_TOKEN_PATTERN = re.compile(r"\ue200?cite.*?\ue201?")

# Removes the chat-style citation block seen in DeepResearch exports.
SPECIAL_CITE_PATTERN = re.compile(r"cite.*?")


@dataclass(frozen=True)
class CompileResult:
    sanitized_payload: dict[str, Any]
    compiled_rules_executable: list[dict[str, Any]]
    compiled_rules_deferred: list[dict[str, Any]]
    references_patch: list[dict[str, Any]]
    overlay_patch: dict[str, Any]
    mapping_contract: dict[str, Any]


INPUT_ALIAS_MAP = {
    "drawing.text_all": "drawing_notes",
    "drawing.title_block.general_tolerance_note": "drawing_title_block",
    "drawing.features_of_size.mating_without_fit_callout_count": "drawing_notes",
    "drawing.gdt.invalid_frame_count": "datum_scheme",
    "drawing.gdt.undefined_datum_reference_count": "datum_scheme",
    "drawing.hygiene.cleaning_instructions_present": "drawing_notes",
    "drawing.hygiene.zone_tagging_present": "drawing_notes",
    "drawing.manufacturing.notes": "drawing_notes",
    "drawing.surface_texture.missing_value_count": "surface_finish_spec",
    "drawing.surface_treatments.anodizing.present": "coating_spec",
    "drawing.surface_treatments.anodizing.references": "coating_spec",
    "drawing.thread_callouts.metric_without_tolerance_class_count": "thread_callouts",
    "drawing.thread_callouts.pipe_threads_text": "thread_callouts",
    "docs.ce.ec_declaration_present": "manual_context",
    "docs.ce.instructions_present": "manual_context",
    "docs.ce.technical_file_present": "manual_context",
    "docs.fcm.eu10_2011.declaration_present": "manual_context",
    "docs.fcm.eu10_2011.supporting_docs_present": "manual_context",
    "docs.fcm.framework_1935_2004.compliance_statement_present": "manual_context",
    "docs.fcm.traceability_system_present": "manual_context",
    "project.manufacturing.process": "manual_context",
    "project.product_category": "manual_context",
    "bom.materials.stainless_spec_text": "material_spec",
    "cad.robot_interface.standard": "geometry_features",
    "cad.robot_interface.variant": "geometry_features",
    "cad.robot_interface.conformance_flag": "geometry_features",
    "cad.fits.all_pairs_intended_fit_type_met": "hole_features",
    "cad.threads.iso228_all_conformant": "hole_features",
    "cad.hygienic_design.crevice_count": "geometry_features",
    "cad.hygienic_design.enclosed_voids_in_product_zone_count": "geometry_features",
    "cad.hygienic_design.trapped_volume_count": "geometry_features",
}


def load_deep_research_payload(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("DeepResearch payload must be a JSON object.")
    return payload


def compile_deep_research_payload(payload: dict[str, Any]) -> CompileResult:
    sanitized_payload = _sanitize_value(payload)
    allowed_inputs = _allowed_runtime_inputs()

    references_patch = _compile_references_patch(sanitized_payload.get("references_patch"))
    overlay_patch = _compile_overlay_patch(sanitized_payload.get("overlay_patch"))

    runtime_rules: list[dict[str, Any]] = []
    deferred_rules: list[dict[str, Any]] = []
    mapping_rows: list[dict[str, Any]] = []

    for candidate in _as_list(sanitized_payload.get("rule_candidates")):
        if not isinstance(candidate, dict):
            continue
        compiled = _compile_rule_candidate(candidate, allowed_inputs=allowed_inputs)
        mapping_rows.append(compiled["mapping"])
        if compiled["status"] == "executable_now":
            runtime_rules.append(compiled["rule"])
        else:
            deferred_rules.append(compiled["rule"])

    mapping_contract = {
        "version": "1.0.0",
        "generated_at": _now_iso(),
        "source": "pilot_deep_research",
        "summary": {
            "rules_total": len(runtime_rules) + len(deferred_rules),
            "rules_executable_now": len(runtime_rules),
            "rules_deferred": len(deferred_rules),
            "references_patch_count": len(references_patch),
        },
        "rule_mappings": mapping_rows,
        "input_alias_map": INPUT_ALIAS_MAP,
        "deferred_rule_ids": [rule["rule_id"] for rule in deferred_rules],
    }

    return CompileResult(
        sanitized_payload=sanitized_payload,
        compiled_rules_executable=runtime_rules,
        compiled_rules_deferred=deferred_rules,
        references_patch=references_patch,
        overlay_patch=overlay_patch,
        mapping_contract=mapping_contract,
    )


def apply_compile_result_to_bundle(result: CompileResult, *, dfm_dir: Path = DFM_DIR) -> dict[str, Any]:
    references_path = dfm_dir / "references.json"
    overlays_path = dfm_dir / "overlays.json"
    rule_library_path = dfm_dir / "rule_library.json"
    manifest_path = dfm_dir / "manifest.json"

    references = json.loads(references_path.read_text(encoding="utf-8"))
    for entry in result.references_patch:
        ref_id = entry.get("ref_id")
        if isinstance(ref_id, str) and ref_id:
            references[ref_id] = {
                "title": entry.get("title", ref_id),
                "url": entry.get("url", ""),
                "type": entry.get("type", "standard"),
                "notes": entry.get("notes", ""),
            }
    references_path.write_text(json.dumps(references, indent=2), encoding="utf-8")

    overlays_payload = json.loads(overlays_path.read_text(encoding="utf-8"))
    overlays = overlays_payload.get("overlays", [])
    if isinstance(overlays, list):
        for overlay in overlays:
            if not isinstance(overlay, dict):
                continue
            if overlay.get("overlay_id") != result.overlay_patch.get("overlay_id"):
                continue
            overlay["label"] = result.overlay_patch.get("label", overlay.get("label"))
            adds_refs = [ref for ref in _as_list(overlay.get("adds_refs")) if isinstance(ref, str) and ref]
            for ref in result.overlay_patch.get("adds_refs", []):
                if ref not in adds_refs:
                    adds_refs.append(ref)
            # Keep both machinery frameworks visible during transition.
            if "REF-MACH-REG" not in adds_refs:
                adds_refs.append("REF-MACH-REG")
            overlay["adds_refs"] = sorted(set(adds_refs))

            prefixes = [prefix for prefix in _as_list(overlay.get("rule_prefixes")) if isinstance(prefix, str) and prefix]
            for prefix in result.overlay_patch.get("rule_prefixes_to_include", []):
                if prefix not in prefixes:
                    prefixes.append(prefix)
            if "PSTD-" not in prefixes:
                prefixes.append("PSTD-")
            overlay["rule_prefixes"] = prefixes
            break
    overlays_path.write_text(json.dumps(overlays_payload, indent=2), encoding="utf-8")

    rule_library = json.loads(rule_library_path.read_text(encoding="utf-8"))
    rules = [rule for rule in _as_list(rule_library.get("rules")) if isinstance(rule, dict)]
    rules = [rule for rule in rules if not str(rule.get("rule_id", "")).startswith("PSTD-")]
    rules.extend(result.compiled_rules_executable)
    rule_library["rules"] = rules
    rule_library["generated_at"] = _now_iso()

    # Keep pack expected count aligned for visibility; loader cross-check uses manifest counts.
    packs = _as_list(rule_library.get("packs"))
    overlay_count = sum(1 for rule in rules if rule.get("pack_id") == "F_OVERLAY")
    for pack in packs:
        if isinstance(pack, dict) and pack.get("pack_id") == "F_OVERLAY":
            pack["expected_rule_count"] = overlay_count
            break

    rule_library_path.write_text(json.dumps(rule_library, indent=2), encoding="utf-8")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["generated_at"] = _now_iso()
    manifest["expected_rule_count"] = len(rules)
    manifest["reference_count"] = len([key for key in references.keys() if isinstance(key, str) and key])

    pack_counts: dict[str, int] = {}
    for rule in rules:
        pack_id = rule.get("pack_id")
        if isinstance(pack_id, str) and pack_id:
            pack_counts[pack_id] = pack_counts.get(pack_id, 0) + 1
    manifest["pack_counts"] = dict(sorted(pack_counts.items()))
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    return {
        "rules_executable_now": len(result.compiled_rules_executable),
        "rules_deferred": len(result.compiled_rules_deferred),
        "references_patched": len(result.references_patch),
    }


def write_compile_artifacts(
    result: CompileResult,
    *,
    source_output_path: Path,
    compiled_output_path: Path,
    mapping_output_path: Path,
) -> None:
    source_output_path.parent.mkdir(parents=True, exist_ok=True)
    source_output_path.write_text(
        json.dumps(result.sanitized_payload, indent=2),
        encoding="utf-8",
    )

    compiled_payload = {
        "generated_at": _now_iso(),
        "source": "pilot_deep_research",
        "executable_rules": result.compiled_rules_executable,
        "deferred_rules": result.compiled_rules_deferred,
    }
    compiled_output_path.parent.mkdir(parents=True, exist_ok=True)
    compiled_output_path.write_text(
        json.dumps(compiled_payload, indent=2),
        encoding="utf-8",
    )

    mapping_output_path.parent.mkdir(parents=True, exist_ok=True)
    mapping_output_path.write_text(
        json.dumps(result.mapping_contract, indent=2),
        encoding="utf-8",
    )


def _compile_references_patch(raw_refs: Any) -> list[dict[str, Any]]:
    refs: dict[str, dict[str, Any]] = {}
    for entry in _as_list(raw_refs):
        if not isinstance(entry, dict):
            continue
        ref_id = _clean_text(entry.get("ref_id"))
        if not ref_id:
            continue
        refs[ref_id] = {
            "ref_id": ref_id,
            "title": _clean_text(entry.get("title")) or ref_id,
            "url": _clean_text(entry.get("url")),
            "type": _clean_text(entry.get("type")) or "standard",
            "notes": _clean_text(entry.get("notes")),
        }
    return [refs[key] for key in sorted(refs.keys())]


def _compile_overlay_patch(raw_overlay: Any) -> dict[str, Any]:
    overlay = raw_overlay if isinstance(raw_overlay, dict) else {}
    adds_refs = sorted(
        {
            _clean_text(ref)
            for ref in _as_list(overlay.get("adds_refs"))
            if _clean_text(ref)
        }
    )
    prefixes = [
        _clean_text(prefix)
        for prefix in _as_list(overlay.get("rule_prefixes_to_include"))
        if _clean_text(prefix)
    ]
    return {
        "overlay_id": _clean_text(overlay.get("overlay_id")) or "pilot_prototype",
        "label": _clean_text(overlay.get("label")) or "Pilots",
        "adds_refs": adds_refs,
        "rule_prefixes_to_include": prefixes,
    }


def _compile_rule_candidate(
    candidate: dict[str, Any],
    *,
    allowed_inputs: set[str],
) -> dict[str, Any]:
    source_rule_id = _clean_text(candidate.get("rule_id")) or "PILOTSTD-000"
    runtime_rule_id = _map_rule_id(source_rule_id)

    raw_inputs = [value for value in _as_list(candidate.get("inputs_required")) if isinstance(value, str)]
    mapped_inputs: list[str] = []
    unknown_source_inputs: list[str] = []
    for input_key in raw_inputs:
        mapped = _map_input_key(input_key)
        if mapped not in allowed_inputs:
            unknown_source_inputs.append(input_key)
            continue
        if mapped not in mapped_inputs:
            mapped_inputs.append(mapped)

    if not mapped_inputs:
        mapped_inputs = ["manual_context"]

    check_logic = candidate.get("check_logic") if isinstance(candidate.get("check_logic"), dict) else {}
    check_type = _clean_text(check_logic.get("type")).lower()
    if check_type not in {"deterministic", "hybrid", "llm_assisted"}:
        check_type = "deterministic"

    status = "executable_now"
    if bool(candidate.get("needs_new_metric")):
        status = "deferred"

    runtime_rule = {
        "rule_id": runtime_rule_id,
        "pack_id": _clean_text(candidate.get("pack_id")) or "F_OVERLAY",
        "title": _clean_text(candidate.get("title")) or runtime_rule_id,
        "description": _clean_text(candidate.get("description")) or _clean_text(candidate.get("title")) or runtime_rule_id,
        "applies_to": ["compliance_overlay"],
        "inputs_required": mapped_inputs,
        "check_logic": {"type": check_type},
        "severity": _normalize_severity(candidate.get("severity")),
        "fix_template": _clean_text(candidate.get("fix_template")) or "Add required compliance evidence and overlay-specific controls.",
        "refs": sorted(
            {
                _clean_text(ref)
                for ref in _as_list(candidate.get("refs"))
                if _clean_text(ref)
            }
        )
        or ["REF-HYG-1"],
        "thresholds": {
            "compiled_from": "pilot_deep_research",
            "source_rule_id": source_rule_id,
            "source_analysis_mode": _clean_text(candidate.get("analysis_mode")),
            "source_standard_clause": _clean_text(candidate.get("standard_clause")) or None,
            "source_predicate": check_logic.get("predicate"),
            "source_evaluator_hint": _clean_text(check_logic.get("evaluator_hint")),
            "source_pilot_sets": [
                _clean_text(value)
                for value in _as_list(candidate.get("pilot_sets"))
                if _clean_text(value)
            ],
            "source_evidence_quality": _clean_text(candidate.get("evidence_quality")),
            "source_needs_manual_confirmation": bool(candidate.get("needs_manual_confirmation")),
            "source_inputs": raw_inputs,
            "compiled_inputs": mapped_inputs,
            "unknown_source_inputs": unknown_source_inputs,
            "compile_status": status,
        },
    }

    mapping_row = {
        "source_rule_id": source_rule_id,
        "runtime_rule_id": runtime_rule_id,
        "status": status,
        "source_analysis_mode": _clean_text(candidate.get("analysis_mode")),
        "input_mapping": [
            {
                "source_input": source_input,
                "runtime_input": _map_input_key(source_input),
            }
            for source_input in raw_inputs
        ],
        "unknown_source_inputs": unknown_source_inputs,
    }
    return {"status": status, "rule": runtime_rule, "mapping": mapping_row}


def _map_rule_id(source_rule_id: str) -> str:
    match = SOURCE_RULE_ID_PATTERN.match(source_rule_id)
    if match:
        index = int(match.group(1))
        return f"PSTD-{index:03d}"
    if RUNTIME_RULE_ID_PATTERN.match(source_rule_id):
        return source_rule_id
    return "PSTD-999"


def _map_input_key(input_key: str) -> str:
    key = _clean_text(input_key)
    if key in INPUT_ALIAS_MAP:
        return INPUT_ALIAS_MAP[key]
    if key.startswith("drawing."):
        return "drawing_notes"
    if key.startswith("docs."):
        return "manual_context"
    if key.startswith("project."):
        return "manual_context"
    if key.startswith("cad."):
        return "geometry_features"
    if key.startswith("bom."):
        return "bom_items"
    return key


def _sanitize_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _sanitize_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_sanitize_value(item) for item in value]
    if isinstance(value, str):
        text = value
        text = SPECIAL_CITE_PATTERN.sub("", text)
        text = CITE_TOKEN_PATTERN.sub("", text)
        replacements = {
            "â€”": "-",
            "â€“": "-",
            "“": '"',
            "”": '"',
            "’": "'",
        }
        for src, dst in replacements.items():
            text = text.replace(src, dst)
        text = " ".join(text.split())
        return text.strip()
    return value


def _allowed_runtime_inputs() -> set[str]:
    schema_payload = json.loads(RULE_SCHEMA_PATH.read_text(encoding="utf-8"))
    values = (
        schema_payload.get("properties", {})
        .get("rules", {})
        .get("items", {})
        .get("properties", {})
        .get("inputs_required", {})
        .get("items", {})
        .get("enum", [])
    )
    return {str(value) for value in values if isinstance(value, str) and value}


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    return []


def _normalize_severity(value: Any) -> str:
    severity = _clean_text(value).lower()
    if severity in {"critical", "major", "minor", "info"}:
        return severity
    if severity == "warning":
        return "major"
    if severity == "caution":
        return "minor"
    return "major"


def _clean_text(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip()


def _now_iso() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )

