from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def test_part_facts_endpoints_are_wired_in_main():
    source = (REPO_ROOT / "server" / "main.py").read_text(encoding="utf-8")
    assert '@app.get("/api/models/{model_id}/components/{node_name}/part-facts")' in source
    assert '@app.post("/api/models/{model_id}/components/{node_name}/part-facts/refresh")' in source

