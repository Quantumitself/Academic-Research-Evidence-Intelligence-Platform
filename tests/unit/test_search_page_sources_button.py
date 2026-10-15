"""Tests for the Discover page sources hint and button."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QPushButton  # noqa: E402

from academic_platform.app.configuration import load_runtime_directories  # noqa: E402
from academic_platform.app.settings import SettingsService  # noqa: E402
from academic_platform.infrastructure.database import Database  # noqa: E402
from academic_platform.ui.main_window import MainWindow  # noqa: E402
from academic_platform.ui.pages.search import GlobalSearchPage  # noqa: E402


@pytest.fixture(scope="module")
def app() -> QApplication:
    return QApplication.instance() or QApplication([])


@pytest.fixture()
def window(app: QApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
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


def test_manage_sources_button_exists(window: MainWindow) -> None:
    page = window._pages["discover"]  # noqa: SLF001
    assert isinstance(page, GlobalSearchPage)
    button = page.findChild(QPushButton, "searchManageSources")
    assert button is not None
    assert button.isEnabled()


def test_sources_hint_updated_on_activation(window: MainWindow) -> None:
    window.navigate_to("discover")
    page = window._pages["discover"]  # noqa: SLF001
    page.on_activated()
    from PySide6.QtWidgets import QLabel

    hint = page.findChild(QLabel, "searchSourcesHint")
    assert hint is not None
    assert "sources" in hint.text().lower()