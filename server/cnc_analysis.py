from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .cnc_geometry_occ import CncGeometryAnalyzer, CncGeometryError
from .cnc_pdf_report import CncPdfReportBuilder, CncPdfReportError


class CncAnalysisError(RuntimeError):
    pass


class CncReportNotFoundError(CncAnalysisError):
    pass


class CncAnalysisService:
    def __init__(
        self,
        *,
        root: Path,
        geometry_analyzer: CncGeometryAnalyzer | None = None,
        pdf_builder: CncPdfReportBuilder | None = None,
    ) -> None:
        self.root = root
        self.geometry_analyzer = geometry_analyzer or CncGeometryAnalyzer()
        self.pdf_builder = pdf_builder or CncPdfReportBuilder()

    def create_geometry_report(
        self,
        *,
        model_id: str,
        step_path: Path,
        component_node_name: str | None = None,
        component_display_name: str | None = None,
        include_ok_rows: bool = False,
        criteria: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not step_path.exists():
            raise CncAnalysisError("STEP file not found for model.")

        report_id = self._next_report_id(model_id)
        report_dir = self._report_dir(model_id, report_id)
        report_dir.mkdir(parents=True, exist_ok=True)

        try:
            geometry_result = self.geometry_analyzer.analyze(
                step_path=step_path,
                component_node_name=component_node_name,
                component_display_name=component_display_name,
                include_ok_rows=include_ok_rows,
                criteria=criteria,
            )
        except CncGeometryError as exc:
            raise CncAnalysisError(str(exc)) from exc
        except Exception as exc:
            raise CncAnalysisError(
                f"Unexpected geometry analysis error: {exc.__class__.__name__}: {exc}"
            ) from exc

        created_at = self._now_iso()
        response_payload = {
            "report_id": report_id,
            "model_id": model_id,
            "component_node_name": geometry_result.get("component_node_name"),
            "component_display_name": geometry_result.get("component_display_name"),
            "summary": geometry_result.get("summary", {}),
            "corners": geometry_result.get("corners", []),
            "assumptions": geometry_result.get("assumptions", []),
            "criteria_applied": geometry_result.get("criteria_applied", {}),
            "pdf_url": f"/api/models/{model_id}/cnc/reports/{report_id}/pdf",
            "created_at": created_at,
            "part_filename": geometry_result.get("part_filename"),
        }

        result_path = report_dir / "result.json"
        pdf_path = report_dir / "report.pdf"

        try:
            result_path.write_text(
                json.dumps(response_payload, indent=2),
                encoding="utf-8",
            )
            self.pdf_builder.build_pdf(report=response_payload, output_path=pdf_path)
        except (OSError, CncPdfReportError) as exc:
            raise CncAnalysisError(f"Failed to persist CNC report artifacts: {exc}") from exc
        except Exception as exc:
            raise CncAnalysisError(
                f"Unexpected CNC report persistence error: {exc.__class__.__name__}: {exc}"
            ) from exc

        return response_payload

    def get_report(self, *, model_id: str, report_id: str) -> dict[str, Any]:
        result_path = self._report_dir(model_id, report_id) / "result.json"
        if not result_path.exists():
            raise CncReportNotFoundError("CNC report not found.")
        try:
            return json.loads(result_path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise CncAnalysisError(f"Failed to read CNC report result: {exc}") from exc

    def get_report_pdf_path(self, *, model_id: str, report_id: str) -> Path:
        pdf_path = self._report_dir(model_id, report_id) / "report.pdf"
        if not pdf_path.exists():
            raise CncReportNotFoundError("CNC report PDF not found.")
        return pdf_path

    def _reports_root(self, model_id: str) -> Path:
        return self.root / model_id / "cnc_reports"

    def _report_dir(self, model_id: str, report_id: str) -> Path:
        return self._reports_root(model_id) / report_id

    def _next_report_id(self, model_id: str) -> str:
        utc_now = datetime.now(timezone.utc)
        date_token = utc_now.strftime("%Y%m%d")
        prefix = f"cnc_rpt_{date_token}_"
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

    def _now_iso(self) -> str:
        return (
            datetime.now(timezone.utc)
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z")
        )
