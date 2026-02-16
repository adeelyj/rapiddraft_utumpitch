from __future__ import annotations

from typing import Any

from .dfm_bundle import DfmBundle


DEFAULT_GEOMETRY_METRICS = {
    "part_volume_mm3": 85000.0,
    "surface_area_mm2": 24000.0,
    "bbox_x_mm": 120.0,
    "bbox_y_mm": 80.0,
    "bbox_z_mm": 40.0,
    "bbox_volume_mm3": 384000.0,
    "body_count": 1.0,
}

MATERIAL_KEYWORDS = {
    "aluminum": "aluminum_6061",
    "stainless": "stainless_304",
    "steel": "steel_generic",
}


def estimate_review_costs(
    *,
    bundle: DfmBundle,
    route_outputs: list[dict[str, Any]],
    review_facts: dict[str, Any],
    component_context: dict[str, Any],
    mismatch: dict[str, Any] | None,
    context_payload: dict[str, Any],
) -> dict[str, Any]:
    cost_model = bundle.cost_model
    currency = _as_string(cost_model.get("currency")) or "USD"

    route_estimates: list[dict[str, Any]] = []
    for route in route_outputs:
        route_estimate = _estimate_route_cost(
            cost_model=cost_model,
            route=route,
            review_facts=review_facts,
            component_context=component_context,
            mismatch=mismatch or {},
            context_payload=context_payload,
        )
        route["cost_estimate"] = route_estimate
        report_skeleton = route.setdefault("report_skeleton", {})
        report_skeleton["cost_summary"] = {
            "currency": route_estimate["currency"],
            "quantity": route_estimate["quantity"],
            "unit_cost": route_estimate["unit_cost"],
            "total_cost": route_estimate["total_cost"],
            "confidence": route_estimate["confidence"],
            "confidence_level": route_estimate["confidence_level"],
            "cost_range": route_estimate["cost_range"],
            "assumptions": route_estimate["assumptions"],
        }
        report_skeleton["cost_drivers"] = route_estimate["cost_drivers"]
        report_skeleton["cost_compare_routes"] = None

        route_estimates.append(
            {
                "plan_id": route.get("plan_id"),
                "route_source": route.get("route_source"),
                "process_id": route.get("process_id"),
                "process_label": route.get("process_label"),
                **route_estimate,
            }
        )

    compare = _build_route_compare(route_estimates) if len(route_estimates) >= 2 else None
    if compare:
        for route in route_outputs:
            route.setdefault("report_skeleton", {})["cost_compare_routes"] = compare

    return {
        "cost_estimate": route_estimates[0] if route_estimates else None,
        "cost_estimate_by_route": route_estimates,
        "cost_compare_routes": compare,
        "currency": currency,
    }


def _estimate_route_cost(
    *,
    cost_model: dict[str, Any],
    route: dict[str, Any],
    review_facts: dict[str, Any],
    component_context: dict[str, Any],
    mismatch: dict[str, Any],
    context_payload: dict[str, Any],
) -> dict[str, Any]:
    assumptions: list[str] = []
    cost_drivers: list[dict[str, Any]] = []
    penalties = cost_model.get("confidence_policy", {}).get("penalties", {})

    geometry_info = _extract_geometry_metrics(
        cost_model=cost_model,
        review_facts=review_facts,
        component_context=component_context,
    )
    metrics = geometry_info["metrics"]
    assumptions.extend(geometry_info["assumptions"])

    quantity = _resolve_quantity(cost_model=cost_model, review_facts=review_facts, context_payload=context_payload)

    process_id = _as_string(route.get("process_id")) or ""
    process_models = cost_model.get("process_models", {})
    process_model = process_models.get(process_id)
    if not isinstance(process_model, dict):
        process_model = {}
        assumptions.append(
            f"No process-specific cost model for '{process_id}'. Using global defaults."
        )

    supplier_profile = context_payload.get("supplier_cost_profile")
    supplier_profile = supplier_profile if isinstance(supplier_profile, dict) else {}
    process_override = _resolve_process_override(supplier_profile, process_id)

    missing_supplier_rates = not _has_supplier_rate_override(process_override)
    if missing_supplier_rates:
        assumptions.append("Supplier-specific process rates not provided; using default model rates.")

    global_defaults = cost_model.get("global_defaults", {})

    material_info = _resolve_material_inputs(
        global_defaults=global_defaults,
        review_facts=review_facts,
        supplier_profile=supplier_profile,
    )
    assumptions.extend(material_info["assumptions"])

    throughput = process_model.get("throughput_model", {})
    coefficients = throughput.get("coefficients", {}) if isinstance(throughput, dict) else {}
    machine_hours, process_feature_missing = _estimate_machine_hours(
        coefficients=coefficients,
        review_facts=review_facts,
        metrics=metrics,
    )
    if process_feature_missing:
        assumptions.append("Some process feature metrics were missing; throughput estimate uses defaults.")

    setup_cost = _first_positive(
        process_override.get("setup_cost"),
        process_model.get("setup_cost"),
        global_defaults.get("setup_cost_default"),
        default=95.0,
    )
    hourly_rate = _first_positive(
        process_override.get("hourly_rate"),
        process_model.get("hourly_rate"),
        supplier_profile.get("hourly_rate"),
        default=85.0,
    )
    scrap_factor = _first_non_negative(
        process_override.get("scrap_factor"),
        process_model.get("scrap_factor"),
        global_defaults.get("scrap_factor_default"),
        default=0.05,
    )
    overhead_factor = _first_positive(
        process_override.get("overhead_factor"),
        process_model.get("overhead_factor"),
        supplier_profile.get("overhead_factor"),
        global_defaults.get("overhead_factor"),
        default=1.15,
    )
    inspection_hourly_rate = _first_positive(
        supplier_profile.get("inspection_hourly_rate"),
        global_defaults.get("inspection_hourly_rate"),
        default=65.0,
    )

    purchased_mass_kg = _estimate_purchased_mass_kg(
        process_model=process_model,
        part_mass_kg=material_info["part_mass_kg"],
    )
    material_cost_base = purchased_mass_kg * material_info["material_rate_per_kg"]
    scrap_cost = material_cost_base * scrap_factor
    material_cost = material_cost_base + scrap_cost

    findings = route.get("findings", [])
    findings = findings if isinstance(findings, list) else []

    process_cost = machine_hours * hourly_rate
    setup_cost_per_unit = setup_cost / max(quantity, 1.0)
    inspection_hours = _estimate_inspection_hours(findings_count=len(findings), findings=findings)
    inspection_cost = inspection_hours * inspection_hourly_rate

    impact_result = _apply_finding_impacts(
        findings=findings,
        finding_cost_impacts=cost_model.get("finding_cost_impacts", []),
    )
    process_cost *= impact_result["time_multiplier"]
    setup_cost_per_unit *= impact_result["setup_multiplier"]
    material_cost *= impact_result["material_multiplier"]
    material_cost *= impact_result["scrap_multiplier"]
    inspection_cost *= impact_result["inspection_multiplier"]
    cost_drivers.extend(impact_result["cost_drivers"])

    subtotal_pre_overhead = material_cost + process_cost + setup_cost_per_unit + inspection_cost
    overhead_cost = subtotal_pre_overhead * max(overhead_factor - 1.0, 0.0)
    unit_cost = subtotal_pre_overhead + overhead_cost
    total_cost = unit_cost * quantity

    confidence_value = _estimate_confidence(
        cost_model=cost_model,
        penalties=penalties,
        missing_supplier_rates=missing_supplier_rates,
        missing_material_density=material_info["missing_material_density"],
        used_default_geometry=geometry_info["used_default_geometry"],
        process_feature_missing=process_feature_missing,
        route_ambiguity=bool(mismatch.get("run_both_executed")),
    )
    confidence_level = _confidence_level(
        confidence_value=confidence_value,
        bands=cost_model.get("confidence_policy", {}).get("bands", {}),
    )
    range_fraction = _range_fraction_from_confidence_level(confidence_level)
    cost_range = {
        "unit_low": _round_amount(max(unit_cost * (1.0 - range_fraction), 0.0)),
        "unit_high": _round_amount(unit_cost * (1.0 + range_fraction)),
        "total_low": _round_amount(max(total_cost * (1.0 - range_fraction), 0.0)),
        "total_high": _round_amount(total_cost * (1.0 + range_fraction)),
    }

    if not cost_drivers:
        cost_drivers.extend(
            _default_cost_drivers(
                process_cost=process_cost,
                material_cost=material_cost,
                setup_cost_per_unit=setup_cost_per_unit,
                inspection_cost=inspection_cost,
            )
        )

    return {
        "currency": _as_string(cost_model.get("currency")) or "USD",
        "quantity": int(quantity) if quantity.is_integer() else _round_amount(quantity),
        "unit_cost": _round_amount(unit_cost),
        "total_cost": _round_amount(total_cost),
        "cost_range": cost_range,
        "confidence": round(confidence_value, 4),
        "confidence_level": confidence_level,
        "assumptions": assumptions,
        "cost_drivers": cost_drivers,
        "breakdown": {
            "material_cost": _round_amount(material_cost),
            "process_cost": _round_amount(process_cost),
            "setup_cost_per_unit": _round_amount(setup_cost_per_unit),
            "inspection_cost": _round_amount(inspection_cost),
            "overhead_cost": _round_amount(overhead_cost),
        },
        "metrics_used": {key: _round_amount(value) for key, value in metrics.items()},
    }


def _extract_geometry_metrics(
    *,
    cost_model: dict[str, Any],
    review_facts: dict[str, Any],
    component_context: dict[str, Any],
) -> dict[str, Any]:
    metrics: dict[str, float] = {}
    assumptions: list[str] = []
    used_default = False

    required_metrics = cost_model.get("required_metrics", [])
    required_metrics = required_metrics if isinstance(required_metrics, list) else []
    for metric_name in required_metrics:
        if not isinstance(metric_name, str):
            continue
        value = _as_positive_float(review_facts.get(metric_name))
        if value is not None:
            metrics[metric_name] = value

    bbox_x = metrics.get("bbox_x_mm")
    bbox_y = metrics.get("bbox_y_mm")
    bbox_z = metrics.get("bbox_z_mm")
    if "bbox_volume_mm3" not in metrics and bbox_x and bbox_y and bbox_z:
        metrics["bbox_volume_mm3"] = bbox_x * bbox_y * bbox_z

    if "part_volume_mm3" not in metrics and "bbox_volume_mm3" in metrics:
        metrics["part_volume_mm3"] = metrics["bbox_volume_mm3"] * 0.32
        assumptions.append("Part volume inferred from bounding box volume.")

    if "surface_area_mm2" not in metrics and bbox_x and bbox_y and bbox_z:
        metrics["surface_area_mm2"] = 2.0 * (
            bbox_x * bbox_y + bbox_y * bbox_z + bbox_x * bbox_z
        ) * 0.78
        assumptions.append("Surface area inferred from bounding box dimensions.")

    if "body_count" not in metrics:
        body_count = _as_positive_float(review_facts.get("body_count"))
        if body_count is None:
            body_count = 1.0
            assumptions.append("Body count defaulted to 1.")
        metrics["body_count"] = body_count

    for key, fallback in DEFAULT_GEOMETRY_METRICS.items():
        if key not in metrics:
            metrics[key] = fallback
            used_default = True
            assumptions.append(f"Geometry metric '{key}' defaulted for quick should-cost.")

    component_triangle_count = _as_positive_float(component_context.get("triangle_count"))
    has_geometry_proxy = component_triangle_count is not None
    if component_triangle_count and used_default:
        metrics["part_volume_mm3"] = max(metrics["part_volume_mm3"], component_triangle_count * 320.0)
        assumptions.append("Triangle count used to improve defaulted volume estimate.")

    return {
        "metrics": metrics,
        "assumptions": assumptions,
        "used_default_geometry": used_default,
        "has_geometry_proxy": has_geometry_proxy,
    }


def _resolve_quantity(
    *,
    cost_model: dict[str, Any],
    review_facts: dict[str, Any],
    context_payload: dict[str, Any],
) -> float:
    quantity_default = _as_positive_float(
        cost_model.get("global_defaults", {}).get("quantity_default")
    ) or 1.0

    quantity = _as_positive_float(context_payload.get("quantity"))
    if quantity is None:
        quantity = _as_positive_float(review_facts.get("quantity"))
    if quantity is None:
        quantity = quantity_default
    return max(quantity, 1.0)


def _resolve_process_override(supplier_profile: dict[str, Any], process_id: str) -> dict[str, Any]:
    process_overrides = supplier_profile.get("process_overrides")
    if isinstance(process_overrides, dict):
        process_override = process_overrides.get(process_id)
        if isinstance(process_override, dict):
            return process_override
    return {}


def _has_supplier_rate_override(process_override: dict[str, Any]) -> bool:
    return _as_positive_float(process_override.get("hourly_rate")) is not None and _as_positive_float(
        process_override.get("setup_cost")
    ) is not None


def _resolve_material_inputs(
    *,
    global_defaults: dict[str, Any],
    review_facts: dict[str, Any],
    supplier_profile: dict[str, Any],
) -> dict[str, Any]:
    assumptions: list[str] = []
    density_map = global_defaults.get("material_density_kg_per_mm3_by_key", {})
    rate_map = global_defaults.get("material_rate_per_kg_by_key", {})
    density_map = density_map if isinstance(density_map, dict) else {}
    rate_map = rate_map if isinstance(rate_map, dict) else {}

    supplier_density_map = supplier_profile.get("material_density_kg_per_mm3_by_key")
    supplier_rate_map = supplier_profile.get("material_rate_per_kg_by_key")
    supplier_density_map = supplier_density_map if isinstance(supplier_density_map, dict) else {}
    supplier_rate_map = supplier_rate_map if isinstance(supplier_rate_map, dict) else {}

    material_key = _as_string(review_facts.get("material_key"))
    if not material_key:
        material_spec = _as_string(review_facts.get("material_spec")) or ""
        material_key = _guess_material_key(material_spec, density_map, rate_map)
        assumptions.append("Material key inferred from component material profile.")

    density = _as_positive_float(supplier_density_map.get(material_key))
    if density is None:
        density = _as_positive_float(density_map.get(material_key))
    missing_material_density = density is None
    if density is None:
        density = _average_numeric_values(density_map.values(), fallback=7.0e-06)
        assumptions.append("Material density missing; using average model density.")

    material_rate = _as_positive_float(supplier_rate_map.get(material_key))
    if material_rate is None:
        material_rate = _as_positive_float(rate_map.get(material_key))
    if material_rate is None:
        material_rate = _average_numeric_values(rate_map.values(), fallback=3.8)
        assumptions.append("Material rate missing; using average model material rate.")

    part_volume_mm3 = _as_positive_float(review_facts.get("part_volume_mm3"))
    if part_volume_mm3 is None:
        part_volume_mm3 = DEFAULT_GEOMETRY_METRICS["part_volume_mm3"]
    part_mass_kg = part_volume_mm3 * density

    return {
        "material_key": material_key,
        "density_kg_per_mm3": density,
        "material_rate_per_kg": material_rate,
        "part_mass_kg": part_mass_kg,
        "missing_material_density": missing_material_density,
        "assumptions": assumptions,
    }


def _guess_material_key(
    material_spec: str,
    density_map: dict[str, Any],
    rate_map: dict[str, Any],
) -> str:
    normalized = material_spec.strip().lower()
    if normalized:
        for token, key in MATERIAL_KEYWORDS.items():
            if token in normalized and (key in density_map or key in rate_map):
                return key
    if density_map:
        first_key = sorted(density_map.keys())[0]
        return first_key
    if rate_map:
        first_key = sorted(rate_map.keys())[0]
        return first_key
    return "material_unknown"


def _estimate_machine_hours(
    *,
    coefficients: dict[str, Any],
    review_facts: dict[str, Any],
    metrics: dict[str, float],
) -> tuple[float, bool]:
    coeffs = coefficients if isinstance(coefficients, dict) else {}
    base_hours = _as_non_negative_float(coeffs.get("base_machine_hours")) or 0.25
    machine_hours = base_hours
    feature_terms = 0
    matched_terms = 0

    feature_values = {
        "bbox_volume_factor": metrics.get("bbox_volume_mm3"),
        "surface_area_factor": metrics.get("surface_area_mm2"),
        "hole_count_factor": _feature_count(review_facts, "hole_count", "hole_features", "threaded_holes_count"),
        "pocket_count_factor": _feature_count(review_facts, "pocket_count", "pocket_features", "pockets_present"),
        "bend_count_factor": _feature_count(review_facts, "bend_count", "bend_features", "bends_present"),
        "weld_length_mm_factor": _as_non_negative_float(review_facts.get("weld_length_mm")),
        "body_count_factor": metrics.get("body_count"),
    }

    for coeff_name, coeff_value in coeffs.items():
        coeff_numeric = _as_non_negative_float(coeff_value)
        if coeff_numeric is None:
            continue
        if coeff_name == "base_machine_hours":
            continue
        feature_terms += 1
        feature_value = feature_values.get(coeff_name)
        if feature_value is None:
            continue
        matched_terms += 1
        machine_hours += coeff_numeric * feature_value

    missing_features = feature_terms > 0 and matched_terms == 0
    return max(machine_hours, 0.05), missing_features


def _feature_count(review_facts: dict[str, Any], numeric_key: str, list_key: str, fallback_key: str) -> float | None:
    numeric = _as_non_negative_float(review_facts.get(numeric_key))
    if numeric is not None:
        return numeric

    listed = review_facts.get(list_key)
    if isinstance(listed, list):
        return float(len(listed))

    fallback = review_facts.get(fallback_key)
    if isinstance(fallback, bool):
        return 1.0 if fallback else 0.0

    fallback_numeric = _as_non_negative_float(fallback)
    if fallback_numeric is not None:
        return fallback_numeric
    return None


def _estimate_purchased_mass_kg(
    *,
    process_model: dict[str, Any],
    part_mass_kg: float,
) -> float:
    utilization_model = process_model.get("material_utilization_model", {})
    if not isinstance(utilization_model, dict):
        return part_mass_kg

    model_type = _as_string(utilization_model.get("type")) or ""
    defaults = utilization_model.get("defaults", {})
    defaults = defaults if isinstance(defaults, dict) else {}

    if model_type == "stock_to_part_ratio":
        ratio = _as_positive_float(defaults.get("ratio")) or 1.5
        return part_mass_kg * ratio
    if model_type == "sheet_nesting_factor":
        utilization = _as_positive_float(defaults.get("utilization")) or 0.78
        return part_mass_kg / max(utilization, 0.05)
    if model_type == "cut_length_factor":
        utilization = _as_positive_float(defaults.get("utilization")) or 0.84
        return part_mass_kg / max(utilization, 0.05)

    return part_mass_kg


def _estimate_inspection_hours(findings_count: int, findings: list[dict[str, Any]]) -> float:
    critical_count = sum(
        1
        for finding in findings
        if _as_string(finding.get("severity")) == "critical"
    )
    return 0.08 + min(findings_count, 24) * 0.008 + critical_count * 0.02


def _apply_finding_impacts(
    *,
    findings: list[dict[str, Any]],
    finding_cost_impacts: list[Any],
) -> dict[str, Any]:
    fired_rule_ids = {
        _as_string(finding.get("rule_id"))
        for finding in findings
        if _as_string(finding.get("rule_id"))
    }

    multipliers = {
        "time": 1.0,
        "setup": 1.0,
        "material": 1.0,
        "scrap": 1.0,
        "inspection": 1.0,
    }
    cost_drivers: list[dict[str, Any]] = []

    impacts = finding_cost_impacts if isinstance(finding_cost_impacts, list) else []
    for impact in impacts:
        if not isinstance(impact, dict):
            continue
        rule_id = _as_string(impact.get("rule_id"))
        if not rule_id or rule_id not in fired_rule_ids:
            continue

        impact_type = _as_string(impact.get("impact_type"))
        if impact_type not in multipliers:
            continue

        percent_range = impact.get("delta_percent_range", {})
        percent_range = percent_range if isinstance(percent_range, dict) else {}
        min_pct = _as_non_negative_float(percent_range.get("min")) or 0.0
        max_pct = _as_non_negative_float(percent_range.get("max")) or 0.0
        mid_pct = ((min_pct + max_pct) / 2.0) / 100.0
        impact_weight = _as_non_negative_float(impact.get("impact_weight")) or 1.0
        delta = mid_pct * impact_weight
        multipliers[impact_type] += delta

        cost_drivers.append(
            {
                "rule_id": rule_id,
                "impact_type": impact_type,
                "delta_percent": round(delta * 100.0, 2),
                "notes": _as_string(impact.get("notes")),
            }
        )

    return {
        "time_multiplier": multipliers["time"],
        "setup_multiplier": multipliers["setup"],
        "material_multiplier": multipliers["material"],
        "scrap_multiplier": multipliers["scrap"],
        "inspection_multiplier": multipliers["inspection"],
        "cost_drivers": cost_drivers,
    }


def _default_cost_drivers(
    *,
    process_cost: float,
    material_cost: float,
    setup_cost_per_unit: float,
    inspection_cost: float,
) -> list[dict[str, Any]]:
    weighted = [
        ("process_time", process_cost),
        ("material_usage", material_cost),
        ("setup_allocation", setup_cost_per_unit),
        ("inspection_effort", inspection_cost),
    ]
    weighted = sorted(weighted, key=lambda item: item[1], reverse=True)
    drivers: list[dict[str, Any]] = []
    for name, value in weighted[:3]:
        drivers.append(
            {
                "driver": name,
                "estimated_cost": _round_amount(value),
            }
        )
    return drivers


def _estimate_confidence(
    *,
    cost_model: dict[str, Any],
    penalties: dict[str, Any],
    missing_supplier_rates: bool,
    missing_material_density: bool,
    used_default_geometry: bool,
    process_feature_missing: bool,
    route_ambiguity: bool,
) -> float:
    base_confidence = _as_non_negative_float(
        cost_model.get("confidence_policy", {}).get("base_confidence")
    )
    confidence = base_confidence if base_confidence is not None else 0.75

    if missing_material_density:
        confidence -= _as_non_negative_float(penalties.get("missing_material_density")) or 0.0
    if missing_supplier_rates:
        confidence -= _as_non_negative_float(penalties.get("missing_supplier_rates")) or 0.0
    if used_default_geometry:
        confidence -= _as_non_negative_float(penalties.get("non_solid_geometry")) or 0.0
    if route_ambiguity:
        confidence -= _as_non_negative_float(penalties.get("route_ambiguity")) or 0.0
    if process_feature_missing:
        confidence -= _as_non_negative_float(penalties.get("missing_process_features")) or 0.0

    return max(min(confidence, 0.99), 0.05)


def _confidence_level(*, confidence_value: float, bands: dict[str, Any]) -> str:
    high_gte = _as_non_negative_float(bands.get("high", {}).get("gte")) if isinstance(bands.get("high"), dict) else None
    medium_gte = _as_non_negative_float(bands.get("medium", {}).get("gte")) if isinstance(bands.get("medium"), dict) else None
    if high_gte is None:
        high_gte = 0.8
    if medium_gte is None:
        medium_gte = 0.65

    if confidence_value >= high_gte:
        return "high"
    if confidence_value >= medium_gte:
        return "medium"
    return "low"


def _range_fraction_from_confidence_level(confidence_level: str) -> float:
    if confidence_level == "high":
        return 0.12
    if confidence_level == "medium":
        return 0.22
    return 0.38


def _build_route_compare(route_estimates: list[dict[str, Any]]) -> dict[str, Any] | None:
    if len(route_estimates) < 2:
        return None
    baseline = route_estimates[0]
    compare = route_estimates[1]

    baseline_unit = _as_non_negative_float(baseline.get("unit_cost")) or 0.0
    compare_unit = _as_non_negative_float(compare.get("unit_cost")) or 0.0
    baseline_total = _as_non_negative_float(baseline.get("total_cost")) or 0.0
    compare_total = _as_non_negative_float(compare.get("total_cost")) or 0.0

    unit_delta = compare_unit - baseline_unit
    total_delta = compare_total - baseline_total
    unit_delta_pct = (unit_delta / baseline_unit * 100.0) if baseline_unit > 0 else 0.0
    total_delta_pct = (total_delta / baseline_total * 100.0) if baseline_total > 0 else 0.0

    cheaper_plan = baseline if baseline_unit <= compare_unit else compare
    return {
        "currency": _as_string(baseline.get("currency")) or _as_string(compare.get("currency")) or "USD",
        "baseline_plan_id": baseline.get("plan_id"),
        "compare_plan_id": compare.get("plan_id"),
        "baseline_process_id": baseline.get("process_id"),
        "compare_process_id": compare.get("process_id"),
        "baseline_unit_cost": _round_amount(baseline_unit),
        "compare_unit_cost": _round_amount(compare_unit),
        "unit_cost_delta": _round_amount(unit_delta),
        "unit_cost_delta_percent": round(unit_delta_pct, 4),
        "baseline_total_cost": _round_amount(baseline_total),
        "compare_total_cost": _round_amount(compare_total),
        "total_cost_delta": _round_amount(total_delta),
        "total_cost_delta_percent": round(total_delta_pct, 4),
        "cheaper_plan_id": cheaper_plan.get("plan_id"),
        "cheaper_process_id": cheaper_plan.get("process_id"),
    }


def _average_numeric_values(values: Any, fallback: float) -> float:
    nums = [_as_positive_float(value) for value in values]
    nums = [value for value in nums if value is not None]
    if not nums:
        return fallback
    return sum(nums) / len(nums)


def _first_positive(*values: Any, default: float) -> float:
    for value in values:
        parsed = _as_positive_float(value)
        if parsed is not None:
            return parsed
    return default


def _first_non_negative(*values: Any, default: float) -> float:
    for value in values:
        parsed = _as_non_negative_float(value)
        if parsed is not None:
            return parsed
    return default


def _as_string(value: Any) -> str | None:
    if isinstance(value, str):
        stripped = value.strip()
        if stripped:
            return stripped
    return None


def _as_non_negative_float(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        value_f = float(value)
        if value_f >= 0:
            return value_f
    return None


def _as_positive_float(value: Any) -> float | None:
    parsed = _as_non_negative_float(value)
    if parsed is None:
        return None
    if parsed <= 0:
        return None
    return parsed


def _round_amount(value: float) -> float:
    return round(float(value), 4)
