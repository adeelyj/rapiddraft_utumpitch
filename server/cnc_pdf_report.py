from __future__ import annotations

from pathlib import Path
from typing import Any


class CncPdfReportError(RuntimeError):
    pass


class CncPdfReportBuilder:
    SECTION_TITLES = (
        "1. Summary Box",
        "2. Corner Detail Table",
        "3. Designer Guidance",
    )

    def build_pdf(self, *, report: dict[str, Any], output_path: Path) -> Path:
        try:
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
            from reportlab.lib.units import mm
            from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
        except Exception as exc:  # pragma: no cover - environment dependent
            raise CncPdfReportError(
                "reportlab is required for CNC PDF export. Install reportlab."
            ) from exc

        output_path.parent.mkdir(parents=True, exist_ok=True)

        summary = report.get("summary", {}) if isinstance(report, dict) else {}
        corners = report.get("corners", []) if isinstance(report, dict) else []
        part_filename = report.get("part_filename") or "Unknown part"

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "CncTitle",
            parent=styles["Heading1"],
            fontSize=16,
            leading=20,
            textColor=colors.HexColor("#14233D"),
            spaceAfter=8,
        )
        section_style = ParagraphStyle(
            "CncSection",
            parent=styles["Heading2"],
            fontSize=12,
            leading=14,
            textColor=colors.HexColor("#1D355B"),
            spaceBefore=10,
            spaceAfter=6,
        )
        text_style = ParagraphStyle(
            "CncText",
            parent=styles["BodyText"],
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#22324A"),
        )

        doc = SimpleDocTemplate(
            str(output_path),
            pagesize=A4,
            leftMargin=16 * mm,
            rightMargin=16 * mm,
            topMargin=14 * mm,
            bottomMargin=12 * mm,
            pageCompression=0,
        )

        summary_rows = [
            ["Part filename", str(part_filename)],
            [
                "Counts",
                (
                    f"CRITICAL: {int(summary.get('critical_count', 0))} | "
                    f"WARNING: {int(summary.get('warning_count', 0))} | "
                    f"CAUTION: {int(summary.get('caution_count', 0))} | "
                    f"OK: {int(summary.get('ok_count', 0))}"
                ),
            ],
            ["Machinability score", str(summary.get("machinability_score", 0))],
            ["Cost impact", str(summary.get("cost_impact", "LOW"))],
        ]
        summary_table = Table(summary_rows, colWidths=[34 * mm, 140 * mm], hAlign="LEFT")
        summary_table.setStyle(
            TableStyle(
                [
                    ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#A6B7CF")),
                    ("INNERGRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CBD7E7")),
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FBFF")),
                    ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                    ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ]
            )
        )

        table_header = [
            "Corner ID",
            "Location Description",
            "Measured Radius",
            "Minimum Tool Required",
            "Status",
            "Recommendation",
        ]

        table_rows = [table_header]
        status_rows: list[tuple[int, str]] = []

        if corners:
            for row_index, corner in enumerate(corners, start=1):
                if not isinstance(corner, dict):
                    continue
                radius = corner.get("radius_mm")
                radius_text = "-"
                if isinstance(radius, (int, float)):
                    radius_text = f"R{float(radius):.3f} mm"
                status = str(corner.get("status", "OK"))
                table_rows.append(
                    [
                        str(corner.get("corner_id", "-")),
                        str(corner.get("location_description", "-")),
                        radius_text,
                        str(corner.get("minimum_tool_required", "-")),
                        status,
                        str(corner.get("recommendation", "-")),
                    ]
                )
                status_rows.append((row_index, status))
        else:
            table_rows.append(["-", "No flagged corners", "-", "-", "OK", "No action needed"])
            status_rows.append((1, "OK"))

        detail_table = Table(
            table_rows,
            colWidths=[16 * mm, 38 * mm, 24 * mm, 34 * mm, 18 * mm, 44 * mm],
            repeatRows=1,
            hAlign="LEFT",
        )
        detail_style = TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.7, colors.HexColor("#A6B7CF")),
                ("INNERGRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#CBD7E7")),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EAF2FF")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 8),
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 1), (-1, -1), 8),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )

        status_colors = {
            "CRITICAL": colors.HexColor("#FDE8E9"),
            "WARNING": colors.HexColor("#FFF1DC"),
            "CAUTION": colors.HexColor("#FFF8DF"),
            "OK": colors.HexColor("#EAF8ED"),
        }
        for row_index, status in status_rows:
            detail_style.add(
                "BACKGROUND",
                (0, row_index),
                (-1, row_index),
                status_colors.get(status, colors.white),
            )
        detail_table.setStyle(detail_style)

        critical_count = int(summary.get("critical_count", 0))
        warning_count = int(summary.get("warning_count", 0))
        caution_count = int(summary.get("caution_count", 0))
        ok_count = int(summary.get("ok_count", 0))

        action_line = (
            "Prioritize CRITICAL corners first, then WARNING corners, then CAUTION corners "
            "to reduce machining risk and cycle-time impact."
            if (critical_count + warning_count + caution_count) > 0
            else "No immediate corner-radius action required for current thresholds."
        )

        guidance_lines = [
            (
                "This report uses deterministic geometry checks for concave internal "
                "corner conditions likely to impact milling feasibility."
            ),
            (
                f"Detected corners: CRITICAL {critical_count}, WARNING {warning_count}, "
                f"CAUTION {caution_count}, OK {ok_count}."
            ),
            action_line,
            "Rule of thumb: Internal corners >= R3mm for aluminum, >= R4mm for steel.",
        ]

        story = [
            Paragraph("CNC Geometry Analysis Report", title_style),
            Paragraph(self.SECTION_TITLES[0], section_style),
            summary_table,
            Spacer(1, 8),
            Paragraph(self.SECTION_TITLES[1], section_style),
            detail_table,
            Spacer(1, 8),
            Paragraph(self.SECTION_TITLES[2], section_style),
        ]
        story.extend(Paragraph(line, text_style) for line in guidance_lines)

        try:
            doc.build(story)
        except Exception as exc:
            raise CncPdfReportError(f"Failed to generate CNC PDF report: {exc}") from exc
        return output_path
