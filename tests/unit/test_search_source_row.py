"""Tests for the SearchSourceRow component."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QCheckBox, QPushButton  # noqa: E402

from academic_platform.ui.components.search_source_row import (  # noqa: E402
    SearchSourceRow,
    SearchSourceSummary,
    SourceType,
)


@pytest.fixture(scope="module")
def app() -> QApplication:
    return QApplication.instance() or QApplication([])


def _summary() -> SearchSourceSummary:
    return SearchSourceSummary(
        identifier="s1",
        name="Crossref",
        source_type=SourceType.BUILT_IN,
        enabled=True,
        last_test_ok=True,
        supports_filters=("year", "author"),
    )


def test_enabled_toggled_signal(app: QApplication) -> None:
    row = SearchSourceRow(_summary())
    received: list[tuple[str, bool]] = []
    row.enabled_toggled.connect(lambda i, e: received.append((i, e)))
    checkbox = row.findChild(QCheckBox, "searchSourceRowEnabled")
    assert checkbox is not None
    checkbox.setChecked(False)
    assert received == [("s1", False)]


def test_set_enabled_no_emit(app: QApplication) -> None:
    row = SearchSourceRow(_summary())
    received: list[tuple[str, bool]] = []
    row.enabled_toggled.connect(lambda i, e: received.append((i, e)))
    row.set_enabled(False)
    assert received == []


def test_actions_disabled_by_default(app: QApplication) -> None:
    row = SearchSourceRow(_summary())
    for name in ("searchSourceRowTest", "searchSourceRowEdit", "searchSourceRowRemove"):
        button = row.findChild(QPushButton, name)
        assert button is not None
        assert not button.isEnabled()


def test_filters_line_rendered(app: QApplication) -> None:
    from PySide6.QtWidgets import QLabel

    row = SearchSourceRow(_summary())
    filters = row.findChild(QLabel, "searchSourceRowFilters")
    assert filters is not None
    assert "year" in filters.text()


def test_no_filters_line_when_empty(app: QApplication) -> None:
    from PySide6.QtWidgets import QLabel

    row = SearchSourceRow(
        SearchSourceSummary(identifier="s", name="X", source_type=SourceType.USER_DEFINED)
    )
    assert row.findChild(QLabel, "searchSourceRowFilters") is None