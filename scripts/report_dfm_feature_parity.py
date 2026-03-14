from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from server.dfm_feature_parity import generate_feature_parity_report


PREFERRED_MANIFEST = REPO_ROOT / "plans" / "20260313" / "dfm_mtk_benchmark_manifest.local.json"
LEGACY_MANIFEST = REPO_ROOT / "plans" / "dfm_mtk_benchmark_manifest.local.json"
DEFAULT_MANIFEST = PREFERRED_MANIFEST if PREFERRED_MANIFEST.exists() else LEGACY_MANIFEST


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate a feature-detection parity report between Cadex feature groups and current RapidDraft STEP-derived signals.",
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
    report = generate_feature_parity_report(
        args.manifest,
        run_label=args.run_label or None,
    )
    print(json.dumps({"case_count": len(report.get("cases", [])), "output_root": report.get("output_root")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
