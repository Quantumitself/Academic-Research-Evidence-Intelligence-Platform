"""Tests for the Phase A validator script."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest


def _load_script():
    repo_root = Path(__file__).resolve().parents[2]
    script_path = repo_root / "scripts" / "validate_phase_a.py"
    spec = importlib.util.spec_from_file_location("validate_phase_a_module", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["validate_phase_a_module"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def script():
    return _load_script()


def test_report_dataclass_ok_property(script) -> None:
    report = script.ValidationReport()
    assert report.ok
    report.add("a", True)
    assert report.ok
    report.add("b", False)
    assert not report.ok


def test_report_to_dict(script) -> None:
    report = script.ValidationReport()
    report.add("x", True, "detail")
    data = report.to_dict()
    assert data["ok"] is True
    assert data["checks"][0]["name"] == "x"
    assert data["checks"][0]["detail"] == "detail"


def test_full_validation_passes(script, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ACADEMIC_PLATFORM_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    report_path = tmp_path / "report.json"
    exit_code = script.main(["--quiet", "--report", str(report_path)])
    assert exit_code == 0
    assert report_path.exists()
    data = json.loads(report_path.read_text(encoding="utf-8"))
    assert data["ok"] is True
    names = {check["name"] for check in data["checks"]}
    assert "package import" in names
    assert "main window construction" in names
    assert "all destinations registered" in names