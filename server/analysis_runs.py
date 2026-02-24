from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class AnalysisRunStoreError(RuntimeError):
    pass


class AnalysisRunNotFoundError(AnalysisRunStoreError):
    pass


class AnalysisRunStore:
    def __init__(self, *, root: Path) -> None:
        self.root = root

    def next_analysis_run_id(self, model_id: str) -> str:
        utc_now = datetime.now(timezone.utc)
        date_token = utc_now.strftime("%Y%m%d")
        prefix = f"analysis_run_{date_token}_"
        runs_root = self._runs_root(model_id)
        runs_root.mkdir(parents=True, exist_ok=True)

        pattern = re.compile(rf"^{re.escape(prefix)}(\d{{3}})$")
        latest = 0
        for entry in runs_root.iterdir():
            if not entry.is_dir():
                continue
            match = pattern.match(entry.name)
            if not match:
                continue
            latest = max(latest, int(match.group(1)))
        return f"{prefix}{latest + 1:03d}"

    def create_manifest(
        self,
        *,
        model_id: str,
        analysis_run_id: str,
        component_node_name: str | None,
        dfm_review: dict[str, Any],
        vision_report_id: str | None,
        vision_report: dict[str, Any] | None,
        fusion_report: dict[str, Any],
    ) -> dict[str, Any]:
        clean_run_id = str(analysis_run_id or "").strip()
        if not clean_run_id:
            raise AnalysisRunStoreError("analysis_run_id is required.")

        run_dir = self._run_dir(model_id, clean_run_id)
        run_dir.mkdir(parents=True, exist_ok=True)

        dfm_snapshot_path = run_dir / "dfm_review.json"
        try:
            dfm_snapshot_path.write_text(
                json.dumps(dfm_review or {}, indent=2),
                encoding="utf-8",
            )
        except OSError as exc:
            raise AnalysisRunStoreError(f"Failed to persist DFM snapshot: {exc}") from exc

        created_at = self._now_iso()
        dfm_created_at = _clean_optional_str((dfm_review or {}).get("created_at"))

        vision_payload = vision_report if isinstance(vision_report, dict) else {}
        clean_vision_report_id = _clean_optional_str(vision_report_id)
        clean_fusion_report_id = _clean_optional_str((fusion_report or {}).get("report_id"))
        fusion_created_at = _clean_optional_str((fusion_report or {}).get("created_at"))

        manifest = {
            "analysis_run_id": clean_run_id,
            "model_id": model_id,
            "component_node_name": component_node_name,
            "created_at": created_at,
            "artifacts": {
                "dfm": {
                    "report_id": f"dfm_snapshot_{clean_run_id}",
                    "created_at": dfm_created_at,
                    "route_count": _safe_int((dfm_review or {}).get("route_count")),
                    "finding_count_total": _safe_int((dfm_review or {}).get("finding_count_total")),
                    "snapshot_path": f"analysis_runs/{clean_run_id}/dfm_review.json",
                },
                "vision": {
                    "report_id": clean_vision_report_id,
                    "created_at": _clean_optional_str(vision_payload.get("created_at")),
                    "available": bool(clean_vision_report_id),
                },
                "fusion": {
                    "report_id": clean_fusion_report_id,
                    "created_at": fusion_created_at,
                },
            },
            "api_links": {
                "analysis_run": f"/api/models/{model_id}/analysis-runs/{clean_run_id}",
                "vision_report": (
                    f"/api/models/{model_id}/vision/reports/{clean_vision_report_id}"
                    if clean_vision_report_id
                    else None
                ),
                "fusion_report": (
                    f"/api/models/{model_id}/fusion/reports/{clean_fusion_report_id}"
                    if clean_fusion_report_id
                    else None
                ),
            },
        }

        manifest_path = run_dir / "manifest.json"
        try:
            manifest_path.write_text(
                json.dumps(manifest, indent=2),
                encoding="utf-8",
            )
        except OSError as exc:
            raise AnalysisRunStoreError(f"Failed to persist analysis run manifest: {exc}") from exc
        return manifest

    def get_manifest(self, *, model_id: str, analysis_run_id: str) -> dict[str, Any]:
        manifest_path = self._run_dir(model_id, analysis_run_id) / "manifest.json"
        if not manifest_path.exists():
            raise AnalysisRunNotFoundError("Analysis run manifest not found.")
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise AnalysisRunStoreError(f"Failed to read analysis run manifest: {exc}") from exc
        if not isinstance(payload, dict):
            raise AnalysisRunStoreError("Analysis run manifest payload has invalid format.")
        return payload

    def _runs_root(self, model_id: str) -> Path:
        return self.root / model_id / "analysis_runs"

    def _run_dir(self, model_id: str, analysis_run_id: str) -> Path:
        return self._runs_root(model_id) / analysis_run_id

    def _now_iso(self) -> str:
        return (
            datetime.now(timezone.utc)
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z")
        )


def _clean_optional_str(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned or None


def _safe_int(value: Any) -> int:
    try:
        if isinstance(value, bool):
            return 0
        return int(value)
    except Exception:
        return 0

