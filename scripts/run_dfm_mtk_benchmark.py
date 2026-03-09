from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from server.dfm_benchmark import run_benchmark


DEFAULT_MANIFEST = REPO_ROOT / "plans" / "dfm_mtk_benchmark_manifest.local.json"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the DFM MTK benchmark against the current RapidDraft backend contracts.",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST,
        help="Path to the benchmark manifest JSON file.",
    )
    parser.add_argument(
        "--run-label",
        type=str,
        default="",
        help="Optional stable label for the output folder.",
    )
    return parser


def main() -> int:
    args = _parser().parse_args()
    summary = run_benchmark(
        args.manifest,
        run_label=args.run_label or None,
    )
    print(json.dumps(summary["summary"], indent=2))
    print(f"Output written to: {summary['output_root']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
