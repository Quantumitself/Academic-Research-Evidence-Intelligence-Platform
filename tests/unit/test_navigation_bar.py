"""Tests for the navigation bar."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from academic_platform.ui.main_window_destinations import DESTINATIONS  # noqa: E402
from academic_platform.ui.navigation.navigation_bar import NavigationBar  # noqa: E402


@pytest.fixture(scope="module")
def app() -> QApplication:
    instance = QApplication.instance() or QApplication([])
    return instance


def test_list_count_matches_destinations(app: QApplication) -> None:
    bar = NavigationBar()
    assert bar._list.count() == len(DESTINATIONS)  # noqa: SLF001


def test_select_emits_signal(app: QApplication) -> None:
    bar = NavigationBar()
    received: list[str] = []
    bar.destination_selected.connect(received.append)
    bar.select("library")
    assert received == ["library"]


def test_labels_hidden_keeps_glyph(app: QApplication) -> None:
    bar = NavigationBar()
    bar.set_labels_visible(False)
    for index in range(bar._list.count()):  # noqa: SLF001
        item = bar._list.item(index)  # noqa: SLF001
        # The label portion must be empty; only the glyph prefix remains.
        assert item.text().strip()
        assert item.toolTip()


def test_labels_visible_restores_text(app: QApplication) -> None:
    bar = NavigationBar()
    bar.set_labels_visible(False)
    bar.set_labels_visible(True)
    for index in range(bar._list.count()):  # noqa: SLF001
        item = bar._list.item(index)  # noqa: SLF001
        identifier = item.data(Qt.ItemDataRole.UserRole)
        expected = next(d.label for d in DESTINATIONS if d.identifier == identifier)
        assert expected in item.text()