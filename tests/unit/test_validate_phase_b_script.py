"""Tests for the Phase B validator script."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest


def _load_script():
    repo_root = Path(__file__).resolve().parents[2]
    script_path = repo_root / "scripts" / "validate_phase_b.py"
    spec = importlib.util.spec_from_file_location("validate_phase_b_module", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["validate_phase_b_module"] = module
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


def test_report_to_dict_shape(script) -> None:
    report = script.ValidationReport()
    report.add("x", True, "detail")
    data = report.to_dict()
    assert data["ok"] is True
    assert data["checks"][0]["name"] == "x"
    assert data["checks"][0]["detail"] == "detail"


def test_full_validation_passes(script, tmp_path: Path) -> None:
    report_path = tmp_path / "phase_b_report.json"
    exit_code = script.main(["--quiet", "--report", str(report_path)])
    assert exit_code == 0
    assert report_path.exists()
    data = json.loads(report_path.read_text(encoding="utf-8"))
    assert data["ok"] is True
    names = {check["name"] for check in data["checks"]}
    assert "declared head revision" in names
    assert "upgrade from empty database" in names
    assert "upgrade is idempotent" in names
    assert "every repository constructs" in names
    assert "every schema is importable" in names
    assert "round-trip persistence" in names
    assert "foreign-key cascade behaviour" in names
    assert "append-only contracts enforced" in names
    assert "downgrade to base" in names


def test_all_checks_pass_individually(script, tmp_path: Path) -> None:
    report_path = tmp_path / "phase_b_report.json"
    script.main(["--quiet", "--report", str(report_path)])
    data = json.loads(report_path.read_text(encoding="utf-8"))
    for check in data["checks"]:
        assert check["ok"], f"check failed: {check['name']} — {check['detail']}"