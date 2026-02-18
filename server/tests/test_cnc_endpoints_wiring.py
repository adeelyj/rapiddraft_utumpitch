from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def test_cnc_endpoints_are_wired_in_main():
    source = (REPO_ROOT / "server" / "main.py").read_text(encoding="utf-8")

    assert '@app.post("/api/models/{model_id}/cnc/geometry-report")' in source
    assert '@app.get("/api/models/{model_id}/cnc/reports/{report_id}")' in source
    assert '@app.get("/api/models/{model_id}/cnc/reports/{report_id}/pdf")' in source


def test_cnc_sidebar_is_wired_in_app():
    source = (REPO_ROOT / "web" / "src" / "App.tsx").read_text(encoding="utf-8")
    assert "CncAnalysisSidebar" in source
    assert 'handleRightRailToggle("cnc")' in source
    assert "sidebar-rail__label\">CNC<" in source
