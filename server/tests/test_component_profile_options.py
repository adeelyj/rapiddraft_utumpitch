from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def test_dfm_profile_options_file_has_expected_shape():
    options_path = REPO_ROOT / "server" / "data" / "dfm_profile_options.json"
    payload = json.loads(options_path.read_text(encoding="utf-8"))

    assert isinstance(payload.get("materials"), list) and payload["materials"]
    assert isinstance(payload.get("manufacturingProcesses"), list) and payload["manufacturingProcesses"]
    assert isinstance(payload.get("industries"), list) and payload["industries"]

    for entry in payload["materials"]:
        assert isinstance(entry.get("id"), str) and entry["id"]
        assert isinstance(entry.get("label"), str) and entry["label"]

    for entry in payload["manufacturingProcesses"]:
        assert isinstance(entry.get("id"), str) and entry["id"]
        assert isinstance(entry.get("label"), str) and entry["label"]

    industry_ids = set()
    for entry in payload["industries"]:
        assert isinstance(entry.get("id"), str) and entry["id"]
        assert isinstance(entry.get("label"), str) and entry["label"]
        assert isinstance(entry.get("standards"), list)
        industry_ids.add(entry["id"])

    assert "none" in industry_ids
