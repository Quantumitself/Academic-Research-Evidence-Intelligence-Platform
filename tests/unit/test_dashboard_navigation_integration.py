"""Integration test: dashboard quick actions navigate the shell."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QPushButton  # noqa: E402

from academic_platform.app.configuration import load_runtime_directories  # noqa: E402
from academic_platform.app.settings import SettingsService  # noqa: E402
from academic_platform.ui.main_window import MainWindow  # noqa: E402
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


def test_quick_action_navigates(window: MainWindow) -> None:
    dashboard = window._pages["dashboard"]  # noqa: SLF001
    button = dashboard.findChild(QPushButton, "quickActionButton_new_project")
    assert button is not None
    button.click()
    assert window._current_identifier == "research_projects"  # noqa: SLF001


def test_dashboard_refresh_on_activation(window: MainWindow) -> None:
    window.navigate_to("library")
    window.navigate_to("dashboard")
    # After activation, the dashboard has rendered at least one empty state.
    from academic_platform.ui.components.empty_state import EmptyState

    dashboard = window._pages["dashboard"]  # noqa: SLF001
    assert dashboard.findChildren(EmptyState)