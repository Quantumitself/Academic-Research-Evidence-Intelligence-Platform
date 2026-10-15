"""Tests for the Phase D validator script."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest


def _load_script():
    repo_root = Path(__file__).resolve().parents[2]
    script_path = repo_root / "scripts" / "validate_phase_d.py"
    spec = importlib.util.spec_from_file_location(
        "validate_phase_d_module", script_path
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["validate_phase_d_module"] = module
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


def test_full_validation_passes(script, tmp_path: Path) -> None:
    report_path = tmp_path / "phase_d_report.json"
    exit_code = script.main(["--quiet", "--report", str(report_path)])
    assert exit_code == 0
    assert report_path.exists()
    data = json.loads(report_path.read_text(encoding="utf-8"))
    assert data["ok"] is True
    names = {check["name"] for check in data["checks"]}
    expected = {
        "file storage",
        "import coordinator",
        "pdf extraction",
        "pdf metadata",
        "ocr gating",
        "fts index",
        "library service",
        "reader service",
        "annotations",
        "in-document search",
        "document linking",
        "assistant handoff",
        "persistence survives reopen",
    }
    assert expected <= names


def test_all_checks_pass_individually(script, tmp_path: Path) -> None:
    report_path = tmp_path / "phase_d_report.json"
    script.main(["--quiet", "--report", str(report_path)])
    data = json.loads(report_path.read_text(encoding="utf-8"))
    for check in data["checks"]:
        assert check["ok"], f"check failed: {check['name']} — {check['detail']}"