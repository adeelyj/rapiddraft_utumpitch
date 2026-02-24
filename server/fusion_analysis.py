from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class FusionAnalysisError(RuntimeError):
    pass


class FusionReportNotFoundError(FusionAnalysisError):
    pass


DFM_SEVERITY_RANK = {
    "critical": 4,
    "major": 3,
    "minor": 2,
    "info": 1,
}

VISION_SEVERITY_RANK = {
    "critical": 4,
    "warning": 3,
    "caution": 2,
    "info": 1,
}

CONFIDENCE_RANK = {
    "low": 1,
    "medium": 2,
    "high": 3,
}

FUSION_MATCH_THRESHOLD = 0.28
FUSION_MATCH_WEIGHT_SEMANTIC = 0.6
FUSION_MATCH_WEIGHT_REFS = 0.25
FUSION_MATCH_WEIGHT_GEOMETRY = 0.15
DEFAULT_FUSION_TUNING = {
    "threshold": FUSION_MATCH_THRESHOLD,
    "weight_semantic": FUSION_MATCH_WEIGHT_SEMANTIC,
    "weight_refs": FUSION_MATCH_WEIGHT_REFS,
    "weight_geometry": FUSION_MATCH_WEIGHT_GEOMETRY,
}


class FusionAnalysisService:
    def __init__(self, *, root: Path) -> None:
        self.root = root

    def create_report(
        self,
        *,
        model_id: str,
        component_node_name: str | None,
        dfm_review: dict[str, Any],
        vision_report: dict[str, Any],
        vision_report_id: str | None,
        fusion_tuning_payload: dict[str, Any] | None = None,
        analysis_run_id: str | None = None,
    ) -> dict[str, Any]:
        report_id = self._next_report_id(model_id)
        report_dir = self._report_dir(model_id, report_id)
        report_dir.mkdir(parents=True, exist_ok=True)
        fusion_tuning = _resolve_fusion_tuning(fusion_tuning_payload)

        fused_payload = build_fusion_payload(
            model_id=model_id,
            component_node_name=component_node_name,
            report_id=report_id,
            dfm_review=dfm_review,
            vision_report=vision_report,
            vision_report_id=vision_report_id,
            fusion_tuning=fusion_tuning,
            analysis_run_id=analysis_run_id,
        )
        try:
            (report_dir / "result.json").write_text(
                json.dumps(fused_payload, indent=2),
                encoding="utf-8",
            )
            (report_dir / "request.json").write_text(
                json.dumps(
                    {
                        "model_id": model_id,
                        "component_node_name": component_node_name,
                        "vision_report_id": vision_report_id,
                        "dfm_route_count": dfm_review.get("route_count"),
                        "fusion_tuning_requested": fusion_tuning_payload or {},
                        "fusion_tuning_applied": fusion_tuning,
                        "analysis_run_id": analysis_run_id,
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
        except OSError as exc:
            raise FusionAnalysisError(f"Failed to persist fusion report artifacts: {exc}") from exc
        return fused_payload

    def get_report(self, *, model_id: str, report_id: str) -> dict[str, Any]:
        result_path = self._report_dir(model_id, report_id) / "result.json"
        if not result_path.exists():
            raise FusionReportNotFoundError("Fusion report not found.")
        try:
            payload = json.loads(result_path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise FusionAnalysisError(f"Failed to read fusion report result: {exc}") from exc
        if not isinstance(payload, dict):
            raise FusionAnalysisError("Fusion report payload has invalid format.")
        return payload

    def latest_vision_report_id(self, model_id: str, *, component_node_name: str | None = None) -> str | None:
        vision_reports_root = self.root / model_id / "vision_reports"
        if not vision_reports_root.exists():
            return None
        candidates = sorted([entry.name for entry in vision_reports_root.iterdir() if entry.is_dir()], reverse=True)
        if not candidates:
            return None
        if component_node_name is None:
            return candidates[0]

        for report_id in candidates:
            report_payload = self._read_vision_report_payload(model_id=model_id, report_id=report_id)
            if not isinstance(report_payload, dict):
                continue
            if vision_report_matches_component(
                vision_report=report_payload,
                component_node_name=component_node_name,
            ):
                return report_id
        return None

    def _read_vision_report_payload(self, *, model_id: str, report_id: str) -> dict[str, Any] | None:
        result_path = self.root / model_id / "vision_reports" / report_id / "result.json"
        if not result_path.exists():
            return None
        try:
            payload = json.loads(result_path.read_text(encoding="utf-8"))
        except Exception:
            return None
        if not isinstance(payload, dict):
            return None
        return payload

    def _reports_root(self, model_id: str) -> Path:
        return self.root / model_id / "fusion_reports"

    def _report_dir(self, model_id: str, report_id: str) -> Path:
        return self._reports_root(model_id) / report_id

    def _next_report_id(self, model_id: str) -> str:
        utc_now = datetime.now(timezone.utc)
        date_token = utc_now.strftime("%Y%m%d")
        prefix = f"fusion_rpt_{date_token}_"
        reports_root = self._reports_root(model_id)
        reports_root.mkdir(parents=True, exist_ok=True)

        pattern = re.compile(rf"^{re.escape(prefix)}(\d{{3}})$")
        latest = 0
        for entry in reports_root.iterdir():
            if not entry.is_dir():
                continue
            match = pattern.match(entry.name)
            if not match:
                continue
            latest = max(latest, int(match.group(1)))
        return f"{prefix}{latest + 1:03d}"


def build_fusion_payload(
    *,
    model_id: str,
    component_node_name: str | None,
    report_id: str,
    dfm_review: dict[str, Any],
    vision_report: dict[str, Any],
    vision_report_id: str | None,
    fusion_tuning: dict[str, Any] | None = None,
    analysis_run_id: str | None = None,
) -> dict[str, Any]:
    tuning = _resolve_fusion_tuning(fusion_tuning)
    dfm_entries = _collect_dfm_entries(dfm_review)
    vision_entries = _collect_vision_entries(vision_report)
    vision_report_exists = bool(vision_entries) or bool(vision_report.get("report_id"))

    unmatched_vision = {entry["id"]: entry for entry in vision_entries}
    confirmed_by_both: list[dict[str, Any]] = []
    dfm_only: list[dict[str, Any]] = []

    for dfm_entry in dfm_entries:
        best_match_id: str | None = None
        best_match_score = 0.0
        best_match_signals: dict[str, Any] | None = None
        for vision_entry in unmatched_vision.values():
            signals = _fusion_match_signals(
                dfm_entry=dfm_entry,
                vision_entry=vision_entry,
                tuning=tuning,
            )
            score = float(signals.get("overall_match_score", 0.0))
            if score > best_match_score:
                best_match_score = score
                best_match_id = vision_entry["id"]
                best_match_signals = signals
        if best_match_id is not None and best_match_score >= float(tuning["threshold"]):
            vision_match = unmatched_vision.pop(best_match_id)
            priority_score = _priority_score(dfm_entry=dfm_entry, vision_entry=vision_match, confirmed=True)
            match_signals = best_match_signals or _empty_match_signals(tuning=tuning)
            confirmed_by_both.append(
                {
                    "id": f"confirmed::{dfm_entry['id']}::{vision_match['id']}",
                    "priority_score": priority_score,
                    "match_score": round(best_match_score, 3),
                    "match_signals": match_signals,
                    "match_rationale": _confirmed_match_rationale(match_signals),
                    "refs": dfm_entry["refs"],
                    "dfm": _dfm_public_entry(dfm_entry),
                    "vision": _vision_public_entry(vision_match),
                }
            )
        else:
            priority_score = _priority_score(dfm_entry=dfm_entry, vision_entry=None, confirmed=False)
            match_signals = best_match_signals or _empty_match_signals(tuning=tuning)
            dfm_only.append(
                {
                    "id": f"dfm::{dfm_entry['id']}",
                    "priority_score": priority_score,
                    "match_signals": match_signals,
                    "match_rationale": _dfm_only_match_rationale(match_signals),
                    "refs": dfm_entry["refs"],
                    "dfm": _dfm_public_entry(dfm_entry),
                }
            )

    vision_only: list[dict[str, Any]] = []
    for vision_entry in unmatched_vision.values():
        priority_score = _priority_score(dfm_entry=None, vision_entry=vision_entry, confirmed=False)
        best_signals = _best_dfm_candidate_signals(
            vision_entry=vision_entry,
            dfm_entries=dfm_entries,
            tuning=tuning,
        )
        vision_only.append(
            {
                "id": f"vision::{vision_entry['id']}",
                "priority_score": priority_score,
                "match_signals": best_signals,
                "match_rationale": _vision_only_match_rationale(best_signals),
                "vision": _vision_public_entry(vision_entry),
            }
        )

    confirmed_by_both.sort(key=lambda entry: entry["priority_score"], reverse=True)
    dfm_only.sort(key=lambda entry: entry["priority_score"], reverse=True)
    vision_only.sort(key=lambda entry: entry["priority_score"], reverse=True)

    all_priorities = (
        [entry["priority_score"] for entry in confirmed_by_both]
        + [entry["priority_score"] for entry in dfm_only]
        + [entry["priority_score"] for entry in vision_only]
    )
    top_actions: list[str] = []
    for entry in confirmed_by_both[:3]:
        dfm_title = str(entry.get("dfm", {}).get("title") or "").strip()
        vision_desc = str(entry.get("vision", {}).get("description") or "").strip()
        top_actions.append(f"Confirmed: {dfm_title or vision_desc}")
    for entry in dfm_only[:2]:
        dfm_title = str(entry.get("dfm", {}).get("title") or "").strip()
        top_actions.append(f"DFM: {dfm_title}")
    if len(top_actions) < 5:
        for entry in vision_only[: 5 - len(top_actions)]:
            vision_desc = str(entry.get("vision", {}).get("description") or "").strip()
            top_actions.append(f"Vision: {vision_desc}")
    if not top_actions:
        top_actions.append("No high-priority issues from current DFM/Vision sources.")

    return {
        "report_id": report_id,
        "analysis_run_id": analysis_run_id,
        "model_id": model_id,
        "component_node_name": component_node_name,
        "source_reports": {
            "vision_report_id": vision_report_id,
            "vision_available": vision_report_exists,
            "dfm_route_count": dfm_review.get("route_count", 0),
            "dfm_finding_count_total": dfm_review.get("finding_count_total", 0),
            "vision_flagged_count": vision_report.get("summary", {}).get("flagged_count", 0),
        },
        "source_status": {
            "dfm": "available",
            "vision": "available" if vision_report_exists else "missing",
        },
        "priority_summary": {
            "max_priority_score": max(all_priorities) if all_priorities else 0,
            "confirmed_count": len(confirmed_by_both),
            "dfm_only_count": len(dfm_only),
            "vision_only_count": len(vision_only),
            "top_actions": top_actions,
        },
        "confirmed_by_both": confirmed_by_both,
        "dfm_only": dfm_only,
        "vision_only": vision_only,
        "standards_trace_union": dfm_review.get("standards_trace_union", []),
        "tuning_applied": tuning,
        "created_at": _now_iso(),
    }


def _collect_dfm_entries(dfm_review: dict[str, Any]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for route in dfm_review.get("routes", []):
        if not isinstance(route, dict):
            continue
        route_key = str(route.get("plan_id") or route.get("process_id") or "route")
        for index, finding in enumerate(route.get("findings", []), start=1):
            if not isinstance(finding, dict):
                continue
            rule_id = str(finding.get("rule_id") or "rule")
            title = str(finding.get("title") or finding.get("description") or "").strip()
            description = str(finding.get("description") or "").strip()
            refs = [ref for ref in finding.get("refs", []) if isinstance(ref, str) and ref]
            finding_type = str(finding.get("finding_type") or "evidence_gap")
            severity = str(finding.get("severity") or "minor").lower()
            text_blob = " ".join([rule_id, title, description]).strip().lower()
            entries.append(
                {
                    "id": f"{route_key}:{rule_id}:{index}",
                    "route_source": route.get("route_source"),
                    "route_process_label": route.get("process_label"),
                    "rule_id": rule_id,
                    "title": title or rule_id,
                    "description": description,
                    "finding_type": finding_type,
                    "severity": severity,
                    "refs": refs,
                    "recommended_action": finding.get("recommended_action"),
                    "text_blob": text_blob,
                    "tokens": _tokenize(text_blob),
                }
            )
    return entries


def _collect_vision_entries(vision_report: dict[str, Any]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for index, finding in enumerate(vision_report.get("findings", []), start=1):
        if not isinstance(finding, dict):
            continue
        description = str(finding.get("description") or "").strip()
        if not description:
            continue
        entries.append(
            {
                "id": str(finding.get("feature_id") or f"V{index}"),
                "description": description,
                "severity": str(finding.get("severity") or "info").lower(),
                "confidence": str(finding.get("confidence") or "medium").lower(),
                "refs": [
                    str(ref).strip()
                    for ref in finding.get("refs", [])
                    if isinstance(ref, str) and str(ref).strip()
                ],
                "source_views": [
                    str(view).strip().lower()
                    for view in finding.get("source_views", [])
                    if isinstance(view, str) and str(view).strip()
                ],
                "geometry_anchor": _normalize_geometry_anchor(finding.get("geometry_anchor")),
            }
        )
    return entries


def _semantic_match_score(dfm_text: str, vision_text: str) -> float:
    left = _tokenize(dfm_text)
    right = _tokenize(vision_text)
    if not left or not right:
        return 0.0
    overlap = len(left & right)
    union = len(left | right)
    jaccard = overlap / union if union else 0.0
    if jaccard <= 0:
        return 0.0
    # Boost if common high-signal DFM terms appear in both.
    priority_tokens = {"radius", "corner", "pocket", "slot", "thread", "hygiene", "surface", "tool", "access"}
    boost = 0.08 if priority_tokens & left & right else 0.0
    return min(1.0, jaccard + boost)


def _fusion_match_signals(
    *,
    dfm_entry: dict[str, Any],
    vision_entry: dict[str, Any],
    tuning: dict[str, float],
) -> dict[str, Any]:
    semantic_score = _semantic_match_score(
        str(dfm_entry.get("text_blob") or ""),
        str(vision_entry.get("description") or ""),
    )

    dfm_refs = {
        str(ref).strip()
        for ref in dfm_entry.get("refs", [])
        if isinstance(ref, str) and str(ref).strip()
    }
    vision_refs = {
        str(ref).strip()
        for ref in vision_entry.get("refs", [])
        if isinstance(ref, str) and str(ref).strip()
    }
    shared_refs = sorted(dfm_refs & vision_refs)
    refs_union_count = len(dfm_refs | vision_refs)
    refs_overlap_score = (
        (len(shared_refs) / refs_union_count)
        if refs_union_count > 0
        else 0.0
    )

    anchor_tokens = _collect_geometry_anchor_tokens(vision_entry.get("geometry_anchor"))
    dfm_tokens = dfm_entry.get("tokens")
    if not isinstance(dfm_tokens, set):
        dfm_tokens = _tokenize(str(dfm_entry.get("text_blob") or ""))
    matched_anchor_tokens = sorted(anchor_tokens & dfm_tokens) if anchor_tokens else []
    geometry_anchor_score = (
        (len(matched_anchor_tokens) / len(anchor_tokens))
        if anchor_tokens
        else 0.0
    )

    overall_match_score = (
        (float(tuning["weight_semantic"]) * semantic_score)
        + (float(tuning["weight_refs"]) * refs_overlap_score)
        + (float(tuning["weight_geometry"]) * geometry_anchor_score)
    )
    overall_match_score = max(0.0, min(1.0, overall_match_score))

    return {
        "semantic_score": round(semantic_score, 3),
        "refs_overlap_score": round(refs_overlap_score, 3),
        "refs_overlap_count": len(shared_refs),
        "shared_refs": shared_refs,
        "geometry_anchor_score": round(geometry_anchor_score, 3),
        "geometry_anchor_considered": bool(anchor_tokens),
        "matched_anchor_tokens": matched_anchor_tokens,
        "overall_match_score": round(overall_match_score, 3),
        "threshold": round(float(tuning["threshold"]), 3),
    }


def _empty_match_signals(*, tuning: dict[str, float]) -> dict[str, Any]:
    return {
        "semantic_score": 0.0,
        "refs_overlap_score": 0.0,
        "refs_overlap_count": 0,
        "shared_refs": [],
        "geometry_anchor_score": 0.0,
        "geometry_anchor_considered": False,
        "matched_anchor_tokens": [],
        "overall_match_score": 0.0,
        "threshold": round(float(tuning["threshold"]), 3),
    }


def _best_dfm_candidate_signals(
    *,
    vision_entry: dict[str, Any],
    dfm_entries: list[dict[str, Any]],
    tuning: dict[str, float],
) -> dict[str, Any]:
    best_signals = _empty_match_signals(tuning=tuning)
    best_score = 0.0
    for dfm_entry in dfm_entries:
        signals = _fusion_match_signals(
            dfm_entry=dfm_entry,
            vision_entry=vision_entry,
            tuning=tuning,
        )
        score = float(signals.get("overall_match_score", 0.0))
        if score > best_score:
            best_score = score
            best_signals = signals
    return best_signals


def _confirmed_match_rationale(signals: dict[str, Any]) -> str:
    semantic = float(signals.get("semantic_score", 0.0))
    refs_overlap_count = int(signals.get("refs_overlap_count", 0))
    shared_refs = [
        str(ref).strip()
        for ref in signals.get("shared_refs", [])
        if isinstance(ref, str) and str(ref).strip()
    ]
    geometry_score = float(signals.get("geometry_anchor_score", 0.0))
    overall = float(signals.get("overall_match_score", 0.0))
    threshold = float(signals.get("threshold", FUSION_MATCH_THRESHOLD))

    fragments = [
        f"Matched above threshold ({overall:.3f} >= {threshold:.3f})",
        f"semantic overlap={semantic:.3f}",
    ]
    if refs_overlap_count > 0:
        refs_text = ", ".join(shared_refs[:3])
        suffix = "..." if len(shared_refs) > 3 else ""
        fragments.append(f"shared refs={refs_overlap_count} ({refs_text}{suffix})")
    else:
        fragments.append("no shared refs")
    if bool(signals.get("geometry_anchor_considered")):
        fragments.append(f"geometry-anchor overlap={geometry_score:.3f}")
    else:
        fragments.append("no geometry-anchor signal")
    return "; ".join(fragments) + "."


def _dfm_only_match_rationale(signals: dict[str, Any]) -> str:
    overall = float(signals.get("overall_match_score", 0.0))
    threshold = float(signals.get("threshold", FUSION_MATCH_THRESHOLD))
    semantic = float(signals.get("semantic_score", 0.0))
    refs_overlap_count = int(signals.get("refs_overlap_count", 0))
    geometry_score = float(signals.get("geometry_anchor_score", 0.0))
    return (
        f"No Vision finding exceeded threshold ({overall:.3f} < {threshold:.3f}). "
        f"Best candidate signals: semantic={semantic:.3f}, shared_refs={refs_overlap_count}, "
        f"geometry_anchor={geometry_score:.3f}."
    )


def _vision_only_match_rationale(signals: dict[str, Any]) -> str:
    overall = float(signals.get("overall_match_score", 0.0))
    threshold = float(signals.get("threshold", FUSION_MATCH_THRESHOLD))
    semantic = float(signals.get("semantic_score", 0.0))
    refs_overlap_count = int(signals.get("refs_overlap_count", 0))
    geometry_score = float(signals.get("geometry_anchor_score", 0.0))
    return (
        f"No DFM finding exceeded threshold ({overall:.3f} < {threshold:.3f}) for this Vision signal. "
        f"Best candidate signals: semantic={semantic:.3f}, shared_refs={refs_overlap_count}, "
        f"geometry_anchor={geometry_score:.3f}."
    )


def _collect_geometry_anchor_tokens(raw_geometry_anchor: Any) -> set[str]:
    if not isinstance(raw_geometry_anchor, dict):
        return set()

    tokens: set[str] = set()

    def _collect(value: Any) -> None:
        if isinstance(value, str):
            tokens.update(_tokenize(value))
            return
        if isinstance(value, list):
            for item in value:
                _collect(item)
            return
        if isinstance(value, dict):
            for nested_value in value.values():
                _collect(nested_value)
            return
        if isinstance(value, (int, float)):
            tokens.update(_tokenize(str(value)))

    for item in raw_geometry_anchor.values():
        _collect(item)
    return tokens


def _normalize_geometry_anchor(raw_geometry_anchor: Any) -> dict[str, Any] | None:
    if not isinstance(raw_geometry_anchor, dict):
        return None
    normalized: dict[str, Any] = {}
    for raw_key, raw_value in raw_geometry_anchor.items():
        if not isinstance(raw_key, str):
            continue
        key = raw_key.strip()
        if not key:
            continue
        if isinstance(raw_value, str):
            value = raw_value.strip()
            if value:
                normalized[key] = value
            continue
        if isinstance(raw_value, (bool, int, float)):
            normalized[key] = raw_value
            continue
        if isinstance(raw_value, list):
            values = []
            for item in raw_value:
                if isinstance(item, str):
                    text = item.strip()
                    if text:
                        values.append(text)
                elif isinstance(item, (bool, int, float)):
                    values.append(item)
            if values:
                normalized[key] = values
            continue
        if isinstance(raw_value, dict):
            nested: dict[str, Any] = {}
            for nested_raw_key, nested_raw_value in raw_value.items():
                if not isinstance(nested_raw_key, str):
                    continue
                nested_key = nested_raw_key.strip()
                if not nested_key:
                    continue
                if isinstance(nested_raw_value, str):
                    text = nested_raw_value.strip()
                    if text:
                        nested[nested_key] = text
                elif isinstance(nested_raw_value, (bool, int, float)):
                    nested[nested_key] = nested_raw_value
            if nested:
                normalized[key] = nested
    return normalized or None


def _resolve_fusion_tuning(raw_tuning: dict[str, Any] | None) -> dict[str, float]:
    tuning = {
        "threshold": float(DEFAULT_FUSION_TUNING["threshold"]),
        "weight_semantic": float(DEFAULT_FUSION_TUNING["weight_semantic"]),
        "weight_refs": float(DEFAULT_FUSION_TUNING["weight_refs"]),
        "weight_geometry": float(DEFAULT_FUSION_TUNING["weight_geometry"]),
    }
    if not isinstance(raw_tuning, dict):
        return tuning

    for key in ("threshold", "weight_semantic", "weight_refs", "weight_geometry"):
        if key not in raw_tuning:
            continue
        raw_value = raw_tuning.get(key)
        try:
            parsed = float(raw_value)
        except (TypeError, ValueError):
            raise FusionAnalysisError(f"fusion_tuning.{key} must be a number.")
        if key == "threshold":
            if not (0.0 <= parsed <= 1.0):
                raise FusionAnalysisError("fusion_tuning.threshold must be between 0 and 1.")
        else:
            if not (0.0 <= parsed <= 1.0):
                raise FusionAnalysisError(f"fusion_tuning.{key} must be between 0 and 1.")
        tuning[key] = parsed

    weight_sum = tuning["weight_semantic"] + tuning["weight_refs"] + tuning["weight_geometry"]
    if weight_sum <= 0:
        raise FusionAnalysisError("fusion_tuning weights must not all be zero.")
    return tuning


def _tokenize(text: str) -> set[str]:
    normalized = str(text or "").lower().strip()
    if not normalized:
        return set()
    return {token for token in re.split(r"[^a-z0-9_]+", normalized) if len(token) >= 3}


def _priority_score(
    *,
    dfm_entry: dict[str, Any] | None,
    vision_entry: dict[str, Any] | None,
    confirmed: bool,
) -> int:
    score = 0
    if dfm_entry is not None:
        score += DFM_SEVERITY_RANK.get(str(dfm_entry.get("severity")), 2) * 20
        if str(dfm_entry.get("finding_type")) == "rule_violation":
            score += 12
        else:
            score += 4
    if vision_entry is not None:
        score += VISION_SEVERITY_RANK.get(str(vision_entry.get("severity")), 2) * 14
        score += CONFIDENCE_RANK.get(str(vision_entry.get("confidence")), 2) * 4
    if confirmed:
        score += 20
    return score


def _dfm_public_entry(dfm_entry: dict[str, Any]) -> dict[str, Any]:
    return {
        "route_source": dfm_entry.get("route_source"),
        "process_label": dfm_entry.get("route_process_label"),
        "rule_id": dfm_entry.get("rule_id"),
        "title": dfm_entry.get("title"),
        "description": dfm_entry.get("description"),
        "severity": dfm_entry.get("severity"),
        "finding_type": dfm_entry.get("finding_type"),
        "recommended_action": dfm_entry.get("recommended_action"),
    }


def _vision_public_entry(vision_entry: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "feature_id": vision_entry.get("id"),
        "description": vision_entry.get("description"),
        "severity": vision_entry.get("severity"),
        "confidence": vision_entry.get("confidence"),
        "refs": vision_entry.get("refs", []),
        "source_views": vision_entry.get("source_views", []),
    }
    geometry_anchor = vision_entry.get("geometry_anchor")
    if isinstance(geometry_anchor, dict) and geometry_anchor:
        payload["geometry_anchor"] = geometry_anchor
    return payload


def _now_iso() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def vision_report_matches_component(*, vision_report: dict[str, Any], component_node_name: str | None) -> bool:
    if not isinstance(component_node_name, str) or not component_node_name.strip():
        return True
    report_component = vision_report.get("component_node_name")
    if not isinstance(report_component, str) or not report_component.strip():
        return False
    return report_component.strip() == component_node_name.strip()
