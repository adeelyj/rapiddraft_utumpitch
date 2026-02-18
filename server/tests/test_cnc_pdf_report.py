from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from server.cnc_pdf_report import CncPdfReportBuilder  # noqa: E402


def test_pdf_generator_has_exactly_three_sections_and_renders_headings(tmp_path: Path):
    report = {
        "report_id": "cnc_rpt_20260218_001",
        "model_id": "abc123",
        "component_node_name": "component_1",
        "component_display_name": "Part 1",
        "part_filename": "part.step",
        "summary": {
            "critical_count": 1,
            "warning_count": 2,
            "caution_count": 1,
            "ok_count": 4,
            "machinability_score": 57,
            "cost_impact": "MODERATE",
        },
        "corners": [
            {
                "corner_id": "C1",
                "edge_index": 5,
                "location_description": "top-left-front pocket corner",
                "radius_mm": 0.0,
                "status": "CRITICAL",
                "minimum_tool_required": "Not machinable (rotary tool)",
                "recommendation": "Increase internal radius to >= R3.0 mm",
            }
        ],
        "assumptions": ["Units assumed mm"],
    }

    output_path = tmp_path / "report.pdf"
    builder = CncPdfReportBuilder()
    builder.build_pdf(report=report, output_path=output_path)

    assert output_path.exists()
    assert output_path.stat().st_size > 0
    assert len(CncPdfReportBuilder.SECTION_TITLES) == 3

    pdf_bytes = output_path.read_bytes()
    for section_title in CncPdfReportBuilder.SECTION_TITLES:
        assert section_title.encode("utf-8") in pdf_bytes
