"""Integration: the Settings destination renders the Settings page."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from academic_platform.app.configuration import load_runtime_directories  # noqa: E402
from academic_platform.app.settings import SettingsService  # noqa: E402
from academic_platform.ui.main_window import MainWindow  # noqa: E402
from academic_platform.ui.pages.settings import SettingsPage  # noqa: E402
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


def test_settings_page_rendered(window: MainWindow) -> None:
    page = window._pages["settings"]  # noqa: SLF001
    assert isinstance(page, SettingsPage)


def test_settings_page_navigable(window: MainWindow) -> None:
    window.navigate_to("settings")
    assert window._current_identifier == "settings"  # noqa: SLF001