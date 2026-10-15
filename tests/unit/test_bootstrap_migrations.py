"""Tests that the bootstrap runs migrations before constructing the UI."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.unit._migration_head import EXPECTED_HEAD


@pytest.fixture()
def isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "home"
    monkeypatch.setenv("ACADEMIC_PLATFORM_HOME", str(home))
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    return home


def test_migrate_or_report_succeeds(isolated_home: Path) -> None:
    from academic_platform.app import bootstrap
    from academic_platform.app.configuration import load_runtime_directories

    directories = load_runtime_directories()
    url = f"sqlite:///{directories.database_file.as_posix()}"
    assert bootstrap._migrate_or_report(url) is True  # noqa: SLF001


def test_run_application_runs_migrations(
    isolated_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from PySide6.QtWidgets import QApplication

    from academic_platform.app import bootstrap
    from academic_platform.app.configuration import load_runtime_directories
    from academic_platform.infrastructure.database.migrations import current_revision

    directories = load_runtime_directories()

    app = QApplication.instance() or QApplication([])
    _ = app

    monkeypatch.setattr(QApplication, "exec", lambda self: 0)

    exit_code = bootstrap.run_application(directories)
    assert exit_code == 0
    url = f"sqlite:///{directories.database_file.as_posix()}"
    assert current_revision(url) == EXPECTED_HEAD


def test_migrate_or_report_reports_failure(
    isolated_home: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    from academic_platform.app import bootstrap
    from academic_platform.infrastructure.database import migrations as migrations_module

    def _boom(_url: str):
        raise migrations_module.DatabaseMigrationError("boom")

    monkeypatch.setattr(migrations_module, "upgrade_to_head", _boom)
    monkeypatch.setattr(bootstrap, "upgrade_to_head", _boom)

    assert bootstrap._migrate_or_report("sqlite://") is False  # noqa: SLF001
    captured = capsys.readouterr()
    assert "boom" in captured.err