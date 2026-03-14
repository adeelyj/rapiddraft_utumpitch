from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from server.freecad_setup import relaunch_with_compatible_freecad_python

TEST_ARGS = [
    "server/tests/test_cnc_geometry_occ.py",
    "server/tests/test_dfm_feature_parity.py",
    "server/tests/test_dfm_benchmark.py",
]


def main() -> int:
    relaunch_exit_code = relaunch_with_compatible_freecad_python(
        argv=[__file__, *sys.argv[1:]],
        require_occ=True,
    )
    if relaunch_exit_code is not None:
        return relaunch_exit_code

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
