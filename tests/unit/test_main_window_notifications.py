"""Tests for the MainWindow notification service attachment."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from academic_platform.app.configuration import load_runtime_directories  # noqa: E402
from academic_platform.app.settings import SettingsService  # noqa: E402
from academic_platform.ui.main_window import MainWindow  # noqa: E402
from academic_platform.ui.notifications import NotificationService  # noqa: E402
from academic_platform.infrastructure.database import Database


@pytest.fixture(scope="module")
def app() -> QApplication:
    return QApplication.instance() or QApplication([])


@pytest.fixture()
def window(app: QApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> MainWindow:
    monkeypatch.setenv("ACADEMIC_PLATFORM_HOME", str(tmp_path / "home"))
    directories = load_runtime_directories()
    settings = SettingsService(directories.config_file)
    settings.load()
    database = Database.from_path(directories.database_file)
    window = MainWindow(
        directories=directories,
        settings_service=settings,
        database=database,
    )
    yield window
    database.dispose()


def test_notifications_raises_without_attachment(window: MainWindow) -> None:
    with pytest.raises(RuntimeError):
        _ = window.notifications


def test_notifications_returns_service_after_attachment(window: MainWindow) -> None:
    service = NotificationService()
    window.attach_notification_service(service)
    assert window.notifications is service