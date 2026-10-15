"""Tests for the migration command-line tool."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

from tests.unit._migration_head import EXPECTED_HEAD


def _load_script():
    repo_root = Path(__file__).resolve().parents[2]
    script_path = repo_root / "scripts" / "migrate.py"
    spec = importlib.util.spec_from_file_location("migrate_script_module", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["migrate_script_module"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def script():
    return _load_script()


@pytest.fixture()
def database_url(tmp_path: Path) -> str:
    target = tmp_path / "app.sqlite3"
    target.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{target.as_posix()}"


def test_upgrade_then_current(script, database_url: str, capsys) -> None:
    assert script.main(["--url", database_url, "upgrade"]) == 0
    capsys.readouterr()
    assert script.main(["--url", database_url, "current"]) == 0
    assert capsys.readouterr().out.strip() == EXPECTED_HEAD


def test_head_reports_baseline(script, database_url: str, capsys) -> None:
    assert script.main(["--url", database_url, "head"]) == 0
    assert capsys.readouterr().out.strip() == EXPECTED_HEAD


def test_downgrade_to_base(script, database_url: str) -> None:
    script.main(["--url", database_url, "upgrade", "--quiet"])
    assert script.main(["--url", database_url, "downgrade", "base", "--quiet"]) == 0
    assert script.main(["--url", database_url, "current"]) == 0