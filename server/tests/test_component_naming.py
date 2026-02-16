from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from server.cad_service import CADService


def test_extract_step_product_names_parses_and_dedupes(tmp_path: Path):
    step_file = tmp_path / "sample.step"
    step_file.write_text(
        "\n".join(
            [
                "ISO-10303-21;",
                "DATA;",
                "#10=PRODUCT('ID_A','Part 1','',(#99));",
                "#11=PRODUCT('ID_B','Part 2','',(#99));",
                "#12=PRODUCT('ID_C','Part 1','',(#99));",
                "ENDSEC;",
                "END-ISO-10303-21;",
            ]
        ),
        encoding="utf-8",
    )

    service = CADService(workspace=tmp_path / "workspace")
    assert service._extract_step_product_names(step_file) == ["Part 1", "Part 2"]


def test_extract_step_product_names_normalizes_whitespace_and_empty(tmp_path: Path):
    step_file = tmp_path / "sample.step"
    step_file.write_text(
        "\n".join(
            [
                "ISO-10303-21;",
                "DATA;",
                "#10=PRODUCT('ID_A','  Bracket   Top  ','',(#99));",
                "#11=PRODUCT('ID_B','','',(#99));",
                "ENDSEC;",
                "END-ISO-10303-21;",
            ]
        ),
        encoding="utf-8",
    )

    service = CADService(workspace=tmp_path / "workspace")
    assert service._extract_step_product_names(step_file) == ["Bracket Top"]


def test_resolve_component_name_uses_fallback_when_missing(tmp_path: Path):
    service = CADService(workspace=tmp_path / "workspace")
    assert service._resolve_component_name(1, ["Part A"]) == "Part A"
    assert service._resolve_component_name(2, ["Part A"]) == "Part 2"
    assert service._resolve_component_name(3, []) == "Part 3"
