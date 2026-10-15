"""Tests for the search result list."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from academic_platform.ui.components.empty_state import EmptyState  # noqa: E402
from academic_platform.ui.pages.search.result_list import (  # noqa: E402
    SearchResultEntry,
    SearchResultList,
    SearchResultOrigin,
)


@pytest.fixture(scope="module")
def app() -> QApplication:
    return QApplication.instance() or QApplication([])


def _entry(identifier: str, origin: SearchResultOrigin = SearchResultOrigin.LOCAL_LIBRARY) -> SearchResultEntry:
    return SearchResultEntry(
        identifier=identifier,
        title=f"Title {identifier}",
        subtitle="Sub",
        snippet="Snip",
        origin=origin,
        source_label="Lib",
        score=0.75,
        metadata=(("year", "2023"),),
    )


def test_initial_state_is_empty(app: QApplication) -> None:
    lst = SearchResultList()
    assert lst.entry_count() == 0
    lst.set_entries([])
    assert lst.findChildren(EmptyState)


def test_set_entries_populates(app: QApplication) -> None:
    lst = SearchResultList()
    lst.set_entries([_entry("a"), _entry("b")])
    assert lst.entry_count() == 2
    assert not lst.findChildren(EmptyState)


def test_set_entries_replaces(app: QApplication) -> None:
    lst = SearchResultList()
    lst.set_entries([_entry("a"), _entry("b")])
    lst.set_entries([_entry("c")])
    assert lst.entry_count() == 1
    assert lst.entries()[0].identifier == "c"


def test_set_entries_with_empty_list_shows_empty(app: QApplication) -> None:
    lst = SearchResultList()
    lst.set_entries([_entry("a")])
    lst.set_entries([])
    assert lst.entry_count() == 0
    assert lst.findChildren(EmptyState)


def test_clear_resets(app: QApplication) -> None:
    lst = SearchResultList()
    lst.set_entries([_entry("a")])
    lst.clear()
    assert lst.entry_count() == 0


def test_entries_preserve_origin(app: QApplication) -> None:
    lst = SearchResultList()
    lst.set_entries([_entry("a", SearchResultOrigin.REMOTE_SOURCE)])
    assert lst.entries()[0].origin is SearchResultOrigin.REMOTE_SOURCE


def test_set_empty_message_replaces_wording(app: QApplication) -> None:
    lst = SearchResultList(empty_title="Old", empty_message="Old")
    lst.set_empty_message("New", "New body")
    lst.set_entries([])
    states = lst.findChildren(EmptyState)
    assert states[0].title == "New"


def test_activate_signal_via_details_button(app: QApplication) -> None:
    from PySide6.QtWidgets import QPushButton

    lst = SearchResultList()
    lst.set_entries([_entry("a")])
    received: list[str] = []
    lst.entry_details_requested.connect(received.append)
    button = lst.findChild(QPushButton, "searchResultRowDetails")
    assert button is not None
    button.click()
    assert received == ["a"]