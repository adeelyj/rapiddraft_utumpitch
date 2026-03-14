"""
Utility helpers to make FreeCAD's Python modules discoverable at runtime.

The backend relies on FreeCAD's `lib` and `bin` directories being available. This
module attempts to locate those paths automatically based on the operating system
and environment variables.
"""
from __future__ import annotations

import importlib
import os
import platform
import subprocess
import sys
from pathlib import Path
from typing import Iterable, List


FREECAD_PYTHON_RELAUNCH_ENV = "RAPIDDRAFT_FREECAD_PYTHON_RELAUNCH"


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


def discover_freecad_python_executables() -> List[Path]:
    candidates: list[Path] = []
    executable_names = ["python.exe"] if platform.system().lower() == "windows" else ["python3", "python"]
    for bin_path in discover_freecad_bins():
        for executable_name in executable_names:
            candidate = bin_path / executable_name
            if candidate.exists():
                candidates.append(candidate)
    return _unique_paths(candidates)


def _bin_site_packages(bin_path: Path) -> list[Path]:
    candidates = [
        bin_path / "Lib" / "site-packages",
        bin_path.parent / "lib" / "site-packages",
    ]
    return [candidate for candidate in candidates if candidate.exists()]


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
        for site_packages in _bin_site_packages(bin_path):
            site_packages_str = str(site_packages)
            if site_packages_str not in sys.path:
                sys.path.insert(0, site_packages_str)

    if updated:
        os.environ["PATH"] = os.pathsep.join(path_entries)


def current_python_supports_freecad(*, require_occ: bool = False) -> bool:
    ensure_freecad_in_path()
    try:
        importlib.import_module("FreeCAD")
        if require_occ:
            importlib.import_module("OCC")
    except Exception:
        return False
    return True


def _candidate_supports_freecad(candidate: Path, *, require_occ: bool = False) -> bool:
    probe_lines = [
        "import importlib",
        "import sys",
        "importlib.import_module('FreeCAD')",
    ]
    if require_occ:
        probe_lines.append("importlib.import_module('OCC')")
    probe_lines.append("print('OK')")

    try:
        completed = subprocess.run(
            [str(candidate), "-c", "; ".join(probe_lines)],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
    except Exception:
        return False
    return completed.returncode == 0 and completed.stdout.strip().endswith("OK")


def relaunch_with_compatible_freecad_python(
    *,
    argv: list[str],
    require_occ: bool = False,
) -> int | None:
    if current_python_supports_freecad(require_occ=require_occ):
        return None

    if os.environ.get(FREECAD_PYTHON_RELAUNCH_ENV) == "1":
        return None

    current_python = Path(sys.executable).resolve()
    for candidate in discover_freecad_python_executables():
        resolved_candidate = candidate.resolve()
        if resolved_candidate == current_python:
            continue
        if not _candidate_supports_freecad(resolved_candidate, require_occ=require_occ):
            continue
        env = os.environ.copy()
        env[FREECAD_PYTHON_RELAUNCH_ENV] = "1"
        print(f"Re-launching under FreeCAD Python: {resolved_candidate}")
        completed = subprocess.run(
            [str(resolved_candidate), *argv],
            env=env,
            check=False,
        )
        return int(completed.returncode)

    return None
