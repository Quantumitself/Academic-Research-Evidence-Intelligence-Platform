"""Tests for the main window's projects page wiring."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from academic_platform.app.configuration import load_runtime_directories  # noqa: E402
from academic_platform.app.settings import SettingsService  # noqa: E402
from academic_platform.infrastructure.database import Database  # noqa: E402
from academic_platform.ui.main_window import MainWindow  # noqa: E402
from academic_platform.ui.pages.projects import ProjectsPage  # noqa: E402


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


def test_projects_destination_is_projects_page(window: MainWindow) -> None:
    page = window._pages["research_projects"]  # noqa: SLF001
    assert isinstance(page, ProjectsPage)


def test_project_service_factory_available(window: MainWindow) -> None:
    factory = window.project_service_factory
    assert callable(factory)
    service = factory()
    assert service is not None


def test_projects_page_navigable(window: MainWindow) -> None:
    window.navigate_to("research_projects")
    assert window._current_identifier == "research_projects"  # noqa: SLF001