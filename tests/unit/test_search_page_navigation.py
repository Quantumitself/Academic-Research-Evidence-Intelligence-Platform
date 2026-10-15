"""Integration: the Discover destination renders the global search page."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from academic_platform.app.configuration import load_runtime_directories  # noqa: E402
from academic_platform.app.settings import SettingsService  # noqa: E402
from academic_platform.ui.main_window import MainWindow  # noqa: E402
from academic_platform.ui.pages.search import GlobalSearchPage  # noqa: E402
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


def test_discover_is_search_page(window: MainWindow) -> None:
    page = window._pages["discover"]  # noqa: SLF001
    assert isinstance(page, GlobalSearchPage)


def test_search_via_shell(window: MainWindow) -> None:
    window.navigate_to("discover")
    page = window._pages["discover"]  # noqa: SLF001
    assert isinstance(page, GlobalSearchPage)
    page.execute_search("sample", "local")
    # With the null controller, no entries are returned; the page still
    # renders the source status panel.
    from PySide6.QtWidgets import QLabel

    lines = page.findChildren(QLabel, "searchStatusLine")
    assert lines