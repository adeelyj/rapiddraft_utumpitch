from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def test_dfm_template_endpoints_are_wired_in_main():
    source = (REPO_ROOT / "server" / "main.py").read_text(encoding="utf-8")

    assert '@app.get("/api/models/{model_id}/dfm/templates")' in source
    assert '@app.get("/api/models/{model_id}/dfm/templates/{template_id}")' in source
    assert '@app.post("/api/models/{model_id}/dfm/templates")' in source
    assert '@app.post("/api/models/{model_id}/dfm/plan")' in source


def test_dfm_global_plan_endpoint_is_retained():
    source = (REPO_ROOT / "server" / "main.py").read_text(encoding="utf-8")
    assert '@app.post("/api/dfm/plan")' in source
