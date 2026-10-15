"""Tests for the global search page."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QTabWidget  # noqa: E402

from academic_platform.ui.components.empty_state import EmptyState  # noqa: E402
from academic_platform.ui.components.search_bar import SearchBar  # noqa: E402
from academic_platform.ui.pages.search.result_list import (  # noqa: E402
    SearchResultEntry,
    SearchResultOrigin,
)
from academic_platform.ui.pages.search.search_controller import (  # noqa: E402
    SearchResponse,
    SourceReport,
    SourceStatus,
)
from academic_platform.ui.pages.search.search_page import GlobalSearchPage  # noqa: E402


@pytest.fixture(scope="module")
def app() -> QApplication:
    return QApplication.instance() or QApplication([])


class _StaticController:
    """Controller returning fixed responses for tests."""

    def __init__(self, local: SearchResponse, remote: SearchResponse) -> None:
        self.local = local
        self.remote = remote

    def search_local(self, query: str) -> SearchResponse:
        return self.local

    def search_remote(self, query: str) -> SearchResponse:
        return self.remote


def _entry(identifier: str, origin: SearchResultOrigin) -> SearchResultEntry:
    return SearchResultEntry(identifier=identifier, title=identifier, origin=origin)


def test_page_composition(app: QApplication) -> None:
    page = GlobalSearchPage()
    assert page.findChild(SearchBar) is not None
    tabs = page.findChild(QTabWidget, "searchTabs")
    assert tabs is not None
    assert tabs.count() == 2


def test_empty_submit_is_ignored(app: QApplication) -> None:
    page = GlobalSearchPage()
    received: list[tuple[str, str]] = []
    page.search_submitted.connect(lambda q, s: received.append((q, s)))
    page.execute_search("   ", "all")
    assert received == []


def test_local_search_renders_results(app: QApplication) -> None:
    local = SearchResponse(
        query="x",
        entries=(_entry("a", SearchResultOrigin.LOCAL_LIBRARY),),
        source_reports=(SourceReport("Library", SourceStatus.OK, 1),),
    )
    remote = SearchResponse(query="x", entries=())
    page = GlobalSearchPage()
    page.set_controller(_StaticController(local, remote))
    page.execute_search("x", "local")
    assert page._local_surface.result_list.entry_count() == 1  # noqa: SLF001
    tabs = page.findChild(QTabWidget, "searchTabs")
    assert tabs is not None
    assert tabs.currentWidget() is page._local_surface  # noqa: SLF001


def test_remote_search_renders_results(app: QApplication) -> None:
    local = SearchResponse(query="x", entries=())
    remote = SearchResponse(
        query="x",
        entries=(_entry("r1", SearchResultOrigin.REMOTE_SOURCE),),
    )
    page = GlobalSearchPage()
    page.set_controller(_StaticController(local, remote))
    page.execute_search("x", "remote")
    assert page._remote_surface.result_list.entry_count() == 1  # noqa: SLF001
    tabs = page.findChild(QTabWidget, "searchTabs")
    assert tabs is not None
    assert tabs.currentWidget() is page._remote_surface  # noqa: SLF001


def test_all_scope_runs_both(app: QApplication) -> None:
    local = SearchResponse(
        query="x",
        entries=(_entry("a", SearchResultOrigin.LOCAL_LIBRARY),),
    )
    remote = SearchResponse(
        query="x",
        entries=(_entry("b", SearchResultOrigin.REMOTE_SOURCE),),
    )
    page = GlobalSearchPage()
    page.set_controller(_StaticController(local, remote))
    page.execute_search("x", "all")
    assert page._local_surface.result_list.entry_count() == 1  # noqa: SLF001
    assert page._remote_surface.result_list.entry_count() == 1  # noqa: SLF001


def test_partial_response_reports_sources(app: QApplication) -> None:
    local = SearchResponse(query="x", entries=())
    remote = SearchResponse(
        query="x",
        entries=(),
        source_reports=(
            SourceReport("A", SourceStatus.OK, 0),
            SourceReport("B", SourceStatus.FAILED, 0, error_message="boom"),
        ),
        partial=True,
    )
    page = GlobalSearchPage()
    page.set_controller(_StaticController(local, remote))
    page.execute_search("x", "remote")
    from PySide6.QtWidgets import QLabel

    lines = page.findChildren(QLabel, "searchStatusLine")
    texts = [line.text() for line in lines]
    assert any("A" in text for text in texts)
    assert any("B" in text for text in texts)


def test_controller_exception_renders_error_state(app: QApplication) -> None:
    class _BoomController:
        def search_local(self, query: str) -> SearchResponse:
            raise RuntimeError("boom")

        def search_remote(self, query: str) -> SearchResponse:
            return SearchResponse(query=query, entries=())

    page = GlobalSearchPage()
    page.show()
    page.set_controller(_BoomController())
    page.execute_search("x", "local")
    assert page._local_surface.error_state.isVisibleTo(page)  # noqa: SLF001


def test_clear_resets_results(app: QApplication) -> None:
    local = SearchResponse(
        query="x",
        entries=(_entry("a", SearchResultOrigin.LOCAL_LIBRARY),),
    )
    remote = SearchResponse(query="x", entries=())
    page = GlobalSearchPage()
    page.set_controller(_StaticController(local, remote))
    page.execute_search("x", "local")
    page._search_bar._clear_button.click()  # noqa: SLF001
    assert page._local_surface.result_list.entry_count() == 0  # noqa: SLF001


def test_page_renders_empty_state_without_controller(app: QApplication) -> None:
    page = GlobalSearchPage()
    page.execute_search("anything", "local")
    assert page._local_surface.result_list.entry_count() == 0  # noqa: SLF001
    assert page.findChildren(EmptyState)