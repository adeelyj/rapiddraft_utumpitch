from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_script_module(script_name: str):
    script_path = REPO_ROOT / "scripts" / script_name
    module_name = f"test_{script_name.replace('.', '_')}"
    spec = importlib.util.spec_from_file_location(module_name, script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_report_dfm_feature_parity_relaunches_before_importing_occ_modules(monkeypatch):
    module = _load_script_module("report_dfm_feature_parity.py")

    monkeypatch.setattr(module, "relaunch_with_compatible_freecad_python", lambda argv, require_occ: 7)

    assert module.main() == 7


def test_report_dfm_feature_parity_runs_after_relaunch_check(monkeypatch, tmp_path: Path):
    module = _load_script_module("report_dfm_feature_parity.py")

    observed: dict[str, object] = {}

    monkeypatch.setattr(module, "relaunch_with_compatible_freecad_python", lambda argv, require_occ: None)
    monkeypatch.setattr(module, "DEFAULT_MANIFEST", tmp_path / "manifest.json")
    monkeypatch.setattr(module.sys, "argv", ["report_dfm_feature_parity.py"])

    fake_parity = types.ModuleType("server.dfm_feature_parity")

    def _fake_generate_feature_parity_report(manifest, run_label=None):
        observed["manifest"] = manifest
        observed["run_label"] = run_label
        return {
            "cases": [{"name": "demo"}],
            "output_root": str(tmp_path / "report"),
        }

    fake_parity.generate_feature_parity_report = _fake_generate_feature_parity_report
    monkeypatch.setitem(sys.modules, "server.dfm_feature_parity", fake_parity)

    assert module.main() == 0
    assert observed["manifest"] == tmp_path / "manifest.json"
    assert observed["run_label"] is None


def test_run_dfm_feature_detection_gate_relaunches_before_running_pytest(monkeypatch):
    module = _load_script_module("run_dfm_feature_detection_gate.py")

    monkeypatch.setattr(module, "relaunch_with_compatible_freecad_python", lambda argv, require_occ: 11)

    assert module.main() == 11


def test_run_dfm_feature_detection_gate_uses_current_python_after_relaunch(monkeypatch):
    module = _load_script_module("run_dfm_feature_detection_gate.py")

    observed: dict[str, object] = {}

    monkeypatch.setattr(module, "relaunch_with_compatible_freecad_python", lambda argv, require_occ: None)
    monkeypatch.setattr(module.sys, "executable", r"C:\FreeCAD\bin\python.exe")

    class _Completed:
        returncode = 0

    def _fake_run(argv, cwd=None):
        observed["argv"] = argv
        observed["cwd"] = cwd
        return _Completed()

    monkeypatch.setattr(module.subprocess, "run", _fake_run)

    assert module.main() == 0
    assert observed["argv"] == [r"C:\FreeCAD\bin\python.exe", "-m", "pytest", "-q", *module.TEST_ARGS]
    assert observed["cwd"] == module.REPO_ROOT
