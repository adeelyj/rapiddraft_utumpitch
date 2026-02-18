from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from server.cnc_analysis import (  # noqa: E402
    CncAnalysisService,
    CncReportNotFoundError,
)


class _FakeAnalyzer:
    def __init__(self):
        self.calls = 0
        self.last_kwargs = {}

    def analyze(self, **kwargs):
        self.last_kwargs = dict(kwargs)
        self.calls += 1
        return {
            "component_node_name": "component_1",
            "component_display_name": "Part 1",
            "part_filename": "source.step",
            "summary": {
                "critical_count": 1,
                "warning_count": 2,
                "caution_count": 3,
                "ok_count": 4,
                "machinability_score": 33,
                "cost_impact": "HIGH",
            },
            "corners": [
                {
                    "corner_id": "C1",
                    "edge_index": 42,
                    "location_description": "top-left-front pocket corner",
                    "radius_mm": 0.0,
                    "status": "CRITICAL",
                    "minimum_tool_required": "Not machinable (rotary tool)",
                    "recommendation": "Increase internal radius to >= R3.0 mm",
                    "pocket_depth_mm": 12.4,
                    "depth_to_radius_ratio": None,
                    "aggravating_factor": False,
                }
            ],
            "assumptions": ["Units assumed mm"],
            "criteria_applied": {
                "thresholds": {
                    "critical_enabled": True,
                    "critical_max_mm": 0.0001,
                    "warning_enabled": True,
                    "warning_max_mm": 1.5,
                    "caution_enabled": True,
                    "caution_max_mm": 3.0,
                    "ok_enabled": True,
                    "ok_min_mm": 3.0,
                },
                "filters": {
                    "concave_internal_edges_only": True,
                    "pocket_internal_cavity_heuristic": True,
                    "exclude_bbox_exterior_edges": True,
                    "include_ok_rows_in_output": False,
                },
                "aggravating_factor_ratio_threshold": 5.0,
            },
        }


class _FakePdfBuilder:
    def build_pdf(self, *, report, output_path: Path):
        output_path.write_bytes(f"PDF::{report['report_id']}".encode("utf-8"))
        return output_path


def test_service_persists_result_json_and_pdf(tmp_path: Path):
    step_path = tmp_path / "model.step"
    step_path.write_text("dummy", encoding="utf-8")

    service = CncAnalysisService(
        root=tmp_path,
        geometry_analyzer=_FakeAnalyzer(),
        pdf_builder=_FakePdfBuilder(),
    )
    payload = service.create_geometry_report(
        model_id="model_x",
        step_path=step_path,
        component_node_name="component_1",
        component_display_name="Part 1",
        include_ok_rows=False,
    )

    assert payload["report_id"].startswith("cnc_rpt_")
    assert payload["pdf_url"] == f"/api/models/model_x/cnc/reports/{payload['report_id']}/pdf"

    report_dir = tmp_path / "model_x" / "cnc_reports" / payload["report_id"]
    assert (report_dir / "result.json").exists()
    assert (report_dir / "report.pdf").exists()

    loaded = service.get_report(model_id="model_x", report_id=payload["report_id"])
    assert loaded["report_id"] == payload["report_id"]
    assert loaded["summary"]["critical_count"] == 1

    pdf_path = service.get_report_pdf_path(model_id="model_x", report_id=payload["report_id"])
    assert pdf_path.name == "report.pdf"


def test_service_increments_report_id_sequence(tmp_path: Path):
    step_path = tmp_path / "model.step"
    step_path.write_text("dummy", encoding="utf-8")
    service = CncAnalysisService(
        root=tmp_path,
        geometry_analyzer=_FakeAnalyzer(),
        pdf_builder=_FakePdfBuilder(),
    )

    first = service.create_geometry_report(model_id="model_x", step_path=step_path)
    second = service.create_geometry_report(model_id="model_x", step_path=step_path)
    assert first["report_id"] != second["report_id"]
    assert first["report_id"].endswith("_001")
    assert second["report_id"].endswith("_002")


def test_service_passes_criteria_to_analyzer(tmp_path: Path):
    step_path = tmp_path / "model.step"
    step_path.write_text("dummy", encoding="utf-8")
    analyzer = _FakeAnalyzer()
    service = CncAnalysisService(
        root=tmp_path,
        geometry_analyzer=analyzer,
        pdf_builder=_FakePdfBuilder(),
    )

    payload = service.create_geometry_report(
        model_id="model_x",
        step_path=step_path,
        include_ok_rows=True,
        criteria={
            "thresholds": {
                "critical_enabled": False,
                "critical_max_mm": 0.2,
            },
            "filters": {
                "include_ok_rows_in_output": True,
            },
            "aggravating_factor_ratio_threshold": 7.0,
        },
    )

    assert analyzer.last_kwargs.get("include_ok_rows") is True
    assert analyzer.last_kwargs.get("criteria", {}).get("aggravating_factor_ratio_threshold") == 7.0
    assert "criteria_applied" in payload


def test_get_report_and_pdf_raise_not_found_for_missing_id(tmp_path: Path):
    service = CncAnalysisService(
        root=tmp_path,
        geometry_analyzer=_FakeAnalyzer(),
        pdf_builder=_FakePdfBuilder(),
    )

    with pytest.raises(CncReportNotFoundError):
        service.get_report(model_id="missing_model", report_id="missing")
    with pytest.raises(CncReportNotFoundError):
        service.get_report_pdf_path(model_id="missing_model", report_id="missing")
