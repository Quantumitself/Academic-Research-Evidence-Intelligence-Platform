"""Tests for the Phase C validator script."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest


def _load_script():
    repo_root = Path(__file__).resolve().parents[2]
    script_path = repo_root / "scripts" / "validate_phase_c.py"
    spec = importlib.util.spec_from_file_location(
        "validate_phase_c_module", script_path
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["validate_phase_c_module"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def script():
    return _load_script()


def test_full_validation_passes(script, tmp_path: Path) -> None:
    report_path = tmp_path / "phase_c_report.json"
    exit_code = script.main(["--quiet", "--report", str(report_path)])
    assert exit_code == 0
    assert report_path.exists()
    data = json.loads(report_path.read_text(encoding="utf-8"))
    assert data["ok"] is True
    names = {check["name"] for check in data["checks"]}
    assert "catalog installer" in names
    assert "provider registry" in names
    assert "orchestrator deduplicates" in names
    assert "orchestrator partial failures" in names
    assert "saved-search service" in names
    assert "session recording" in names
    assert "source management" in names
    assert "publication idempotence" in names


def test_all_checks_pass_individually(script, tmp_path: Path) -> None:
    report_path = tmp_path / "phase_c_report.json"
    script.main(["--quiet", "--report", str(report_path)])
    data = json.loads(report_path.read_text(encoding="utf-8"))
    for check in data["checks"]:
        assert check["ok"], f"check failed: {check['name']} — {check['detail']}"