"""Tests for the SearchBar component."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from academic_platform.ui.components.search_bar import SearchBar  # noqa: E402


@pytest.fixture(scope="module")
def app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_text_round_trip(app: QApplication) -> None:
    bar = SearchBar()
    bar.set_text("hello")
    assert bar.text() == "hello"


def test_submit_emits_text_and_scope(app: QApplication) -> None:
    bar = SearchBar(scopes=(("a", "Alpha"), ("b", "Beta")))
    bar.set_text("query")
    bar.set_scope("b")
    received: list[tuple[str, str]] = []
    bar.submitted.connect(lambda text, scope: received.append((text, scope)))
    bar._submit_button.click()  # noqa: SLF001
    assert received == [("query", "b")]


def test_submit_without_scope_emits_empty_string(app: QApplication) -> None:
    bar = SearchBar()
    bar.set_text("q")
    received: list[tuple[str, str]] = []
    bar.submitted.connect(lambda text, scope: received.append((text, scope)))
    bar._submit_button.click()  # noqa: SLF001
    assert received == [("q", "")]


def test_enter_submits(app: QApplication) -> None:
    bar = SearchBar()
    bar.set_text("q")
    received: list[tuple[str, str]] = []
    bar.submitted.connect(lambda text, scope: received.append((text, scope)))
    QTest.keyClick(bar._input, Qt.Key.Key_Return)  # noqa: SLF001
    assert received and received[0][0] == "q"


def test_clear_emits_signal(app: QApplication) -> None:
    bar = SearchBar()
    bar.set_text("q")
    received: list[int] = []
    bar.cleared.connect(lambda: received.append(1))
    bar._clear_button.click()  # noqa: SLF001
    assert bar.text() == ""
    assert received == [1]


def test_escape_clears(app: QApplication) -> None:
    bar = SearchBar()
    bar.set_text("q")
    QTest.keyClick(bar._input, Qt.Key.Key_Escape)  # noqa: SLF001
    assert bar.text() == ""


def test_scope_changed_signal(app: QApplication) -> None:
    bar = SearchBar(scopes=(("a", "Alpha"), ("b", "Beta")))
    received: list[str] = []
    bar.scope_changed.connect(received.append)
    bar.set_scope("b")
    assert "b" in received


def test_set_enabled_toggles_all(app: QApplication) -> None:
    bar = SearchBar()
    bar.set_enabled(False)
    assert not bar._input.isEnabled()  # noqa: SLF001
    assert not bar._submit_button.isEnabled()  # noqa: SLF001
    bar.set_enabled(True)
    assert bar._input.isEnabled()  # noqa: SLF001