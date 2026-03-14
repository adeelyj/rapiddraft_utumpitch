from __future__ import annotations

import sys
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

import freecad_setup as fs


def test_discover_freecad_python_executables_prefers_bin_python(monkeypatch, tmp_path: Path):
    freecad_bin = tmp_path / "FreeCAD" / "bin"
    freecad_bin.mkdir(parents=True)
    python_exe = freecad_bin / "python.exe"
    python_exe.write_text("", encoding="utf-8")

    monkeypatch.setattr(fs, "discover_freecad_bins", lambda: [freecad_bin])

    candidates = fs.discover_freecad_python_executables()

    assert candidates == [python_exe.resolve()]


def test_relaunch_with_compatible_freecad_python_returns_none_when_current_python_is_compatible(
    monkeypatch,
):
    monkeypatch.setattr(fs, "current_python_supports_freecad", lambda require_occ=False: True)

    result = fs.relaunch_with_compatible_freecad_python(
        argv=["scripts/run_dfm_mtk_benchmark.py"],
        require_occ=True,
    )

    assert result is None


def test_relaunch_with_compatible_freecad_python_uses_discovered_candidate(
    monkeypatch,
    tmp_path: Path,
):
    candidate = tmp_path / "FreeCAD" / "bin" / "python.exe"
    candidate.parent.mkdir(parents=True)
    candidate.write_text("", encoding="utf-8")
    observed: dict[str, object] = {}

    monkeypatch.setattr(fs, "current_python_supports_freecad", lambda require_occ=False: False)
    monkeypatch.delenv(fs.FREECAD_PYTHON_RELAUNCH_ENV, raising=False)
    monkeypatch.setattr(fs, "discover_freecad_python_executables", lambda: [candidate])
    monkeypatch.setattr(fs, "_candidate_supports_freecad", lambda path, require_occ=False: True)

    class _Completed:
        returncode = 0

    def _fake_run(argv, env=None, check=False):
        observed["argv"] = argv
        observed["env"] = env
        observed["check"] = check
        return _Completed()

    monkeypatch.setattr(fs.subprocess, "run", _fake_run)

    result = fs.relaunch_with_compatible_freecad_python(
        argv=["scripts/run_dfm_mtk_benchmark.py", "--run-label", "demo"],
        require_occ=True,
    )

    assert result == 0
    assert observed["argv"] == [str(candidate.resolve()), "scripts/run_dfm_mtk_benchmark.py", "--run-label", "demo"]
    assert observed["env"][fs.FREECAD_PYTHON_RELAUNCH_ENV] == "1"
    assert observed["check"] is False
