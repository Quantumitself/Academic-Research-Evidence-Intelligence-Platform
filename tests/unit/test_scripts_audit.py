"""Tests for the repository audit script."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


def _load_script(module_name: str, relative_path: str):
    repo_root = Path(__file__).resolve().parents[2]
    script_path = repo_root / relative_path
    spec = importlib.util.spec_from_file_location(module_name, script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def audit_module():
    return _load_script("audit_repository_module", "scripts/audit_repository.py")


@pytest.fixture(scope="module")
def inventory_module():
    return _load_script("dependency_inventory_module", "scripts/dependency_inventory.py")


def test_audit_runs(audit_module) -> None:
    exit_code = audit_module.main(["--quiet"])
    assert exit_code == 0
    output = Path(audit_module.OUTPUT_FILE)
    assert output.exists()
    content = output.read_text(encoding="utf-8")
    assert "# Repository Audit" in content


def test_inventory_runs(inventory_module) -> None:
    exit_code = inventory_module.main(["--quiet"])
    assert exit_code == 0
    output = Path(inventory_module.OUTPUT_FILE)
    assert output.exists()
    content = output.read_text(encoding="utf-8")
    assert "# Dependency Inventory" in content
    assert "Declared Runtime Dependencies" in content