"""Tests for the MainWindow navigation shell."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from academic_platform.app.configuration import load_runtime_directories  # noqa: E402
from academic_platform.app.settings import SettingsService  # noqa: E402
from academic_platform.infrastructure.database import Database  # noqa: E402
from academic_platform.ui.main_window import MainWindow  # noqa: E402
from academic_platform.ui.main_window_destinations import DESTINATIONS  # noqa: E402


@pytest.fixture(scope="module")
def app() -> QApplication:
    return QApplication.instance() or QApplication([])


@pytest.fixture()
def window(
    app: QApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> MainWindow:
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


def test_all_destinations_registered(window: MainWindow) -> None:
    assert set(window._pages) == {  # noqa: SLF001
        destination.identifier for destination in DESTINATIONS
    }


def test_initial_page_is_dashboard(window: MainWindow) -> None:
    assert window._current_identifier == "dashboard"  # noqa: SLF001


def test_navigate_between_destinations(window: MainWindow) -> None:
    window.navigate_to("library")
    assert window._current_identifier == "library"  # noqa: SLF001
    window.navigate_to("settings")
    assert window._current_identifier == "settings"  # noqa: SLF001


def test_navigate_unknown_destination_is_ignored(window: MainWindow) -> None:
    window.navigate_to("nonexistent")
    assert window._current_identifier == "dashboard"  # noqa: SLF001


def test_database_property_returns_instance(window: MainWindow) -> None:
    assert window.database is not None
    assert window.database.health_check()