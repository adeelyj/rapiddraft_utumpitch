from __future__ import annotations

from typing import Any

from .dfm_bundle import DfmBundle


BASE_DRAWING_PACK_ID = "A_DRAWING"

LEGACY_MATERIAL_OPTIONS = (
    {"id": "aluminum", "label": "Aluminum"},
    {"id": "steel", "label": "Steel"},
    {"id": "stainless_steel", "label": "Stainless Steel"},
    {"id": "abs", "label": "ABS"},
    {"id": "nylon", "label": "Nylon"},
)

LEGACY_PROCESS_OPTIONS = (
    {"id": "cnc_machining", "label": "CNC Machining"},
    {"id": "sheet_metal_fabrication", "label": "Sheet Metal Fabrication"},
    {"id": "injection_molding", "label": "Injection Molding"},
    {"id": "welding_fabrication", "label": "Welding & Fabrication"},
    {"id": "additive_manufacturing", "label": "Additive Manufacturing"},
    {"id": "assembly", "label": "Assembly"},
)

LEGACY_INDUSTRY_OPTIONS = (
    {
        "id": "app_advance",
        "label": "App Advance",
        "standards": ["ISO 2768", "ISO 1011", "ISO 1302", "ISO 965-1"],
    },
    {
        "id": "aerospace",
        "label": "Aerospace",
        "standards": ["AS9100", "ASME Y14.5", "NADCAP"],
    },
    {
        "id": "medical_devices",
        "label": "Medical Devices",
        "standards": ["ISO 13485", "ISO 14971", "ISO 20417"],
    },
)


class DfmPlanningError(ValueError):
    pass


def build_dfm_config(bundle: DfmBundle) -> dict[str, Any]:
    manifest = bundle.manifest
    source_dir = str(bundle.bundle_dir)
    try:
        source_dir = str(bundle.bundle_dir.relative_to(bundle.repo_root))
    except ValueError:
        pass

    return {
        "bundle": {
            "version": manifest.get("version"),
            "generated_at": manifest.get("generated_at"),
            "source_dir": source_dir,
        },
        "manifest": {
            "expected_rule_count": manifest.get("expected_rule_count"),
            "pack_counts": manifest.get("pack_counts"),
            "reference_count": manifest.get("reference_count"),
            "roles_count": manifest.get("roles_count"),
            "templates_count": manifest.get("templates_count"),
        },
        "processes": bundle.process_classifier.get("process_families", []),
        "overlays": bundle.overlays.get("overlays", []),
        "roles": bundle.roles.get("roles", []),
        "templates": bundle.report_templates.get("templates", []),
        "packs": bundle.rule_library.get("packs", []),
        "profile_options": build_component_profile_options(bundle),
        "ui_bindings": bundle.ui_bindings,
        "interaction_rules": bundle.ui_bindings.get("interaction_rules", {}),
    }


def build_component_profile_options(bundle: DfmBundle) -> dict[str, Any]:
    process_options: list[dict[str, str]] = []
    for process in bundle.process_classifier.get("process_families", []):
        if not isinstance(process, dict):
            continue
        process_id = process.get("process_id")
        label = process.get("label")
        if isinstance(process_id, str) and process_id and isinstance(label, str) and label:
            process_options.append({"id": process_id, "label": label})
    for legacy_option in LEGACY_PROCESS_OPTIONS:
        _append_option_if_missing(process_options, legacy_option)

    industries: list[dict[str, Any]] = [{"id": "none", "label": "None", "standards": []}]
    reference_titles = _reference_title_map(bundle.references)
    for overlay in bundle.overlays.get("overlays", []):
        if not isinstance(overlay, dict):
            continue
        overlay_id = overlay.get("overlay_id")
        label = overlay.get("label")
        if not isinstance(overlay_id, str) or not overlay_id:
            continue
        if not isinstance(label, str) or not label:
            label = overlay_id

        standards: list[str] = []
        seen: set[str] = set()
        for ref_id in overlay.get("adds_refs", []):
            if not isinstance(ref_id, str) or not ref_id:
                continue
            standard_label = reference_titles.get(ref_id, ref_id)
            if standard_label in seen:
                continue
            seen.add(standard_label)
            standards.append(standard_label)

        industries.append(
            {
                "id": overlay_id,
                "label": label,
                "standards": standards,
            }
        )
    for legacy_industry in LEGACY_INDUSTRY_OPTIONS:
        _append_industry_if_missing(industries, legacy_industry)

    global_defaults = bundle.cost_model.get("global_defaults", {})
    material_keys: set[str] = set()
    for mapping_key in (
        "material_rate_per_kg_by_key",
        "material_density_kg_per_mm3_by_key",
    ):
        mapping = global_defaults.get(mapping_key, {})
        if isinstance(mapping, dict):
            for material_key in mapping.keys():
                if isinstance(material_key, str) and material_key:
                    material_keys.add(material_key)

    materials = [
        {"id": material_key, "label": _humanize_material_key(material_key)}
        for material_key in sorted(material_keys)
    ]
    if not materials:
        materials = [{"id": "material_generic", "label": "Material Generic"}]
    for legacy_material in LEGACY_MATERIAL_OPTIONS:
        _append_option_if_missing(materials, legacy_material)

    return {
        "materials": sorted(materials, key=lambda entry: str(entry.get("label", "")).lower()),
        "manufacturingProcesses": sorted(
            process_options, key=lambda entry: str(entry.get("label", "")).lower()
        ),
        "industries": [industries[0]]
        + sorted(industries[1:], key=lambda entry: str(entry.get("label", "")).lower()),
    }


def plan_dfm_execution(
    bundle: DfmBundle,
    *,
    extracted_part_facts: dict[str, Any],
    selected_role: str,
    selected_template: str,
    selected_process_override: str | None = None,
    selected_overlay: str | None = None,
    run_both_if_mismatch: bool = True,
) -> dict[str, Any]:
    return plan_dfm_execution_with_template_catalog(
        bundle,
        extracted_part_facts=extracted_part_facts,
        selected_role=selected_role,
        selected_template=selected_template,
        selected_process_override=selected_process_override,
        selected_overlay=selected_overlay,
        run_both_if_mismatch=run_both_if_mismatch,
        template_catalog=[
            template
            for template in bundle.report_templates.get("templates", [])
            if isinstance(template, dict)
        ],
    )


def plan_dfm_execution_with_template_catalog(
    bundle: DfmBundle,
    *,
    extracted_part_facts: dict[str, Any],
    selected_role: str,
    selected_template: str,
    selected_process_override: str | None = None,
    selected_overlay: str | None = None,
    run_both_if_mismatch: bool = True,
    template_catalog: list[dict[str, Any]],
) -> dict[str, Any]:
    process_map = _index_by_id(bundle.process_classifier.get("process_families", []), "process_id")
    overlay_map = _index_by_id(bundle.overlays.get("overlays", []), "overlay_id")
    role_map = _index_by_id(bundle.roles.get("roles", []), "role_id")
    template_map = _index_by_id(template_catalog, "template_id")
    pack_map = _index_by_id(bundle.rule_library.get("packs", []), "pack_id")

    if selected_role not in role_map:
        raise DfmPlanningError(f"Unknown selected_role '{selected_role}'.")
    if selected_template not in template_map:
        raise DfmPlanningError(f"Unknown selected_template '{selected_template}'.")
    if selected_process_override and selected_process_override not in process_map:
        raise DfmPlanningError(
            f"Unknown selected_process_override '{selected_process_override}'."
        )
    if selected_overlay and selected_overlay not in overlay_map:
        raise DfmPlanningError(f"Unknown selected_overlay '{selected_overlay}'.")

    ai_recommendation = _recommend_process(
        process_classifier=bundle.process_classifier,
        extracted_part_facts=extracted_part_facts,
    )
    ai_process_id = ai_recommendation["process_id"]

    user_process_id = selected_process_override or None
    has_mismatch = bool(user_process_id and user_process_id != ai_process_id)

    mismatch_policy = (
        bundle.process_classifier.get("tie_break_logic", {}).get("mismatch_policy", {})
    )
    policy_allows_run_both = bool(mismatch_policy.get("run_both_if_user_override", False))
    run_both_requested = bool(run_both_if_mismatch)
    run_both_executed = bool(
        has_mismatch and run_both_requested and policy_allows_run_both
    )

    if run_both_executed:
        process_plan_order = [user_process_id, ai_process_id]
    else:
        process_plan_order = [user_process_id or ai_process_id]

    overlay_pack_id = None
    overlay_label = None
    if selected_overlay:
        overlay = overlay_map[selected_overlay]
        overlay_pack_id = overlay.get("adds_rules_pack")
        overlay_label = overlay.get("label")

    execution_plans: list[dict[str, Any]] = []
    for idx, process_id in enumerate(process_plan_order):
        process_entry = process_map[process_id]
        pack_ids = _build_pack_ids_for_plan(
            process_entry.get("default_packs", []), overlay_pack_id
        )
        selected_template_entry = template_map[selected_template]
        template_sections = _resolve_template_sections_for_plan(
            template=selected_template_entry,
            selected_overlay=selected_overlay,
        )

        if run_both_executed and idx == 0:
            route_source = "user_override"
        elif run_both_executed and idx == 1:
            route_source = "ai_recommendation"
        elif user_process_id:
            route_source = "user_override"
        else:
            route_source = "ai_recommendation"

        execution_plans.append(
            {
                "plan_id": f"plan_{idx + 1}",
                "route_source": route_source,
                "process_id": process_id,
                "process_label": process_entry.get("label"),
                "pack_ids": pack_ids,
                "pack_labels": [_label_for_pack(pack_map, pack_id) for pack_id in pack_ids],
                "overlay_id": selected_overlay,
                "overlay_label": overlay_label,
                "role_id": selected_role,
                "role_label": role_map[selected_role].get("label"),
                "template_id": selected_template,
                "template_label": selected_template_entry.get("label"),
                "template_sections": template_sections["enabled"],
                "suppressed_template_sections": template_sections["suppressed"],
                "standards_used_mode": "findings.refs_auto",
            }
        )

    banner = None
    if has_mismatch and mismatch_policy.get("record_mismatch_banner"):
        template = mismatch_policy.get("banner_template")
        if isinstance(template, str) and template.strip():
            user_process_label = process_map[user_process_id]["label"]
            ai_process_label = process_map[ai_process_id]["label"]
            banner = template.format(
                user_process=user_process_label,
                ai_process=ai_process_label,
                ai_confidence=f"{ai_recommendation['confidence']:.2f}",
            )

    primary_process_id = process_plan_order[0]
    return {
        "ai_recommendation": ai_recommendation,
        "selected_process": {
            "process_id": primary_process_id,
            "process_label": process_map[primary_process_id]["label"],
            "selected_via": "user_override" if user_process_id else "ai_recommendation",
        },
        "selected_packs": execution_plans[0]["pack_ids"],
        "mismatch": {
            "has_mismatch": has_mismatch,
            "user_selected_process": _process_ref(process_map, user_process_id),
            "ai_process": _process_ref(process_map, ai_process_id),
            "run_both_requested": run_both_requested,
            "policy_allows_run_both": policy_allows_run_both,
            "run_both_executed": run_both_executed,
            "banner": banner,
        },
        "execution_plans": execution_plans,
    }


def _index_by_id(items: list[Any], id_key: str) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        item_id = item.get(id_key)
        if isinstance(item_id, str) and item_id:
            indexed[item_id] = item
    return indexed


def _reference_title_map(references_payload: dict[str, Any]) -> dict[str, str]:
    if isinstance(references_payload.get("references"), list):
        mapping: dict[str, str] = {}
        for entry in references_payload.get("references", []):
            if not isinstance(entry, dict):
                continue
            ref_id = entry.get("ref_id")
            title = entry.get("title")
            if isinstance(ref_id, str) and ref_id:
                if isinstance(title, str) and title.strip():
                    mapping[ref_id] = title.strip()
                else:
                    mapping[ref_id] = ref_id
        return mapping

    mapping = {}
    for ref_id, entry in references_payload.items():
        if not isinstance(ref_id, str) or not ref_id:
            continue
        if isinstance(entry, dict):
            title = entry.get("title")
            mapping[ref_id] = title.strip() if isinstance(title, str) and title.strip() else ref_id
        else:
            mapping[ref_id] = ref_id
    return mapping


def _humanize_material_key(material_key: str) -> str:
    parts = [part for part in material_key.replace("-", "_").split("_") if part]
    if not parts:
        return material_key
    return " ".join(part if part.isdigit() else part.capitalize() for part in parts)


def _append_option_if_missing(options: list[dict[str, Any]], candidate: dict[str, Any]) -> None:
    label = candidate.get("label")
    if not isinstance(label, str) or not label:
        return
    if any(isinstance(entry.get("label"), str) and entry.get("label") == label for entry in options):
        return
    option_id = candidate.get("id")
    if not isinstance(option_id, str) or not option_id:
        return
    options.append({"id": option_id, "label": label})


def _append_industry_if_missing(
    industries: list[dict[str, Any]], candidate: dict[str, Any]
) -> None:
    label = candidate.get("label")
    if not isinstance(label, str) or not label:
        return
    if any(isinstance(entry.get("label"), str) and entry.get("label") == label for entry in industries):
        return
    industry_id = candidate.get("id")
    if not isinstance(industry_id, str) or not industry_id:
        return
    standards = candidate.get("standards")
    standards = standards if isinstance(standards, list) else []
    standards = [item for item in standards if isinstance(item, str)]
    industries.append(
        {
            "id": industry_id,
            "label": label,
            "standards": standards,
        }
    )


def _recommend_process(
    process_classifier: dict[str, Any],
    extracted_part_facts: dict[str, Any],
) -> dict[str, Any]:
    process_families = process_classifier.get("process_families", [])
    heuristics = process_classifier.get("heuristics", [])

    scores: dict[str, float] = {}
    reasons_by_process: dict[str, list[str]] = {}

    for family in process_families:
        if not isinstance(family, dict):
            continue
        process_id = family.get("process_id")
        if not isinstance(process_id, str) or not process_id:
            continue
        scores[process_id] = 0.5
        reasons_by_process[process_id] = []

    for heuristic in heuristics:
        if not isinstance(heuristic, dict):
            continue
        process_id = heuristic.get("process_id")
        if process_id not in scores:
            continue
        if not _heuristic_matches(heuristic, extracted_part_facts):
            continue
        boost = _as_float(heuristic.get("confidence_boost"), default=0.0)
        scores[process_id] = min(1.0, scores[process_id] + boost)
        for reason in heuristic.get("reasons", []):
            if isinstance(reason, str) and reason.strip():
                reasons_by_process[process_id].append(reason.strip())

    if not scores:
        raise DfmPlanningError("No process_families available for planning.")

    ranked = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    top_process_id, top_score = ranked[0]
    family_map = _index_by_id(process_families, "process_id")

    confidence_level = _resolve_confidence_level(
        confidence_value=top_score,
        thresholds=process_classifier.get("confidence_thresholds", {}),
    )
    top_reasons = reasons_by_process.get(top_process_id, [])
    if not top_reasons:
        top_reasons = ["No strong heuristic fired; using baseline process confidence."]

    return {
        "process_id": top_process_id,
        "process_label": family_map[top_process_id].get("label"),
        "confidence": round(top_score, 4),
        "confidence_level": confidence_level,
        "reasons": top_reasons,
        "candidate_scores": [
            {
                "process_id": process_id,
                "process_label": family_map[process_id].get("label"),
                "score": round(score, 4),
            }
            for process_id, score in ranked
        ],
    }


def _heuristic_matches(heuristic: dict[str, Any], facts: dict[str, Any]) -> bool:
    conditions_all = heuristic.get("conditions_all", [])
    conditions_any = heuristic.get("conditions_any", [])
    conditions_not = heuristic.get("conditions_not", [])

    if any(not _evaluate_condition(condition, facts) for condition in conditions_all):
        return False
    if conditions_any and not any(_evaluate_condition(condition, facts) for condition in conditions_any):
        return False
    if any(_evaluate_condition(condition, facts) for condition in conditions_not):
        return False
    return True


def _evaluate_condition(condition: Any, facts: dict[str, Any]) -> bool:
    if not isinstance(condition, str):
        return False
    token = condition.strip()
    if not token:
        return False

    if " and " in token:
        return all(_evaluate_condition(part, facts) for part in token.split(" and "))
    if " or " in token:
        return any(_evaluate_condition(part, facts) for part in token.split(" or "))

    return _truthy_fact(facts.get(token))


def _truthy_fact(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, (int, float)):
        return value > 0
    if isinstance(value, str):
        normalized = value.strip().lower()
        if not normalized:
            return False
        if normalized in {"0", "false", "none", "null", "no"}:
            return False
        return True
    if isinstance(value, (list, tuple, set, dict)):
        return len(value) > 0
    return bool(value)


def _as_float(value: Any, default: float) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    return default


def _resolve_confidence_level(confidence_value: float, thresholds: dict[str, Any]) -> str:
    high_threshold = _as_float(
        thresholds.get("high", {}).get("gte"), default=0.8
    )
    medium_floor = _as_float(
        thresholds.get("medium", {}).get("gte"), default=0.65
    )

    if confidence_value >= high_threshold:
        return "high"
    if confidence_value >= medium_floor:
        return "medium"
    return "low"


def _build_pack_ids_for_plan(
    process_default_packs: list[Any], overlay_pack_id: str | None
) -> list[str]:
    ordered: list[str] = []

    if BASE_DRAWING_PACK_ID not in ordered:
        ordered.append(BASE_DRAWING_PACK_ID)

    for pack_id in process_default_packs:
        if isinstance(pack_id, str) and pack_id and pack_id not in ordered:
            ordered.append(pack_id)

    if overlay_pack_id and overlay_pack_id not in ordered:
        ordered.append(overlay_pack_id)

    return ordered


def _label_for_pack(pack_map: dict[str, dict[str, Any]], pack_id: str) -> str | None:
    entry = pack_map.get(pack_id)
    if not entry:
        return None
    label = entry.get("label")
    return label if isinstance(label, str) else None


def _resolve_template_sections(
    template: dict[str, Any], selected_overlay: str | None
) -> dict[str, list[str]]:
    enabled_sections: list[str] = []
    suppressed_sections: list[str] = []

    for section in template.get("sections", []):
        if not isinstance(section, dict):
            continue
        section_key = section.get("section_key")
        if not isinstance(section_key, str) or not section_key:
            continue
        overlay_required = section.get("overlay_required")
        if overlay_required and overlay_required != selected_overlay:
            suppressed_sections.append(section_key)
            continue
        enabled_sections.append(section_key)

    return {"enabled": enabled_sections, "suppressed": suppressed_sections}


def _resolve_template_sections_for_plan(
    template: dict[str, Any], selected_overlay: str | None
) -> dict[str, list[str]]:
    explicit_enabled = template.get("template_sections")
    if isinstance(explicit_enabled, list):
        enabled = _dedupe_strings(explicit_enabled)
        suppressed = _dedupe_strings(template.get("suppressed_template_sections", []))
        return {"enabled": enabled, "suppressed": suppressed}

    return _resolve_template_sections(template, selected_overlay)


def _dedupe_strings(values: list[Any]) -> list[str]:
    deduped: list[str] = []
    for value in values:
        if not isinstance(value, str):
            continue
        normalized = value.strip()
        if not normalized or normalized in deduped:
            continue
        deduped.append(normalized)
    return deduped


def _process_ref(
    process_map: dict[str, dict[str, Any]], process_id: str | None
) -> dict[str, str] | None:
    if not process_id:
        return None
    process_entry = process_map.get(process_id)
    if not process_entry:
        return {"process_id": process_id, "process_label": process_id}
    return {
        "process_id": process_id,
        "process_label": process_entry.get("label", process_id),
    }
