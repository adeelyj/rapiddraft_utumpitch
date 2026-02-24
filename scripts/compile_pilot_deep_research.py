from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from server.dfm_pilot_deep_research import (
    apply_compile_result_to_bundle,
    compile_deep_research_payload,
    load_deep_research_payload,
    write_compile_artifacts,
)


DEFAULT_EXTERNAL_INPUT = Path(
    r"d:\04_Training_Data\rapiddraft_backend_config\backend\dfm\schemas\piloat_rules_standards.md"
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compile pilot DeepResearch standards/rules into runtime-compatible DFM artifacts.",
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_EXTERNAL_INPUT,
        help="Path to DeepResearch JSON payload.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply compiled executable rules/refs/overlay patch directly into server/dfm bundle files.",
    )
    return parser


def main() -> int:
    args = _parser().parse_args()
    if not args.input.exists():
        raise SystemExit(f"Input payload not found: {args.input}")

    payload = load_deep_research_payload(args.input)
    result = compile_deep_research_payload(payload)

    source_output = REPO_ROOT / "server" / "dfm" / "pilot_deep_research_source.json"
    compiled_output = REPO_ROOT / "server" / "dfm" / "pilot_deep_research_compiled.json"
    mapping_output = REPO_ROOT / "plans" / "dfm_plan_07_pilot_deep_research_mapping_contract.json"
    write_compile_artifacts(
        result,
        source_output_path=source_output,
        compiled_output_path=compiled_output,
        mapping_output_path=mapping_output,
    )

    summary = {
        "source_output": str(source_output),
        "compiled_output": str(compiled_output),
        "mapping_output": str(mapping_output),
        "rules_executable_now": len(result.compiled_rules_executable),
        "rules_deferred": len(result.compiled_rules_deferred),
        "references_patch_count": len(result.references_patch),
    }

    if args.apply:
        apply_summary = apply_compile_result_to_bundle(result)
        summary["apply"] = apply_summary

    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
