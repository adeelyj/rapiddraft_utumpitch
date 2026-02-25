from __future__ import annotations

import copy
import csv
import datetime as dt
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4


class DraftLintDemoError(RuntimeError):
    """Base error for DraftLint demo service."""


class DraftLintSessionNotFoundError(DraftLintDemoError):
    """Raised when a session id cannot be found."""


class DraftLintReportNotFoundError(DraftLintDemoError):
    """Raised when a report id cannot be found."""


@dataclass(frozen=True)
class DraftLintStageSpec:
    stage_id: str
    label: str
    duration_sec: float


class DraftLintDemoService:
    """Deterministic DraftLint mock backend for customer demo recording."""

    _ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg"}
    _STAGES: tuple[DraftLintStageSpec, ...] = (
        DraftLintStageSpec(stage_id="load_drawing", label="Load drawing", duration_sec=1.2),
        DraftLintStageSpec(stage_id="preprocess", label="Preprocess image", duration_sec=1.4),
        DraftLintStageSpec(stage_id="layout_analysis", label="Layout analysis", duration_sec=1.8),
        DraftLintStageSpec(stage_id="ocr_extraction", label="OCR extraction", duration_sec=2.1),
        DraftLintStageSpec(stage_id="symbol_detection", label="Symbol detection", duration_sec=1.9),
        DraftLintStageSpec(stage_id="ai_validation", label="AI validation", duration_sec=2.5),
        DraftLintStageSpec(stage_id="rule_validation", label="Rule validation", duration_sec=1.5),
        DraftLintStageSpec(stage_id="report_generation", label="Report generation", duration_sec=1.1),
    )

    def __init__(self, *, root: Path, fixture_path: Path, template_png_path: Path):
        self.root = root
        self.fixture_path = fixture_path
        self.template_png_path = template_png_path
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "sessions").mkdir(parents=True, exist_ok=True)
        (self.root / "reports").mkdir(parents=True, exist_ok=True)
        self._sessions: dict[str, dict[str, Any]] = {}
        self._reports: dict[str, dict[str, Any]] = {}

    def create_session(
        self,
        *,
        filename: str,
        file_bytes: bytes,
        standard_profile: str | None,
    ) -> dict[str, Any]:
        extension = Path(filename).suffix.lower()
        if extension not in self._ALLOWED_EXTENSIONS:
            allowed = ", ".join(sorted(self._ALLOWED_EXTENSIONS))
            raise DraftLintDemoError(f"Unsupported file type '{extension}'. Allowed: {allowed}")

        now = dt.datetime.now(dt.timezone.utc)
        session_id = f"draftlint_sess_{now.strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:6]}"
        report_id = f"draftlint_rpt_{now.strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:6]}"
        profile = (standard_profile or "ISO 1101 + ISO 5457").strip() or "ISO 1101 + ISO 5457"
        drawing_id = f"drawing_{uuid4().hex[:8]}"

        session_dir = self.root / "sessions" / session_id
        report_dir = self.root / "reports" / report_id
        session_dir.mkdir(parents=True, exist_ok=True)
        report_dir.mkdir(parents=True, exist_ok=True)

        source_file_name = f"input{extension}"
        source_path = session_dir / source_file_name
        source_path.write_bytes(file_bytes)

        report_payload = self._build_report_payload(
            report_id=report_id,
            drawing_id=drawing_id,
            source_filename=filename,
            standard_profile=profile,
            created_at=now,
        )
        self._write_report_artifacts(
            report_dir=report_dir,
            report_payload=report_payload,
        )

        self._sessions[session_id] = {
            "session_id": session_id,
            "report_id": report_id,
            "drawing_id": drawing_id,
            "standard_profile": profile,
            "created_at": now,
            "source_file_name": source_file_name,
            "source_original_name": filename,
            "source_mime_type": self._guess_mime_type(extension),
        }
        self._reports[report_id] = {
            "report_id": report_id,
            "payload": report_payload,
        }

        status_payload = self.get_session(session_id=session_id)
        status_payload["source_url"] = f"/api/draftlint/sessions/{session_id}/source"
        status_payload["source_original_name"] = filename
        status_payload["source_mime_type"] = self._guess_mime_type(extension)
        return status_payload

    def get_session(self, *, session_id: str) -> dict[str, Any]:
        session = self._sessions.get(session_id)
        if not session:
            raise DraftLintSessionNotFoundError("DraftLint session not found.")

        created_at: dt.datetime = session["created_at"]
        now = dt.datetime.now(dt.timezone.utc)
        elapsed = max((now - created_at).total_seconds(), 0.0)
        total_duration = sum(stage.duration_sec for stage in self._STAGES)
        progress_pct = min(100.0, (elapsed / total_duration) * 100.0 if total_duration > 0 else 100.0)
        completed = elapsed >= total_duration

        stages: list[dict[str, Any]] = []
        consumed = 0.0
        for stage in self._STAGES:
            stage_start = consumed
            stage_end = consumed + stage.duration_sec
            if elapsed >= stage_end:
                status = "completed"
                stage_progress = 100.0
                started_at = created_at + dt.timedelta(seconds=stage_start)
                completed_at = created_at + dt.timedelta(seconds=stage_end)
            elif elapsed > stage_start:
                status = "running"
                stage_progress = min(100.0, ((elapsed - stage_start) / stage.duration_sec) * 100.0)
                started_at = created_at + dt.timedelta(seconds=stage_start)
                completed_at = None
            else:
                status = "pending"
                stage_progress = 0.0
                started_at = None
                completed_at = None

            stages.append(
                {
                    "stage_id": stage.stage_id,
                    "label": stage.label,
                    "status": status,
                    "progress_percent": round(stage_progress, 1),
                    "started_at": started_at.isoformat() if started_at else None,
                    "completed_at": completed_at.isoformat() if completed_at else None,
                }
            )
            consumed = stage_end

        return {
            "session_id": session_id,
            "report_id": session["report_id"] if completed else None,
            "status": "completed" if completed else "running",
            "progress_percent": round(progress_pct, 1),
            "standard_profile": session["standard_profile"],
            "created_at": created_at.isoformat(),
            "updated_at": now.isoformat(),
            "stages": stages,
            "poll_after_ms": 900 if not completed else 0,
        }

    def get_report(self, *, report_id: str) -> dict[str, Any]:
        report = self._reports.get(report_id)
        if not report:
            raise DraftLintReportNotFoundError("DraftLint report not found.")
        return report["payload"]

    def get_artifact_path(self, *, report_id: str, artifact_name: str) -> Path:
        report_dir = self.root / "reports" / report_id
        if not report_dir.exists():
            raise DraftLintReportNotFoundError("DraftLint report not found.")

        normalized = artifact_name.strip().lower()
        mapping = {
            "report.json": report_dir / "report.json",
            "report.html": report_dir / "report.html",
            "issues.csv": report_dir / "issues.csv",
            "annotated.png": self.template_png_path,
        }
        target = mapping.get(normalized)
        if not target or not target.exists():
            raise DraftLintReportNotFoundError("DraftLint artifact not found.")
        return target

    def get_session_source_path(self, *, session_id: str) -> Path:
        session = self._sessions.get(session_id)
        if not session:
            raise DraftLintSessionNotFoundError("DraftLint session not found.")
        source_path = self.root / "sessions" / session_id / session["source_file_name"]
        if not source_path.exists():
            raise DraftLintSessionNotFoundError("DraftLint source file not found.")
        return source_path

    def get_session_source_mime_type(self, *, session_id: str) -> str:
        session = self._sessions.get(session_id)
        if not session:
            raise DraftLintSessionNotFoundError("DraftLint session not found.")
        return session["source_mime_type"]

    def _build_report_payload(
        self,
        *,
        report_id: str,
        drawing_id: str,
        source_filename: str,
        standard_profile: str,
        created_at: dt.datetime,
    ) -> dict[str, Any]:
        try:
            template = json.loads(self.fixture_path.read_text(encoding="utf-8"))
        except Exception as exc:  # pragma: no cover - defensive runtime guard
            raise DraftLintDemoError(f"Failed to load DraftLint fixture: {exc}") from exc

        payload = copy.deepcopy(template)
        payload["report_id"] = report_id
        payload["drawing_id"] = drawing_id
        payload["drawing_name"] = source_filename
        payload["standard_profile"] = standard_profile
        payload["validation_date"] = created_at.isoformat()
        payload["artifacts"] = {
            "annotated_png_url": f"/api/draftlint/reports/{report_id}/artifacts/annotated.png",
            "report_json_url": f"/api/draftlint/reports/{report_id}/artifacts/report.json",
            "report_html_url": f"/api/draftlint/reports/{report_id}/artifacts/report.html",
            "issues_csv_url": f"/api/draftlint/reports/{report_id}/artifacts/issues.csv",
        }
        return payload

    def _write_report_artifacts(self, *, report_dir: Path, report_payload: dict[str, Any]) -> None:
        report_json_path = report_dir / "report.json"
        report_html_path = report_dir / "report.html"
        issues_csv_path = report_dir / "issues.csv"

        report_json_path.write_text(
            json.dumps(report_payload, indent=2),
            encoding="utf-8",
        )
        report_html_path.write_text(
            self._build_html(report_payload=report_payload),
            encoding="utf-8",
        )
        self._write_issues_csv(
            issues=report_payload.get("issues", []),
            output_path=issues_csv_path,
        )

    def _build_html(self, *, report_payload: dict[str, Any]) -> str:
        summary = report_payload.get("summary", {})
        issues = report_payload.get("issues", [])
        rows = "\n".join(
            (
                f"<tr><td>{issue.get('issue_id', '-')}</td>"
                f"<td>{issue.get('severity', '-')}</td>"
                f"<td>{issue.get('rule_id', '-')}</td>"
                f"<td>{issue.get('title', '-')}</td>"
                f"<td>{issue.get('recommended_action', '-')}</td></tr>"
            )
            for issue in issues
        )
        return (
            "<!doctype html><html><head><meta charset='utf-8'><title>DraftLint Report</title>"
            "<style>body{font-family:Arial,sans-serif;padding:20px;color:#1f2a44}"
            "table{border-collapse:collapse;width:100%}th,td{border:1px solid #d7deef;padding:8px;font-size:13px}"
            "th{background:#f2f6ff;text-align:left}</style></head><body>"
            f"<h1>DraftLint Report {report_payload.get('report_id')}</h1>"
            f"<p><strong>Drawing:</strong> {report_payload.get('drawing_name')}</p>"
            f"<p><strong>Standard profile:</strong> {report_payload.get('standard_profile')}</p>"
            f"<p><strong>Total issues:</strong> {summary.get('total_issues', 0)} | "
            f"<strong>Critical:</strong> {summary.get('critical_count', 0)} | "
            f"<strong>Major:</strong> {summary.get('major_count', 0)} | "
            f"<strong>Minor:</strong> {summary.get('minor_count', 0)}</p>"
            "<table><thead><tr><th>ID</th><th>Severity</th><th>Rule</th><th>Title</th><th>Recommended Action</th></tr></thead>"
            f"<tbody>{rows}</tbody></table></body></html>"
        )

    def _write_issues_csv(self, *, issues: list[dict[str, Any]], output_path: Path) -> None:
        with output_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=[
                    "issue_id",
                    "severity",
                    "rule_id",
                    "standard",
                    "category",
                    "title",
                    "description",
                    "recommended_action",
                    "confidence",
                    "bbox_x1",
                    "bbox_y1",
                    "bbox_x2",
                    "bbox_y2",
                ],
            )
            writer.writeheader()
            for issue in issues:
                bbox = issue.get("bbox", {}) if isinstance(issue.get("bbox"), dict) else {}
                writer.writerow(
                    {
                        "issue_id": issue.get("issue_id"),
                        "severity": issue.get("severity"),
                        "rule_id": issue.get("rule_id"),
                        "standard": issue.get("standard"),
                        "category": issue.get("category"),
                        "title": issue.get("title"),
                        "description": issue.get("description"),
                        "recommended_action": issue.get("recommended_action"),
                        "confidence": issue.get("confidence"),
                        "bbox_x1": bbox.get("x1"),
                        "bbox_y1": bbox.get("y1"),
                        "bbox_x2": bbox.get("x2"),
                        "bbox_y2": bbox.get("y2"),
                    }
                )

    def _guess_mime_type(self, extension: str) -> str:
        if extension in {".jpg", ".jpeg"}:
            return "image/jpeg"
        if extension == ".png":
            return "image/png"
        return "application/pdf"
