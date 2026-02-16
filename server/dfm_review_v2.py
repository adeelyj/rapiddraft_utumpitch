from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .dfm_bundle import DfmBundle
from .dfm_costing import estimate_review_costs
from .dfm_planning import DfmPlanningError, plan_dfm_execution


BASE_DRAWING_PACK_ID = "A_DRAWING"
OVERLAY_PACK_ID = "F_OVERLAY"
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
    selected_process_override: str | None = None
    selected_overlay: str | None = None
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
    screenshot_data_url: str | None = None
    context_payload: dict[str, object] = Field(default_factory=dict)


def generate_dfm_review_v2(
    bundle: DfmBundle,
    *,
    model_id: str,
    component_context: dict[str, Any],
    planning_inputs: dict[str, Any] | None = None,
    execution_plans: list[dict[str, Any]] | None = None,
    selected_execution_plan_id: str | None = None,
    screenshot_data_url: str | None = None,
    context_payload: dict[str, Any] | None = None,
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
    review_facts = _build_review_facts(
        planning_inputs=planning_inputs or {},
        context_payload=context_payload,
        screenshot_data_url=screenshot_data_url,
        component_context=component_context,
    )

    route_outputs = [
        _evaluate_plan(
            bundle=bundle,
            execution_plan=plan,
            review_facts=review_facts,
            mismatch=plan_payload.get("mismatch"),
        )
        for plan in resolved_plans
    ]

    all_standards = _dedupe_standards(
        standards_lists=[route["standards_used_auto"] for route in route_outputs]
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
        "ai_recommendation": ai_recommendation,
        "mismatch": mismatch,
        "route_count": len(route_outputs),
        "finding_count_total": total_findings,
        "standards_used_auto_union": all_standards,
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
        try:
            plan_payload = plan_dfm_execution(bundle, **planning_inputs)
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

    if process_id not in process_map:
        raise DfmReviewV2Error(f"Execution plan has unknown process_id '{process_id}'.")
    if role_id not in role_map:
        raise DfmReviewV2Error(f"Execution plan has unknown role_id '{role_id}'.")
    if template_id not in template_map:
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

    if raw_plan.get("template_sections") is None:
        template_sections = _resolve_template_sections(
            template=template_map[template_id],
            selected_overlay=overlay_id,
        )
    else:
        template_sections = {
            "enabled": list(raw_plan.get("template_sections") or []),
            "suppressed": list(raw_plan.get("suppressed_template_sections") or []),
        }

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
        "template_label": raw_plan.get("template_label") or template_map[template_id].get("label"),
        "template_sections": template_sections["enabled"],
        "suppressed_template_sections": template_sections["suppressed"],
    }


def _build_review_facts(
    *,
    planning_inputs: dict[str, Any],
    context_payload: dict[str, Any],
    screenshot_data_url: str | None,
    component_context: dict[str, Any],
) -> dict[str, Any]:
    facts: dict[str, Any] = {}

    extracted = planning_inputs.get("extracted_part_facts")
    if isinstance(extracted, dict):
        facts.update(extracted)

    facts.update(context_payload)

    if screenshot_data_url:
        facts["screenshot_data_url"] = screenshot_data_url
        facts["manual_context"] = True
    elif context_payload:
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
) -> dict[str, Any]:
    pack_ids = execution_plan["pack_ids"]
    overlay_id = execution_plan.get("overlay_id")

    findings: list[dict[str, Any]] = []
    for rule in _iter_rules_for_plan(bundle, pack_ids, overlay_id):
        missing_inputs = _missing_required_inputs(rule, review_facts)
        if not missing_inputs:
            continue
        refs = [ref for ref in rule.get("refs", []) if isinstance(ref, str) and ref]
        finding = {
            "rule_id": rule.get("rule_id"),
            "pack_id": rule.get("pack_id"),
            "severity": rule.get("severity"),
            "title": rule.get("title"),
            "description": rule.get("description"),
            "refs": refs,
            "evidence": {
                "missing_inputs": missing_inputs,
                "provided_inputs": [
                    key for key in rule.get("inputs_required", []) if key not in missing_inputs
                ],
            },
        }
        findings.append(finding)

    standards = _derive_standards_used_auto(bundle, findings)
    role_map = _index_by_id(bundle.roles.get("roles", []), "role_id")
    role = role_map.get(execution_plan["role_id"], {})

    return {
        "plan_id": execution_plan.get("plan_id"),
        "route_source": execution_plan.get("route_source"),
        "process_id": execution_plan.get("process_id"),
        "process_label": execution_plan.get("process_label"),
        "pack_ids": pack_ids,
        "pack_labels": execution_plan.get("pack_labels", []),
        "overlay_id": execution_plan.get("overlay_id"),
        "overlay_label": execution_plan.get("overlay_label"),
        "role_id": execution_plan.get("role_id"),
        "role_label": execution_plan.get("role_label"),
        "template_id": execution_plan.get("template_id"),
        "template_label": execution_plan.get("template_label"),
        "finding_count": len(findings),
        "findings": findings,
        "standards_used_auto": standards,
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
    bundle: DfmBundle, pack_ids: list[str], overlay_id: str | None
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
        for rule in rules_by_pack.get(pack_id, []):
            if pack_id == OVERLAY_PACK_ID and overlay_prefixes:
                rule_id = rule.get("rule_id")
                if not isinstance(rule_id, str):
                    continue
                if not any(rule_id.startswith(prefix) for prefix in overlay_prefixes):
                    continue
            yield rule


def _missing_required_inputs(rule: dict[str, Any], review_facts: dict[str, Any]) -> list[str]:
    required = rule.get("inputs_required", [])
    if not isinstance(required, list):
        return []
    missing: list[str] = []
    for key in required:
        if not isinstance(key, str) or not key:
            continue
        if not _truthy(review_facts.get(key)):
            missing.append(key)
    return missing


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
