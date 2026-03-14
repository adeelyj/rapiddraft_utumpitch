from __future__ import annotations

from typing import Any, Callable, Literal

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
    geometry_evidence = _build_geometry_evidence(
        review_facts=review_facts,
        route_outputs=route_outputs,
        effective_context=effective_context,
        ai_recommendation=ai_recommendation,
        component_context=component_context,
    )

    return {
        "model_id": model_id,
        "component_context": component_context,
        "effective_context": effective_context,
        "ai_recommendation": ai_recommendation,
        "geometry_evidence": geometry_evidence,
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


def _build_geometry_evidence(
    *,
    review_facts: dict[str, Any],
    route_outputs: list[dict[str, Any]],
    effective_context: dict[str, Any] | None,
    ai_recommendation: dict[str, Any] | None,
    component_context: dict[str, Any],
) -> dict[str, Any] | None:
    effective_process_label = ""
    if isinstance(effective_context, dict):
        process_context = effective_context.get("process")
        if isinstance(process_context, dict):
            effective_process_label = _clean_optional_string(
                process_context.get("effective_process_label")
            )
    if not effective_process_label and route_outputs:
        effective_process_label = _clean_optional_string(
            route_outputs[0].get("process_label")
        )

    ai_process_label = ""
    if isinstance(ai_recommendation, dict):
        ai_process_label = _clean_optional_string(ai_recommendation.get("process_label"))

    geometry_anchors = _build_geometry_anchor_lookup(component_context)
    localized_features = _build_geometry_localized_feature_lookup(component_context)

    turning_metrics: list[dict[str, Any]] = []
    turning_detail_metrics: list[dict[str, Any]] = []
    hole_metrics: list[dict[str, Any]] = []
    hole_detail_metrics: list[dict[str, Any]] = []
    pocket_metrics: list[dict[str, Any]] = []
    pocket_detail_metrics: list[dict[str, Any]] = []
    groove_metrics: list[dict[str, Any]] = []
    milled_metrics: list[dict[str, Any]] = []
    milled_detail_metrics: list[dict[str, Any]] = []
    boss_metrics: list[dict[str, Any]] = []

    rotational_symmetry = _bool_fact(review_facts, "rotational_symmetry")
    if rotational_symmetry:
        turning_metrics.append(
            _geometry_metric(
                "rotational_symmetry",
                "Rotational symmetry",
                True,
                geometry_anchor=geometry_anchors.get("rotational_symmetry"),
            )
        )

    turned_face_count = _geometry_count_fact(review_facts, "turned_face_count")
    turned_diameter_faces_count = _geometry_count_fact(
        review_facts, "turned_diameter_faces_count"
    )
    turned_end_faces_count = _geometry_count_fact(
        review_facts, "turned_end_faces_count"
    )
    turned_profile_faces_count = _geometry_count_fact(
        review_facts, "turned_profile_faces_count"
    )
    if turned_face_count > 0:
        turning_metrics.append(
            _geometry_metric(
                "turned_face_count",
                "Turned faces",
                turned_face_count,
                geometry_anchor=geometry_anchors.get("turned_face_count"),
            )
        )
    if turned_diameter_faces_count > 0:
        turning_detail_metrics.append(
            _geometry_metric(
                "turned_diameter_faces_count",
                "Turned diameter faces",
                turned_diameter_faces_count,
                geometry_anchor=geometry_anchors.get("turned_diameter_faces_count"),
            )
        )
    if turned_end_faces_count > 0:
        turning_detail_metrics.append(
            _geometry_metric(
                "turned_end_faces_count",
                "Turned end faces",
                turned_end_faces_count,
                geometry_anchor=geometry_anchors.get("turned_end_faces_count"),
            )
        )
    if turned_profile_faces_count > 0:
        turning_detail_metrics.append(
            _geometry_metric(
                "turned_profile_faces_count",
                "Turned profile faces",
                turned_profile_faces_count,
                geometry_anchor=geometry_anchors.get("turned_profile_faces_count"),
            )
        )

    outer_diameter_groove_count = _geometry_count_fact(
        review_facts, "outer_diameter_groove_count"
    )
    end_face_groove_count = _geometry_count_fact(
        review_facts, "end_face_groove_count"
    )
    if outer_diameter_groove_count > 0:
        groove_metrics.append(
            _geometry_metric(
                "outer_diameter_groove_count",
                "Outer diameter grooves",
                outer_diameter_groove_count,
                geometry_anchor=geometry_anchors.get("outer_diameter_groove_count"),
            )
        )
    if end_face_groove_count > 0:
        groove_metrics.append(
            _geometry_metric(
                "end_face_groove_count",
                "End-face grooves",
                end_face_groove_count,
                geometry_anchor=geometry_anchors.get("end_face_groove_count"),
            )
        )

    hole_count = _geometry_count_fact(review_facts, "hole_count")
    through_hole_count = _geometry_count_fact(review_facts, "through_hole_count")
    partial_hole_count = _geometry_count_fact(review_facts, "partial_hole_count")
    stepped_hole_count = _geometry_count_fact(review_facts, "stepped_hole_count")
    bore_count = _geometry_count_fact(review_facts, "bore_count")
    if hole_count > 0:
        hole_metrics.append(
            _geometry_metric(
                "hole_count",
                "Hole features",
                hole_count,
                geometry_anchor=geometry_anchors.get("hole_count"),
            )
        )
    if through_hole_count > 0:
        hole_metrics.append(
            _geometry_metric(
                "through_hole_count",
                "Through holes",
                through_hole_count,
                geometry_anchor=geometry_anchors.get("through_hole_count"),
            )
        )
    if bore_count > 0:
        hole_metrics.append(
            _geometry_metric(
                "bore_count",
                "Bores",
                bore_count,
                geometry_anchor=geometry_anchors.get("bore_count"),
            )
        )
    if partial_hole_count > 0:
        hole_detail_metrics.append(
            _geometry_metric(
                "partial_hole_count",
                "Partial holes",
                partial_hole_count,
                geometry_anchor=geometry_anchors.get("partial_hole_count"),
            )
        )
    if stepped_hole_count > 0:
        hole_detail_metrics.append(
            _geometry_metric(
                "stepped_hole_count",
                "Stepped holes",
                stepped_hole_count,
                geometry_anchor=geometry_anchors.get("stepped_hole_count"),
            )
        )

    pocket_count = _geometry_count_fact(review_facts, "pocket_count")
    open_pocket_count = _geometry_count_fact(review_facts, "open_pocket_count")
    closed_pocket_count = _geometry_count_fact(review_facts, "closed_pocket_count")
    if pocket_count > 0:
        pocket_metrics.append(
            _geometry_metric(
                "pocket_count",
                "Pocket features",
                pocket_count,
                geometry_anchor=geometry_anchors.get("pocket_count"),
            )
        )
    if open_pocket_count > 0:
        pocket_metrics.append(
            _geometry_metric(
                "open_pocket_count",
                "Open pockets",
                open_pocket_count,
                geometry_anchor=geometry_anchors.get("open_pocket_count"),
            )
        )
    if closed_pocket_count > 0:
        pocket_metrics.append(
            _geometry_metric(
                "closed_pocket_count",
                "Closed pockets",
                closed_pocket_count,
                geometry_anchor=geometry_anchors.get("closed_pocket_count"),
            )
        )

    milled_face_count = _geometry_count_fact(review_facts, "milled_face_count")
    circular_milled_face_count = _geometry_count_fact(
        review_facts, "circular_milled_face_count"
    )
    flat_milled_face_count = _geometry_count_fact(
        review_facts, "flat_milled_face_count"
    )
    flat_side_milled_face_count = _geometry_count_fact(
        review_facts, "flat_side_milled_face_count"
    )
    curved_milled_face_count = _geometry_count_fact(
        review_facts, "curved_milled_face_count"
    )
    convex_profile_edge_milled_face_count = _geometry_count_fact(
        review_facts, "convex_profile_edge_milled_face_count"
    )
    concave_fillet_edge_milled_face_count = _geometry_count_fact(
        review_facts, "concave_fillet_edge_milled_face_count"
    )
    if milled_face_count > 0:
        milled_metrics.append(
            _geometry_metric(
                "milled_face_count",
                "Milled faces",
                milled_face_count,
                geometry_anchor=geometry_anchors.get("milled_face_count"),
            )
        )
    if circular_milled_face_count > 0:
        milled_metrics.append(
            _geometry_metric(
                "circular_milled_face_count",
                "Circular milled faces",
                circular_milled_face_count,
                geometry_anchor=geometry_anchors.get("circular_milled_face_count"),
            )
        )
    if flat_milled_face_count > 0:
        milled_detail_metrics.append(
            _geometry_metric(
                "flat_milled_face_count",
                "Flat milled faces",
                flat_milled_face_count,
                geometry_anchor=geometry_anchors.get("flat_milled_face_count"),
            )
        )
    if flat_side_milled_face_count > 0:
        milled_detail_metrics.append(
            _geometry_metric(
                "flat_side_milled_face_count",
                "Flat-side milled faces",
                flat_side_milled_face_count,
                geometry_anchor=geometry_anchors.get("flat_side_milled_face_count"),
            )
        )
    if curved_milled_face_count > 0:
        milled_detail_metrics.append(
            _geometry_metric(
                "curved_milled_face_count",
                "Curved milled faces",
                curved_milled_face_count,
                geometry_anchor=geometry_anchors.get("curved_milled_face_count"),
            )
        )
    if convex_profile_edge_milled_face_count > 0:
        milled_detail_metrics.append(
            _geometry_metric(
                "convex_profile_edge_milled_face_count",
                "Convex profile-edge milled faces",
                convex_profile_edge_milled_face_count,
                geometry_anchor=geometry_anchors.get(
                    "convex_profile_edge_milled_face_count"
                ),
            )
        )
    if concave_fillet_edge_milled_face_count > 0:
        milled_detail_metrics.append(
            _geometry_metric(
                "concave_fillet_edge_milled_face_count",
                "Concave fillet-edge milled faces",
                concave_fillet_edge_milled_face_count,
                geometry_anchor=geometry_anchors.get(
                    "concave_fillet_edge_milled_face_count"
                ),
            )
        )

    boss_count = _geometry_count_fact(review_facts, "boss_count")
    if boss_count > 0:
        boss_metrics.append(
            _geometry_metric(
                "boss_count",
                "Bosses",
                boss_count,
                geometry_anchor=geometry_anchors.get("boss_count"),
            )
        )

    feature_groups: list[dict[str, Any]] = []
    if turning_metrics:
        feature_groups.append(
            _geometry_feature_group(
                "turning",
                "Turning features",
                _turning_summary(
                    rotational_symmetry=bool(rotational_symmetry),
                    turned_face_count=turned_face_count,
                ),
                turning_metrics,
                geometry_anchor=_first_geometry_anchor(
                    geometry_anchors.get("turned_face_count"),
                    geometry_anchors.get("rotational_symmetry"),
                ),
                localized_features=localized_features.get("turning"),
            )
        )
    if hole_metrics:
        feature_groups.append(
            _geometry_feature_group(
                "holes",
                "Hole features",
                _hole_summary(
                    hole_count=hole_count,
                    through_hole_count=through_hole_count,
                    bore_count=bore_count,
                ),
                hole_metrics,
                geometry_anchor=geometry_anchors.get("hole_count"),
                localized_features=localized_features.get("holes"),
            )
        )
    if pocket_metrics:
        feature_groups.append(
            _geometry_feature_group(
                "pockets",
                "Pocket features",
                _pocket_summary(
                    pocket_count=pocket_count,
                    open_pocket_count=open_pocket_count,
                    closed_pocket_count=closed_pocket_count,
                ),
                pocket_metrics,
                geometry_anchor=geometry_anchors.get("pocket_count"),
                localized_features=localized_features.get("pockets"),
            )
        )
    if groove_metrics:
        feature_groups.append(
            _geometry_feature_group(
                "grooves",
                "Groove features",
                _groove_summary(
                    outer_diameter_groove_count=outer_diameter_groove_count,
                    end_face_groove_count=end_face_groove_count,
                ),
                groove_metrics,
                geometry_anchor=_first_geometry_anchor(
                    geometry_anchors.get("outer_diameter_groove_count"),
                    geometry_anchors.get("end_face_groove_count"),
                ),
                localized_features=localized_features.get("grooves"),
            )
        )
    if milled_metrics:
        feature_groups.append(
            _geometry_feature_group(
                "milled_faces",
                "Milled-face features",
                _milled_summary(
                    milled_face_count=milled_face_count,
                    circular_milled_face_count=circular_milled_face_count,
                ),
                milled_metrics,
                geometry_anchor=geometry_anchors.get("milled_face_count"),
                localized_features=localized_features.get("milled_faces"),
            )
        )
    if boss_metrics:
        feature_groups.append(
            _geometry_feature_group(
                "bosses",
                "Boss features",
                _boss_summary(boss_count=boss_count),
                boss_metrics,
                geometry_anchor=geometry_anchors.get("boss_count"),
                localized_features=localized_features.get("bosses"),
            )
        )

    detail_metrics = [
        *turning_detail_metrics,
        *hole_detail_metrics,
        *pocket_detail_metrics,
        *milled_detail_metrics,
    ]

    reason_tags = _geometry_reason_tags(
        rotational_symmetry=bool(rotational_symmetry),
        turned_face_count=turned_face_count,
        hole_count=hole_count,
        pocket_count=pocket_count,
        groove_count=outer_diameter_groove_count + end_face_groove_count,
        circular_milled_face_count=circular_milled_face_count,
    )

    if (
        not effective_process_label
        and not ai_process_label
        and not reason_tags
        and not feature_groups
        and not detail_metrics
    ):
        return None

    return {
        "process_summary": {
            "effective_process_label": effective_process_label or None,
            "ai_process_label": ai_process_label or None,
            "reason_tags": reason_tags,
        },
        "feature_groups": feature_groups,
        "detail_metrics": detail_metrics,
    }


def _geometry_metric(
    key: str,
    label: str,
    value: str | int | float | bool,
    *,
    unit: str | None = None,
    geometry_anchor: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "key": key,
        "label": label,
        "value": _normalize_geometry_metric_value(value),
        "unit": unit,
        "geometry_anchor": geometry_anchor,
    }


def _geometry_feature_group(
    group_id: str,
    label: str,
    summary: str,
    metrics: list[dict[str, Any]],
    *,
    geometry_anchor: dict[str, Any] | None = None,
    localized_features: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    payload = {
        "group_id": group_id,
        "label": label,
        "summary": summary,
        "metrics": metrics,
    }
    if geometry_anchor:
        payload["geometry_anchor"] = geometry_anchor
    if localized_features:
        payload["localized_features"] = localized_features
    return payload


def _geometry_feature_item(
    feature_id: str,
    label: str,
    *,
    summary: str | None = None,
    geometry_anchor: dict[str, Any] | None = None,
    feature_type: str | None = None,
    feature_subtype: str | None = None,
) -> dict[str, Any]:
    payload = {
        "feature_id": feature_id,
        "label": label,
    }
    if summary:
        payload["summary"] = summary
    if geometry_anchor:
        payload["geometry_anchor"] = geometry_anchor
    if feature_type:
        payload["feature_type"] = feature_type
    if feature_subtype:
        payload["feature_subtype"] = feature_subtype
    return payload


def _normalize_geometry_metric_value(value: str | int | float | bool) -> str | int | float | bool:
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def _build_geometry_localized_feature_lookup(component_context: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    inventory = component_context.get("geometry_feature_inventory")
    if not isinstance(inventory, dict):
        return {}

    component_node_name = _clean_optional_string(component_context.get("component_node_name")) or _clean_optional_string(
        inventory.get("component_node_name")
    )
    face_lookup = {
        int(face.get("face_index")): face
        for face in inventory.get("face_inventory", [])
        if isinstance(face, dict) and isinstance(face.get("face_index"), int)
    }

    turning_detection = inventory.get("turning_detection")
    hole_detection = inventory.get("hole_detection")
    pocket_detection = inventory.get("pocket_detection")
    boss_detection = inventory.get("boss_detection")

    localized_features = {
        "holes": _geometry_feature_items_from_payloads(
            component_node_name=component_node_name or None,
            face_lookup=face_lookup,
            payloads=hole_detection.get("candidates") if isinstance(hole_detection, dict) else None,
            anchor_prefix="hole-feature",
            feature_type="hole",
            label_builder=_hole_feature_item_label,
            summary_builder=_hole_feature_item_summary,
        ),
        "pockets": [
            *_geometry_feature_items_from_payloads(
                component_node_name=component_node_name or None,
                face_lookup=face_lookup,
                payloads=pocket_detection.get("open_pocket_feature_groups") if isinstance(pocket_detection, dict) else None,
                anchor_prefix="open-pocket",
                feature_type="pocket",
                feature_subtype="open_pocket",
                label_builder=lambda _payload, index: f"Open pocket {index}",
                summary_builder=_pocket_feature_item_summary,
            ),
            *_geometry_feature_items_from_payloads(
                component_node_name=component_node_name or None,
                face_lookup=face_lookup,
                payloads=pocket_detection.get("closed_pocket_feature_groups") if isinstance(pocket_detection, dict) else None,
                anchor_prefix="closed-pocket",
                feature_type="pocket",
                feature_subtype="closed_pocket",
                label_builder=lambda _payload, index: f"Closed pocket {index}",
                summary_builder=_pocket_feature_item_summary,
            ),
        ],
        "grooves": [
            *_geometry_feature_items_from_payloads(
                component_node_name=component_node_name or None,
                face_lookup=face_lookup,
                payloads=turning_detection.get("outer_diameter_groove_groups") if isinstance(turning_detection, dict) else None,
                anchor_prefix="outer-groove",
                feature_type="groove",
                feature_subtype="outer_diameter",
                label_builder=lambda _payload, index: f"Outer diameter groove {index}",
                summary_builder=_groove_feature_item_summary,
            ),
            *_geometry_feature_items_from_payloads(
                component_node_name=component_node_name or None,
                face_lookup=face_lookup,
                payloads=turning_detection.get("end_face_groove_groups") if isinstance(turning_detection, dict) else None,
                anchor_prefix="end-face-groove",
                feature_type="groove",
                feature_subtype="end_face",
                label_builder=lambda _payload, index: f"End-face groove {index}",
                summary_builder=_groove_feature_item_summary,
            ),
        ],
        "bosses": _geometry_feature_items_from_payloads(
            component_node_name=component_node_name or None,
            face_lookup=face_lookup,
            payloads=boss_detection.get("candidates") if isinstance(boss_detection, dict) else None,
            anchor_prefix="boss",
            feature_type="boss",
            label_builder=lambda _payload, index: f"Boss {index}",
            summary_builder=_boss_feature_item_summary,
        ),
    }

    return {
        key: items
        for key, items in localized_features.items()
        if items
    }


def _geometry_feature_items_from_payloads(
    *,
    component_node_name: str | None,
    face_lookup: dict[int, dict[str, Any]],
    payloads: Any,
    anchor_prefix: str,
    feature_type: str,
    label_builder: Callable[[Any, int], str],
    summary_builder: Callable[[Any], str | None] | None = None,
    feature_subtype: str | None = None,
) -> list[dict[str, Any]]:
    if not isinstance(payloads, list):
        return []

    items: list[dict[str, Any]] = []
    for index, payload in enumerate(payloads, start=1):
        label = label_builder(payload, index)
        payload_subtype = _clean_optional_string(payload.get("subtype")) if isinstance(payload, dict) else ""
        anchor = _anchor_from_payload(
            component_node_name=component_node_name,
            face_lookup=face_lookup,
            payload=payload,
            anchor_id=f"{anchor_prefix}-{index}",
            label=label,
        )
        if not anchor:
            continue
        anchor["label"] = label
        items.append(
            _geometry_feature_item(
                f"{anchor_prefix}-{index}",
                label,
                summary=summary_builder(payload) if summary_builder else None,
                geometry_anchor=anchor,
                feature_type=feature_type,
                feature_subtype=feature_subtype or payload_subtype or None,
            )
        )
    return items


def _hole_feature_item_label(payload: Any, index: int) -> str:
    subtype = _clean_optional_string(payload.get("subtype")) if isinstance(payload, dict) else ""
    normalized_subtype = subtype.replace("_", " ").strip().title() if subtype else "Hole"
    return f"{normalized_subtype} {index}"


def _hole_feature_item_summary(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return None
    fragments = []
    diameter_mm = _optional_float(payload.get("diameter_mm"))
    depth_mm = _optional_float(payload.get("depth_mm"))
    depth_to_diameter_ratio = _optional_float(payload.get("depth_to_diameter_ratio"))
    if diameter_mm is not None and diameter_mm > 0:
        fragments.append(f"Dia {_format_geometry_number(diameter_mm)} mm")
    if depth_mm is not None and depth_mm > 0:
        fragments.append(f"Depth {_format_geometry_number(depth_mm)} mm")
    if depth_to_diameter_ratio is not None and depth_to_diameter_ratio > 0:
        fragments.append(f"D/D {_format_geometry_number(depth_to_diameter_ratio)}")
    selection_reason = _clean_optional_string(payload.get("selection_reason"))
    if selection_reason:
        fragments.append(selection_reason.replace("_", " "))
    return " | ".join(fragments) or None


def _pocket_feature_item_summary(payload: Any) -> str | None:
    face_count = len(_extract_face_indices(payload))
    if face_count <= 0:
        return None
    return f"{face_count} connected face{'s' if face_count != 1 else ''}"


def _groove_feature_item_summary(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return None
    fragments = []
    radius_mm = _optional_float(payload.get("radius_mm"))
    span_mm = _optional_float(payload.get("span_mm"))
    face_count = len(_extract_face_indices(payload))
    if radius_mm is not None and radius_mm > 0:
        fragments.append(f"R {_format_geometry_number(radius_mm)} mm")
    if span_mm is not None and span_mm > 0:
        fragments.append(f"Span {_format_geometry_number(span_mm)} mm")
    if face_count > 0:
        fragments.append(f"{face_count} face{'s' if face_count != 1 else ''}")
    return " | ".join(fragments) or None


def _boss_feature_item_summary(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return None
    fragments = []
    max_diameter_mm = _optional_float(payload.get("max_diameter_mm"))
    group_span_mm = _optional_float(payload.get("group_span_mm"))
    face_count = len(_extract_face_indices(payload))
    if max_diameter_mm is not None and max_diameter_mm > 0:
        fragments.append(f"Max dia {_format_geometry_number(max_diameter_mm)} mm")
    if group_span_mm is not None and group_span_mm > 0:
        fragments.append(f"Span {_format_geometry_number(group_span_mm)} mm")
    if face_count > 0:
        fragments.append(f"{face_count} face{'s' if face_count != 1 else ''}")
    return " | ".join(fragments) or None


def _format_geometry_number(value: float, digits: int = 2) -> str:
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.{digits}f}".rstrip("0").rstrip(".")


def _build_geometry_anchor_lookup(component_context: dict[str, Any]) -> dict[str, dict[str, Any]]:
    inventory = component_context.get("geometry_feature_inventory")
    if not isinstance(inventory, dict):
        return {}

    component_node_name = _clean_optional_string(component_context.get("component_node_name")) or _clean_optional_string(
        inventory.get("component_node_name")
    )
    face_lookup = {
        int(face.get("face_index")): face
        for face in inventory.get("face_inventory", [])
        if isinstance(face, dict) and isinstance(face.get("face_index"), int)
    }

    turning_detection = inventory.get("turning_detection")
    hole_detection = inventory.get("hole_detection")
    pocket_detection = inventory.get("pocket_detection")
    boss_detection = inventory.get("boss_detection")
    milled_face_detection = inventory.get("milled_face_detection")

    hole_candidates = (
        [candidate for candidate in hole_detection.get("candidates", []) if isinstance(candidate, dict)]
        if isinstance(hole_detection, dict)
        else []
    )
    boss_candidates = (
        [candidate for candidate in boss_detection.get("candidates", []) if isinstance(candidate, dict)]
        if isinstance(boss_detection, dict)
        else []
    )

    turning_primary_anchor = _anchor_from_payload(
        component_node_name=component_node_name or None,
        face_lookup=face_lookup,
        payload=turning_detection.get("primary_cluster") if isinstance(turning_detection, dict) else None,
        anchor_id="turning-primary",
        label="Turning feature region",
    )
    turned_diameter_anchor = _anchor_from_first_payload(
        component_node_name=component_node_name or None,
        face_lookup=face_lookup,
        payloads=turning_detection.get("turned_diameter_groups") if isinstance(turning_detection, dict) else None,
        anchor_id="turning-diameter",
        label="Turned diameter region",
    )
    turned_end_anchor = _anchor_from_face_indices(
        component_node_name=component_node_name or None,
        face_lookup=face_lookup,
        face_indices=turning_detection.get("turned_end_face_indices") if isinstance(turning_detection, dict) else None,
        anchor_id="turning-end",
        label="Turned end-face region",
    )
    outer_groove_anchor = _anchor_from_first_payload(
        component_node_name=component_node_name or None,
        face_lookup=face_lookup,
        payloads=turning_detection.get("outer_diameter_groove_groups") if isinstance(turning_detection, dict) else None,
        anchor_id="groove-outer-diameter",
        label="Outer diameter groove",
    )
    end_face_groove_anchor = _anchor_from_first_payload(
        component_node_name=component_node_name or None,
        face_lookup=face_lookup,
        payloads=turning_detection.get("end_face_groove_groups") if isinstance(turning_detection, dict) else None,
        anchor_id="groove-end-face",
        label="End-face groove",
    )

    open_pocket_anchor = _anchor_from_first_group(
        component_node_name=component_node_name or None,
        face_lookup=face_lookup,
        groups=pocket_detection.get("open_pocket_feature_groups") if isinstance(pocket_detection, dict) else None,
        anchor_id="pocket-open",
        label="Open pocket",
    )
    closed_pocket_anchor = _anchor_from_first_group(
        component_node_name=component_node_name or None,
        face_lookup=face_lookup,
        groups=pocket_detection.get("closed_pocket_feature_groups") if isinstance(pocket_detection, dict) else None,
        anchor_id="pocket-closed",
        label="Closed pocket",
    )

    milled_anchor = _first_geometry_anchor(
        _anchor_from_first_group(
            component_node_name=component_node_name or None,
            face_lookup=face_lookup,
            groups=milled_face_detection.get("flat_milled_feature_groups") if isinstance(milled_face_detection, dict) else None,
            anchor_id="milled-flat",
            label="Flat milled face region",
        ),
        _anchor_from_first_group(
            component_node_name=component_node_name or None,
            face_lookup=face_lookup,
            groups=milled_face_detection.get("curved_milled_feature_groups") if isinstance(milled_face_detection, dict) else None,
            anchor_id="milled-curved",
            label="Curved milled face region",
        ),
        _anchor_from_first_group(
            component_node_name=component_node_name or None,
            face_lookup=face_lookup,
            groups=milled_face_detection.get("circular_milled_feature_groups") if isinstance(milled_face_detection, dict) else None,
            anchor_id="milled-circular",
            label="Circular milled face",
        ),
        _anchor_from_face_indices(
            component_node_name=component_node_name or None,
            face_lookup=face_lookup,
            face_indices=milled_face_detection.get("face_indices") if isinstance(milled_face_detection, dict) else None,
            anchor_id="milled-any",
            label="Milled feature region",
        ),
    )

    return {
        key: anchor
        for key, anchor in {
            "rotational_symmetry": turning_primary_anchor,
            "turned_face_count": turning_primary_anchor,
            "turned_diameter_faces_count": turned_diameter_anchor,
            "turned_end_faces_count": turned_end_anchor,
            "turned_profile_faces_count": turning_primary_anchor,
            "outer_diameter_groove_count": outer_groove_anchor,
            "end_face_groove_count": end_face_groove_anchor,
            "hole_count": _anchor_from_first_candidate(
                component_node_name=component_node_name or None,
                face_lookup=face_lookup,
                candidates=hole_candidates,
                anchor_id="hole-any",
                label="Hole feature",
            ),
            "through_hole_count": _anchor_from_first_candidate(
                component_node_name=component_node_name or None,
                face_lookup=face_lookup,
                candidates=hole_candidates,
                anchor_id="hole-through",
                label="Through hole",
                subtype="through_hole",
            ),
            "bore_count": _anchor_from_first_candidate(
                component_node_name=component_node_name or None,
                face_lookup=face_lookup,
                candidates=hole_candidates,
                anchor_id="hole-bore",
                label="Bore feature",
                subtype="bore",
            ),
            "partial_hole_count": _anchor_from_first_candidate(
                component_node_name=component_node_name or None,
                face_lookup=face_lookup,
                candidates=hole_candidates,
                anchor_id="hole-partial",
                label="Partial hole",
                subtype="partial_hole",
            ),
            "stepped_hole_count": _anchor_from_first_candidate(
                component_node_name=component_node_name or None,
                face_lookup=face_lookup,
                candidates=hole_candidates,
                anchor_id="hole-stepped",
                label="Stepped hole",
                subtype="stepped_hole",
            ),
            "pocket_count": _first_geometry_anchor(open_pocket_anchor, closed_pocket_anchor),
            "open_pocket_count": open_pocket_anchor,
            "closed_pocket_count": closed_pocket_anchor,
            "milled_face_count": milled_anchor,
            "circular_milled_face_count": _anchor_from_first_group(
                component_node_name=component_node_name or None,
                face_lookup=face_lookup,
                groups=milled_face_detection.get("circular_milled_feature_groups") if isinstance(milled_face_detection, dict) else None,
                anchor_id="milled-circular",
                label="Circular milled face",
            ),
            "flat_milled_face_count": _anchor_from_first_group(
                component_node_name=component_node_name or None,
                face_lookup=face_lookup,
                groups=milled_face_detection.get("flat_milled_feature_groups") if isinstance(milled_face_detection, dict) else None,
                anchor_id="milled-flat",
                label="Flat milled face region",
            ),
            "flat_side_milled_face_count": _anchor_from_first_group(
                component_node_name=component_node_name or None,
                face_lookup=face_lookup,
                groups=milled_face_detection.get("flat_side_milled_feature_groups") if isinstance(milled_face_detection, dict) else None,
                anchor_id="milled-flat-side",
                label="Flat-side milled face region",
            ),
            "curved_milled_face_count": _anchor_from_first_group(
                component_node_name=component_node_name or None,
                face_lookup=face_lookup,
                groups=milled_face_detection.get("curved_milled_feature_groups") if isinstance(milled_face_detection, dict) else None,
                anchor_id="milled-curved",
                label="Curved milled face region",
            ),
            "convex_profile_edge_milled_face_count": _anchor_from_first_group(
                component_node_name=component_node_name or None,
                face_lookup=face_lookup,
                groups=milled_face_detection.get("convex_profile_edge_milled_feature_groups") if isinstance(milled_face_detection, dict) else None,
                anchor_id="milled-convex-profile",
                label="Convex profile-edge milled face",
            ),
            "concave_fillet_edge_milled_face_count": _anchor_from_first_group(
                component_node_name=component_node_name or None,
                face_lookup=face_lookup,
                groups=milled_face_detection.get("concave_fillet_edge_milled_feature_groups") if isinstance(milled_face_detection, dict) else None,
                anchor_id="milled-concave-fillet",
                label="Concave fillet-edge milled face",
            ),
            "boss_count": _anchor_from_first_candidate(
                component_node_name=component_node_name or None,
                face_lookup=face_lookup,
                candidates=boss_candidates,
                anchor_id="boss-any",
                label="Boss feature",
            ),
        }.items()
        if anchor
    }


def _first_geometry_anchor(*anchors: dict[str, Any] | None) -> dict[str, Any] | None:
    for anchor in anchors:
        if isinstance(anchor, dict):
            return anchor
    return None


def _anchor_from_first_candidate(
    *,
    component_node_name: str | None,
    face_lookup: dict[int, dict[str, Any]],
    candidates: list[dict[str, Any]],
    anchor_id: str,
    label: str,
    subtype: str | None = None,
) -> dict[str, Any] | None:
    for candidate in candidates:
        if subtype and str(candidate.get("subtype") or "").strip().lower() != subtype:
            continue
        anchor = _anchor_from_payload(
            component_node_name=component_node_name,
            face_lookup=face_lookup,
            payload=candidate,
            anchor_id=anchor_id,
            label=label,
        )
        if anchor:
            return anchor
    return None


def _anchor_from_first_payload(
    *,
    component_node_name: str | None,
    face_lookup: dict[int, dict[str, Any]],
    payloads: Any,
    anchor_id: str,
    label: str,
) -> dict[str, Any] | None:
    if not isinstance(payloads, list):
        return None
    for payload in payloads:
        anchor = _anchor_from_payload(
            component_node_name=component_node_name,
            face_lookup=face_lookup,
            payload=payload,
            anchor_id=anchor_id,
            label=label,
        )
        if anchor:
            return anchor
    return None


def _anchor_from_first_group(
    *,
    component_node_name: str | None,
    face_lookup: dict[int, dict[str, Any]],
    groups: Any,
    anchor_id: str,
    label: str,
) -> dict[str, Any] | None:
    if not isinstance(groups, list):
        return None
    for group in groups:
        anchor = _anchor_from_payload(
            component_node_name=component_node_name,
            face_lookup=face_lookup,
            payload=group,
            anchor_id=anchor_id,
            label=label,
        )
        if anchor:
            return anchor
    return None


def _anchor_from_face_indices(
    *,
    component_node_name: str | None,
    face_lookup: dict[int, dict[str, Any]],
    face_indices: Any,
    anchor_id: str,
    label: str,
) -> dict[str, Any] | None:
    return _build_geometry_anchor(
        component_node_name=component_node_name,
        face_lookup=face_lookup,
        face_indices=_extract_face_indices(face_indices),
        bbox_bounds=None,
        anchor_id=anchor_id,
        label=label,
    )


def _anchor_from_payload(
    *,
    component_node_name: str | None,
    face_lookup: dict[int, dict[str, Any]],
    payload: Any,
    anchor_id: str,
    label: str,
) -> dict[str, Any] | None:
    if payload is None:
        return None
    if isinstance(payload, list):
        return _build_geometry_anchor(
            component_node_name=component_node_name,
            face_lookup=face_lookup,
            face_indices=_extract_face_indices(payload),
            bbox_bounds=None,
            anchor_id=anchor_id,
            label=label,
        )
    if not isinstance(payload, dict):
        return None

    return _build_geometry_anchor(
        component_node_name=component_node_name,
        face_lookup=face_lookup,
        face_indices=_extract_face_indices(payload),
        bbox_bounds=payload.get("bbox_bounds"),
        anchor_id=anchor_id,
        label=str(payload.get("selection_reason") or label).replace("_", " ").strip().title()
        if payload.get("selection_reason")
        else label,
    )


def _build_geometry_anchor(
    *,
    component_node_name: str | None,
    face_lookup: dict[int, dict[str, Any]],
    face_indices: list[int],
    bbox_bounds: Any,
    anchor_id: str,
    label: str,
) -> dict[str, Any] | None:
    normalized_face_indices = sorted({face_index for face_index in face_indices if isinstance(face_index, int)})
    collected_bounds: list[tuple[float, float, float, float, float, float]] = []
    collected_positions: list[tuple[float, float, float]] = []
    normal: tuple[float, float, float] | None = None

    normalized_bbox = _normalize_bbox_bounds(bbox_bounds)
    if normalized_bbox is not None:
        collected_bounds.append(normalized_bbox)

    for face_index in normalized_face_indices:
        face = face_lookup.get(face_index)
        if not isinstance(face, dict):
            continue
        face_bbox = _normalize_bbox_bounds(face.get("bbox_bounds"))
        if face_bbox is not None:
            collected_bounds.append(face_bbox)
        face_position = _normalize_xyz(face.get("sample_point_mm")) or _normalize_xyz(face.get("centroid_mm"))
        if face_position is not None:
            collected_positions.append(face_position)
        if normal is None:
            normal = _normalize_xyz(face.get("sample_normal"))

    merged_bounds = _merge_bbox_bounds(collected_bounds)
    position = _mean_xyz(collected_positions) or _bbox_center(merged_bounds)
    if merged_bounds is None and position is None:
        return None

    return {
        "anchor_id": anchor_id,
        "component_node_name": component_node_name,
        "anchor_kind": "point" if len(normalized_face_indices) <= 1 else "region",
        "position_mm": list(position) if position is not None else None,
        "normal": list(normal) if normal is not None else None,
        "bbox_bounds_mm": list(merged_bounds) if merged_bounds is not None else None,
        "face_indices": normalized_face_indices,
        "label": label,
    }


def _extract_face_indices(payload: Any) -> list[int]:
    if isinstance(payload, dict):
        if isinstance(payload.get("group_face_indices"), list):
            return _extract_face_indices(payload.get("group_face_indices"))
        if isinstance(payload.get("face_indices"), list):
            return _extract_face_indices(payload.get("face_indices"))
        face_index = payload.get("face_index")
        return [face_index] if isinstance(face_index, int) else []
    if not isinstance(payload, list):
        return []
    return [int(face_index) for face_index in payload if isinstance(face_index, int)]


def _normalize_xyz(value: Any) -> tuple[float, float, float] | None:
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        return None
    coordinates = tuple(float(entry) for entry in value)
    if not all(isinstance(entry, float) and entry == entry for entry in coordinates):
        return None
    if not all(abs(entry) != float("inf") for entry in coordinates):
        return None
    return coordinates


def _normalize_bbox_bounds(value: Any) -> tuple[float, float, float, float, float, float] | None:
    if not isinstance(value, (list, tuple)) or len(value) != 6:
        return None
    bounds = tuple(float(entry) for entry in value)
    if not all(bound == bound and abs(bound) != float("inf") for bound in bounds):
        return None
    return bounds


def _merge_bbox_bounds(
    bounds_list: list[tuple[float, float, float, float, float, float]]
) -> tuple[float, float, float, float, float, float] | None:
    if not bounds_list:
        return None
    x_mins = [bounds[0] for bounds in bounds_list]
    y_mins = [bounds[1] for bounds in bounds_list]
    z_mins = [bounds[2] for bounds in bounds_list]
    x_maxs = [bounds[3] for bounds in bounds_list]
    y_maxs = [bounds[4] for bounds in bounds_list]
    z_maxs = [bounds[5] for bounds in bounds_list]
    return (
        min(x_mins),
        min(y_mins),
        min(z_mins),
        max(x_maxs),
        max(y_maxs),
        max(z_maxs),
    )


def _bbox_center(
    bounds: tuple[float, float, float, float, float, float] | None,
) -> tuple[float, float, float] | None:
    if bounds is None:
        return None
    return (
        (bounds[0] + bounds[3]) * 0.5,
        (bounds[1] + bounds[4]) * 0.5,
        (bounds[2] + bounds[5]) * 0.5,
    )


def _mean_xyz(points: list[tuple[float, float, float]]) -> tuple[float, float, float] | None:
    if not points:
        return None
    count = float(len(points))
    return (
        sum(point[0] for point in points) / count,
        sum(point[1] for point in points) / count,
        sum(point[2] for point in points) / count,
    )


def _geometry_count_fact(review_facts: dict[str, Any], *keys: str) -> int:
    value = _numeric_fact(review_facts, *keys)
    if value is None:
        return 0
    return max(0, int(round(value)))


def _geometry_reason_tags(
    *,
    rotational_symmetry: bool,
    turned_face_count: int,
    hole_count: int,
    pocket_count: int,
    groove_count: int,
    circular_milled_face_count: int,
) -> list[str]:
    tags: list[str] = []
    if rotational_symmetry:
        tags.append("Rotational symmetry detected")
    if turned_face_count > 0:
        tags.append(f"{turned_face_count} turned faces detected")
    if groove_count > 0:
        tags.append(
            f"{groove_count} groove feature{'s' if groove_count != 1 else ''} detected"
        )
    if circular_milled_face_count > 0:
        tags.append(
            f"{circular_milled_face_count} circular milled face{'s' if circular_milled_face_count != 1 else ''} detected"
        )
    if hole_count > 0:
        tags.append(f"{hole_count} hole feature{'s' if hole_count != 1 else ''} detected")
    elif pocket_count > 0:
        tags.append(
            f"{pocket_count} pocket feature{'s' if pocket_count != 1 else ''} detected"
        )
    return tags[:4]


def _turning_summary(*, rotational_symmetry: bool, turned_face_count: int) -> str:
    if rotational_symmetry and turned_face_count > 0:
        return (
            f"Rotational symmetry and {turned_face_count} turned faces suggest turning-dominant geometry."
        )
    if turned_face_count > 0:
        return f"{turned_face_count} turned faces were detected in the part geometry."
    if rotational_symmetry:
        return "Rotational symmetry suggests turning compatibility."
    return "Turning-style geometry evidence detected."


def _hole_summary(*, hole_count: int, through_hole_count: int, bore_count: int) -> str:
    fragments: list[str] = []
    if hole_count > 0:
        fragments.append(
            f"{hole_count} hole feature{'s' if hole_count != 1 else ''}"
        )
    if through_hole_count > 0:
        fragments.append(
            f"{through_hole_count} through hole{'s' if through_hole_count != 1 else ''}"
        )
    if bore_count > 0:
        fragments.append(f"{bore_count} bore{'s' if bore_count != 1 else ''}")
    if not fragments:
        return "Hole-style geometry evidence detected."
    return f"Detected {', '.join(fragments)}."


def _pocket_summary(*, pocket_count: int, open_pocket_count: int, closed_pocket_count: int) -> str:
    fragments: list[str] = []
    if pocket_count > 0:
        fragments.append(
            f"{pocket_count} pocket feature{'s' if pocket_count != 1 else ''}"
        )
    if open_pocket_count > 0:
        fragments.append(
            f"{open_pocket_count} open pocket{'s' if open_pocket_count != 1 else ''}"
        )
    if closed_pocket_count > 0:
        fragments.append(
            f"{closed_pocket_count} closed pocket{'s' if closed_pocket_count != 1 else ''}"
        )
    if not fragments:
        return "Pocket-style geometry evidence detected."
    return f"Detected {', '.join(fragments)}."


def _groove_summary(*, outer_diameter_groove_count: int, end_face_groove_count: int) -> str:
    fragments: list[str] = []
    if outer_diameter_groove_count > 0:
        fragments.append(
            f"{outer_diameter_groove_count} outer diameter groove{'s' if outer_diameter_groove_count != 1 else ''}"
        )
    if end_face_groove_count > 0:
        fragments.append(
            f"{end_face_groove_count} end-face groove{'s' if end_face_groove_count != 1 else ''}"
        )
    if not fragments:
        return "Groove-style geometry evidence detected."
    return f"Detected {', '.join(fragments)}."


def _milled_summary(*, milled_face_count: int, circular_milled_face_count: int) -> str:
    fragments: list[str] = []
    if milled_face_count > 0:
        fragments.append(
            f"{milled_face_count} milled face{'s' if milled_face_count != 1 else ''}"
        )
    if circular_milled_face_count > 0:
        fragments.append(
            f"{circular_milled_face_count} circular milled face{'s' if circular_milled_face_count != 1 else ''}"
        )
    if not fragments:
        return "Milled-face evidence detected."
    return f"Detected {', '.join(fragments)}."


def _boss_summary(*, boss_count: int) -> str:
    if boss_count > 0:
        return f"Detected {boss_count} boss feature{'s' if boss_count != 1 else ''}."
    return "Boss-style geometry evidence detected."


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

    component_node_name = _clean_optional_string(component_context.get("component_node_name"))
    if component_node_name:
        facts.setdefault("component_node_name", component_node_name)

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
    coverage_summary = _init_route_coverage_summary()

    findings: list[dict[str, Any]] = []
    evaluated_pack_ids: list[str] = []
    for rule in _iter_rules_for_plan(
        bundle,
        pack_ids,
        overlay_id,
        analysis_mode=analysis_mode,
    ):
        coverage_summary["rules_considered"] = int(coverage_summary.get("rules_considered", 0)) + 1
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
            rule_id = _clean_optional_string(rule.get("rule_id"))
            has_registered_evaluator = bool(
                rule_id and rule_id in RULE_VIOLATION_EVALUATORS
            )
            violation = _evaluate_rule_violation(rule, review_facts)
            if not violation:
                coverage_summary["checks_unresolved"] = int(
                    coverage_summary.get("checks_unresolved", 0)
                ) + 1
                if has_registered_evaluator:
                    coverage_summary["checks_unsupported_inputs"] = int(
                        coverage_summary.get("checks_unsupported_inputs", 0)
                    ) + 1
                else:
                    coverage_summary["checks_no_evaluator"] = int(
                        coverage_summary.get("checks_no_evaluator", 0)
                    ) + 1
                _update_standards_trace(
                    standards_trace=standards_trace,
                    bundle=bundle,
                    refs=refs,
                    outcome="unresolved",
                )
                continue
            if not violation.get("violated"):
                coverage_summary["checks_passed"] = int(
                    coverage_summary.get("checks_passed", 0)
                ) + 1
                _update_standards_trace(
                    standards_trace=standards_trace,
                    bundle=bundle,
                    refs=refs,
                    outcome="passed",
                )
                continue
            coverage_summary["design_risk_findings"] = int(
                coverage_summary.get("design_risk_findings", 0)
            ) + 1
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
            evidence = {
                "provided_inputs": required_inputs,
                "evaluation": violation.get("evaluation", {}),
            }
            violating_instances = violation.get("violating_instances")
            if isinstance(violating_instances, list) and violating_instances:
                evidence["violating_instances"] = violating_instances
            blame_map = _build_finding_blame_map(
                rule_id=_clean_optional_string(rule.get("rule_id")) or None,
                review_facts=review_facts,
                violation=violation,
                violating_instances=violating_instances
                if isinstance(violating_instances, list)
                else [],
            )
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
                "evidence": evidence,
            }
            if blame_map:
                finding["blame_map"] = blame_map
            findings.append(finding)
            continue
        coverage_summary["blocked_by_missing_inputs"] = int(
            coverage_summary.get("blocked_by_missing_inputs", 0)
        ) + 1
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
        "coverage_summary": _finalize_route_coverage_summary(coverage_summary),
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
    result = {
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
    if violated:
        result["violating_instances"] = _matching_wall_thickness_instances(
            review_facts,
            threshold=threshold,
        )
    return result


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
    result = {
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
    if violated:
        result["violating_instances"] = _matching_hole_instances(
            review_facts,
            ratio_threshold=hard_max,
        )
    return result


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
            "violating_instances": _matching_internal_radius_instances(
                review_facts,
                radius_floor=0.0,
                allow_zero_radius=True,
            ),
        }

    ratio = pocket_depth / corner_radius
    threshold = 8.0
    violated = ratio > threshold
    result = {
        "violated": violated,
        "evaluation": {
            "operator": "<=",
            "fact_key": "pocket_depth_to_corner_radius_ratio",
            "actual": round(ratio, 4),
            "threshold": threshold,
            "rule_expression": "(pocket_depth_mm / corner_radius_mm) <= 8.0",
        },
    }
    if violated:
        result["violating_instances"] = _matching_internal_radius_instances(
            review_facts,
            ratio_threshold=threshold,
        )
    return result


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
            "violating_instances": _matching_internal_radius_instances(
                review_facts,
                allow_zero_radius=True,
                min_pocket_depth=12.0,
            ),
        }

    depth_threshold = 12.0
    ratio_threshold = 10.0
    ratio = pocket_depth / corner_radius
    violated = pocket_depth > depth_threshold and ratio > ratio_threshold
    result = {
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
    if violated:
        result["violating_instances"] = _matching_internal_radius_instances(
            review_facts,
            ratio_threshold=ratio_threshold,
            min_pocket_depth=depth_threshold,
        )
    return result


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

    standard_diameters_mm = _standard_hole_diameters_mm()
    nearest = min(standard_diameters_mm, key=lambda value: abs(value - hole_diameter))
    tolerance = 0.15
    violated = abs(nearest - hole_diameter) > tolerance
    result = {
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
    if violated:
        result["violating_instances"] = _matching_hole_instances(
            review_facts,
            standard_diameters_mm=standard_diameters_mm,
            standard_tolerance_mm=tolerance,
        )
    return result


def _evaluate_cnc_004(review_facts: dict[str, Any]) -> dict[str, Any] | None:
    if not _truthy(review_facts.get("hole_features")):
        return None
    flat_bottom_required = _bool_fact(
        review_facts,
        "cad.holes.blind_flat_bottom_functional_required",
        "blind_hole_flat_bottom_required",
        "blind_hole_flat_bottom_functional",
        "hole_flat_bottom_functional",
    )
    if flat_bottom_required is None:
        flat_bottom_required = False
    return {
        "violated": flat_bottom_required,
        "evaluation": {
            "operator": "==",
            "fact_key": "blind_hole_flat_bottom_functional_required",
            "actual": flat_bottom_required,
            "threshold": False,
            "rule_expression": "blind_hole_flat_bottom_functional_required == false",
        },
    }


def _evaluate_cnc_020(review_facts: dict[str, Any]) -> dict[str, Any] | None:
    if not _truthy(review_facts.get("wall_thickness_map")):
        return None
    min_wall_thickness = _numeric_fact(
        review_facts,
        "min_wall_thickness",
        "min_wall_thickness_mm",
    )
    if min_wall_thickness is None:
        return None
    tight_tolerance_requested = _bool_fact(
        review_facts,
        "tight_tolerance_flag",
        "tight_tolerance_on_thin_walls",
        "cad.tolerances.tight_profile_on_thin_walls",
    )
    threshold = 1.2 if tight_tolerance_requested else 0.8
    violated = min_wall_thickness < threshold
    result = {
        "violated": violated,
        "evaluation": {
            "operator": ">=",
            "fact_key": "min_wall_thickness_mm",
            "actual": round(min_wall_thickness, 4),
            "threshold": threshold,
            "tight_tolerance_requested": bool(tight_tolerance_requested),
            "rule_expression": "min_wall_thickness_mm >= threshold_mm",
        },
    }
    if violated:
        result["violating_instances"] = _matching_wall_thickness_instances(
            review_facts,
            threshold=threshold,
        )
    return result


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
            "violating_instances": _matching_internal_radius_instances(
                review_facts,
                radius_floor=0.0,
                allow_zero_radius=True,
            ),
        }

    depth_to_radius = pocket_depth / min_radius
    radius_floor = 3.0
    ratio_threshold = 6.0
    violated = (min_radius < radius_floor) and (depth_to_radius > ratio_threshold)
    result = {
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
    if violated:
        result["violating_instances"] = _matching_internal_radius_instances(
            review_facts,
            radius_floor=radius_floor,
            ratio_threshold=ratio_threshold,
        )
    return result


def _evaluate_turn_001(review_facts: dict[str, Any]) -> dict[str, Any] | None:
    if not _truthy(review_facts.get("wall_thickness_map")):
        return None
    min_wall_thickness = _numeric_fact(
        review_facts,
        "min_wall_thickness",
        "min_wall_thickness_mm",
    )
    if min_wall_thickness is None:
        return None
    material_spec = _string_fact(review_facts.get("material_spec"))
    wall_threshold, material_class = _wall_threshold_for_material(material_spec)
    turning_threshold = max(0.8, wall_threshold + 0.2)
    violated = min_wall_thickness < turning_threshold
    result = {
        "violated": violated,
        "evaluation": {
            "operator": ">=",
            "fact_key": "min_wall_thickness_mm",
            "actual": round(min_wall_thickness, 4),
            "threshold": round(turning_threshold, 4),
            "material_class": material_class,
            "rule_expression": "min_wall_thickness_mm >= turning_material_threshold_mm",
        },
    }
    if violated:
        result["violating_instances"] = _matching_wall_thickness_instances(
            review_facts,
            threshold=turning_threshold,
        )
    return result


def _evaluate_turn_004(review_facts: dict[str, Any]) -> dict[str, Any] | None:
    if not _truthy(review_facts.get("hole_features")):
        return None
    hole_diameter = _numeric_fact(
        review_facts,
        "hole_diameter_mm",
        "hole_diameter",
        "min_hole_diameter_mm",
    )
    if hole_diameter is None or hole_diameter <= 0:
        return None
    radial_hole = _bool_fact(
        review_facts,
        "hole_orientation_radial",
        "radial_hole",
    )
    threshold = 2.5 if radial_hole else 2.0
    violated = hole_diameter < threshold
    result = {
        "violated": violated,
        "evaluation": {
            "operator": ">=",
            "fact_key": "hole_diameter_mm",
            "actual": round(hole_diameter, 4),
            "threshold": threshold,
            "hole_orientation": "radial" if radial_hole else "axial_or_unknown",
            "rule_expression": "hole_diameter_mm >= turning_min_hole_diameter_mm",
        },
    }
    if violated:
        result["violating_instances"] = _matching_hole_instances(
            review_facts,
            max_diameter=threshold,
        )
    return result


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

    result = {
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
    if violated:
        result["violating_instances"] = _matching_internal_radius_consistency_instances(
            review_facts,
            unique_threshold=unique_threshold,
            ratio_threshold=ratio_threshold,
        )
    return result


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

    result = {
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
    if violated:
        result["violating_instances"] = _matching_internal_radius_instances(
            review_facts,
            ratio_threshold=ratio_threshold,
            include_aggravating_factor=True,
        )
    return result


def _evaluate_food_002(review_facts: dict[str, Any]) -> dict[str, Any] | None:
    critical_corner_count = _numeric_fact(review_facts, "critical_corner_count")
    if critical_corner_count is None:
        return None

    violated = critical_corner_count > 0
    result = {
        "violated": violated,
        "evaluation": {
            "operator": "==",
            "fact_key": "critical_corner_count",
            "actual": round(critical_corner_count, 4),
            "threshold": 0.0,
            "rule_expression": "critical_corner_count == 0",
        },
    }
    if violated:
        result["violating_instances"] = _matching_critical_corner_instances(review_facts)
    return result


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
    result = {
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
    if violated:
        result["violating_instances"] = _matching_internal_radius_instances(
            review_facts,
            radius_floor=3.0,
        )
    return result


def _evaluate_fix_003(review_facts: dict[str, Any]) -> dict[str, Any] | None:
    min_wall = _numeric_fact(review_facts, "min_wall_thickness", "min_wall_thickness_mm")
    if min_wall is None:
        return None
    threshold = 1.5
    violated = min_wall < threshold
    result = {
        "violated": violated,
        "evaluation": {
            "operator": ">=",
            "fact_key": "min_wall_thickness_mm",
            "actual": round(min_wall, 4),
            "threshold": threshold,
            "rule_expression": "min_wall_thickness_mm >= 1.5",
        },
    }
    if violated:
        result["violating_instances"] = _matching_wall_thickness_instances(
            review_facts,
            threshold=threshold,
        )
    return result


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


def _evaluate_pstd_016(review_facts: dict[str, Any]) -> dict[str, Any] | None:
    material_spec = _string_fact(review_facts.get("material_spec"))
    if not material_spec:
        return None
    normalized = material_spec.lower()
    stainless_tokens = ("stainless", "316l", "1.4404", "304", "1.4301")
    stainless_detected = any(token in normalized for token in stainless_tokens)
    en10088_3_present = "en 10088-3" in normalized or "en10088-3" in normalized
    violated = stainless_detected and not en10088_3_present
    return {
        "violated": violated,
        "evaluation": {
            "operator": "contains_when_applicable",
            "fact_key": "material_spec",
            "actual": material_spec,
            "stainless_detected": stainless_detected,
            "threshold": "EN 10088-3 reference required for stainless specs",
            "en10088_3_reference_detected": en10088_3_present,
            "rule_expression": "if stainless material then material_spec contains 'EN 10088-3'",
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
    result = {
        "violated": count > 0,
        "evaluation": {
            "operator": "==",
            "fact_key": "cad.hygienic_design.crevice_count",
            "actual": round(count, 4),
            "threshold": 0,
            "rule_expression": "cad.hygienic_design.crevice_count == 0",
        },
    }
    if count > 0:
        result["violating_instances"] = _matching_critical_corner_instances(review_facts)
    return result


RULE_VIOLATION_EVALUATORS: dict[str, Any] = {
    "CNC-001": _evaluate_cnc_001,
    "CNC-002": _evaluate_cnc_002,
    "CNC-003": _evaluate_cnc_003,
    "CNC-004": _evaluate_cnc_004,
    "CNC-005": _evaluate_cnc_005,
    "CNC-006": _evaluate_cnc_006,
    "CNC-010": _evaluate_cnc_010,
    "CNC-013": _evaluate_cnc_013,
    "CNC-020": _evaluate_cnc_020,
    "CNC-024": _evaluate_cnc_024,
    "CNC-025": _evaluate_cnc_025,
    "FIX-003": _evaluate_fix_003,
    "FOOD-002": _evaluate_food_002,
    "FOOD-004": _evaluate_food_004,
    "SM-001": _evaluate_sm_001,
    "TURN-001": _evaluate_turn_001,
    "TURN-004": _evaluate_turn_004,
    "PSTD-001": _evaluate_pstd_001,
    "PSTD-004": _evaluate_pstd_004,
    "PSTD-008": _evaluate_pstd_008,
    "PSTD-009": _evaluate_pstd_009,
    "PSTD-012": _evaluate_pstd_012,
    "PSTD-016": _evaluate_pstd_016,
    "PSTD-019": _evaluate_pstd_019,
}


def _matching_internal_radius_instances(
    review_facts: dict[str, Any],
    *,
    radius_floor: float | None = None,
    ratio_threshold: float | None = None,
    min_pocket_depth: float | None = None,
    include_aggravating_factor: bool = False,
    allow_zero_radius: bool = False,
) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    for instance in _normalized_internal_radius_instances(review_facts):
        radius_mm = instance.get("radius_mm")
        if not isinstance(radius_mm, (int, float)):
            continue
        reasons: list[str] = []
        if allow_zero_radius and radius_mm <= 0:
            reasons.append("zero_or_negative_radius")
        if radius_floor is not None and radius_mm < radius_floor:
            reasons.append(f"radius_below_{radius_floor:.1f}_mm")
        if min_pocket_depth is not None:
            pocket_depth_mm = instance.get("pocket_depth_mm")
            if isinstance(pocket_depth_mm, (int, float)) and pocket_depth_mm > min_pocket_depth:
                reasons.append(f"pocket_depth_above_{min_pocket_depth:.1f}_mm")
        if ratio_threshold is not None:
            depth_to_radius_ratio = instance.get("depth_to_radius_ratio")
            if isinstance(depth_to_radius_ratio, (int, float)) and depth_to_radius_ratio > ratio_threshold:
                reasons.append(f"depth_to_radius_ratio_above_{ratio_threshold:.1f}")
        if include_aggravating_factor and bool(instance.get("aggravating_factor")):
            reasons.append("long_reach_tool_risk")
        if not reasons:
            continue
        enriched = dict(instance)
        enriched["violation_reasons"] = reasons
        matches.append(enriched)
    return matches


def _matching_internal_radius_consistency_instances(
    review_facts: dict[str, Any],
    *,
    unique_threshold: float,
    ratio_threshold: float,
) -> list[dict[str, Any]]:
    instances = _normalized_internal_radius_instances(review_facts)
    if not instances:
        return []

    rounded_radius_buckets: dict[float, int] = {}
    for instance in instances:
        radius_mm = instance.get("radius_mm")
        if isinstance(radius_mm, (int, float)):
            rounded_radius = round(float(radius_mm), 3)
            rounded_radius_buckets[rounded_radius] = rounded_radius_buckets.get(rounded_radius, 0) + 1

    dominant_radius = None
    if rounded_radius_buckets:
        dominant_radius = max(
            rounded_radius_buckets.items(),
            key=lambda item: (item[1], -abs(item[0])),
        )[0]

    numeric_radii = [
        float(instance["radius_mm"])
        for instance in instances
        if isinstance(instance.get("radius_mm"), (int, float))
    ]
    min_radius = min(numeric_radii) if numeric_radii else None
    max_radius = max(numeric_radii) if numeric_radii else None
    aggregate_unique_count = _numeric_fact(review_facts, "unique_internal_radius_count")
    unique_count = max(float(len(rounded_radius_buckets)), float(aggregate_unique_count or 0.0))
    aggregate_ratio = _numeric_fact(review_facts, "radius_variation_ratio")
    ratio = None
    if min_radius is not None and min_radius > 0 and max_radius is not None:
        ratio = max_radius / min_radius
    if aggregate_ratio is not None:
        ratio = max(ratio or 0.0, float(aggregate_ratio))

    matches: list[dict[str, Any]] = []
    for instance in instances:
        radius_mm = instance.get("radius_mm")
        if not isinstance(radius_mm, (int, float)):
            continue
        reasons: list[str] = []
        rounded_radius = round(float(radius_mm), 3)
        if dominant_radius is not None and unique_count > unique_threshold and rounded_radius != dominant_radius:
            reasons.append("non_dominant_corner_radius")
        if (
            ratio is not None
            and ratio > ratio_threshold
            and (rounded_radius == round(min_radius, 3) or rounded_radius == round(max_radius, 3))
        ):
            reasons.append(f"radius_variation_ratio_above_{ratio_threshold:.1f}")
        if not reasons:
            continue
        enriched = dict(instance)
        enriched["violation_reasons"] = reasons
        matches.append(enriched)
    return matches


def _matching_critical_corner_instances(review_facts: dict[str, Any]) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    for instance in _normalized_internal_radius_instances(review_facts):
        status = _clean_optional_string(instance.get("status")).upper()
        if status != "CRITICAL":
            continue
        enriched = dict(instance)
        enriched["violation_reasons"] = ["critical_corner_crevice"]
        matches.append(enriched)
    return matches


def _matching_hole_instances(
    review_facts: dict[str, Any],
    *,
    ratio_threshold: float | None = None,
    max_diameter: float | None = None,
    standard_diameters_mm: list[float] | None = None,
    standard_tolerance_mm: float | None = None,
) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    for instance in _normalized_hole_instances(review_facts):
        reasons: list[str] = []
        diameter_mm = instance.get("diameter_mm")
        if isinstance(max_diameter, (int, float)) and isinstance(diameter_mm, (int, float)):
            if diameter_mm < max_diameter:
                reasons.append(f"diameter_below_{max_diameter:.1f}_mm")
        depth_ratio = instance.get("depth_to_diameter_ratio")
        if isinstance(ratio_threshold, (int, float)) and isinstance(depth_ratio, (int, float)):
            if depth_ratio > ratio_threshold:
                reasons.append(f"depth_to_diameter_ratio_above_{ratio_threshold:.1f}")
        if (
            standard_diameters_mm
            and isinstance(standard_tolerance_mm, (int, float))
            and isinstance(diameter_mm, (int, float))
        ):
            nearest = min(standard_diameters_mm, key=lambda value: abs(value - diameter_mm))
            if abs(nearest - diameter_mm) > standard_tolerance_mm:
                reasons.append("non_standard_hole_diameter")
        if not reasons:
            continue
        enriched = dict(instance)
        enriched["violation_reasons"] = reasons
        matches.append(enriched)
    return matches


def _matching_wall_thickness_instances(
    review_facts: dict[str, Any],
    *,
    threshold: float,
) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    for instance in _normalized_wall_thickness_instances(review_facts):
        thickness_mm = instance.get("thickness_mm")
        if not isinstance(thickness_mm, (int, float)):
            continue
        if thickness_mm >= threshold:
            continue
        enriched = dict(instance)
        enriched["violation_reasons"] = [f"wall_thickness_below_{threshold:.1f}_mm"]
        matches.append(enriched)
    return matches


def _build_finding_blame_map(
    *,
    rule_id: str | None,
    review_facts: dict[str, Any],
    violation: dict[str, Any],
    violating_instances: list[dict[str, Any]],
) -> dict[str, Any] | None:
    component_node_name = _clean_optional_string(review_facts.get("component_node_name")) or None
    evaluation = violation.get("evaluation")
    source_fact_keys: list[str] = []
    if isinstance(evaluation, dict):
        fact_key = _clean_optional_string(evaluation.get("fact_key"))
        if fact_key:
            source_fact_keys.append(fact_key)
        fact_keys = evaluation.get("fact_keys")
        if isinstance(fact_keys, list):
            for candidate in fact_keys:
                cleaned = _clean_optional_string(candidate)
                if cleaned and cleaned not in source_fact_keys:
                    source_fact_keys.append(cleaned)

    if not violating_instances:
        if not component_node_name:
            return None
        return {
            "localization_status": "part_level",
            "primary_anchor": {
                "anchor_id": f"{rule_id or 'dfm'}-part-level",
                "component_node_name": component_node_name,
                "anchor_kind": "part",
                "position_mm": None,
                "normal": None,
                "bbox_bounds_mm": None,
                "face_indices": [],
                "label": "Whole part focus",
            },
            "secondary_anchors": [],
            "source_fact_keys": source_fact_keys,
            "source_feature_refs": [],
            "explanation": f"Whole-part focus for {rule_id or 'DFM finding'}; no exact local region is preserved yet.",
        }

    anchor_entries: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for instance in violating_instances:
        if not isinstance(instance, dict):
            continue
        anchor = _anchor_from_violating_instance(
            instance=instance,
            component_node_name=component_node_name,
            rule_id=rule_id,
        )
        if anchor:
            anchor_entries.append((instance, anchor))

    if not anchor_entries:
        if not component_node_name:
            return None
        return {
            "localization_status": "part_level",
            "primary_anchor": {
                "anchor_id": f"{rule_id or 'dfm'}-part-level",
                "component_node_name": component_node_name,
                "anchor_kind": "part",
                "position_mm": None,
                "normal": None,
                "bbox_bounds_mm": None,
                "face_indices": [],
                "label": "Whole part focus",
            },
            "secondary_anchors": [],
            "source_fact_keys": source_fact_keys,
            "source_feature_refs": [],
            "explanation": f"Whole-part focus for {rule_id or 'DFM finding'}; no exact local region is preserved yet.",
        }

    primary_index = _select_primary_blame_anchor_index(anchor_entries)
    primary_instance, primary_anchor = anchor_entries[primary_index]
    secondary_anchors = [
        anchor
        for index, (_, anchor) in enumerate(anchor_entries)
        if index != primary_index
    ]

    source_feature_refs = [
        _clean_optional_string(instance.get("instance_id"))
        for instance, _ in anchor_entries
        if _clean_optional_string(instance.get("instance_id"))
    ]

    if len(anchor_entries) > 1:
        localization_status = "multi"
    elif primary_anchor.get("anchor_kind") == "region":
        localization_status = "region"
    else:
        localization_status = "exact_feature"

    return {
        "localization_status": localization_status,
        "primary_anchor": primary_anchor,
        "secondary_anchors": secondary_anchors,
        "source_fact_keys": source_fact_keys,
        "source_feature_refs": source_feature_refs,
        "explanation": _build_blame_map_explanation(
            rule_id=rule_id,
            primary_instance=primary_instance,
            anchor_count=len(anchor_entries),
        ),
    }


def _anchor_from_violating_instance(
    *,
    instance: dict[str, Any],
    component_node_name: str | None,
    rule_id: str | None,
) -> dict[str, Any] | None:
    bbox_bounds = _rounded_bbox_bounds(instance.get("bbox_bounds_mm"))
    position = _rounded_point(instance.get("position_mm"))
    if bbox_bounds is None and position is None:
        return None

    instance_id = _clean_optional_string(instance.get("instance_id")) or "instance"
    label = _clean_optional_string(instance.get("location_description")) or instance_id
    face_indices = [
        int(face_index)
        for face_index in instance.get("face_indices", [])
        if isinstance(face_index, int)
    ]

    return {
        "anchor_id": f"{rule_id or 'dfm'}-{instance_id}",
        "component_node_name": component_node_name,
        "anchor_kind": "region" if bbox_bounds is not None else "point",
        "position_mm": position,
        "normal": None,
        "bbox_bounds_mm": bbox_bounds,
        "face_indices": face_indices,
        "label": label,
    }


def _select_primary_blame_anchor_index(
    anchor_entries: list[tuple[dict[str, Any], dict[str, Any]]],
) -> int:
    best_index = 0
    best_score = -1
    for index, (instance, anchor) in enumerate(anchor_entries):
        reason_count = (
            len(instance.get("violation_reasons", []))
            if isinstance(instance.get("violation_reasons"), list)
            else 0
        )
        score = reason_count * 100
        if anchor.get("bbox_bounds_mm") is not None:
            score += 10
        if bool(instance.get("aggravating_factor")):
            score += 5
        if score > best_score:
            best_score = score
            best_index = index
    return best_index


def _build_blame_map_explanation(
    *,
    rule_id: str | None,
    primary_instance: dict[str, Any],
    anchor_count: int,
) -> str:
    label = _clean_optional_string(primary_instance.get("location_description")) or _clean_optional_string(
        primary_instance.get("instance_id")
    )
    if anchor_count > 1 and label:
        return f"Primary mapped region for {rule_id or 'DFM finding'} chosen from {anchor_count} localized locations: {label}."
    if label:
        return f"Mapped region for {rule_id or 'DFM finding'}: {label}."
    return f"Primary mapped region for {rule_id or 'DFM finding'}."


def _normalized_internal_radius_instances(review_facts: dict[str, Any]) -> list[dict[str, Any]]:
    payload = review_facts.get("internal_radius_instances")
    if not isinstance(payload, list):
        return []
    normalized: list[dict[str, Any]] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        radius_mm = _optional_float(item.get("radius_mm"))
        if radius_mm is None:
            continue
        normalized.append(
            {
                "instance_id": _clean_optional_string(item.get("instance_id"))
                or f"corner_{len(normalized) + 1}",
                "edge_index": _optional_int(item.get("edge_index")),
                "location_description": _clean_optional_string(item.get("location_description")),
                "radius_mm": round(radius_mm, 4),
                "status": _clean_optional_string(item.get("status")) or None,
                "recommendation": _clean_optional_string(item.get("recommendation")) or None,
                "pocket_depth_mm": _rounded_optional_float(item.get("pocket_depth_mm")),
                "depth_to_radius_ratio": _rounded_optional_float(item.get("depth_to_radius_ratio")),
                "aggravating_factor": bool(item.get("aggravating_factor")),
                "position_mm": _rounded_point(item.get("position_mm")),
                "bbox_bounds_mm": _rounded_bbox_bounds(item.get("bbox_bounds_mm")),
            }
        )
    return normalized


def _normalized_hole_instances(review_facts: dict[str, Any]) -> list[dict[str, Any]]:
    payload = review_facts.get("hole_instances")
    if not isinstance(payload, list):
        return []
    normalized: list[dict[str, Any]] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        diameter_mm = _optional_float(item.get("diameter_mm"))
        if diameter_mm is None or diameter_mm <= 0:
            continue
        normalized.append(
            {
                "instance_id": _clean_optional_string(item.get("instance_id"))
                or f"hole_{len(normalized) + 1}",
                "subtype": _clean_optional_string(item.get("subtype")) or None,
                "location_description": _clean_optional_string(item.get("location_description")),
                "diameter_mm": round(diameter_mm, 4),
                "depth_mm": _rounded_optional_float(item.get("depth_mm")),
                "depth_to_diameter_ratio": _rounded_optional_float(item.get("depth_to_diameter_ratio")),
                "position_mm": _rounded_point(item.get("position_mm")),
                "bbox_bounds_mm": _rounded_bbox_bounds(item.get("bbox_bounds_mm")),
                "face_indices": [
                    int(face_index)
                    for face_index in item.get("face_indices", [])
                    if isinstance(face_index, int)
                ],
            }
        )
    return normalized


def _normalized_wall_thickness_instances(review_facts: dict[str, Any]) -> list[dict[str, Any]]:
    payload = review_facts.get("wall_thickness_instances")
    if not isinstance(payload, list):
        return []
    normalized: list[dict[str, Any]] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        thickness_mm = _optional_float(item.get("thickness_mm"))
        if thickness_mm is None or thickness_mm <= 0:
            continue
        normalized.append(
            {
                "instance_id": _clean_optional_string(item.get("instance_id"))
                or f"wall_{len(normalized) + 1}",
                "location_description": _clean_optional_string(item.get("location_description")),
                "thickness_mm": round(thickness_mm, 4),
                "position_mm": _rounded_point(item.get("position_mm")),
                "bbox_bounds_mm": _rounded_bbox_bounds(item.get("bbox_bounds_mm")),
                "face_indices": [
                    int(face_index)
                    for face_index in item.get("face_indices", [])
                    if isinstance(face_index, int)
                ],
            }
        )
    return normalized


def _standard_hole_diameters_mm() -> list[float]:
    return [
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


def _optional_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        candidate = float(value)
        if candidate == candidate and candidate not in (float("inf"), float("-inf")):
            return candidate
    return None


def _optional_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None


def _rounded_optional_float(value: Any) -> float | None:
    candidate = _optional_float(value)
    if candidate is None:
        return None
    return round(candidate, 4)


def _rounded_point(value: Any) -> list[float] | None:
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        return None
    rounded: list[float] = []
    for axis_value in value:
        candidate = _optional_float(axis_value)
        if candidate is None:
            return None
        rounded.append(round(candidate, 4))
    return rounded


def _rounded_bbox_bounds(value: Any) -> list[float] | None:
    if not isinstance(value, (list, tuple)) or len(value) != 6:
        return None
    rounded: list[float] = []
    for axis_value in value:
        candidate = _optional_float(axis_value)
        if candidate is None:
            return None
        rounded.append(round(candidate, 4))
    return rounded


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


def _init_route_coverage_summary() -> dict[str, int]:
    return {
        "rules_considered": 0,
        "checks_passed": 0,
        "design_risk_findings": 0,
        "blocked_by_missing_inputs": 0,
        "checks_unresolved": 0,
        "checks_no_evaluator": 0,
        "checks_unsupported_inputs": 0,
    }


def _finalize_route_coverage_summary(summary: dict[str, int]) -> dict[str, Any]:
    rules_considered = int(summary.get("rules_considered", 0))
    checks_passed = int(summary.get("checks_passed", 0))
    design_risk_findings = int(summary.get("design_risk_findings", 0))
    blocked_by_missing_inputs = int(summary.get("blocked_by_missing_inputs", 0))
    checks_unresolved = int(summary.get("checks_unresolved", 0))
    checks_no_evaluator = int(summary.get("checks_no_evaluator", 0))
    checks_unsupported_inputs = int(summary.get("checks_unsupported_inputs", 0))
    checks_evaluated = checks_passed + design_risk_findings
    evaluated_ratio = (
        round(checks_evaluated / float(rules_considered), 4)
        if rules_considered
        else 0.0
    )
    return {
        "rules_considered": rules_considered,
        "checks_evaluated": checks_evaluated,
        "checks_passed": checks_passed,
        "design_risk_findings": design_risk_findings,
        "blocked_by_missing_inputs": blocked_by_missing_inputs,
        "checks_unresolved": checks_unresolved,
        "checks_no_evaluator": checks_no_evaluator,
        "checks_unsupported_inputs": checks_unsupported_inputs,
        "evaluated_ratio": evaluated_ratio,
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
