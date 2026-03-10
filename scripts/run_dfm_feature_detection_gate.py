from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

TEST_ARGS = [
    "server/tests/test_cnc_geometry_occ.py",
    "server/tests/test_dfm_feature_parity.py",
    "server/tests/test_dfm_benchmark.py",
]


def main() -> int:
    command = [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        *TEST_ARGS,
    ]
    completed = subprocess.run(command, cwd=REPO_ROOT)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
