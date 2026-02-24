from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from server.dfm_bundle import load_dfm_bundle
from server.dfm_review_v2 import generate_dfm_review_v2


GOLDEN_PATH = REPO_ROOT / "plans" / "dfm_plan_03_review_golden_examples.json"


def test_review_v2_golden_payloads_match_runtime_output():
    bundle = load_dfm_bundle(bundle_dir=REPO_ROOT / "server" / "dfm", repo_root=REPO_ROOT)
    assert GOLDEN_PATH.exists(), f"Missing golden file: {GOLDEN_PATH}"

    payload = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
    scenarios = payload.get("scenarios", [])
    assert scenarios, "Golden payload file has no scenarios."

    for scenario in scenarios:
        scenario_name = scenario["name"]
        request = scenario["request"]
        expected_response = scenario["response"]
        component_context = scenario["component_context"]

        actual_response = generate_dfm_review_v2(
            bundle,
            model_id=request["model_id"],
            component_context=component_context,
            planning_inputs=request.get("planning_inputs"),
            execution_plans=request.get("execution_plans"),
            selected_execution_plan_id=request.get("selected_execution_plan_id"),
            context_payload=request.get("context_payload"),
        )

        assert actual_response == expected_response, (
            f"Golden mismatch for scenario '{scenario_name}'. "
            "If this is expected standards catalog metadata drift (for example "
            "title/notes/url updates in server/dfm/references.json), verify runtime behavior "
            "and rebaseline with: python scripts/rebaseline_dfm_review_v2_golden.py"
        )
