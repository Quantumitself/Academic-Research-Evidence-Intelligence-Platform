"""Tests for the command-line entry point."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from academic_platform import main as main_module


@pytest.fixture(autouse=True)
def _isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ACADEMIC_PLATFORM_HOME", str(tmp_path / "home"))
    from academic_platform.app import logging_setup

    logging_setup._configured = False  # noqa: SLF001 - test reset


def test_version_flag(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main_module.main(["--version"])
    captured = capsys.readouterr()
    assert exit_code == main_module.EXIT_SUCCESS
    assert captured.out.strip()


def test_audit_flag(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    exit_code = main_module.main(["--audit"])
    captured = capsys.readouterr()
    assert exit_code == main_module.EXIT_SUCCESS
    assert "Resolved runtime directories" in captured.out
    assert str(tmp_path / "home") in captured.out


def test_no_log_file_flag(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    exit_code = main_module.main(["--audit", "--no-log-file"])
    capsys.readouterr()
    assert exit_code == main_module.EXIT_SUCCESS
    assert not (tmp_path / "home" / "logs" / "academic_platform.log").exists()


def test_log_file_created_by_default(tmp_path: Path) -> None:
    exit_code = main_module.main(["--audit"])
    assert exit_code == main_module.EXIT_SUCCESS
    log_file = tmp_path / "home" / "logs" / "academic_platform.log"
    assert log_file.exists()


def test_settings_flag_prints_path_and_defaults(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    exit_code = main_module.main(["--settings"])
    captured = capsys.readouterr()
    assert exit_code == main_module.EXIT_SUCCESS
    assert str(tmp_path / "home" / "config" / "config.toml") in captured.out
    # The JSON payload must be parseable and contain the current schema version.
    payload = captured.out.split("Effective settings:\n", 1)[1]
    parsed = json.loads(payload)
    assert parsed["schema_version"] >= 1
    assert "appearance" in parsed


def test_settings_flag_reports_invalid_file(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    config_path = tmp_path / "home" / "config" / "config.toml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text("this is not = valid = toml\n", encoding="utf-8")
    exit_code = main_module.main(["--settings"])
    captured = capsys.readouterr()
    assert exit_code == main_module.EXIT_CONFIGURATION_ERROR
    assert "Configuration error" in captured.err