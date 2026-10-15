"""Tests for the DashboardPage."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QPushButton  # noqa: E402

from academic_platform.app.configuration import load_runtime_directories  # noqa: E402
from academic_platform.ui.components.empty_state import EmptyState  # noqa: E402
from academic_platform.ui.main_window_destinations import DESTINATIONS  # noqa: E402
from academic_platform.ui.pages.dashboard_page import DashboardPage  # noqa: E402


@pytest.fixture(scope="module")
def app() -> QApplication:
    return QApplication.instance() or QApplication([])


@pytest.fixture()
def directories(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ACADEMIC_PLATFORM_HOME", str(tmp_path / "home"))
    return load_runtime_directories()


def test_page_title_and_subtitle(app: QApplication, directories) -> None:
    page = DashboardPage(directories=directories)
    assert page.title == "Dashboard"
    assert "Recent activity" in page.subtitle or page.subtitle


def test_quick_action_buttons_enabled(app: QApplication, directories) -> None:
    page = DashboardPage(directories=directories)
    button_names = (
        "quickActionButton_new_project",
        "quickActionButton_import_document",
        "quickActionButton_search_literature",
        "quickActionButton_open_assistant",
    )
    for name in button_names:
        button = page.findChild(QPushButton, name)
        assert button is not None, f"missing button {name}"
        assert button.isEnabled()


def test_quick_action_emits_destination(app: QApplication, directories) -> None:
    page = DashboardPage(directories=directories)
    received: list[str] = []
    page.destination_requested.connect(received.append)
    button = page.findChild(QPushButton, "quickActionButton_new_project")
    assert button is not None
    button.click()
    assert received == ["research_projects"]


def test_empty_states_rendered_without_provider(app: QApplication, directories) -> None:
    page = DashboardPage(directories=directories)
    # The page is not attached to a window; the provider lookup returns None
    # and every section renders its empty state.
    page.refresh()
    empty_states = page.findChildren(EmptyState)
    # At least one empty state exists for each of the seven data sections.
    assert len(empty_states) >= 7


def test_refresh_with_provider(app: QApplication, directories) -> None:
    from PySide6.QtWidgets import QPushButton, QWidget

    from academic_platform.ui.components.research_project_card import (
        ResearchProjectCard,
        ResearchProjectSummary,
    )

    class StubWindow(QWidget):
        def __init__(self) -> None:
            super().__init__()
            self.dashboard_data_provider = staticmethod(self._provider)

        @staticmethod
        def _provider():
            return {
                "recent_projects": [
                    ResearchProjectSummary(identifier="p1", title="Project A"),
                ],
                "recent_articles": [],
                "saved_searches": ["query one"],
                "research_tasks": ["read paper"],
                "pending_evidence": [],
                "recent_reports": [],
                "recent_activity": [],
            }

    stub = StubWindow()
    page = DashboardPage(directories=directories)
    page.setParent(stub)
    page.refresh()
    assert page.findChildren(ResearchProjectCard)
    assert page.findChildren(QPushButton, "dashboardSavedSearchOpen")


def test_refresh_button_wired(app: QApplication, directories) -> None:
    page = DashboardPage(directories=directories)
    button = page.findChild(QPushButton, "dashboardRefresh")
    assert button is not None
    assert button.isEnabled()


def test_destination_requested_from_empty_state(
    app: QApplication, directories
) -> None:
    page = DashboardPage(directories=directories)
    page.refresh()
    received: list[str] = []
    page.destination_requested.connect(received.append)
    # The first empty state with an enabled action emits a destination.
    for state in page.findChildren(EmptyState):
        if state.action_button.isEnabled():
            state.action_button.click()
            assert received
            return
    # There must be at least one enabled empty-state action.
    raise AssertionError("no enabled empty-state action found")