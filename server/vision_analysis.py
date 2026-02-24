from __future__ import annotations

import base64
import binascii
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
            refs = _normalize_refs(raw_finding.get("refs"))
            geometry_anchor = _normalize_geometry_anchor(raw_finding.get("geometry_anchor"))
            evidence_quality = _normalize_optional_evidence_quality(raw_finding.get("evidence_quality"))

            existing = aggregated.get(key)
            if not existing:
                entry = {
                    "description": description,
                    "severity": severity,
                    "confidence": finding_confidence,
                    "source_views": [view_name],
                    "refs": refs,
                }
                if geometry_anchor is not None:
                    entry["geometry_anchor"] = geometry_anchor
                if evidence_quality is not None:
                    entry["evidence_quality"] = evidence_quality
                aggregated[key] = entry
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

            merged_refs = set(existing.get("refs", []))
            merged_refs.update(refs)
            existing["refs"] = sorted(merged_refs)

            if existing.get("geometry_anchor") is None and geometry_anchor is not None:
                existing["geometry_anchor"] = geometry_anchor

            existing_evidence_quality = existing.get("evidence_quality")
            if existing_evidence_quality is None:
                if evidence_quality is not None:
                    existing["evidence_quality"] = evidence_quality
            elif evidence_quality is not None and existing_evidence_quality != evidence_quality:
                existing["evidence_quality"] = "low"

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
        payload = {
            "feature_id": f"V{index}",
            "description": finding["description"],
            "severity": finding["severity"],
            "confidence": finding["confidence"],
            "source_views": finding.get("source_views", []),
        }
        refs = _normalize_refs(finding.get("refs"))
        if refs:
            payload["refs"] = refs
        geometry_anchor = _normalize_geometry_anchor(finding.get("geometry_anchor"))
        if geometry_anchor is not None:
            payload["geometry_anchor"] = geometry_anchor
        evidence_quality = _normalize_optional_evidence_quality(finding.get("evidence_quality"))
        if evidence_quality is not None:
            payload["evidence_quality"] = evidence_quality
        normalized_findings.append(payload)

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
        refs = _normalize_refs(item.get("refs"))
        geometry_anchor = _normalize_geometry_anchor(item.get("geometry_anchor"))
        evidence_quality = _normalize_optional_evidence_quality(item.get("evidence_quality"))

        source_views_raw = item.get("source_views")
        source_views: list[str] = []
        if isinstance(source_views_raw, list):
            for source in source_views_raw:
                if isinstance(source, str) and source.strip():
                    source_views.append(source.strip().lower())

        if fallback_view and fallback_view not in source_views:
            source_views.append(fallback_view)

        finding_payload = {
            "description": description,
            "severity": severity,
            "confidence": confidence,
            "source_views": sorted(set(source_views)),
            "refs": refs,
        }
        if geometry_anchor is not None:
            finding_payload["geometry_anchor"] = geometry_anchor
        if evidence_quality is not None:
            finding_payload["evidence_quality"] = evidence_quality
        normalized_findings.append(finding_payload)

    overall_confidence = _normalize_confidence_label(raw_payload.get("confidence"), fallback="medium")
    general_observations = str(raw_payload.get("general_observations") or "").strip()

    normalized_with_ids: list[dict[str, Any]] = []
    for index, finding in enumerate(normalized_findings, start=1):
        payload = {
            "feature_id": f"V{index}",
            "description": finding["description"],
            "severity": finding["severity"],
            "confidence": finding["confidence"],
            "source_views": finding["source_views"],
        }
        refs = _normalize_refs(finding.get("refs"))
        if refs:
            payload["refs"] = refs
        geometry_anchor = _normalize_geometry_anchor(finding.get("geometry_anchor"))
        if geometry_anchor is not None:
            payload["geometry_anchor"] = geometry_anchor
        evidence_quality = _normalize_optional_evidence_quality(finding.get("evidence_quality"))
        if evidence_quality is not None:
            payload["evidence_quality"] = evidence_quality
        normalized_with_ids.append(payload)

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
        provider_defaults: dict[str, dict[str, str]] = {}
        for key in ordered_keys:
            provider = self.providers.get(key)
            if provider is None:
                continue
            provider_entry = provider.availability()
            provider_entry["id"] = key
            providers_payload.append(provider_entry)
            provider_base_url = getattr(provider, "base_url", None)
            if isinstance(provider_base_url, str) and provider_base_url.strip():
                provider_defaults[key] = {
                    "base_url": provider_base_url,
                }

        default_provider = "openai"
        for candidate in ordered_keys:
            provider = self.providers.get(candidate)
            if provider and provider.configured:
                default_provider = candidate
                break

        local_base_url = provider_defaults.get("local", {}).get(
            "base_url",
            "http://127.0.0.1:1234/v1",
        )

        return {
            "providers": providers_payload,
            "default_provider": default_provider,
            "provider_defaults": provider_defaults,
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
        selected_view_names: list[str] | None = None,
        pasted_images_payload: list[dict[str, Any]] | None = None,
        prompt_override: str | None = None,
        part_facts_payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        criteria = parse_vision_criteria(criteria_payload)
        provider_payload = provider_payload or {}

        route_requested = str(provider_payload.get("route") or "openai").strip().lower()
        if route_requested not in self.providers:
            raise VisionAnalysisError("provider.route must be one of: openai, claude, local")

        provider = self.providers[route_requested]
        model_override = _clean_optional_str(provider_payload.get("model_override"))
        base_url_override = _clean_optional_str(provider_payload.get("base_url_override"))
        api_key_override = _clean_optional_str(provider_payload.get("api_key_override"))
        legacy_local_base_url_override = _clean_optional_str(provider_payload.get("local_base_url"))
        if base_url_override is None and legacy_local_base_url_override is not None:
            base_url_override = legacy_local_base_url_override

        provider_default_model = _clean_optional_str(getattr(provider, "default_model", None))
        if (
            not provider.configured
            and not model_override
            and not (api_key_override and provider_default_model)
        ):
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

        selected_generated_view_names = self._resolve_selected_view_names(
            view_paths=view_paths,
            selected_view_names=selected_view_names,
        )
        pasted_analysis_inputs = self._materialize_pasted_images(
            report_dir=report_dir,
            pasted_images_payload=pasted_images_payload,
        )
        analysis_inputs: list[tuple[str, Path]] = [
            (view_name, view_paths[view_name]) for view_name in selected_generated_view_names
        ] + pasted_analysis_inputs
        if not analysis_inputs:
            raise VisionAnalysisError("Select at least one generated or pasted image for analysis.")

        analysis_image_labels = [label for label, _ in analysis_inputs]
        part_facts_context_lines = _build_part_facts_prompt_context(part_facts_payload)
        default_prompt = _build_prompt(
            criteria=criteria,
            component_node_name=component_node_name,
            selected_image_labels=analysis_image_labels,
            part_facts_context_lines=part_facts_context_lines,
        )
        prompt_override_text = _clean_optional_str(prompt_override)
        prompt_base = prompt_override_text or default_prompt

        request_artifact = {
            "model_id": model_id,
            "component_node_name": component_node_name,
            "view_set_id": view_set_id,
            "criteria_applied": criteria.to_dict(),
            "image_selection": {
                "selected_view_names": selected_generated_view_names,
                "pasted_image_labels": [label for label, _ in pasted_analysis_inputs],
            },
            "analysis_image_labels": analysis_image_labels,
            "provider_request": {
                "route": route_requested,
                "model_override": model_override,
                "base_url_override": base_url_override,
                "api_key_override_provided": bool(api_key_override),
                "local_base_url": legacy_local_base_url_override if route_requested == "local" else None,
            },
            "prompt_override_provided": bool(prompt_override_text),
            "prompt_used": prompt_base,
        }
        if part_facts_context_lines:
            request_artifact["part_facts_prompt_context"] = part_facts_context_lines
        (report_dir / "request.json").write_text(
            json.dumps(request_artifact, indent=2),
            encoding="utf-8",
        )

        raw_response_artifact: dict[str, Any]
        raw_output_text = ""

        try:
            if route_requested == "local":
                parsed_by_view: list[dict[str, Any]] = []
                per_view_raw: list[dict[str, Any]] = []
                for view_label, image_path in analysis_inputs:
                    if view_label in self.REQUIRED_VIEWS:
                        context_line = f"Current orthographic view: {view_label.upper()}."
                    else:
                        context_line = f"Current supplemental image label: {view_label}."
                    prompt = f"{prompt_base}\n\n{context_line}"
                    provider_result = provider.analyze(
                        prompt=prompt,
                        image_paths=[image_path],
                        model_override=model_override,
                        base_url_override=base_url_override,
                        api_key_override=api_key_override,
                    )
                    parsed_payload = _parse_model_output_as_json(provider_result.text)
                    normalized = normalize_provider_result(
                        parsed_payload,
                        fallback_view=view_label,
                    )
                    parsed_by_view.append(normalized)
                    per_view_raw.append(
                        {
                            "view_name": view_label,
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
                    "analysis_image_labels": [label for label, _ in analysis_inputs],
                    "results": per_view_raw,
                }
                raw_output_sections: list[str] = []
                for item in per_view_raw:
                    view_name = str(item.get("view_name") or "").strip() or "unknown"
                    response_text = str(item.get("response_text") or "").strip()
                    if not response_text:
                        raw_payload = item.get("raw_response")
                        if raw_payload is not None:
                            try:
                                response_text = json.dumps(raw_payload, indent=2)
                            except Exception:
                                response_text = str(raw_payload)
                    if not response_text:
                        continue
                    raw_output_sections.append(f"--- {view_name} ---\n{response_text}")
                raw_output_text = "\n\n".join(raw_output_sections).strip()
            else:
                provider_result = provider.analyze(
                    prompt=prompt_base,
                    image_paths=[image_path for _, image_path in analysis_inputs],
                    model_override=model_override,
                    base_url_override=base_url_override,
                    api_key_override=api_key_override,
                )
                parsed_payload = _parse_model_output_as_json(provider_result.text)
                merged = normalize_provider_result(parsed_payload)
                source_fallback_views = [label for label, _ in analysis_inputs]
                for finding in merged.get("flagged_features", []):
                    if not finding.get("source_views"):
                        finding["source_views"] = source_fallback_views

                model_used = provider_result.model_used
                base_url_used = provider_result.base_url_used
                raw_response_artifact = {
                    "mode": "multi_image",
                    "provider": route_requested,
                    "analysis_image_labels": source_fallback_views,
                    "response_text": provider_result.text,
                    "request_metadata": provider_result.request_metadata,
                    "raw_response": provider_result.raw_response,
                }
                raw_output_text = str(provider_result.text or "").strip()
                if not raw_output_text and provider_result.raw_response is not None:
                    try:
                        raw_output_text = json.dumps(provider_result.raw_response, indent=2)
                    except Exception:
                        raw_output_text = str(provider_result.raw_response)

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
            report_confidence = _normalize_confidence_label(
                merged.get("confidence"),
                fallback="medium",
            )
            general_observations = str(merged.get("general_observations") or "").strip()
            customer_payload = _build_customer_output(
                findings=filtered_findings,
                report_confidence=report_confidence,
                general_observations=general_observations,
            )

            result_payload = {
                "report_id": report_id,
                "model_id": model_id,
                "component_node_name": component_node_name,
                "view_set_id": view_set_id,
                "summary": {
                    "flagged_count": len(filtered_findings),
                    "confidence": report_confidence,
                },
                "findings": filtered_findings,
                "general_observations": general_observations,
                "raw_output_text": raw_output_text,
                "prompt_used": prompt_base,
                "customer_summary": customer_payload["summary"],
                "customer_findings": customer_payload["findings"],
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
            for index, (view_label, image_path) in enumerate(analysis_inputs, start=1):
                suffix = image_path.suffix if image_path.suffix else ".png"
                safe_label = _sanitize_view_label(view_label, fallback=f"image_{index}")
                artifact_name = f"{index:02d}_{safe_label}{suffix}"
                shutil.copy2(image_path, report_views_dir / artifact_name)
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

    def _resolve_selected_view_names(
        self,
        *,
        view_paths: dict[str, Path],
        selected_view_names: list[str] | None,
    ) -> list[str]:
        available_view_names = {str(name).strip().lower() for name in view_paths.keys()}
        if selected_view_names is None:
            candidates = list(self.REQUIRED_VIEWS)
        else:
            candidates = [
                str(name).strip().lower()
                for name in selected_view_names
                if isinstance(name, str) and str(name).strip()
            ]

        selected: list[str] = []
        seen: set[str] = set()
        for candidate in candidates:
            if candidate in available_view_names and candidate not in seen:
                selected.append(candidate)
                seen.add(candidate)
        return selected

    def _materialize_pasted_images(
        self,
        *,
        report_dir: Path,
        pasted_images_payload: list[dict[str, Any]] | None,
    ) -> list[tuple[str, Path]]:
        if not pasted_images_payload:
            return []

        pasted_images_dir = report_dir / "pasted_images"
        pasted_images_dir.mkdir(parents=True, exist_ok=True)

        materialized: list[tuple[str, Path]] = []
        for index, payload in enumerate(pasted_images_payload, start=1):
            if not isinstance(payload, dict):
                continue

            data_url = _clean_optional_str(payload.get("data_url"))
            if not data_url:
                continue

            raw_name = _clean_optional_str(payload.get("name")) or f"screenshot_{index}"
            safe_name = _sanitize_view_label(raw_name, fallback=f"screenshot_{index}")
            extension, image_bytes = _decode_image_data_url(data_url)
            image_path = pasted_images_dir / f"{index:02d}_{safe_name}{extension}"
            image_path.write_bytes(image_bytes)
            materialized.append((safe_name, image_path))

        return materialized

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


def _build_prompt(
    *,
    criteria: VisionCriteria,
    component_node_name: str | None,
    selected_image_labels: list[str],
    part_facts_context_lines: list[str],
) -> str:
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
    image_labels = [label for label in selected_image_labels if isinstance(label, str) and label.strip()]
    image_manifest_text = "\n".join(f"- {label}" for label in image_labels) if image_labels else "- (no labels)"
    part_facts_text = (
        "\n".join(f"- {line}" for line in part_facts_context_lines)
        if part_facts_context_lines
        else "- unavailable"
    )

    return (
        "You are a manufacturing engineer reviewing manufacturing images.\n"
        "Image sets can include orthographic, isometric, section, or screenshot captures.\n"
        f"{component_line}\n"
        f"Sensitivity level: {criteria.sensitivity}.\n"
        "Analyze only what is visible in the provided images.\n"
        "Focus checks:\n"
        f"{focus_text}\n\n"
        "Image labels provided for this run:\n"
        f"{image_manifest_text}\n\n"
        "PartFacts context (use as priors, not direct visual evidence):\n"
        f"{part_facts_text}\n\n"
        "Evidence rules:\n"
        "- Use only provided image labels in source_views.\n"
        "- If a claim is not visible, lower confidence and use low evidence_quality.\n"
        "- If PartFacts and image evidence conflict, call out the contradiction in general_observations.\n\n"
        "Return JSON only with this schema:\n"
        "{\n"
        '  "flagged_features": [\n'
        "    {\n"
        '      "feature_id": "V1",\n'
        '      "description": "short finding",\n'
        '      "severity": "critical|warning|caution|info",\n'
        '      "confidence": "low|medium|high",\n'
        '      "source_views": ["x", "y", "z"],\n'
        '      "refs": ["REF-CNC-2"],\n'
        '      "geometry_anchor": {"feature": "pocket", "view": "x"},\n'
        '      "evidence_quality": "low|medium|high"\n'
        "    }\n"
        "  ],\n"
        '  "general_observations": "short paragraph",\n'
        '  "confidence": "low|medium|high"\n'
        "}"
    )


def _build_part_facts_prompt_context(part_facts_payload: dict[str, Any] | None) -> list[str]:
    if not isinstance(part_facts_payload, dict):
        return []

    lines: list[str] = []

    declared_bits: list[str] = []
    for key, label in (
        ("material", "material"),
        ("manufacturing_process", "process"),
        ("industry", "industry"),
    ):
        value_text = _part_fact_metric_value_text(
            part_facts_payload=part_facts_payload,
            section_name="declared_context",
            metric_key=key,
        )
        if value_text:
            declared_bits.append(f"{label}={value_text}")
    if declared_bits:
        lines.append("Declared context: " + ", ".join(declared_bits))

    geometry_bits: list[str] = []
    for section_name, metric_key, label in (
        ("manufacturing_signals", "min_internal_radius_mm", "min_internal_radius"),
        ("manufacturing_signals", "count_radius_below_1_5_mm", "count_radius_below_1.5mm"),
        ("manufacturing_signals", "max_pocket_depth_mm", "max_pocket_depth"),
        ("manufacturing_signals", "max_depth_to_radius_ratio", "max_depth_radius_ratio"),
        ("manufacturing_signals", "pockets_present", "pockets_present"),
        ("manufacturing_signals", "hole_features", "hole_features"),
        ("manufacturing_signals", "min_hole_diameter_mm", "min_hole_diameter"),
        ("manufacturing_signals", "max_hole_depth_mm", "max_hole_depth"),
    ):
        value_text = _part_fact_metric_value_text(
            part_facts_payload=part_facts_payload,
            section_name=section_name,
            metric_key=metric_key,
        )
        if value_text:
            geometry_bits.append(f"{label}={value_text}")
    if geometry_bits:
        lines.append("Geometry/manufacturing signals: " + ", ".join(geometry_bits))

    coverage = part_facts_payload.get("coverage")
    full_readiness_coverage = (
        coverage.get("full_rule_readiness_coverage")
        if isinstance(coverage, dict)
        else None
    )
    readiness_percent = (
        _safe_float(full_readiness_coverage.get("percent"))
        if isinstance(full_readiness_coverage, dict)
        else None
    )
    overall_confidence = part_facts_payload.get("overall_confidence")
    confidence_text = (
        str(overall_confidence).strip().lower()
        if isinstance(overall_confidence, str) and overall_confidence.strip()
        else None
    )
    if readiness_percent is not None or confidence_text is not None:
        readiness_fragment = (
            f"{round(readiness_percent, 1)}%"
            if readiness_percent is not None
            else "unknown"
        )
        confidence_fragment = confidence_text or "unknown"
        lines.append(
            f"PartFacts quality: overall_confidence={confidence_fragment}, readiness_coverage={readiness_fragment}"
        )

    return lines


def _part_fact_metric_value_text(
    *,
    part_facts_payload: dict[str, Any],
    section_name: str,
    metric_key: str,
) -> str | None:
    sections = part_facts_payload.get("sections")
    if not isinstance(sections, dict):
        return None
    section = sections.get(section_name)
    if not isinstance(section, dict):
        return None
    metric = section.get(metric_key)
    if not isinstance(metric, dict):
        return None

    state = str(metric.get("state") or "").strip().lower()
    if state in {"", "unknown", "failed", "not_applicable"}:
        return None

    value = metric.get("value")
    value_text = _part_fact_value_to_text(value)
    if value_text is None:
        return None

    unit = metric.get("unit")
    if isinstance(unit, str) and unit.strip():
        return f"{value_text} {unit.strip()}"
    return value_text


def _part_fact_value_to_text(value: Any) -> str | None:
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, (int, float)):
        number = float(value)
        if abs(number) >= 1000:
            return f"{number:,.2f}".rstrip("0").rstrip(".")
        return f"{number:.4g}"
    if isinstance(value, str):
        text = value.strip()
        return text if text else None
    return None


def _safe_float(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _parse_model_output_as_json(text: str) -> dict[str, Any]:
    if not isinstance(text, str):
        return _fallback_model_output_payload("")

    stripped = text.strip()
    if not stripped:
        return _fallback_model_output_payload("")

    candidates: list[tuple[int, int, dict[str, Any]]] = []

    def _append_candidate(payload: Any, *, position: int) -> None:
        if not isinstance(payload, dict):
            return
        score = _score_schema_candidate(payload)
        candidates.append((score, position, payload))

    try:
        payload = json.loads(stripped)
        _append_candidate(payload, position=0)
    except Exception:
        pass

    for fenced_match in re.finditer(r"```(?:json)?\s*(\{.*?\})\s*```", stripped, flags=re.DOTALL | re.IGNORECASE):
        candidate = fenced_match.group(1)
        try:
            payload = json.loads(candidate)
            _append_candidate(payload, position=fenced_match.start())
        except Exception:
            pass

    # Try parsing JSON from each opening brace position to handle prose + JSON mixtures.
    decoder = json.JSONDecoder()
    for match in re.finditer(r"\{", stripped):
        candidate = stripped[match.start() :]
        try:
            payload, _ = decoder.raw_decode(candidate)
            _append_candidate(payload, position=match.start())
        except Exception:
            pass

    if candidates:
        candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
        best_score, _, best_payload = candidates[0]
        if best_score > 0:
            return best_payload

    return _fallback_model_output_payload(stripped)


def _score_schema_candidate(payload: dict[str, Any]) -> int:
    score = 0

    flagged_features = payload.get("flagged_features")
    if isinstance(flagged_features, list):
        score += 3
        if any(isinstance(item, dict) and str(item.get("description") or "").strip() for item in flagged_features):
            score += 2
    elif "flagged_features" in payload:
        score += 1

    if isinstance(payload.get("general_observations"), str):
        score += 2
    elif "general_observations" in payload:
        score += 1

    confidence_raw = payload.get("confidence")
    if isinstance(confidence_raw, str) and confidence_raw.strip().lower() in VALID_CONFIDENCE:
        score += 2
    elif "confidence" in payload:
        score += 1

    return score


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
        refs = _normalize_refs(item.get("refs"))
        geometry_anchor = _normalize_geometry_anchor(item.get("geometry_anchor"))
        evidence_quality = _normalize_optional_evidence_quality(item.get("evidence_quality"))
        views: list[str] = []
        if isinstance(source_views, list):
            for source in source_views:
                if isinstance(source, str) and source.strip():
                    views.append(source.strip().lower())

        finding_payload = {
            "feature_id": str(item.get("feature_id") or ""),
            "description": str(item.get("description") or "").strip(),
            "severity": severity,
            "confidence": confidence,
            "source_views": sorted(set(views)),
        }
        if refs:
            finding_payload["refs"] = refs
        if geometry_anchor is not None:
            finding_payload["geometry_anchor"] = geometry_anchor
        if evidence_quality is not None:
            finding_payload["evidence_quality"] = evidence_quality

        normalized.append(finding_payload)

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


def _build_customer_output(
    *,
    findings: list[dict[str, Any]],
    report_confidence: str,
    general_observations: str,
) -> dict[str, Any]:
    return {
        "summary": _build_customer_summary(
            findings=findings,
            report_confidence=report_confidence,
            general_observations=general_observations,
        ),
        "findings": _build_customer_findings(findings=findings),
    }


def _build_customer_summary(
    *,
    findings: list[dict[str, Any]],
    report_confidence: str,
    general_observations: str,
) -> dict[str, Any]:
    severity_counts = {
        "critical": 0,
        "warning": 0,
        "caution": 0,
        "info": 0,
    }
    for item in findings:
        if not isinstance(item, dict):
            continue
        severity = _normalize_severity(item.get("severity"))
        severity_counts[severity] += 1

    total_findings = sum(severity_counts.values())
    top_risks = [
        str(item.get("description") or "").strip()
        for item in findings[:3]
        if isinstance(item, dict) and str(item.get("description") or "").strip()
    ]

    if total_findings == 0:
        status = "clear"
        headline = "No manufacturability issues were flagged with the current criteria and confidence threshold."
        recommended_next_step = (
            "Proceed with quote/release review, and confirm with full DFM/Fusion checks before final sign-off."
        )
    elif severity_counts["critical"] > 0:
        status = "critical"
        headline = (
            f"{total_findings} issue(s) flagged, including {severity_counts['critical']} critical risk(s) "
            "that can affect manufacturability."
        )
        recommended_next_step = (
            "Resolve critical geometry risks first, then re-run Vision and Fusion before quoting."
        )
    elif severity_counts["warning"] > 0:
        status = "attention"
        headline = (
            f"{total_findings} issue(s) flagged with warning-level risk that may increase cost or lead time."
        )
        recommended_next_step = (
            "Apply recommended geometry/drawing updates and re-run analysis to confirm risk reduction."
        )
    else:
        status = "watch"
        headline = f"{total_findings} low-to-moderate issue(s) flagged for engineering review."
        recommended_next_step = (
            "Review cautionary items and confirm acceptance criteria with manufacturing before release."
        )

    summary = {
        "status": status,
        "headline": headline,
        "confidence": report_confidence,
        "risk_counts": severity_counts,
        "top_risks": top_risks,
        "recommended_next_step": recommended_next_step,
    }
    observations = general_observations.strip()
    if observations:
        summary["analysis_note"] = observations
    return summary


def _build_customer_findings(*, findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    customer_findings: list[dict[str, Any]] = []

    for index, item in enumerate(findings, start=1):
        if not isinstance(item, dict):
            continue

        description = str(item.get("description") or "").strip()
        if not description:
            continue
        severity = _normalize_severity(item.get("severity"))
        confidence = _normalize_confidence_label(item.get("confidence"), fallback="medium")
        finding_id = str(item.get("feature_id") or f"V{index}").strip() or f"V{index}"

        views: list[str] = []
        source_views = item.get("source_views")
        if isinstance(source_views, list):
            for source in source_views:
                if isinstance(source, str) and source.strip():
                    views.append(source.strip().lower())

        payload = {
            "finding_id": finding_id,
            "title": _to_customer_title(description),
            "severity": severity,
            "confidence": confidence,
            "why_it_matters": _infer_customer_impact_text(description=description, severity=severity),
            "recommended_action": _infer_customer_action_text(description=description, severity=severity),
            "source_views": sorted(set(views)),
        }
        refs = _normalize_refs(item.get("refs"))
        if refs:
            payload["refs"] = refs

        customer_findings.append(payload)

    return customer_findings


def _to_customer_title(text: str) -> str:
    clean_text = re.sub(r"\s+", " ", text.strip())
    if not clean_text:
        return "Manufacturability finding"
    if len(clean_text) > 120:
        clean_text = f"{clean_text[:117].rstrip()}..."
    return clean_text[:1].upper() + clean_text[1:]


def _infer_customer_impact_text(*, description: str, severity: str) -> str:
    lowered = description.lower()

    if any(token in lowered for token in ("corner", "radius", "fillet", "sharp")):
        return (
            "Tight internal corners can require smaller tools, slower machining, and possible redesign, "
            "which increases cost and schedule risk."
        )
    if any(token in lowered for token in ("deep", "depth", "access", "reach", "narrow slot")):
        return (
            "Hard-to-reach geometry can reduce tool life and stability, increasing cycle time and quality risk."
        )
    if any(token in lowered for token in ("annotation", "note", "callout", "drawing", "dimension")):
        return (
            "Unclear drawing intent can create quoting ambiguity and downstream manufacturing errors."
        )

    if severity == "critical":
        return "This issue can materially affect manufacturability, cost, and delivery risk."
    if severity == "warning":
        return "This issue can increase machining cost or lead time if left unresolved."
    if severity == "caution":
        return "This issue is moderate but should be reviewed before release."
    return "This item should be verified during final engineering review."


def _infer_customer_action_text(*, description: str, severity: str) -> str:
    lowered = description.lower()

    if any(token in lowered for token in ("corner", "radius", "fillet", "sharp")):
        return "Increase internal radii where possible and align drawing callouts with tool capability."
    if any(token in lowered for token in ("deep", "depth", "access", "reach", "narrow slot")):
        return "Reduce depth-to-tool ratio or add access relief to support standard tooling."
    if any(token in lowered for token in ("annotation", "note", "callout", "drawing", "dimension")):
        return "Add explicit drawing notes and critical dimensions for manufacturability intent."

    if severity == "critical":
        return "Escalate for immediate design update and re-run manufacturability checks."
    if severity == "warning":
        return "Review with manufacturing engineer and update geometry or process assumptions."
    if severity == "caution":
        return "Confirm this condition is acceptable for the selected process and quality targets."
    return "Track this item in release notes and verify during design review."


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


def _normalize_refs(raw_value: Any) -> list[str]:
    if not isinstance(raw_value, list):
        return []
    refs: list[str] = []
    seen: set[str] = set()
    for entry in raw_value:
        if not isinstance(entry, str):
            continue
        value = entry.strip()
        if not value or value in seen:
            continue
        seen.add(value)
        refs.append(value)
    return refs


def _normalize_geometry_anchor(raw_value: Any) -> dict[str, Any] | None:
    if not isinstance(raw_value, dict):
        return None

    normalized: dict[str, Any] = {}
    for raw_key, raw_entry in raw_value.items():
        if not isinstance(raw_key, str):
            continue
        key = raw_key.strip()
        if not key:
            continue

        if isinstance(raw_entry, str):
            value = raw_entry.strip()
            if value:
                normalized[key] = value
            continue

        if isinstance(raw_entry, (bool, int, float)):
            normalized[key] = raw_entry
            continue

        if isinstance(raw_entry, list):
            values: list[Any] = []
            for item in raw_entry:
                if isinstance(item, str):
                    text = item.strip()
                    if text:
                        values.append(text)
                elif isinstance(item, (bool, int, float)):
                    values.append(item)
            if values:
                normalized[key] = values
            continue

        if isinstance(raw_entry, dict):
            nested: dict[str, Any] = {}
            for nested_raw_key, nested_raw_value in raw_entry.items():
                if not isinstance(nested_raw_key, str):
                    continue
                nested_key = nested_raw_key.strip()
                if not nested_key:
                    continue
                if isinstance(nested_raw_value, str):
                    nested_text = nested_raw_value.strip()
                    if nested_text:
                        nested[nested_key] = nested_text
                elif isinstance(nested_raw_value, (bool, int, float)):
                    nested[nested_key] = nested_raw_value
            if nested:
                normalized[key] = nested

    return normalized or None


def _normalize_optional_evidence_quality(raw_value: Any) -> str | None:
    if not isinstance(raw_value, str):
        return None
    value = raw_value.strip().lower()
    if value in VALID_CONFIDENCE:
        return value
    return None


def _sanitize_view_label(raw_value: str, *, fallback: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", raw_value.strip().lower())
    normalized = normalized.strip("_")
    if not normalized:
        normalized = fallback
    return normalized[:48]


def _decode_image_data_url(data_url: str) -> tuple[str, bytes]:
    match = re.match(
        r"^\s*data:(image/[a-zA-Z0-9.+-]+);base64,(?P<data>.+)\s*$",
        data_url,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not match:
        raise VisionAnalysisError("Pasted images must be base64 data URLs.")

    media_type = match.group(1).lower()
    encoded_data = re.sub(r"\s+", "", match.group("data"))
    try:
        image_bytes = base64.b64decode(encoded_data, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise VisionAnalysisError("Pasted image payload contains invalid base64 data.") from exc

    if not image_bytes:
        raise VisionAnalysisError("Pasted image payload was empty.")

    extension_map = {
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "image/webp": ".webp",
        "image/gif": ".gif",
        "image/bmp": ".bmp",
    }
    extension = extension_map.get(media_type, ".png")
    return extension, image_bytes


def _fallback_model_output_payload(raw_text: str) -> dict[str, Any]:
    clipped = raw_text.strip()
    if len(clipped) > 2000:
        clipped = f"{clipped[:2000]}..."

    note = "Model returned non-JSON output; included raw text summary below."
    if clipped:
        observations = f"{note}\n\n{clipped}"
    else:
        observations = f"{note}\n\n(No content returned by provider.)"

    return {
        "flagged_features": [],
        "general_observations": observations,
        "confidence": "low",
    }
