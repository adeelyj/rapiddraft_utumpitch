from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from server.dfm_bundle import load_dfm_bundle
from server.dfm_review_v2 import generate_dfm_review_v2


GOLDEN_PATH = REPO_ROOT / "plans" / "dfm_plan_03_review_golden_examples.json"


def main() -> None:
    bundle = load_dfm_bundle(bundle_dir=REPO_ROOT / "server" / "dfm", repo_root=REPO_ROOT)
    if not GOLDEN_PATH.exists():
        raise FileNotFoundError(f"Missing golden file: {GOLDEN_PATH}")

    payload = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
    scenarios = payload.get("scenarios", [])
    if not isinstance(scenarios, list) or not scenarios:
        raise ValueError("Golden payload file has no scenarios.")

    for scenario in scenarios:
        if not isinstance(scenario, dict):
            continue
        request = scenario.get("request", {})
        component_context = scenario.get("component_context", {})
        if not isinstance(request, dict):
            continue
        if not isinstance(component_context, dict):
            component_context = {}
        scenario["response"] = generate_dfm_review_v2(
            bundle,
            model_id=request.get("model_id", ""),
            component_context=component_context,
            planning_inputs=request.get("planning_inputs"),
            execution_plans=request.get("execution_plans"),
            selected_execution_plan_id=request.get("selected_execution_plan_id"),
            context_payload=request.get("context_payload"),
        )

    GOLDEN_PATH.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"Rebaselined review-v2 golden scenarios: {len(scenarios)}")


if __name__ == "__main__":
    main()
