"""
Smoke test to confirm that required Python dependencies are present.

Running `pytest server/tests/test_dependencies.py -s` will print a line per dependency
in the format `Dependency name - Status`.
"""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

from freecad_setup import ensure_freecad_in_path

ensure_freecad_in_path()

DEPENDENCIES = [
    ("fastapi", "fastapi"),
    ("uvicorn", "uvicorn"),
    ("python-multipart", "multipart"),
    ("pydantic", "pydantic"),
    ("aiofiles", "aiofiles"),
    ("numpy", "numpy"),
    ("matplotlib", "matplotlib"),
    ("FreeCAD", "FreeCAD"),  # required for CAD processing
]


def test_dependencies_available():
    missing = []
    status_lines = []

    for display_name, module_name in DEPENDENCIES:
        try:
            importlib.import_module(module_name)
            status_lines.append(f"{display_name} - OK")
        except Exception as exc:  # pragma: no cover - import errors don't need coverage
            status_lines.append(f"{display_name} - MISSING ({exc})")
            missing.append(display_name)

    print("\n".join(status_lines))

    if missing:
        raise AssertionError(f"Missing dependencies: {', '.join(missing)}")
