from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .dfm_bundle import DfmBundle
from .dfm_costing import estimate_review_costs
from .dfm_part_facts_bridge import NOT_APPLICABLE_INPUTS_KEY
from .dfm_planning import DfmPlanningError, plan_dfm_execution


BASE_DRAWING_PACK_ID = "A_DRAWING"
OVERLAY_PACK_ID = "F_OVERLAY"
ANALYSIS_MODES = {"geometry_dfm", "drawing_spec", "full"}
DEFAULT_ANALYSIS_MODE = "full"
DOC_INPUT_PREFIXES = ("drawing_",)
DOC_INPUT_KEYS = {
    "manual_context",
    "bom_items",
    "datum_scheme",
    "surface_finish_spec",
    "thread_callouts",
    "weld_data",
    "weld_notes",
    "weld_symbols",
    "control_plan",
    "risk_file",
    "inspection_plan",
    "hazard_analysis",
    "nameplate_parameters",
    "coating_spec",
}
MANUAL_STANDARDS_KEYS = {
    "standards_used_auto",
    "standards_used",
    "standards",
    "manual_standards",
    "manual_standards_refs",
}


class DfmReviewV2Error(ValueError):
    pass


class DfmReviewV2PlanningInputs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    extracted_part_facts: dict[str, object] = Field(default_factory=dict)
    analysis_mode: Literal["geometry_dfm", "drawing_spec", "full"] = "full"
    selected_process_override: str | None = None
    selected_overlay: str | None = None
    process_selection_mode: Literal["auto", "profile", "override"] | None = None
    overlay_selection_mode: Literal["none", "profile", "override"] | None = None
    selected_role: str
    selected_template: str
    run_both_if_mismatch: bool = True


class DfmReviewV2ExecutionPlanInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan_id: str | None = None
    route_source: str | None = None
    process_id: str
    process_label: str | None = None
    pack_ids: list[str]
    pack_labels: list[str | None] | None = None
    overlay_id: str | None = None
    overlay_label: str | None = None
    role_id: str
    role_label: str | None = None
    template_id: str
    template_label: str | None = None
    template_sections: list[str] | None = None
    suppressed_template_sections: list[str] | None = None
    standards_used_mode: str | None = None


class DfmReviewV2Body(BaseModel):
    model_config = ConfigDict(extra="forbid")

    component_node_name: str | None = None
    planning_inputs: DfmReviewV2PlanningInputs | None = None
    execution_plans: list[DfmReviewV2ExecutionPlanInput] | None = None
    selected_execution_plan_id: str | None = None
    context_payload: dict[str, object] = Field(default_factory=dict)


def generate_dfm_review_v2(
    bundle: DfmBundle,
    *,
    model_id: str,
    component_context: dict[str, Any],
    planning_inputs: dict[str, Any] | None = None,
    execution_plans: list[dict[str, Any]] | None = None,
    selected_execution_plan_id: str | None = None,
    context_payload: dict[str, Any] | None = None,
    effective_context: dict[str, Any] | None = None,
    cost_enabled: bool = True,
) -> dict[str, Any]:
    context_payload = dict(context_payload or {})
    _assert_no_manual_standards_injection(context_payload)

    plan_payload = _resolve_plan_payload(
        bundle=bundle,
        planning_inputs=planning_inputs,
        execution_plans=execution_plans,
    )
    plans = plan_payload["execution_plans"]

    if selected_execution_plan_id:
        plans = [plan for plan in plans if plan.get("plan_id") == selected_execution_plan_id]
        if not plans:
            raise DfmReviewV2Error(
                f"selected_execution_plan_id '{selected_execution_plan_id}' not found."
            )

    resolved_plans = [_normalize_execution_plan(bundle, plan) for plan in plans]
    analysis_mode = _resolve_analysis_mode(planning_inputs, context_payload)
    review_facts = _build_review_facts(
        planning_inputs=planning_inputs or {},
        context_payload=context_payload,
        component_context=component_context,
    )

    if effective_context is None:
        effective_context = {}
    if isinstance(effective_context, dict):
        effective_context.setdefault(
            "analysis_mode",
            {
                "selected_mode": analysis_mode,
                "source": "planning_inputs" if planning_inputs else "execution_plans_default",
            },
        )

    route_outputs = [
        _evaluate_plan(
            bundle=bundle,
            execution_plan=plan,
            review_facts=review_facts,
            mismatch=plan_payload.get("mismatch"),
            analysis_mode=analysis_mode,
        )
        for plan in resolved_plans
    ]

    all_standards = _dedupe_standards(
        standards_lists=[route["standards_used_auto"] for route in route_outputs]
    )
    standards_trace_union = _merge_standards_trace(
        standards_trace_lists=[route.get("standards_trace", []) for route in route_outputs]
    )
    total_findings = sum(route["finding_count"] for route in route_outputs)
    ai_recommendation = plan_payload.get("ai_recommendation")
    mismatch = plan_payload.get("mismatch", {})
    cost_outputs = {
        "cost_estimate": None,
        "cost_estimate_by_route": [],
        "cost_compare_routes": None,
    }
    if cost_enabled:
        cost_outputs = estimate_review_costs(
            bundle=bundle,
            route_outputs=route_outputs,
            review_facts=review_facts,
            component_context=component_context,
            mismatch=mismatch,
            context_payload=context_payload,
        )

    return {
        "model_id": model_id,
        "component_context": component_context,
        "effective_context": effective_context,
        "ai_recommendation": ai_recommendation,
        "mismatch": mismatch,
        "route_count": len(route_outputs),
        "finding_count_total": total_findings,
        "standards_used_auto_union": all_standards,
        "standards_trace_union": standards_trace_union,
        "cost_estimate": cost_outputs["cost_estimate"],
        "cost_estimate_by_route": cost_outputs["cost_estimate_by_route"],
        "cost_compare_routes": cost_outputs["cost_compare_routes"],
        "routes": route_outputs,
    }


def _resolve_plan_payload(
    *,
    bundle: DfmBundle,
    planning_inputs: dict[str, Any] | None,
    execution_plans: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    if planning_inputs and execution_plans:
        raise DfmReviewV2Error(
            "Provide either planning_inputs or execution_plans, not both."
        )
    if not planning_inputs and not execution_plans:
        raise DfmReviewV2Error(
            "One of planning_inputs or execution_plans is required for review-v2."
        )

    if planning_inputs:
        planner_inputs = _planner_inputs(planning_inputs)
        try:
            plan_payload = plan_dfm_execution(bundle, **planner_inputs)
        except DfmPlanningError as exc:
            raise DfmReviewV2Error(str(exc)) from exc
        return plan_payload

    return {
        "ai_recommendation": None,
        "mismatch": {
            "has_mismatch": len(execution_plans or []) > 1,
            "run_both_requested": False,
            "policy_allows_run_both": False,
            "run_both_executed": len(execution_plans or []) > 1,
            "banner": None,
        },
        "execution_plans": execution_plans or [],
    }


def _planner_inputs(planning_inputs: dict[str, Any]) -> dict[str, Any]:
    allowed_keys = {
        "extracted_part_facts",
        "analysis_mode",
        "selected_process_override",
        "selected_overlay",
        "selected_role",
        "selected_template",
        "run_both_if_mismatch",
    }
    return {
        key: value
        for key, value in planning_inputs.items()
        if key in allowed_keys
    }


def _resolve_analysis_mode(
    planning_inputs: dict[str, Any] | None,
    context_payload: dict[str, Any] | None,
) -> str:
    candidate = ""
    if isinstance(planning_inputs, dict):
        candidate = _clean_optional_string(planning_inputs.get("analysis_mode")).lower()
    if not candidate and isinstance(context_payload, dict):
        candidate = _clean_optional_string(context_payload.get("analysis_mode")).lower()
    if candidate in ANALYSIS_MODES:
        return candidate
    return DEFAULT_ANALYSIS_MODE


def _normalize_execution_plan(bundle: DfmBundle, raw_plan: dict[str, Any]) -> dict[str, Any]:
    process_map = _index_by_id(bundle.process_classifier.get("process_families", []), "process_id")
    overlay_map = _index_by_id(bundle.overlays.get("overlays", []), "overlay_id")
    role_map = _index_by_id(bundle.roles.get("roles", []), "role_id")
    template_map = _index_by_id(bundle.report_templates.get("templates", []), "template_id")
    pack_map = _index_by_id(bundle.rule_library.get("packs", []), "pack_id")

    process_id = raw_plan.get("process_id")
    role_id = raw_plan.get("role_id")
    template_id = raw_plan.get("template_id")
    overlay_id = raw_plan.get("overlay_id")
    pack_ids = raw_plan.get("pack_ids", [])
    template_sections_provided = isinstance(raw_plan.get("template_sections"), list)

    if process_id not in process_map:
        raise DfmReviewV2Error(f"Execution plan has unknown process_id '{process_id}'.")
    if role_id not in role_map:
        raise DfmReviewV2Error(f"Execution plan has unknown role_id '{role_id}'.")
    if template_id not in template_map and not template_sections_provided:
        raise DfmReviewV2Error(f"Execution plan has unknown template_id '{template_id}'.")
    if overlay_id and overlay_id not in overlay_map:
        raise DfmReviewV2Error(f"Execution plan has unknown overlay_id '{overlay_id}'.")
    if not isinstance(pack_ids, list) or not pack_ids:
        raise DfmReviewV2Error("Execution plan pack_ids must be a non-empty array.")

    normalized_pack_ids: list[str] = []
    for pack_id in pack_ids:
        if not isinstance(pack_id, str) or not pack_id:
            raise DfmReviewV2Error("Execution plan pack_ids must contain non-empty strings.")
        if pack_id not in pack_map:
            raise DfmReviewV2Error(f"Execution plan uses unknown pack_id '{pack_id}'.")
        if pack_id not in normalized_pack_ids:
            normalized_pack_ids.append(pack_id)

    if BASE_DRAWING_PACK_ID not in normalized_pack_ids:
        normalized_pack_ids.insert(0, BASE_DRAWING_PACK_ID)

    if not template_sections_provided:
        template_sections = _resolve_template_sections(
            template=template_map[template_id],
            selected_overlay=overlay_id,
        )
    else:
        template_sections = {
            "enabled": list(raw_plan.get("template_sections") or []),
            "suppressed": list(raw_plan.get("suppressed_template_sections") or []),
        }

    template_label = raw_plan.get("template_label")
    if not isinstance(template_label, str) or not template_label.strip():
        if template_id in template_map:
            template_label = template_map[template_id].get("label")
        elif isinstance(template_id, str) and template_id:
            template_label = template_id
        else:
            template_label = "Custom Template"

    return {
        "plan_id": raw_plan.get("plan_id") or "plan_1",
        "route_source": raw_plan.get("route_source") or "selected",
        "process_id": process_id,
        "process_label": raw_plan.get("process_label") or process_map[process_id].get("label"),
        "pack_ids": normalized_pack_ids,
        "pack_labels": [_label_for_pack(pack_map, pack_id) for pack_id in normalized_pack_ids],
        "overlay_id": overlay_id,
        "overlay_label": raw_plan.get("overlay_label")
        or (overlay_map[overlay_id].get("label") if overlay_id else None),
        "role_id": role_id,
        "role_label": raw_plan.get("role_label") or role_map[role_id].get("label"),
        "template_id": template_id,
        "template_label": template_label,
        "template_sections": template_sections["enabled"],
        "suppressed_template_sections": template_sections["suppressed"],
    }


def _build_review_facts(
    *,
    planning_inputs: dict[str, Any],
    context_payload: dict[str, Any],
    component_context: dict[str, Any],
) -> dict[str, Any]:
    facts: dict[str, Any] = {}

    extracted = planning_inputs.get("extracted_part_facts")
    if isinstance(extracted, dict):
        facts.update(extracted)

    facts.update(context_payload)
    if _truthy(context_payload.get("manual_context")):
        facts["manual_context"] = True

    profile = component_context.get("profile")
    if isinstance(profile, dict):
        if profile.get("material"):
            facts.setdefault("material_spec", profile.get("material"))
        if profile.get("manufacturingProcess"):
            facts.setdefault("manufacturing_process", profile.get("manufacturingProcess"))
        if profile.get("industry"):
            facts.setdefault("industry", profile.get("industry"))

    return facts


def _evaluate_plan(
    *,
    bundle: DfmBundle,
    execution_plan: dict[str, Any],
    review_facts: dict[str, Any],
    mismatch: dict[str, Any] | None,
    analysis_mode: str,
) -> dict[str, Any]:
    pack_ids = execution_plan["pack_ids"]
    overlay_id = execution_plan.get("overlay_id")
    not_applicable_inputs = _not_applicable_inputs(review_facts)
    pack_map = _index_by_id(bundle.rule_library.get("packs", []), "pack_id")
    standards_trace = _init_standards_trace(bundle=bundle, overlay_id=overlay_id)

    findings: list[dict[str, Any]] = []
    evaluated_pack_ids: list[str] = []
    for rule in _iter_rules_for_plan(
        bundle,
        pack_ids,
        overlay_id,
        analysis_mode=analysis_mode,
    ):
        pack_id = _clean_optional_string(rule.get("pack_id"))
        if pack_id and pack_id not in evaluated_pack_ids:
            evaluated_pack_ids.append(pack_id)
        refs = [ref for ref in rule.get("refs", []) if isinstance(ref, str) and ref]
        required_inputs = rule.get("inputs_required", [])
        if not isinstance(required_inputs, list):
            required_inputs = []
        missing_inputs = _missing_required_inputs(
            rule,
            review_facts,
            not_applicable_inputs=not_applicable_inputs,
        )
        if not missing_inputs:
            violation = _evaluate_rule_violation(rule, review_facts)
            if not violation:
                _update_standards_trace(
                    standards_trace=standards_trace,
                    bundle=bundle,
                    refs=refs,
                    outcome="unresolved",
                )
                continue
            if not violation.get("violated"):
                _update_standards_trace(
                    standards_trace=standards_trace,
                    bundle=bundle,
                    refs=refs,
                    outcome="passed",
                )
                continue
            _update_standards_trace(
                standards_trace=standards_trace,
                bundle=bundle,
                refs=refs,
                outcome="rule_violation",
            )
            guidance = _build_finding_guidance(
                rule=rule,
                finding_type="rule_violation",
                missing_inputs=[],
                evaluation=violation.get("evaluation"),
            )
            trace_fields = _rule_trace_fields(rule)
            finding = {
                "rule_id": rule.get("rule_id"),
                "pack_id": rule.get("pack_id"),
                "finding_type": "rule_violation",
                "severity": rule.get("severity"),
                "title": rule.get("title"),
                "description": rule.get("description"),
                "refs": refs,
                **trace_fields,
                "recommended_action": guidance["recommended_action"],
                "expected_impact": guidance["expected_impact"],
                "evidence": {
                    "provided_inputs": required_inputs,
                    "evaluation": violation.get("evaluation", {}),
                },
            }
            findings.append(finding)
            continue
        _update_standards_trace(
            standards_trace=standards_trace,
            bundle=bundle,
            refs=refs,
            outcome="evidence_gap",
        )
        guidance = _build_finding_guidance(
            rule=rule,
            finding_type="evidence_gap",
            missing_inputs=missing_inputs,
            evaluation=None,
        )
        trace_fields = _rule_trace_fields(rule)
        finding = {
            "rule_id": rule.get("rule_id"),
            "pack_id": rule.get("pack_id"),
            "finding_type": "evidence_gap",
            "severity": rule.get("severity"),
            "title": rule.get("title"),
            "description": rule.get("description"),
            "refs": refs,
            **trace_fields,
            "recommended_action": guidance["recommended_action"],
            "expected_impact": guidance["expected_impact"],
            "evidence": {
                "missing_inputs": missing_inputs,
                "not_applicable_inputs": [key for key in required_inputs if key in not_applicable_inputs],
                "provided_inputs": [
                    key
                    for key in required_inputs
                    if key not in missing_inputs and key not in not_applicable_inputs
                ],
            },
        }
        findings.append(finding)

    standards = _derive_standards_used_auto(bundle, findings)
    standards_trace_payload = _standards_trace_payload(standards_trace)
    role_map = _index_by_id(bundle.roles.get("roles", []), "role_id")
    role = role_map.get(execution_plan["role_id"], {})

    return {
        "plan_id": execution_plan.get("plan_id"),
        "route_source": execution_plan.get("route_source"),
        "process_id": execution_plan.get("process_id"),
        "process_label": execution_plan.get("process_label"),
        "pack_ids": evaluated_pack_ids,
        "pack_labels": [_label_for_pack(pack_map, pack_id) for pack_id in evaluated_pack_ids],
        "overlay_id": execution_plan.get("overlay_id"),
        "overlay_label": execution_plan.get("overlay_label"),
        "role_id": execution_plan.get("role_id"),
        "role_label": execution_plan.get("role_label"),
        "template_id": execution_plan.get("template_id"),
        "template_label": execution_plan.get("template_label"),
        "analysis_mode": analysis_mode,
        "finding_count": len(findings),
        "findings": findings,
        "standards_used_auto": standards,
        "standards_trace": standards_trace_payload,
        "report_skeleton": {
            "template_sections": execution_plan.get("template_sections", []),
            "suppressed_template_sections": execution_plan.get(
                "suppressed_template_sections", []
            ),
            "role_formatting": {
                "wording_style": role.get("wording_style"),
                "default_issue_sort": role.get("default_issue_sort"),
            },
            "mismatch_context": {
                "has_mismatch": bool((mismatch or {}).get("has_mismatch")),
                "route_source": execution_plan.get("route_source"),
                "banner": (mismatch or {}).get("banner"),
            },
        },
    }


def _iter_rules_for_plan(
    bundle: DfmBundle,
    pack_ids: list[str],
    overlay_id: str | None,
    *,
    analysis_mode: str = DEFAULT_ANALYSIS_MODE,
):
    rules = bundle.rule_library.get("rules", [])
    overlay_map = _index_by_id(bundle.overlays.get("overlays", []), "overlay_id")
    overlay_prefixes: list[str] = []
    if overlay_id:
        overlay = overlay_map.get(overlay_id, {})
        overlay_prefixes = [
            prefix
            for prefix in overlay.get("rule_prefixes", [])
            if isinstance(prefix, str) and prefix
        ]

    rules_by_pack: dict[str, list[dict[str, Any]]] = {}
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        pack_id = rule.get("pack_id")
        if not isinstance(pack_id, str):
            continue
        rules_by_pack.setdefault(pack_id, []).append(rule)

    for pack_id in pack_ids:
        if analysis_mode == "geometry_dfm" and pack_id == BASE_DRAWING_PACK_ID:
            continue
        for rule in rules_by_pack.get(pack_id, []):
            if pack_id == OVERLAY_PACK_ID and overlay_prefixes:
                rule_id = rule.get("rule_id")
                if not isinstance(rule_id, str):
                    continue
                if not any(rule_id.startswith(prefix) for prefix in overlay_prefixes):
                    continue
            if not _rule_is_included_for_analysis_mode(rule, analysis_mode):
                continue
            yield rule


def _missing_required_inputs(
    rule: dict[str, Any],
    review_facts: dict[str, Any],
    *,
    not_applicable_inputs: set[str] | None = None,
) -> list[str]:
    required = rule.get("inputs_required", [])
    if not isinstance(required, list):
        return []
    if not_applicable_inputs is None:
        not_applicable_inputs = _not_applicable_inputs(review_facts)
    missing: list[str] = []
    for key in required:
        if not isinstance(key, str) or not key:
            continue
        if key in not_applicable_inputs:
            continue
        if not _truthy(review_facts.get(key)):
            missing.append(key)
    return missing


def _rule_is_included_for_analysis_mode(rule: dict[str, Any], analysis_mode: str) -> bool:
    if analysis_mode not in ANALYSIS_MODES or analysis_mode == "full":
        return True
    required = rule.get("inputs_required", [])
    if not isinstance(required, list):
        required = []
    doc_required = [
        key
        for key in required
        if isinstance(key, str) and key and _is_doc_input_key(key)
    ]
    if analysis_mode == "geometry_dfm":
        return not doc_required
    if analysis_mode == "drawing_spec":
        return bool(doc_required)
    return True


def _is_doc_input_key(key: str) -> bool:
    normalized = key.strip().lower()
    if not normalized:
        return False
    if normalized.startswith(DOC_INPUT_PREFIXES):
        return True
    return normalized in DOC_INPUT_KEYS


def _not_applicable_inputs(review_facts: dict[str, Any]) -> set[str]:
    payload = review_facts.get(NOT_APPLICABLE_INPUTS_KEY)
    if not isinstance(payload, list):
        return set()
    return {
        key.strip()
        for key in payload
        if isinstance(key, str) and key.strip()
    }


def _truthy(value: Any) -> bool:
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


def _build_finding_guidance(
    *,
    rule: dict[str, Any],
    finding_type: str,
    missing_inputs: list[str],
    evaluation: dict[str, Any] | None,
) -> dict[str, Any]:
    severity = _clean_optional_string(rule.get("severity")).lower()
    risk_reduction = _impact_level_for_severity(severity)
    fix_template = _sentence_or_empty(rule.get("fix_template"))

    if finding_type == "rule_violation":
        recommended_action = (
            fix_template
            or "Update geometry/specification to satisfy the manufacturing rule intent."
        )
        rule_expression = ""
        if isinstance(evaluation, dict):
            rule_expression = _clean_optional_string(evaluation.get("rule_expression"))
        if rule_expression:
            recommended_action = (
                f"{recommended_action} Target: {rule_expression}."
            )
        expected_impact = {
            "impact_type": "design_risk_reduction",
            "risk_reduction": risk_reduction,
            "cost_impact": "medium" if severity in {"critical", "major"} else "low",
            "lead_time_impact": "medium" if severity == "critical" else "low",
            "rationale": "Resolving violated checks reduces scrap/rework and stabilizes process capability.",
        }
        return {
            "recommended_action": recommended_action,
            "expected_impact": expected_impact,
        }

    missing_label = ", ".join(missing_inputs[:4]) if missing_inputs else "required rule inputs"
    recommended_action = (
        f"Provide evidence for: {missing_label}."
    )
    if fix_template:
        recommended_action = (
            f"{recommended_action} Then apply: {fix_template}"
        )
    expected_impact = {
        "impact_type": "evidence_readiness",
        "risk_reduction": risk_reduction,
        "cost_impact": "low",
        "lead_time_impact": "low",
        "rationale": "Closing evidence gaps enables deterministic checks and more reliable risk ranking.",
    }
    return {
        "recommended_action": recommended_action,
        "expected_impact": expected_impact,
    }


def _impact_level_for_severity(severity: str) -> str:
    if severity == "critical":
        return "high"
    if severity == "major":
        return "medium"
    return "low"


def _sentence_or_empty(value: Any) -> str:
    text = _clean_optional_string(value)
    if not text:
        return ""
    if text.endswith((".", "!", "?")):
        return text
    return f"{text}."


def _clean_optional_string(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip()


def _rule_trace_fields(rule: dict[str, Any]) -> dict[str, str]:
    thresholds = rule.get("thresholds")
    if not isinstance(thresholds, dict):
        return {}
    fields: dict[str, str] = {}
    standard_clause = _clean_optional_string(thresholds.get("source_standard_clause"))
    source_rule_id = _clean_optional_string(thresholds.get("source_rule_id"))
    evidence_quality = _clean_optional_string(thresholds.get("source_evidence_quality"))
    if standard_clause:
        fields["standard_clause"] = standard_clause
    if source_rule_id:
        fields["source_rule_id"] = source_rule_id
    if evidence_quality:
        fields["evidence_quality"] = evidence_quality
    return fields


def _evaluate_rule_violation(
    rule: dict[str, Any],
    review_facts: dict[str, Any],
) -> dict[str, Any] | None:
    rule_id = rule.get("rule_id")
    if not isinstance(rule_id, str) or not rule_id:
        return None

    evaluator = RULE_VIOLATION_EVALUATORS.get(rule_id)
    if evaluator is None:
        return None
    return evaluator(review_facts)


def _evaluate_cnc_001(review_facts: dict[str, Any]) -> dict[str, Any] | None:
    wall_thickness = _numeric_fact(
        review_facts,
        "min_wall_thickness",
        "min_wall_thickness_mm",
    )
    if wall_thickness is None:
        return None

    material_spec = _string_fact(review_facts.get("material_spec"))
    threshold, material_class = _wall_threshold_for_material(material_spec)
    violated = wall_thickness < threshold
    return {
        "violated": violated,
        "evaluation": {
            "operator": ">=",
            "fact_key": "min_wall_thickness",
            "units": "mm",
            "actual": round(wall_thickness, 4),
            "threshold": round(threshold, 4),
            "material_class": material_class,
            "rule_expression": "min_wall_thickness >= material_threshold_mm",
        },
    }


def _evaluate_cnc_002(review_facts: dict[str, Any]) -> dict[str, Any] | None:
    hole_depth = _numeric_fact(
        review_facts,
        "hole_depth_mm",
        "hole_depth",
    )
    hole_diameter = _numeric_fact(
        review_facts,
        "hole_diameter_mm",
        "hole_diameter",
        "min_hole_diameter_mm",
    )
    if hole_depth is None or hole_diameter is None or hole_diameter <= 0:
        return None

    depth_ratio = hole_depth / hole_diameter
    recommended_max = 4.0
    hard_max = 10.0
    violated = depth_ratio > hard_max
    return {
        "violated": violated,
        "evaluation": {
            "operator": "<=",
            "fact_key": "hole_depth_to_diameter_ratio",
            "actual": round(depth_ratio, 4),
            "threshold": hard_max,
            "recommended_threshold": recommended_max,
            "rule_expression": "(hole_depth / hole_diameter) <= 10.0",
        },
    }


def _evaluate_cnc_005(review_facts: dict[str, Any]) -> dict[str, Any] | None:
    pocket_depth = _numeric_fact(
        review_facts,
        "max_pocket_depth_mm",
        "pocket_depth",
    )
    corner_radius = _numeric_fact(
        review_facts,
        "min_internal_radius_mm",
        "pocket_corner_radius",
    )
    if pocket_depth is None or corner_radius is None:
        return None
    if corner_radius <= 0:
        return {
            "violated": True,
            "evaluation": {
                "operator": ">",
                "fact_key": "corner_radius_mm",
                "actual": round(corner_radius, 4),
                "threshold": 0.0,
                "rule_expression": "corner_radius_mm > 0.0",
            },
        }

    ratio = pocket_depth / corner_radius
    threshold = 8.0
    violated = ratio > threshold
    return {
        "violated": violated,
        "evaluation": {
            "operator": "<=",
            "fact_key": "pocket_depth_to_corner_radius_ratio",
            "actual": round(ratio, 4),
            "threshold": threshold,
            "rule_expression": "(pocket_depth_mm / corner_radius_mm) <= 8.0",
        },
    }


def _evaluate_cnc_024(review_facts: dict[str, Any]) -> dict[str, Any] | None:
    pocket_depth = _numeric_fact(
        review_facts,
        "max_pocket_depth_mm",
        "pocket_depth",
    )
    corner_radius = _numeric_fact(
        review_facts,
        "min_internal_radius_mm",
        "pocket_corner_radius",
    )
    if pocket_depth is None or corner_radius is None:
        return None
    if corner_radius <= 0:
        return {
            "violated": True,
            "evaluation": {
                "operator": "and",
                "fact_keys": ["max_pocket_depth_mm", "min_internal_radius_mm"],
                "actual": {
                    "pocket_depth_mm": round(pocket_depth, 4),
                    "corner_radius_mm": round(corner_radius, 4),
                    "depth_to_radius_ratio": float("inf"),
                },
                "thresholds": {
                    "min_depth_mm": 12.0,
                    "max_depth_to_radius_ratio": 10.0,
                },
                "rule_expression": "corner_radius_mm > 0 and depth_to_radius_ratio <= 10.0",
            },
        }

    depth_threshold = 12.0
    ratio_threshold = 10.0
    ratio = pocket_depth / corner_radius
    violated = pocket_depth > depth_threshold and ratio > ratio_threshold
    return {
        "violated": violated,
        "evaluation": {
            "operator": "and",
            "fact_keys": ["max_pocket_depth_mm", "min_internal_radius_mm"],
            "actual": {
                "pocket_depth_mm": round(pocket_depth, 4),
                "corner_radius_mm": round(corner_radius, 4),
                "depth_to_radius_ratio": round(ratio, 4),
            },
            "thresholds": {
                "min_depth_mm": depth_threshold,
                "max_depth_to_radius_ratio": ratio_threshold,
            },
            "rule_expression": "pocket_depth_mm > 12.0 and (pocket_depth_mm / corner_radius_mm) > 10.0",
        },
    }


def _evaluate_cnc_025(review_facts: dict[str, Any]) -> dict[str, Any] | None:
    x = _numeric_fact(review_facts, "bbox_x_mm")
    y = _numeric_fact(review_facts, "bbox_y_mm")
    z = _numeric_fact(review_facts, "bbox_z_mm")
    if x is None or y is None or z is None:
        return None

    limits = {"bbox_x_mm": 1000.0, "bbox_y_mm": 700.0, "bbox_z_mm": 500.0}
    actual = {"bbox_x_mm": round(x, 4), "bbox_y_mm": round(y, 4), "bbox_z_mm": round(z, 4)}
    exceeded = [
        key for key, limit in limits.items() if actual.get(key, 0.0) > limit
    ]
    violated = bool(exceeded)
    return {
        "violated": violated,
        "evaluation": {
            "operator": "<=",
            "fact_keys": list(actual.keys()),
            "actual": actual,
            "thresholds": limits,
            "exceeded_axes": exceeded,
            "rule_expression": "bbox_x<=1000 && bbox_y<=700 && bbox_z<=500",
        },
    }


def _evaluate_cnc_003(review_facts: dict[str, Any]) -> dict[str, Any] | None:
    hole_diameter = _numeric_fact(
        review_facts,
        "hole_diameter_mm",
        "hole_diameter",
        "min_hole_diameter_mm",
    )
    if hole_diameter is None or hole_diameter <= 0:
        return None

    standard_diameters_mm = [
        1.0,
        1.5,
        2.0,
        2.5,
        3.0,
        3.5,
        4.0,
        4.2,
        4.5,
        5.0,
        5.5,
        6.0,
        6.8,
        8.0,
        8.5,
        10.0,
        12.0,
        14.0,
        16.0,
        18.0,
        20.0,
    ]
    nearest = min(standard_diameters_mm, key=lambda value: abs(value - hole_diameter))
    tolerance = 0.15
    violated = abs(nearest - hole_diameter) > tolerance
    return {
        "violated": violated,
        "evaluation": {
            "operator": "<=",
            "fact_key": "hole_diameter_mm",
            "actual": round(hole_diameter, 4),
            "nearest_standard_mm": nearest,
            "tolerance_mm": tolerance,
            "rule_expression": "abs(hole_diameter_mm - nearest_standard_mm) <= 0.15",
        },
    }


def _evaluate_cnc_006(review_facts: dict[str, Any]) -> dict[str, Any] | None:
    pocket_depth = _numeric_fact(
        review_facts,
        "max_pocket_depth_mm",
        "pocket_depth",
    )
    min_radius = _numeric_fact(
        review_facts,
        "min_internal_radius_mm",
        "pocket_corner_radius",
    )
    if pocket_depth is None or min_radius is None:
        return None
    if min_radius <= 0:
        return {
            "violated": True,
            "evaluation": {
                "operator": ">",
                "fact_key": "min_internal_radius_mm",
                "actual": round(min_radius, 4),
                "threshold": 0.0,
                "rule_expression": "min_internal_radius_mm > 0",
            },
        }

    depth_to_radius = pocket_depth / min_radius
    radius_floor = 3.0
    ratio_threshold = 6.0
    violated = (min_radius < radius_floor) and (depth_to_radius > ratio_threshold)
    return {
        "violated": violated,
        "evaluation": {
            "operator": "and",
            "fact_keys": ["min_internal_radius_mm", "max_pocket_depth_mm"],
            "actual": {
                "min_internal_radius_mm": round(min_radius, 4),
                "max_pocket_depth_mm": round(pocket_depth, 4),
                "depth_to_radius_ratio": round(depth_to_radius, 4),
            },
            "thresholds": {
                "min_radius_mm": radius_floor,
                "max_depth_to_radius_ratio": ratio_threshold,
            },
            "rule_expression": "min_radius_mm >= 3.0 or (depth/radius) <= 6.0",
        },
    }


def _evaluate_cnc_010(review_facts: dict[str, Any]) -> dict[str, Any] | None:
    unique_radius_count = _numeric_fact(
        review_facts,
        "unique_internal_radius_count",
    )
    radius_variation_ratio = _numeric_fact(
        review_facts,
        "radius_variation_ratio",
    )
    if unique_radius_count is None and radius_variation_ratio is None:
        return None

    unique_threshold = 4.0
    ratio_threshold = 3.0
    violated = False
    if unique_radius_count is not None and unique_radius_count > unique_threshold:
        violated = True
    if radius_variation_ratio is not None and radius_variation_ratio > ratio_threshold:
        violated = True

    return {
        "violated": violated,
        "evaluation": {
            "operator": "or",
            "fact_keys": ["unique_internal_radius_count", "radius_variation_ratio"],
            "actual": {
                "unique_internal_radius_count": None if unique_radius_count is None else round(unique_radius_count, 4),
                "radius_variation_ratio": None if radius_variation_ratio is None else round(radius_variation_ratio, 4),
            },
            "thresholds": {
                "max_unique_internal_radius_count": unique_threshold,
                "max_radius_variation_ratio": ratio_threshold,
            },
            "rule_expression": "unique_radius_count <= 4 and radius_variation_ratio <= 3.0",
        },
    }


def _evaluate_cnc_013(review_facts: dict[str, Any]) -> dict[str, Any] | None:
    long_reach_risk_count = _numeric_fact(
        review_facts,
        "long_reach_tool_risk_count",
    )
    depth_to_radius_ratio = _numeric_fact(
        review_facts,
        "max_depth_to_radius_ratio",
    )
    if long_reach_risk_count is None and depth_to_radius_ratio is None:
        return None

    count_threshold = 0.0
    ratio_threshold = 8.0
    violated = False
    if long_reach_risk_count is not None and long_reach_risk_count > count_threshold:
        violated = True
    if depth_to_radius_ratio is not None and depth_to_radius_ratio > ratio_threshold:
        violated = True

    return {
        "violated": violated,
        "evaluation": {
            "operator": "or",
            "fact_keys": ["long_reach_tool_risk_count", "max_depth_to_radius_ratio"],
            "actual": {
                "long_reach_tool_risk_count": None if long_reach_risk_count is None else round(long_reach_risk_count, 4),
                "max_depth_to_radius_ratio": None if depth_to_radius_ratio is None else round(depth_to_radius_ratio, 4),
            },
            "thresholds": {
                "max_long_reach_tool_risk_count": count_threshold,
                "max_depth_to_radius_ratio": ratio_threshold,
            },
            "rule_expression": "long_reach_tool_risk_count == 0 and depth_to_radius_ratio <= 8.0",
        },
    }


def _evaluate_food_002(review_facts: dict[str, Any]) -> dict[str, Any] | None:
    critical_corner_count = _numeric_fact(review_facts, "critical_corner_count")
    if critical_corner_count is None:
        return None

    violated = critical_corner_count > 0
    return {
        "violated": violated,
        "evaluation": {
            "operator": "==",
            "fact_key": "critical_corner_count",
            "actual": round(critical_corner_count, 4),
            "threshold": 0.0,
            "rule_expression": "critical_corner_count == 0",
        },
    }


def _evaluate_food_004(review_facts: dict[str, Any]) -> dict[str, Any] | None:
    min_radius = _numeric_fact(review_facts, "min_internal_radius_mm", "pocket_corner_radius")
    count_below_3 = _numeric_fact(review_facts, "count_radius_below_3_0_mm")
    if min_radius is None and count_below_3 is None:
        return None

    violated = False
    if min_radius is not None and min_radius < 3.0:
        violated = True
    if count_below_3 is not None and count_below_3 > 0:
        violated = True
    return {
        "violated": violated,
        "evaluation": {
            "operator": "and",
            "fact_keys": ["min_internal_radius_mm", "count_radius_below_3_0_mm"],
            "actual": {
                "min_internal_radius_mm": None if min_radius is None else round(min_radius, 4),
                "count_radius_below_3_0_mm": None if count_below_3 is None else round(count_below_3, 4),
            },
            "thresholds": {
                "min_radius_mm": 3.0,
                "max_count_below_3_0_mm": 0.0,
            },
            "rule_expression": "min_internal_radius_mm >= 3.0 and count_radius_below_3_0_mm == 0",
        },
    }


def _evaluate_fix_003(review_facts: dict[str, Any]) -> dict[str, Any] | None:
    min_wall = _numeric_fact(review_facts, "min_wall_thickness", "min_wall_thickness_mm")
    if min_wall is None:
        return None
    threshold = 1.5
    violated = min_wall < threshold
    return {
        "violated": violated,
        "evaluation": {
            "operator": ">=",
            "fact_key": "min_wall_thickness_mm",
            "actual": round(min_wall, 4),
            "threshold": threshold,
            "rule_expression": "min_wall_thickness_mm >= 1.5",
        },
    }


def _evaluate_sm_001(review_facts: dict[str, Any]) -> dict[str, Any] | None:
    flange_length = _numeric_fact(review_facts, "flange_length")
    thickness = _numeric_fact(review_facts, "sheet_thickness")
    if flange_length is None or thickness is None:
        return None

    threshold = thickness * 4.0
    violated = flange_length < threshold
    return {
        "violated": violated,
        "evaluation": {
            "operator": ">=",
            "fact_key": "flange_length",
            "actual": round(flange_length, 4),
            "threshold": round(threshold, 4),
            "rule_expression": "flange_length >= 4 * sheet_thickness",
        },
    }


def _evaluate_pstd_001(review_facts: dict[str, Any]) -> dict[str, Any] | None:
    actual = _bool_fact(
        review_facts,
        "cad.robot_interface.conformance_flag",
        "robot_interface_conformance_flag",
        "iso9409_1_robot_interface_candidate",
    )
    if actual is None:
        return None
    expected = True
    return {
        "violated": actual != expected,
        "evaluation": {
            "operator": "==",
            "fact_key": "cad.robot_interface.conformance_flag",
            "actual": actual,
            "threshold": expected,
            "rule_expression": "cad.robot_interface.conformance_flag == true",
        },
    }


def _evaluate_pstd_004(review_facts: dict[str, Any]) -> dict[str, Any] | None:
    actual = _bool_fact(
        review_facts,
        "cad.fits.all_pairs_intended_fit_type_met",
        "fits_all_pairs_intended_fit_type_met",
        "fit_conformance_flag",
    )
    if actual is None:
        return None
    expected = True
    return {
        "violated": actual != expected,
        "evaluation": {
            "operator": "==",
            "fact_key": "cad.fits.all_pairs_intended_fit_type_met",
            "actual": actual,
            "threshold": expected,
            "rule_expression": "cad.fits.all_pairs_intended_fit_type_met == true",
        },
    }


def _evaluate_pstd_008(review_facts: dict[str, Any]) -> dict[str, Any] | None:
    actual = _bool_fact(
        review_facts,
        "cad.threads.iso228_all_conformant",
        "iso228_all_conformant",
        "iso228_1_thread_standard_candidate",
    )
    if actual is None:
        return None
    expected = True
    return {
        "violated": actual != expected,
        "evaluation": {
            "operator": "==",
            "fact_key": "cad.threads.iso228_all_conformant",
            "actual": actual,
            "threshold": expected,
            "rule_expression": "cad.threads.iso228_all_conformant == true",
        },
    }


def _evaluate_pstd_009(review_facts: dict[str, Any]) -> dict[str, Any] | None:
    count = _numeric_fact(
        review_facts,
        "cad.hygienic_design.enclosed_voids_in_product_zone_count",
        "enclosed_voids_in_product_zone_count",
        "count_radius_below_3_0_mm",
    )
    if count is None:
        return None
    return {
        "violated": count > 0,
        "evaluation": {
            "operator": "==",
            "fact_key": "cad.hygienic_design.enclosed_voids_in_product_zone_count",
            "actual": round(count, 4),
            "threshold": 0,
            "rule_expression": "cad.hygienic_design.enclosed_voids_in_product_zone_count == 0",
        },
    }


def _evaluate_pstd_012(review_facts: dict[str, Any]) -> dict[str, Any] | None:
    count = _numeric_fact(
        review_facts,
        "cad.hygienic_design.trapped_volume_count",
        "trapped_volume_count",
        "long_reach_tool_risk_count",
    )
    if count is None:
        return None
    return {
        "violated": count > 0,
        "evaluation": {
            "operator": "==",
            "fact_key": "cad.hygienic_design.trapped_volume_count",
            "actual": round(count, 4),
            "threshold": 0,
            "rule_expression": "cad.hygienic_design.trapped_volume_count == 0",
        },
    }


def _evaluate_pstd_019(review_facts: dict[str, Any]) -> dict[str, Any] | None:
    count = _numeric_fact(
        review_facts,
        "cad.hygienic_design.crevice_count",
        "crevice_count",
        "critical_corner_count",
    )
    if count is None:
        return None
    return {
        "violated": count > 0,
        "evaluation": {
            "operator": "==",
            "fact_key": "cad.hygienic_design.crevice_count",
            "actual": round(count, 4),
            "threshold": 0,
            "rule_expression": "cad.hygienic_design.crevice_count == 0",
        },
    }


RULE_VIOLATION_EVALUATORS: dict[str, Any] = {
    "CNC-001": _evaluate_cnc_001,
    "CNC-002": _evaluate_cnc_002,
    "CNC-003": _evaluate_cnc_003,
    "CNC-005": _evaluate_cnc_005,
    "CNC-006": _evaluate_cnc_006,
    "CNC-010": _evaluate_cnc_010,
    "CNC-013": _evaluate_cnc_013,
    "CNC-024": _evaluate_cnc_024,
    "CNC-025": _evaluate_cnc_025,
    "FIX-003": _evaluate_fix_003,
    "FOOD-002": _evaluate_food_002,
    "FOOD-004": _evaluate_food_004,
    "SM-001": _evaluate_sm_001,
    "PSTD-001": _evaluate_pstd_001,
    "PSTD-004": _evaluate_pstd_004,
    "PSTD-008": _evaluate_pstd_008,
    "PSTD-009": _evaluate_pstd_009,
    "PSTD-012": _evaluate_pstd_012,
    "PSTD-019": _evaluate_pstd_019,
}


def _numeric_fact(review_facts: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        value = review_facts.get(key)
        if isinstance(value, bool):
            continue
        if isinstance(value, (int, float)):
            return float(value)
    return None


def _bool_fact(review_facts: dict[str, Any], *keys: str) -> bool | None:
    for key in keys:
        value = review_facts.get(key)
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return float(value) > 0.0
        if isinstance(value, str):
            normalized = value.strip().lower()
            if not normalized:
                continue
            if normalized in {"true", "yes", "y", "1"}:
                return True
            if normalized in {"false", "no", "n", "0"}:
                return False
    return None


def _string_fact(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip()


def _wall_threshold_for_material(material_spec: str) -> tuple[float, str]:
    normalized = material_spec.lower()
    if any(token in normalized for token in ("aluminum", "steel", "stainless", "titanium", "nickel", "brass", "copper")):
        return 1.0, "metal"
    if any(token in normalized for token in ("abs", "nylon", "plastic", "poly", "peek", "ptfe")):
        return 0.8, "polymer"
    return 1.0, "generic"


def _derive_standards_used_auto(
    bundle: DfmBundle, findings: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    reference_catalog = bundle.references
    ref_ids = sorted(
        {
            ref_id
            for finding in findings
            for ref_id in finding.get("refs", [])
            if isinstance(ref_id, str) and ref_id
        }
    )

    standards: list[dict[str, Any]] = []
    for ref_id in ref_ids:
        ref_entry = reference_catalog.get(ref_id)
        if not isinstance(ref_entry, dict):
            raise DfmReviewV2Error(
                f"Finding references unknown ref id '{ref_id}' in reference catalog."
            )
        standards.append(
            {
                "ref_id": ref_id,
                "title": ref_entry.get("title"),
                "url": ref_entry.get("url"),
                "type": ref_entry.get("type"),
                "notes": ref_entry.get("notes"),
            }
        )

    return standards


def _init_standards_trace(
    *,
    bundle: DfmBundle,
    overlay_id: str | None,
) -> dict[str, dict[str, Any]]:
    standards_trace: dict[str, dict[str, Any]] = {}
    overlay_map = _index_by_id(bundle.overlays.get("overlays", []), "overlay_id")
    overlay = overlay_map.get(overlay_id) if overlay_id else None
    overlay_refs = overlay.get("adds_refs", []) if isinstance(overlay, dict) else []
    for ref_id in overlay_refs:
        if not isinstance(ref_id, str) or not ref_id:
            continue
        standards_trace[ref_id] = _new_standards_trace_entry(bundle, ref_id)
    return standards_trace


def _new_standards_trace_entry(bundle: DfmBundle, ref_id: str) -> dict[str, Any]:
    reference_catalog = bundle.references
    ref_entry = reference_catalog.get(ref_id)
    if not isinstance(ref_entry, dict):
        raise DfmReviewV2Error(
            f"Rule references unknown ref id '{ref_id}' in reference catalog."
        )
    return {
        "ref_id": ref_id,
        "title": ref_entry.get("title"),
        "url": ref_entry.get("url"),
        "type": ref_entry.get("type"),
        "notes": ref_entry.get("notes"),
        "active_in_mode": False,
        "rules_considered": 0,
        "design_risk_findings": 0,
        "evidence_gap_findings": 0,
        "blocked_by_missing_inputs": 0,
        "checks_passed": 0,
        "checks_unresolved": 0,
    }


def _update_standards_trace(
    *,
    standards_trace: dict[str, dict[str, Any]],
    bundle: DfmBundle,
    refs: list[str],
    outcome: str,
) -> None:
    for ref_id in refs:
        if ref_id not in standards_trace:
            standards_trace[ref_id] = _new_standards_trace_entry(bundle, ref_id)
        entry = standards_trace[ref_id]
        entry["active_in_mode"] = True
        entry["rules_considered"] = int(entry.get("rules_considered", 0)) + 1
        if outcome == "rule_violation":
            entry["design_risk_findings"] = int(entry.get("design_risk_findings", 0)) + 1
        elif outcome == "evidence_gap":
            entry["evidence_gap_findings"] = int(entry.get("evidence_gap_findings", 0)) + 1
            entry["blocked_by_missing_inputs"] = int(entry.get("blocked_by_missing_inputs", 0)) + 1
        elif outcome == "passed":
            entry["checks_passed"] = int(entry.get("checks_passed", 0)) + 1
        elif outcome == "unresolved":
            entry["checks_unresolved"] = int(entry.get("checks_unresolved", 0)) + 1


def _standards_trace_payload(
    standards_trace: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    return [standards_trace[key] for key in sorted(standards_trace.keys())]


def _dedupe_standards(
    standards_lists: list[list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for standards in standards_lists:
        for entry in standards:
            ref_id = entry.get("ref_id")
            if isinstance(ref_id, str) and ref_id:
                merged[ref_id] = entry
    return [merged[ref_id] for ref_id in sorted(merged.keys())]


def _merge_standards_trace(
    standards_trace_lists: list[list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    additive_fields = (
        "rules_considered",
        "design_risk_findings",
        "evidence_gap_findings",
        "blocked_by_missing_inputs",
        "checks_passed",
        "checks_unresolved",
    )
    for trace_list in standards_trace_lists:
        for entry in trace_list:
            ref_id = entry.get("ref_id")
            if not isinstance(ref_id, str) or not ref_id:
                continue
            if ref_id not in merged:
                merged[ref_id] = dict(entry)
                continue
            target = merged[ref_id]
            target["active_in_mode"] = bool(target.get("active_in_mode")) or bool(entry.get("active_in_mode"))
            for field in additive_fields:
                target[field] = int(target.get(field, 0)) + int(entry.get(field, 0))
    return [merged[ref_id] for ref_id in sorted(merged.keys())]


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


def _index_by_id(items: list[Any], id_key: str) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        item_id = item.get(id_key)
        if isinstance(item_id, str) and item_id:
            indexed[item_id] = item
    return indexed


def _label_for_pack(pack_map: dict[str, dict[str, Any]], pack_id: str) -> str | None:
    entry = pack_map.get(pack_id)
    if not entry:
        return None
    label = entry.get("label")
    return label if isinstance(label, str) else None


def _assert_no_manual_standards_injection(context_payload: dict[str, Any]) -> None:
    manual_keys = [key for key in MANUAL_STANDARDS_KEYS if key in context_payload]
    if manual_keys:
        joined = ", ".join(sorted(manual_keys))
        raise DfmReviewV2Error(
            f"Manual standards injection is not allowed: {joined}"
        )
