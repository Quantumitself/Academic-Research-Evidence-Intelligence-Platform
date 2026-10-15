"""Tests for the bootstrap reconciliation of settings and the database."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture()
def isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "home"
    monkeypatch.setenv("ACADEMIC_PLATFORM_HOME", str(home))
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    return home


def test_reconcile_creates_singleton_row(isolated_home: Path) -> None:
    from academic_platform.app import bootstrap
    from academic_platform.app.configuration import load_runtime_directories
    from academic_platform.app.settings import SettingsService
    from academic_platform.infrastructure.database import Database
    from academic_platform.infrastructure.database.migrations import upgrade_to_head

    directories = load_runtime_directories()
    database = Database.from_path(directories.database_file)
    try:
        upgrade_to_head(database.configuration.url)
        settings_service = SettingsService(directories.config_file)
        settings_service.load()
        assert bootstrap._reconcile_settings_or_report(settings_service, database) is True  # noqa: SLF001

        from academic_platform.infrastructure.repositories.app_settings_repository import (
            AppSettingsRepository,
        )

        with database.session() as session:
            repo = AppSettingsRepository(session)
            row = repo.get_singleton()
            assert row.settings_schema_version >= 1
    finally:
        database.dispose()


def test_run_application_reconciles(
    isolated_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from PySide6.QtWidgets import QApplication

    from academic_platform.app import bootstrap
    from academic_platform.app.configuration import load_runtime_directories

    directories = load_runtime_directories()

    app = QApplication.instance() or QApplication([])
    _ = app

    monkeypatch.setattr(QApplication, "exec", lambda self: 0)

    exit_code = bootstrap.run_application(directories)
    assert exit_code == 0