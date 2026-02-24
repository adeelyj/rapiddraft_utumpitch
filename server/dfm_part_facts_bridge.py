from __future__ import annotations

from typing import Any

KNOWN_METRIC_STATES = {"measured", "inferred", "declared"}
NOT_APPLICABLE_STATE = "not_applicable"
NOT_APPLICABLE_INPUTS_KEY = "__not_applicable_inputs__"


def build_extracted_facts_from_part_facts(
    part_facts_payload: dict[str, Any] | None,
    component_profile: dict[str, Any] | None,
    context_payload: dict[str, Any] | None,
) -> dict[str, Any]:
    facts: dict[str, Any] = {}
    not_applicable_inputs: set[str] = set()

    sections = {}
    if isinstance(part_facts_payload, dict):
        raw_sections = part_facts_payload.get("sections")
        if isinstance(raw_sections, dict):
            sections = raw_sections

    ordered_sections = (
        "geometry",
        "manufacturing_signals",
        "declared_context",
        "process_inputs",
        "rule_inputs",
    )
    for section_name in ordered_sections:
        metrics = sections.get(section_name)
        if not isinstance(metrics, dict):
            continue
        for key, metric in metrics.items():
            if not isinstance(key, str) or not isinstance(metric, dict):
                continue
            state = metric.get("state")
            if state == NOT_APPLICABLE_STATE:
                not_applicable_inputs.add(key)
                continue
            if state not in KNOWN_METRIC_STATES:
                continue
            _merge_fact_value(facts, key, _metric_fact_value(metric))

    _derive_hole_features(facts=facts, sections=sections, not_applicable_inputs=not_applicable_inputs)
    _derive_wall_thickness_signals(facts=facts, sections=sections, not_applicable_inputs=not_applicable_inputs)
    _derive_pilot_geometry_signals(facts=facts, sections=sections, not_applicable_inputs=not_applicable_inputs)
    _apply_profile_defaults(facts=facts, component_profile=component_profile or {})

    if context_payload and isinstance(context_payload, dict):
        manual_context_value = context_payload.get("manual_context")
        if _truthy_context_value(manual_context_value):
            facts["manual_context"] = True

    if context_payload and isinstance(context_payload, dict):
        explicit_na = context_payload.get(NOT_APPLICABLE_INPUTS_KEY)
        if isinstance(explicit_na, list):
            for key in explicit_na:
                if isinstance(key, str) and key:
                    not_applicable_inputs.add(key)

    facts[NOT_APPLICABLE_INPUTS_KEY] = sorted(not_applicable_inputs)
    return facts


def _metric_fact_value(metric: dict[str, Any]) -> Any:
    value = metric.get("value")
    if value is None:
        return True
    return value


def _merge_fact_value(facts: dict[str, Any], key: str, candidate: Any) -> None:
    if key not in facts:
        facts[key] = candidate
        return

    existing = facts[key]

    if existing in (None, ""):
        facts[key] = candidate
        return
    if candidate in (None, ""):
        return

    # Preserve richer values (numbers/strings) when a later metric only offers
    # a boolean availability signal.
    if isinstance(existing, bool) and not isinstance(candidate, bool):
        facts[key] = candidate
        return
    if isinstance(candidate, bool) and not isinstance(existing, bool):
        return

    if isinstance(existing, (int, float)) and isinstance(candidate, (int, float)):
        # Keep the larger numeric value when duplicate numeric signals exist.
        facts[key] = max(float(existing), float(candidate))
        return

    # Preserve the first non-empty value for remaining duplicate key cases.


def _derive_hole_features(
    *,
    facts: dict[str, Any],
    sections: dict[str, Any],
    not_applicable_inputs: set[str],
) -> None:
    if "hole_features" in not_applicable_inputs:
        return

    hole_count = _known_numeric_metric(sections, "manufacturing_signals", "hole_count")
    threaded_count = _known_numeric_metric(sections, "manufacturing_signals", "threaded_holes_count")
    if threaded_count is None:
        threaded_count = _known_numeric_metric(sections, "process_inputs", "threaded_holes_count")

    hole_depth_available = _known_truthy_metric(sections, "rule_inputs", "hole_depth")
    hole_diameter_available = _known_truthy_metric(sections, "rule_inputs", "hole_diameter")

    has_hole_signals = any(
        [
            hole_count is not None and hole_count > 0,
            threaded_count is not None and threaded_count > 0,
            hole_depth_available,
            hole_diameter_available,
        ]
    )
    if has_hole_signals:
        facts.setdefault("hole_features", True)


def _derive_wall_thickness_signals(
    *,
    facts: dict[str, Any],
    sections: dict[str, Any],
    not_applicable_inputs: set[str],
) -> None:
    if "wall_thickness_map" in not_applicable_inputs:
        return

    min_wall_thickness = _known_numeric_metric(sections, "manufacturing_signals", "min_wall_thickness_mm")
    if min_wall_thickness is None:
        min_wall_thickness = _known_numeric_metric(sections, "process_inputs", "min_wall_thickness")
    if min_wall_thickness is None:
        return

    facts.setdefault("min_wall_thickness", min_wall_thickness)
    facts.setdefault("wall_thickness_map", True)


def _derive_pilot_geometry_signals(
    *,
    facts: dict[str, Any],
    sections: dict[str, Any],
    not_applicable_inputs: set[str],
) -> None:
    # Robot interface and ISO 228 conformance flags can be inferred from
    # declared context hints when present.
    robot_interface_candidate = _known_truthy_metric(
        sections,
        "declared_context",
        "iso9409_1_robot_interface_candidate",
    )
    if robot_interface_candidate:
        facts.setdefault("cad.robot_interface.conformance_flag", True)
        facts.setdefault("robot_interface_conformance_flag", True)

    iso228_candidate = _known_truthy_metric(
        sections,
        "declared_context",
        "iso228_1_thread_standard_candidate",
    )
    if iso228_candidate:
        facts.setdefault("cad.threads.iso228_all_conformant", True)
        facts.setdefault("iso228_all_conformant", True)

    # Hygienic geometry proxies are derived from existing corner/radius signals
    # so geometry-only pilot rules can be evaluated for early-stage CAD.
    crevice_count = _known_numeric_metric(
        sections,
        "manufacturing_signals",
        "critical_corner_count",
    )
    if crevice_count is not None:
        crevice_value = max(0.0, crevice_count)
        facts.setdefault("cad.hygienic_design.crevice_count", crevice_value)
        facts.setdefault("crevice_count", crevice_value)

    enclosed_void_count = _known_numeric_metric(
        sections,
        "manufacturing_signals",
        "count_radius_below_3_0_mm",
    )
    if enclosed_void_count is None:
        enclosed_void_count = _known_numeric_metric(
            sections,
            "manufacturing_signals",
            "warning_corner_count",
        )
    if enclosed_void_count is not None:
        enclosed_void_value = max(0.0, enclosed_void_count)
        facts.setdefault(
            "cad.hygienic_design.enclosed_voids_in_product_zone_count",
            enclosed_void_value,
        )
        facts.setdefault("enclosed_voids_in_product_zone_count", enclosed_void_value)

    trapped_volume_count = _known_numeric_metric(
        sections,
        "manufacturing_signals",
        "long_reach_tool_risk_count",
    )
    if trapped_volume_count is not None:
        trapped_value = max(0.0, trapped_volume_count)
        facts.setdefault("cad.hygienic_design.trapped_volume_count", trapped_value)
        facts.setdefault("trapped_volume_count", trapped_value)


def _apply_profile_defaults(
    *,
    facts: dict[str, Any],
    component_profile: dict[str, Any],
) -> None:
    material = _clean_optional_string(component_profile.get("material"))
    process = _clean_optional_string(component_profile.get("manufacturingProcess"))
    industry = _clean_optional_string(component_profile.get("industry"))

    if material:
        facts["material_spec"] = material
    if process:
        facts["manufacturing_process"] = process
    if industry:
        facts["industry"] = industry


def _metric_with_state(
    sections: dict[str, Any],
    section_name: str,
    key: str,
) -> dict[str, Any] | None:
    section = sections.get(section_name)
    if not isinstance(section, dict):
        return None
    metric = section.get(key)
    if not isinstance(metric, dict):
        return None
    if metric.get("state") not in KNOWN_METRIC_STATES:
        return None
    return metric


def _known_numeric_metric(
    sections: dict[str, Any],
    section_name: str,
    key: str,
) -> float | None:
    metric = _metric_with_state(sections, section_name, key)
    if not metric:
        return None
    value = metric.get("value")
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _known_truthy_metric(
    sections: dict[str, Any],
    section_name: str,
    key: str,
) -> bool:
    metric = _metric_with_state(sections, section_name, key)
    if not metric:
        return False
    value = metric.get("value")
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


def _clean_optional_string(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip()


def _truthy_context_value(value: Any) -> bool:
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
