"""Tests that the bootstrap opens a database and disposes it correctly."""

from __future__ import annotations

from pathlib import Path

import pytest

from academic_platform.app import bootstrap


@pytest.fixture()
def isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "home"
    monkeypatch.setenv("ACADEMIC_PLATFORM_HOME", str(home))
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    return home


def test_open_database_creates_file(isolated_home: Path) -> None:
    from academic_platform.app.configuration import load_runtime_directories

    directories = load_runtime_directories()
    database = bootstrap._open_database_or_report(directories)  # noqa: SLF001
    try:
        assert database is not None
        assert database.health_check()
        assert directories.database_file.exists()
    finally:
        if database is not None:
            database.dispose()


def test_run_application_disposes_database(
    isolated_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from academic_platform.app.configuration import load_runtime_directories

    directories = load_runtime_directories()

    disposed: list[int] = []

    from academic_platform.infrastructure.database import Database as _Database

    original_dispose = _Database.dispose

    def _tracking_dispose(self) -> None:
        disposed.append(1)
        return original_dispose(self)

    monkeypatch.setattr(_Database, "dispose", _tracking_dispose)

    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    _ = app

    # Skip the actual event loop by patching ``QApplication.exec`` to
    # return immediately.
    monkeypatch.setattr(QApplication, "exec", lambda self: 0)

    exit_code = bootstrap.run_application(directories)
    assert exit_code == 0
    assert disposed, "database.dispose was not called"