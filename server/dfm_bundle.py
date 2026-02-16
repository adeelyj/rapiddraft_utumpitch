from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_BUNDLE_DIR = Path(__file__).resolve().parent / "dfm"
DEFAULT_REPO_ROOT = DEFAULT_BUNDLE_DIR.parent.parent

REQUIRED_JSON_FILES = (
    "manifest.json",
    "references.json",
    "rule_library.json",
    "process_classifier.json",
    "overlays.json",
    "roles.json",
    "report_templates.json",
    "ui_bindings.json",
    "accounts_pilot_targets.json",
    "supplier_profile_template.json",
    "cost_model.json",
)

SCHEMA_MAP = {
    "rule_library.json": "rule_library.schema.json",
    "overlays.json": "overlays.schema.json",
    "roles.json": "roles.schema.json",
    "report_templates.json": "report_templates.schema.json",
    "ui_bindings.json": "ui_bindings.schema.json",
    "accounts_pilot_targets.json": "accounts_pilot_targets.schema.json",
    "cost_model.json": "cost_model.schema.json",
    "supplier_profile_template.json": "supplier_profile_template.schema.json",
}


class DfmBundleValidationError(RuntimeError):
    pass


@dataclass(frozen=True)
class DfmBundle:
    bundle_dir: Path
    repo_root: Path
    manifest: dict[str, Any]
    references: dict[str, Any]
    rule_library: dict[str, Any]
    process_classifier: dict[str, Any]
    overlays: dict[str, Any]
    roles: dict[str, Any]
    report_templates: dict[str, Any]
    ui_bindings: dict[str, Any]
    accounts_pilot_targets: dict[str, Any]
    supplier_profile_template: dict[str, Any]
    cost_model: dict[str, Any]


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise DfmBundleValidationError(f"Invalid JSON in '{path}': {exc}") from exc
    if not isinstance(payload, dict):
        raise DfmBundleValidationError(f"Expected object JSON in '{path}', got {type(payload).__name__}")
    return payload


def _validate_schema(payload: dict[str, Any], schema_path: Path, data_filename: str) -> None:
    try:
        import jsonschema
    except ModuleNotFoundError as exc:
        raise DfmBundleValidationError(
            "Schema validation dependency missing. Install 'jsonschema' to validate DFM bundle."
        ) from exc

    schema = _read_json(schema_path)
    try:
        jsonschema.validate(payload, schema)
    except Exception as exc:
        raise DfmBundleValidationError(
            f"Schema validation failed for '{data_filename}' with '{schema_path.name}': {exc}"
        ) from exc


def _extract_reference_ids(references: dict[str, Any]) -> set[str]:
    if "references" in references and isinstance(references["references"], list):
        ids = {
            str(item.get("ref_id"))
            for item in references["references"]
            if isinstance(item, dict) and isinstance(item.get("ref_id"), str)
        }
        return {item for item in ids if item}
    return {str(key) for key in references.keys() if isinstance(key, str) and key}


def _validate_manifest_file_entries(manifest: dict[str, Any], repo_root: Path) -> list[str]:
    errors: list[str] = []
    files = manifest.get("files")
    if not isinstance(files, list):
        return ["manifest.json: 'files' must be an array."]
    for entry in files:
        if not isinstance(entry, str) or not entry.strip():
            errors.append("manifest.json: each 'files' entry must be a non-empty string.")
            continue
        file_path = Path(entry)
        resolved = file_path if file_path.is_absolute() else repo_root / file_path
        if not resolved.exists():
            errors.append(f"manifest.json: listed file does not exist: '{entry}'")
    return errors


def _validate_cross_file_integrity(payloads: dict[str, dict[str, Any]], repo_root: Path) -> list[str]:
    errors: list[str] = []

    manifest = payloads["manifest.json"]
    rule_library = payloads["rule_library.json"]
    process_classifier = payloads["process_classifier.json"]
    overlays = payloads["overlays.json"]
    roles = payloads["roles.json"]
    report_templates = payloads["report_templates.json"]
    references = payloads["references.json"]

    errors.extend(_validate_manifest_file_entries(manifest, repo_root))

    rules = rule_library.get("rules", [])
    packs = rule_library.get("packs", [])
    if not isinstance(rules, list):
        return errors + ["rule_library.json: 'rules' must be an array."]
    if not isinstance(packs, list):
        return errors + ["rule_library.json: 'packs' must be an array."]

    pack_ids = {
        pack.get("pack_id")
        for pack in packs
        if isinstance(pack, dict) and isinstance(pack.get("pack_id"), str)
    }
    reference_ids = _extract_reference_ids(references)

    for idx, rule in enumerate(rules):
        if not isinstance(rule, dict):
            errors.append(f"rule_library.json: rule at index {idx} is not an object.")
            continue
        rule_id = str(rule.get("rule_id", f"index:{idx}"))
        pack_id = rule.get("pack_id")
        if pack_id not in pack_ids:
            errors.append(f"rule_library.json: rule '{rule_id}' uses unknown pack_id '{pack_id}'.")
        refs = rule.get("refs")
        if not isinstance(refs, list):
            errors.append(f"rule_library.json: rule '{rule_id}' has non-array refs.")
            continue
        for ref_id in refs:
            if not isinstance(ref_id, str):
                errors.append(f"rule_library.json: rule '{rule_id}' has non-string ref id.")
                continue
            if ref_id not in reference_ids:
                errors.append(f"rule_library.json: rule '{rule_id}' references missing ref '{ref_id}'.")

    for family in process_classifier.get("process_families", []):
        if not isinstance(family, dict):
            errors.append("process_classifier.json: process_families entry is not an object.")
            continue
        process_id = family.get("process_id", "<missing>")
        for pack_id in family.get("default_packs", []):
            if pack_id not in pack_ids:
                errors.append(
                    f"process_classifier.json: process '{process_id}' default pack '{pack_id}' does not exist."
                )

    overlay_ids = set()
    for overlay in overlays.get("overlays", []):
        if not isinstance(overlay, dict):
            errors.append("overlays.json: overlays entry is not an object.")
            continue
        overlay_id = overlay.get("overlay_id")
        if isinstance(overlay_id, str):
            overlay_ids.add(overlay_id)
        adds_pack = overlay.get("adds_rules_pack")
        if isinstance(adds_pack, str) and adds_pack not in pack_ids:
            errors.append(
                f"overlays.json: overlay '{overlay_id}' adds unknown rules pack '{adds_pack}'."
            )

    for role in roles.get("roles", []):
        if not isinstance(role, dict):
            errors.append("roles.json: roles entry is not an object.")
            continue
        role_id = role.get("role_id", "<missing>")
        for pack_id in role.get("emphasize_packs", []):
            if pack_id not in pack_ids:
                errors.append(f"roles.json: role '{role_id}' emphasizes unknown pack '{pack_id}'.")

    for template in report_templates.get("templates", []):
        if not isinstance(template, dict):
            errors.append("report_templates.json: templates entry is not an object.")
            continue
        template_id = template.get("template_id", "<missing>")
        for section in template.get("sections", []):
            if not isinstance(section, dict):
                errors.append(
                    f"report_templates.json: template '{template_id}' has non-object section."
                )
                continue
            overlay_required = section.get("overlay_required")
            if overlay_required and overlay_required not in overlay_ids:
                errors.append(
                    f"report_templates.json: template '{template_id}' section "
                    f"requires unknown overlay '{overlay_required}'."
                )

    actual_rule_count = len(rules)
    if manifest.get("expected_rule_count") != actual_rule_count:
        errors.append(
            f"manifest.json: expected_rule_count={manifest.get('expected_rule_count')} "
            f"does not match actual={actual_rule_count}."
        )

    actual_pack_counts = dict(
        sorted(
            Counter(
                rule.get("pack_id")
                for rule in rules
                if isinstance(rule, dict) and isinstance(rule.get("pack_id"), str)
            ).items()
        )
    )
    expected_pack_counts = manifest.get("pack_counts")
    if expected_pack_counts != actual_pack_counts:
        errors.append(
            f"manifest.json: pack_counts mismatch expected={expected_pack_counts} "
            f"actual={actual_pack_counts}."
        )

    actual_reference_count = len(reference_ids)
    if manifest.get("reference_count") != actual_reference_count:
        errors.append(
            f"manifest.json: reference_count={manifest.get('reference_count')} "
            f"does not match actual={actual_reference_count}."
        )

    actual_roles_count = len([r for r in roles.get("roles", []) if isinstance(r, dict)])
    if manifest.get("roles_count") != actual_roles_count:
        errors.append(
            f"manifest.json: roles_count={manifest.get('roles_count')} "
            f"does not match actual={actual_roles_count}."
        )

    actual_templates_count = len(
        [t for t in report_templates.get("templates", []) if isinstance(t, dict)]
    )
    if manifest.get("templates_count") != actual_templates_count:
        errors.append(
            f"manifest.json: templates_count={manifest.get('templates_count')} "
            f"does not match actual={actual_templates_count}."
        )

    return errors


def load_dfm_bundle(bundle_dir: Path | None = None, repo_root: Path | None = None) -> DfmBundle:
    bundle_dir = bundle_dir or DEFAULT_BUNDLE_DIR
    repo_root = repo_root or DEFAULT_REPO_ROOT

    if not bundle_dir.exists():
        raise DfmBundleValidationError(f"DFM bundle directory not found: '{bundle_dir}'")
    if not bundle_dir.is_dir():
        raise DfmBundleValidationError(f"DFM bundle path is not a directory: '{bundle_dir}'")

    payloads: dict[str, dict[str, Any]] = {}
    for filename in REQUIRED_JSON_FILES:
        path = bundle_dir / filename
        if not path.exists():
            raise DfmBundleValidationError(f"Required DFM file is missing: '{path}'")
        payloads[filename] = _read_json(path)

    schema_dir = bundle_dir / "schemas"
    if not schema_dir.exists() or not schema_dir.is_dir():
        raise DfmBundleValidationError(f"Schema directory is missing: '{schema_dir}'")

    for data_filename, schema_filename in SCHEMA_MAP.items():
        schema_path = schema_dir / schema_filename
        if not schema_path.exists():
            raise DfmBundleValidationError(
                f"Required schema file for '{data_filename}' is missing: '{schema_path}'"
            )
        _validate_schema(payloads[data_filename], schema_path, data_filename)

    cross_errors = _validate_cross_file_integrity(payloads, repo_root=repo_root)
    if cross_errors:
        joined = "\n- ".join(cross_errors)
        raise DfmBundleValidationError(f"DFM bundle cross-validation failed:\n- {joined}")

    return DfmBundle(
        bundle_dir=bundle_dir,
        repo_root=repo_root,
        manifest=payloads["manifest.json"],
        references=payloads["references.json"],
        rule_library=payloads["rule_library.json"],
        process_classifier=payloads["process_classifier.json"],
        overlays=payloads["overlays.json"],
        roles=payloads["roles.json"],
        report_templates=payloads["report_templates.json"],
        ui_bindings=payloads["ui_bindings.json"],
        accounts_pilot_targets=payloads["accounts_pilot_targets.json"],
        supplier_profile_template=payloads["supplier_profile_template.json"],
        cost_model=payloads["cost_model.json"],
    )
