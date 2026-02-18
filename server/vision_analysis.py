from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .vision_providers import VisionProviderError, build_default_providers
from .vision_views import (
    VisionViewSetError,
    VisionViewSetNotFoundError,
    VisionViewSetService,
)

if TYPE_CHECKING:
    from .cad_service_occ import CADServiceOCC

CONFIDENCE_ORDER = {
    "low": 0,
    "medium": 1,
    "high": 2,
}
SEVERITY_ORDER = {
    "info": 0,
    "caution": 1,
    "warning": 2,
    "critical": 3,
}
VALID_CONFIDENCE = set(CONFIDENCE_ORDER.keys())
VALID_SENSITIVITY = set(CONFIDENCE_ORDER.keys())


class VisionAnalysisError(RuntimeError):
    pass


class VisionExecutionError(VisionAnalysisError):
    pass


class VisionReportNotFoundError(VisionAnalysisError):
    pass


class VisionViewSetMissingError(VisionAnalysisError):
    pass


@dataclass
class VisionCriteria:
    check_internal_pocket_tight_corners: bool = True
    check_tool_access_risk: bool = True
    check_annotation_note_scan: bool = True
    sensitivity: str = "medium"
    max_flagged_features: int = 8
    confidence_threshold: str = "medium"

    def to_dict(self) -> dict[str, Any]:
        return {
            "checks": {
                "internal_pocket_tight_corners": self.check_internal_pocket_tight_corners,
                "tool_access_risk": self.check_tool_access_risk,
                "annotation_note_scan": self.check_annotation_note_scan,
            },
            "sensitivity": self.sensitivity,
            "max_flagged_features": self.max_flagged_features,
            "confidence_threshold": self.confidence_threshold,
        }


def parse_vision_criteria(criteria_payload: dict[str, Any] | None) -> VisionCriteria:
    if not isinstance(criteria_payload, dict):
        return VisionCriteria()

    checks = criteria_payload.get("checks")
    if not isinstance(checks, dict):
        checks = {}

    sensitivity = _normalize_confidence_label(criteria_payload.get("sensitivity"), fallback="medium")
    confidence_threshold = _normalize_confidence_label(
        criteria_payload.get("confidence_threshold"),
        fallback="medium",
    )

    max_flagged_features = criteria_payload.get("max_flagged_features")
    if isinstance(max_flagged_features, bool):
        max_flagged_features = 8
    if not isinstance(max_flagged_features, int):
        max_flagged_features = 8
    max_flagged_features = max(1, min(50, max_flagged_features))

    return VisionCriteria(
        check_internal_pocket_tight_corners=_as_bool(
            checks.get("internal_pocket_tight_corners"),
            default=True,
        ),
        check_tool_access_risk=_as_bool(
            checks.get("tool_access_risk"),
            default=True,
        ),
        check_annotation_note_scan=_as_bool(
            checks.get("annotation_note_scan"),
            default=True,
        ),
        sensitivity=sensitivity if sensitivity in VALID_SENSITIVITY else "medium",
        max_flagged_features=max_flagged_features,
        confidence_threshold=confidence_threshold,
    )


def merge_view_results(
    parsed_by_view: list[dict[str, Any]],
) -> dict[str, Any]:
    aggregated: dict[str, dict[str, Any]] = {}
    confidence_values: list[str] = []
    observation_lines: list[str] = []

    for item in parsed_by_view:
        view_name = str(item.get("view_name") or "").strip().lower() or "unknown"
        confidence = _normalize_confidence_label(item.get("confidence"), fallback="medium")
        confidence_values.append(confidence)

        observations = str(item.get("general_observations") or "").strip()
        if observations:
            observation_lines.append(f"[{view_name}] {observations}")

        findings = item.get("flagged_features")
        if not isinstance(findings, list):
            continue

        for raw_finding in findings:
            if not isinstance(raw_finding, dict):
                continue
            description = str(raw_finding.get("description") or "").strip()
            if not description:
                continue
            key = _normalize_description_key(description)
            severity = _normalize_severity(raw_finding.get("severity"))
            finding_confidence = _normalize_confidence_label(
                raw_finding.get("confidence"),
                fallback=confidence,
            )

            existing = aggregated.get(key)
            if not existing:
                aggregated[key] = {
                    "description": description,
                    "severity": severity,
                    "confidence": finding_confidence,
                    "source_views": [view_name],
                }
                continue

            if SEVERITY_ORDER[severity] > SEVERITY_ORDER[existing["severity"]]:
                existing["severity"] = severity

            current_conf = existing.get("confidence", "medium")
            if current_conf != finding_confidence:
                existing["confidence"] = "low"
            else:
                existing["confidence"] = current_conf

            source_views = set(existing.get("source_views", []))
            source_views.add(view_name)
            existing["source_views"] = sorted(source_views)

    merged_confidence = "medium"
    distinct_confidence = {value for value in confidence_values if value in VALID_CONFIDENCE}
    if len(distinct_confidence) > 1:
        merged_confidence = "low"
    elif len(distinct_confidence) == 1:
        merged_confidence = next(iter(distinct_confidence))

    findings = list(aggregated.values())
    findings.sort(
        key=lambda finding: (
            -SEVERITY_ORDER.get(finding.get("severity", "info"), 0),
            finding.get("description", ""),
        )
    )

    normalized_findings: list[dict[str, Any]] = []
    for index, finding in enumerate(findings, start=1):
        normalized_findings.append(
            {
                "feature_id": f"V{index}",
                "description": finding["description"],
                "severity": finding["severity"],
                "confidence": finding["confidence"],
                "source_views": finding.get("source_views", []),
            }
        )

    return {
        "flagged_features": normalized_findings,
        "general_observations": "\n".join(observation_lines),
        "confidence": merged_confidence,
    }


def normalize_provider_result(
    raw_payload: dict[str, Any],
    *,
    fallback_view: str | None = None,
) -> dict[str, Any]:
    findings = raw_payload.get("flagged_features")
    if not isinstance(findings, list):
        findings = []

    normalized_findings: list[dict[str, Any]] = []
    for item in findings:
        if isinstance(item, str):
            description = item.strip()
            if not description:
                continue
            normalized_findings.append(
                {
                    "description": description,
                    "severity": "warning",
                    "confidence": "medium",
                    "source_views": [fallback_view] if fallback_view else [],
                }
            )
            continue

        if not isinstance(item, dict):
            continue

        description = str(item.get("description") or "").strip()
        if not description:
            continue

        severity = _normalize_severity(item.get("severity"))
        confidence = _normalize_confidence_label(item.get("confidence"), fallback="medium")

        source_views_raw = item.get("source_views")
        source_views: list[str] = []
        if isinstance(source_views_raw, list):
            for source in source_views_raw:
                if isinstance(source, str) and source.strip():
                    source_views.append(source.strip().lower())

        if fallback_view and fallback_view not in source_views:
            source_views.append(fallback_view)

        normalized_findings.append(
            {
                "description": description,
                "severity": severity,
                "confidence": confidence,
                "source_views": sorted(set(source_views)),
            }
        )

    overall_confidence = _normalize_confidence_label(raw_payload.get("confidence"), fallback="medium")
    general_observations = str(raw_payload.get("general_observations") or "").strip()

    normalized_with_ids: list[dict[str, Any]] = []
    for index, finding in enumerate(normalized_findings, start=1):
        normalized_with_ids.append(
            {
                "feature_id": f"V{index}",
                "description": finding["description"],
                "severity": finding["severity"],
                "confidence": finding["confidence"],
                "source_views": finding["source_views"],
            }
        )

    return {
        "flagged_features": normalized_with_ids,
        "general_observations": general_observations,
        "confidence": overall_confidence,
        "view_name": fallback_view,
    }


class VisionAnalysisService:
    REQUIRED_VIEWS = ("x", "y", "z")

    def __init__(
        self,
        *,
        root: Path,
        occ_service: "CADServiceOCC",
        view_set_service: VisionViewSetService | None = None,
        providers: dict[str, Any] | None = None,
    ) -> None:
        self.root = root
        self.view_set_service = view_set_service or VisionViewSetService(
            root=root,
            occ_service=occ_service,
        )
        self.providers = providers or build_default_providers()

    def list_providers(self) -> dict[str, Any]:
        ordered_keys = ["openai", "claude", "local"]
        providers_payload: list[dict[str, Any]] = []
        for key in ordered_keys:
            provider = self.providers.get(key)
            if provider is None:
                continue
            provider_entry = provider.availability()
            provider_entry["id"] = key
            providers_payload.append(provider_entry)

        default_provider = "openai"
        for candidate in ordered_keys:
            provider = self.providers.get(candidate)
            if provider and provider.configured:
                default_provider = candidate
                break

        local_provider = self.providers.get("local")
        local_base_url = "http://127.0.0.1:1234/v1"
        if local_provider and isinstance(getattr(local_provider, "base_url", None), str):
            local_base_url = local_provider.base_url

        return {
            "providers": providers_payload,
            "default_provider": default_provider,
            "local_defaults": {
                "base_url": local_base_url,
            },
        }

    def create_view_set(
        self,
        *,
        model_id: str,
        step_path: Path,
        component_node_name: str | None = None,
        component_solid_index: int | None = None,
    ) -> dict[str, Any]:
        try:
            return self.view_set_service.create_view_set(
                model_id=model_id,
                step_path=step_path,
                component_node_name=component_node_name,
                component_solid_index=component_solid_index,
            )
        except VisionViewSetError as exc:
            raise VisionAnalysisError(str(exc)) from exc

    def create_report(
        self,
        *,
        model_id: str,
        component_node_name: str | None,
        view_set_id: str,
        criteria_payload: dict[str, Any] | None,
        provider_payload: dict[str, Any] | None,
    ) -> dict[str, Any]:
        criteria = parse_vision_criteria(criteria_payload)
        provider_payload = provider_payload or {}

        route_requested = str(provider_payload.get("route") or "openai").strip().lower()
        if route_requested not in self.providers:
            raise VisionAnalysisError("provider.route must be one of: openai, claude, local")

        provider = self.providers[route_requested]
        model_override = _clean_optional_str(provider_payload.get("model_override"))
        local_base_url_override = _clean_optional_str(provider_payload.get("local_base_url"))

        if not provider.configured and not model_override:
            raise VisionAnalysisError(
                f"Provider '{route_requested}' is not configured. Check environment variables."
            )

        try:
            view_paths = self.view_set_service.get_view_set_paths(
                model_id=model_id,
                view_set_id=view_set_id,
            )
        except VisionViewSetNotFoundError as exc:
            raise VisionViewSetMissingError(str(exc)) from exc
        except VisionViewSetError as exc:
            raise VisionAnalysisError(str(exc)) from exc

        report_id = self._next_report_id(model_id)
        report_dir = self._report_dir(model_id, report_id)
        report_dir.mkdir(parents=True, exist_ok=True)

        prompt_base = _build_prompt(
            criteria=criteria,
            component_node_name=component_node_name,
        )

        request_artifact = {
            "model_id": model_id,
            "component_node_name": component_node_name,
            "view_set_id": view_set_id,
            "criteria_applied": criteria.to_dict(),
            "provider_request": {
                "route": route_requested,
                "model_override": model_override,
                "local_base_url": local_base_url_override if route_requested == "local" else None,
            },
        }
        (report_dir / "request.json").write_text(
            json.dumps(request_artifact, indent=2),
            encoding="utf-8",
        )

        raw_response_artifact: dict[str, Any]

        try:
            if route_requested == "local":
                parsed_by_view: list[dict[str, Any]] = []
                per_view_raw: list[dict[str, Any]] = []
                for view_name in self.REQUIRED_VIEWS:
                    prompt = f"{prompt_base}\n\nCurrent orthographic view: {view_name.upper()}."
                    provider_result = provider.analyze(
                        prompt=prompt,
                        image_paths=[view_paths[view_name]],
                        model_override=model_override,
                        base_url_override=local_base_url_override,
                    )
                    parsed_payload = _parse_model_output_as_json(provider_result.text)
                    normalized = normalize_provider_result(
                        parsed_payload,
                        fallback_view=view_name,
                    )
                    parsed_by_view.append(normalized)
                    per_view_raw.append(
                        {
                            "view_name": view_name,
                            "response_text": provider_result.text,
                            "request_metadata": provider_result.request_metadata,
                            "raw_response": provider_result.raw_response,
                        }
                    )

                merged = merge_view_results(parsed_by_view)
                model_used = provider_result.model_used
                base_url_used = provider_result.base_url_used
                raw_response_artifact = {
                    "mode": "sequential_single_image",
                    "provider": route_requested,
                    "results": per_view_raw,
                }
            else:
                provider_result = provider.analyze(
                    prompt=prompt_base,
                    image_paths=[view_paths[name] for name in self.REQUIRED_VIEWS],
                    model_override=model_override,
                )
                parsed_payload = _parse_model_output_as_json(provider_result.text)
                merged = normalize_provider_result(parsed_payload)
                for finding in merged.get("flagged_features", []):
                    if not finding.get("source_views"):
                        finding["source_views"] = list(self.REQUIRED_VIEWS)

                model_used = provider_result.model_used
                base_url_used = provider_result.base_url_used
                raw_response_artifact = {
                    "mode": "multi_image",
                    "provider": route_requested,
                    "response_text": provider_result.text,
                    "request_metadata": provider_result.request_metadata,
                    "raw_response": provider_result.raw_response,
                }

            findings = merged.get("flagged_features")
            if not isinstance(findings, list):
                findings = []

            filtered_findings = _filter_findings_by_criteria(
                findings=findings,
                report_confidence=_normalize_confidence_label(
                    merged.get("confidence"),
                    fallback="medium",
                ),
                criteria=criteria,
            )

            result_payload = {
                "report_id": report_id,
                "model_id": model_id,
                "component_node_name": component_node_name,
                "view_set_id": view_set_id,
                "summary": {
                    "flagged_count": len(filtered_findings),
                    "confidence": _normalize_confidence_label(
                        merged.get("confidence"),
                        fallback="medium",
                    ),
                },
                "findings": filtered_findings,
                "general_observations": str(merged.get("general_observations") or "").strip(),
                "criteria_applied": criteria.to_dict(),
                "provider_applied": {
                    "route_requested": route_requested,
                    "route_used": route_requested,
                    "model_used": model_used,
                    "base_url_used": base_url_used,
                },
                "created_at": self._now_iso(),
            }
        except VisionProviderError as exc:
            raw_response_artifact = {
                "mode": "error",
                "provider": route_requested,
                "error": str(exc),
            }
            (report_dir / "raw_response.json").write_text(
                json.dumps(raw_response_artifact, indent=2),
                encoding="utf-8",
            )
            raise VisionExecutionError(str(exc)) from exc
        except Exception as exc:
            raw_response_artifact = {
                "mode": "error",
                "provider": route_requested,
                "error": f"{exc.__class__.__name__}: {exc}",
            }
            (report_dir / "raw_response.json").write_text(
                json.dumps(raw_response_artifact, indent=2),
                encoding="utf-8",
            )
            raise VisionExecutionError(f"Vision analysis failed: {exc}") from exc

        try:
            (report_dir / "result.json").write_text(
                json.dumps(result_payload, indent=2),
                encoding="utf-8",
            )
            (report_dir / "raw_response.json").write_text(
                json.dumps(raw_response_artifact, indent=2),
                encoding="utf-8",
            )
            report_views_dir = report_dir / "views"
            report_views_dir.mkdir(parents=True, exist_ok=True)
            for view_name in self.REQUIRED_VIEWS:
                shutil.copy2(view_paths[view_name], report_views_dir / f"{view_name}.png")
        except Exception as exc:
            raise VisionAnalysisError(f"Failed to persist vision report artifacts: {exc}") from exc

        return result_payload

    def get_report(self, *, model_id: str, report_id: str) -> dict[str, Any]:
        result_path = self._report_dir(model_id, report_id) / "result.json"
        if not result_path.exists():
            raise VisionReportNotFoundError("Vision report not found.")
        try:
            payload = json.loads(result_path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise VisionAnalysisError(f"Failed to read vision report result: {exc}") from exc
        if not isinstance(payload, dict):
            raise VisionAnalysisError("Vision report payload has invalid format.")
        return payload

    def get_view_image_path(self, *, model_id: str, view_set_id: str, view_name: str) -> Path:
        try:
            return self.view_set_service.get_view_image_path(
                model_id=model_id,
                view_set_id=view_set_id,
                view_name=view_name,
            )
        except VisionViewSetNotFoundError as exc:
            raise VisionViewSetMissingError(str(exc)) from exc
        except VisionViewSetError as exc:
            raise VisionAnalysisError(str(exc)) from exc

    def _reports_root(self, model_id: str) -> Path:
        return self.root / model_id / "vision_reports"

    def _report_dir(self, model_id: str, report_id: str) -> Path:
        return self._reports_root(model_id) / report_id

    def _next_report_id(self, model_id: str) -> str:
        utc_now = datetime.now(timezone.utc)
        date_token = utc_now.strftime("%Y%m%d")
        prefix = f"vision_rpt_{date_token}_"

        root = self._reports_root(model_id)
        root.mkdir(parents=True, exist_ok=True)

        pattern = re.compile(rf"^{re.escape(prefix)}(\d{{3}})$")
        latest = 0
        for entry in root.iterdir():
            if not entry.is_dir():
                continue
            match = pattern.match(entry.name)
            if not match:
                continue
            latest = max(latest, int(match.group(1)))
        return f"{prefix}{latest + 1:03d}"

    def _now_iso(self) -> str:
        return (
            datetime.now(timezone.utc)
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z")
        )


def _build_prompt(*, criteria: VisionCriteria, component_node_name: str | None) -> str:
    focus_checks: list[str] = []
    if criteria.check_internal_pocket_tight_corners:
        focus_checks.append("internal pocket/slot corners that appear sharp or very tight")
    if criteria.check_tool_access_risk:
        focus_checks.append("features that seem difficult to reach with standard milling tools")
    if criteria.check_annotation_note_scan:
        focus_checks.append("annotations/notes relevant to corner radii or finish")

    if not focus_checks:
        focus_checks.append("general manufacturability observations")

    component_line = (
        f"Target component: {component_node_name}."
        if component_node_name
        else "Target component: full current model context."
    )

    focus_text = "\n".join(f"- {item}" for item in focus_checks)

    return (
        "You are a manufacturing engineer reviewing CNC orthographic views.\n"
        f"{component_line}\n"
        f"Sensitivity level: {criteria.sensitivity}.\n"
        "Analyze only what is visible in the provided images.\n"
        "Focus checks:\n"
        f"{focus_text}\n\n"
        "Return JSON only with this schema:\n"
        "{\n"
        '  "flagged_features": [\n'
        "    {\n"
        '      "feature_id": "V1",\n'
        '      "description": "short finding",\n'
        '      "severity": "critical|warning|caution|info",\n'
        '      "confidence": "low|medium|high",\n'
        '      "source_views": ["x", "y", "z"]\n'
        "    }\n"
        "  ],\n"
        '  "general_observations": "short paragraph",\n'
        '  "confidence": "low|medium|high"\n'
        "}"
    )


def _parse_model_output_as_json(text: str) -> dict[str, Any]:
    if not isinstance(text, str) or not text.strip():
        raise VisionExecutionError("Vision provider returned empty text response.")

    stripped = text.strip()

    try:
        payload = json.loads(stripped)
        if isinstance(payload, dict):
            return payload
    except Exception:
        pass

    fenced_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", stripped, flags=re.DOTALL | re.IGNORECASE)
    if fenced_match:
        candidate = fenced_match.group(1)
        try:
            payload = json.loads(candidate)
            if isinstance(payload, dict):
                return payload
        except Exception:
            pass

    start = stripped.find("{")
    end = stripped.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidate = stripped[start : end + 1]
        try:
            payload = json.loads(candidate)
            if isinstance(payload, dict):
                return payload
        except Exception:
            pass

    raise VisionExecutionError("Vision provider response was not valid JSON.")


def _filter_findings_by_criteria(
    *,
    findings: list[dict[str, Any]],
    report_confidence: str,
    criteria: VisionCriteria,
) -> list[dict[str, Any]]:
    threshold_rank = CONFIDENCE_ORDER.get(criteria.confidence_threshold, 1)

    normalized: list[dict[str, Any]] = []
    for item in findings:
        if not isinstance(item, dict):
            continue

        confidence = _normalize_confidence_label(item.get("confidence"), fallback=report_confidence)
        if CONFIDENCE_ORDER.get(confidence, 0) < threshold_rank:
            continue

        severity = _normalize_severity(item.get("severity"))
        source_views = item.get("source_views")
        views: list[str] = []
        if isinstance(source_views, list):
            for source in source_views:
                if isinstance(source, str) and source.strip():
                    views.append(source.strip().lower())

        normalized.append(
            {
                "feature_id": str(item.get("feature_id") or ""),
                "description": str(item.get("description") or "").strip(),
                "severity": severity,
                "confidence": confidence,
                "source_views": sorted(set(views)),
            }
        )

    normalized = [item for item in normalized if item["description"]]
    normalized.sort(
        key=lambda item: (
            -SEVERITY_ORDER.get(item.get("severity", "info"), 0),
            -CONFIDENCE_ORDER.get(item.get("confidence", "low"), 0),
            item.get("description", ""),
        )
    )

    limited = normalized[: criteria.max_flagged_features]
    for index, item in enumerate(limited, start=1):
        item["feature_id"] = f"V{index}"
    return limited


def _normalize_description_key(text: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", " ", text.lower())
    return re.sub(r"\s+", " ", normalized).strip()


def _as_bool(value: Any, *, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    return default


def _normalize_severity(raw_value: Any) -> str:
    if not isinstance(raw_value, str):
        return "warning"
    value = raw_value.strip().lower()
    if value in {"critical", "high", "severe"}:
        return "critical"
    if value in {"warning", "warn", "medium"}:
        return "warning"
    if value in {"caution", "moderate"}:
        return "caution"
    if value in {"info", "low", "ok"}:
        return "info"
    return "warning"


def _normalize_confidence_label(raw_value: Any, *, fallback: str) -> str:
    if not isinstance(raw_value, str):
        return fallback
    value = raw_value.strip().lower()
    if value in VALID_CONFIDENCE:
        return value
    return fallback


def _clean_optional_str(raw_value: Any) -> str | None:
    if not isinstance(raw_value, str):
        return None
    value = raw_value.strip()
    return value if value else None
