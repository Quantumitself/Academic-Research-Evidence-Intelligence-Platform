"""Tests for the page factory."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from academic_platform.app.configuration import load_runtime_directories  # noqa: E402
from academic_platform.app.settings import SettingsService  # noqa: E402
from academic_platform.infrastructure.database import Database  # noqa: E402
from academic_platform.ui.main_window_destinations import DESTINATIONS  # noqa: E402
from academic_platform.ui.pages import create_page  # noqa: E402
from academic_platform.ui.pages.dashboard_page import DashboardPage  # noqa: E402
from academic_platform.ui.pages.placeholder_page import PlaceholderPage  # noqa: E402

#: Destinations that return a concrete page rather than a placeholder.
#: Extend this set when a new page is implemented. Every test in this
#: module consults this set so that adding a page requires a single edit.
IMPLEMENTED_DESTINATIONS: frozenset[str] = frozenset(
    {
        "collections",
        "dashboard",
        "discover",
        "library",
        "research_assistant",
        "research_projects",
        "settings",
    }
)

@pytest.fixture(scope="module")
def app() -> QApplication:
    return QApplication.instance() or QApplication([])


@pytest.fixture()
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ACADEMIC_PLATFORM_HOME", str(tmp_path / "home"))
    directories = load_runtime_directories()
    settings = SettingsService(directories.config_file)
    settings.load()
    database = Database.from_path(directories.database_file)
    yield directories, settings, database
    database.dispose()


def test_dashboard_returns_dashboard_page(app: QApplication, env) -> None:
    directories, settings, database = env
    page = create_page("dashboard", directories, settings, database)
    assert isinstance(page, DashboardPage)


def test_discover_returns_global_search_page(app: QApplication, env) -> None:
    from academic_platform.ui.pages.search import GlobalSearchPage

    directories, settings, database = env
    page = create_page("discover", directories, settings, database)
    assert isinstance(page, GlobalSearchPage)


def test_settings_returns_settings_page(app: QApplication, env) -> None:
    from academic_platform.ui.pages.settings import SettingsPage

    directories, settings, database = env
    page = create_page("settings", directories, settings, database)
    assert isinstance(page, SettingsPage)

def test_library_returns_library_page(app: QApplication, env) -> None:
    from academic_platform.ui.pages.library import LibraryPage

    directories, settings, database = env
    page = create_page("library", directories, settings, database)
    assert isinstance(page, LibraryPage)

def test_other_destinations_return_placeholder(app: QApplication, env) -> None:
    directories, settings, database = env
    for destination in DESTINATIONS:
        if destination.identifier in IMPLEMENTED_DESTINATIONS:
            continue
        page = create_page(destination, directories, settings, database)
        assert isinstance(page, PlaceholderPage)
        assert page.destination is destination


def test_unknown_identifier_raises(app: QApplication, env) -> None:
    directories, settings, database = env
    with pytest.raises(KeyError):
        create_page("nonexistent", directories, settings, database)