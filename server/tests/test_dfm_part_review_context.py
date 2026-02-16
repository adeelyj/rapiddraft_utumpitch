from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from server.dfm_review import generate_dfm_report_markdown


def test_dfm_report_includes_component_and_industry_inputs():
    markdown, structured = generate_dfm_report_markdown(
        technology="CNC Machining",
        material="Aluminum",
        industry="App Advance",
        rule_set_id="general-dfm-v1",
        component_name="Part 1",
    )

    assert "- Component: **Part 1**" in markdown
    assert "- Industry: **App Advance**" in markdown
    assert structured["assumptions"]
    assert structured["highRiskChecks"]
