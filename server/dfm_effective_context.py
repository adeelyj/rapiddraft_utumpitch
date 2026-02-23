from __future__ import annotations

from typing import Any

from .dfm_bundle import DfmBundle

PROCESS_MODES = {"auto", "profile", "override"}
OVERLAY_MODES = {"none", "profile", "override"}
ANALYSIS_MODES = {"geometry_dfm", "drawing_spec", "full"}


def resolve_effective_planning_inputs(
    bundle: DfmBundle,
    *,
    planning_inputs: dict[str, Any],
    component_profile: dict[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    profile = component_profile if isinstance(component_profile, dict) else {}
    process_map = _index_by_id(bundle.process_classifier.get("process_families", []), "process_id")
    overlay_map = _index_by_id(bundle.overlays.get("overlays", []), "overlay_id")

    resolved = dict(planning_inputs)
    requested_process_override = _clean_optional_string(resolved.get("selected_process_override"))
    requested_overlay = _clean_optional_string(resolved.get("selected_overlay"))
    profile_process = _clean_optional_string(profile.get("manufacturingProcess"))
    profile_industry = _clean_optional_string(profile.get("industry"))

    process_mode = _normalize_process_mode(
        mode_value=resolved.get("process_selection_mode"),
        requested_override=requested_process_override,
    )
    overlay_mode = _normalize_overlay_mode(
        mode_value=resolved.get("overlay_selection_mode"),
        requested_overlay=requested_overlay,
    )
    requested_analysis_mode = _clean_optional_string(resolved.get("analysis_mode")).lower()
    analysis_mode = _normalize_analysis_mode(requested_analysis_mode)

    mapped_profile_process_id = _match_profile_label_to_id(
        options=process_map,
        label=profile_process,
        label_key="label",
    )
    mapped_profile_overlay_id = _match_profile_label_to_id(
        options=overlay_map,
        label=profile_industry,
        label_key="label",
    )

    effective_process_id = _resolve_process_id(
        mode=process_mode,
        requested_override=requested_process_override,
        mapped_profile_id=mapped_profile_process_id,
    )
    effective_overlay_id = _resolve_overlay_id(
        mode=overlay_mode,
        requested_overlay=requested_overlay,
        mapped_profile_id=mapped_profile_overlay_id,
    )

    resolved["selected_process_override"] = effective_process_id
    resolved["selected_overlay"] = effective_overlay_id
    resolved["process_selection_mode"] = process_mode
    resolved["overlay_selection_mode"] = overlay_mode
    resolved["analysis_mode"] = analysis_mode

    effective_context = {
        "analysis_mode": {
            "selected_mode": analysis_mode,
            "source": "user_selection" if requested_analysis_mode else "default_full",
        },
        "process": {
            "selection_mode": process_mode,
            "source": _process_source(
                mode=process_mode,
                profile_value=profile_process,
                mapped_profile_id=mapped_profile_process_id,
                requested_override=requested_process_override,
            ),
            "profile_value": profile_process or None,
            "profile_mapped_process_id": mapped_profile_process_id,
            "requested_override": requested_process_override or None,
            "effective_process_id": effective_process_id,
            "effective_process_label": _label_for_id(
                process_map, effective_process_id, label_key="label"
            ),
        },
        "overlay": {
            "selection_mode": overlay_mode,
            "source": _overlay_source(
                mode=overlay_mode,
                profile_value=profile_industry,
                mapped_profile_id=mapped_profile_overlay_id,
                requested_override=requested_overlay,
            ),
            "profile_value": profile_industry or None,
            "profile_mapped_overlay_id": mapped_profile_overlay_id,
            "requested_override": requested_overlay or None,
            "effective_overlay_id": effective_overlay_id,
            "effective_overlay_label": _label_for_id(
                overlay_map, effective_overlay_id, label_key="label"
            ),
        },
    }
    return resolved, effective_context


def _normalize_analysis_mode(mode_value: Any) -> str:
    mode = _clean_optional_string(mode_value).lower()
    if mode in ANALYSIS_MODES:
        return mode
    return "full"


def _normalize_process_mode(
    *,
    mode_value: Any,
    requested_override: str,
) -> str:
    mode = _clean_optional_string(mode_value).lower()
    if mode in PROCESS_MODES:
        return mode
    return "override" if requested_override else "auto"


def _normalize_overlay_mode(
    *,
    mode_value: Any,
    requested_overlay: str,
) -> str:
    mode = _clean_optional_string(mode_value).lower()
    if mode in OVERLAY_MODES:
        return mode
    return "override" if requested_overlay else "none"


def _resolve_process_id(
    *,
    mode: str,
    requested_override: str,
    mapped_profile_id: str | None,
) -> str | None:
    if mode == "profile":
        return mapped_profile_id
    if mode == "override":
        return requested_override or None
    return None


def _resolve_overlay_id(
    *,
    mode: str,
    requested_overlay: str,
    mapped_profile_id: str | None,
) -> str | None:
    if mode == "profile":
        return mapped_profile_id
    if mode == "override":
        return requested_overlay or None
    return None


def _process_source(
    *,
    mode: str,
    profile_value: str,
    mapped_profile_id: str | None,
    requested_override: str,
) -> str:
    if mode == "profile":
        if mapped_profile_id:
            return "profile_mapped"
        if profile_value:
            return "profile_unmapped_fallback_auto"
        return "profile_missing_fallback_auto"
    if mode == "override":
        if requested_override:
            return "user_override"
        return "override_missing_fallback_auto"
    return "auto_ai"


def _overlay_source(
    *,
    mode: str,
    profile_value: str,
    mapped_profile_id: str | None,
    requested_override: str,
) -> str:
    if mode == "profile":
        if mapped_profile_id:
            return "profile_mapped"
        if profile_value:
            return "profile_unmapped_none"
        return "profile_missing_none"
    if mode == "override":
        if requested_override:
            return "user_override"
        return "override_none"
    return "none"


def _match_profile_label_to_id(
    *,
    options: dict[str, dict[str, Any]],
    label: str,
    label_key: str,
) -> str | None:
    normalized_target = _normalize_token(label)
    if not normalized_target:
        return None

    for option_id, option in options.items():
        label_value = _normalize_token(_clean_optional_string(option.get(label_key)))
        if normalized_target == _normalize_token(option_id) or (
            label_value and normalized_target == label_value
        ):
            return option_id

    for option_id, option in options.items():
        label_value = _normalize_token(_clean_optional_string(option.get(label_key)))
        if not label_value:
            continue
        if normalized_target in label_value or label_value in normalized_target:
            return option_id
    return None


def _label_for_id(
    options: dict[str, dict[str, Any]],
    option_id: str | None,
    *,
    label_key: str,
) -> str | None:
    if not option_id:
        return None
    option = options.get(option_id)
    if not option:
        return option_id
    label = option.get(label_key)
    if isinstance(label, str) and label.strip():
        return label.strip()
    return option_id


def _index_by_id(items: list[Any], id_key: str) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        item_id = item.get(id_key)
        if isinstance(item_id, str) and item_id:
            indexed[item_id] = item
    return indexed


def _clean_optional_string(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip()


def _normalize_token(value: str) -> str:
    return " ".join(value.strip().lower().split())
