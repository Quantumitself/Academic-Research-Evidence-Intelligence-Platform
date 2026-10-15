"""Integration tests for the Discover page with the orchestration controller."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

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


def test_discover_page_has_orchestration_controller(window: MainWindow) -> None:
    page = window._pages["discover"]  # noqa: SLF001
    assert isinstance(page, GlobalSearchPage)
    # The controller attached to the page is the orchestration controller.
    from academic_platform.ui.pages.search.orchestration_controller import (
        OrchestrationSearchController,
    )

    assert isinstance(page._controller, OrchestrationSearchController)  # noqa: SLF001


def test_orchestrator_factory_available(window: MainWindow) -> None:
    factory = window.search_orchestrator_factory
    assert callable(factory)


def test_discover_page_local_search_reports_unavailable(window: MainWindow) -> None:
    page = window._pages["discover"]  # noqa: SLF001
    response = page._controller.search_local("x")  # noqa: SLF001
    assert response.entries == ()
    assert response.source_reports