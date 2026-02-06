"""
Utility helpers to make FreeCAD's Python modules discoverable at runtime.

The backend relies on FreeCAD's `lib` and `bin` directories being available. This
module attempts to locate those paths automatically based on the operating system
and environment variables.
"""
from __future__ import annotations

import os
import platform
import sys
from pathlib import Path
from typing import Iterable, List


def _unique_paths(paths: Iterable[Path]) -> List[Path]:
    seen = set()
    unique = []
    for path in paths:
        normalized = path.resolve()
        if not normalized.exists():
            continue
        if normalized in seen:
            continue
        seen.add(normalized)
        unique.append(normalized)
    return unique


def _windows_candidates() -> Iterable[Path]:
    program_files = Path(os.environ.get("PROGRAMFILES", r"C:\Program Files"))
    program_files_x86 = Path(os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)"))
    for base in (program_files, program_files_x86):
        for entry in base.glob("FreeCAD*"):
            yield entry / "lib"


def _linux_candidates() -> Iterable[Path]:
    common = [
        Path("/usr/lib/freecad/lib"),
        Path("/usr/local/lib/freecad/lib"),
    ]
    for path in common:
        yield path


def _darwin_candidates() -> Iterable[Path]:
    yield Path("/Applications/FreeCAD.app/Contents/lib")


def discover_freecad_libs() -> List[Path]:
    env_candidates = [
        os.environ.get("FREECAD_LIB"),
        os.environ.get("FREECAD_LIBRARY"),
        os.environ.get("FREECAD_PYTHON_LIB"),
    ]
    paths = [Path(p) for p in env_candidates if p]

    system = platform.system().lower()
    if system == "windows":
        paths.extend(_windows_candidates())
    elif system == "darwin":
        paths.extend(_darwin_candidates())
    else:
        paths.extend(_linux_candidates())
    return _unique_paths(paths)


def discover_freecad_bins() -> List[Path]:
    env_candidates = [
        os.environ.get("FREECAD_BIN"),
        os.environ.get("FREECAD_BINARY"),
    ]
    paths = [Path(p) for p in env_candidates if p]

    system = platform.system().lower()
    if system == "windows":
        program_files = Path(os.environ.get("PROGRAMFILES", r"C:\Program Files"))
        program_files_x86 = Path(os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)"))
        for base in (program_files, program_files_x86):
            for entry in base.glob("FreeCAD*"):
                paths.append(entry / "bin")
    elif system == "darwin":
        paths.append(Path("/Applications/FreeCAD.app/Contents/MacOS"))
    else:
        paths.append(Path("/usr/bin"))
    return _unique_paths(paths)


def ensure_freecad_in_path() -> None:
    """
    Inject discovered FreeCAD library/bin directories into sys.path and PATH.
    """
    libs = discover_freecad_libs()
    for lib in libs:
        lib_str = str(lib)
        if lib_str not in sys.path:
            sys.path.insert(0, lib_str)

    bins = discover_freecad_bins()
    existing_path = os.environ.get("PATH", "")
    path_entries = existing_path.split(os.pathsep) if existing_path else []
    updated = False

    for bin_path in bins:
        bin_str = str(bin_path)
        if bin_str not in path_entries:
            path_entries.insert(0, bin_str)
            updated = True
        # FreeCAD's Python module on Windows is shipped as a .pyd in the bin dir.
        # Add bin to sys.path so `import FreeCAD` works without manual PYTHONPATH tweaks.
        if bin_str not in sys.path:
            sys.path.insert(0, bin_str)

    if updated:
        os.environ["PATH"] = os.pathsep.join(path_entries)
