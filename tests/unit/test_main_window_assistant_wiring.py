"""Tests for the main window's research assistant wiring."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from academic_platform.app.configuration import load_runtime_directories  # noqa: E402
from academic_platform.app.settings import SettingsService  # noqa: E402
from academic_platform.infrastructure.database import Database  # noqa: E402
from academic_platform.ui.main_window import MainWindow  # noqa: E402
from academic_platform.ui.pages.research_assistant import (  # noqa: E402
    ResearchAssistantPage,
)


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


def test_assistant_destination_is_page(window: MainWindow) -> None:
    page = window._pages["research_assistant"]  # noqa: SLF001
    assert isinstance(page, ResearchAssistantPage)


def test_assistant_page_navigable(window: MainWindow) -> None:
    window.navigate_to("research_assistant")
    assert window._current_identifier == "research_assistant"  # noqa: SLF001


def test_assistant_open_projects_navigates(window: MainWindow) -> None:
    page = window._pages["research_assistant"]  # noqa: SLF001
    assert isinstance(page, ResearchAssistantPage)
    page.destination_requested.emit("research_projects")
    assert window._current_identifier == "research_projects"  # noqa: SLF001