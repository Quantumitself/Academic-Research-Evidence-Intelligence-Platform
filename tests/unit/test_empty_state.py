"""Tests for the EmptyState component."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from academic_platform.ui.components.empty_state import EmptyState  # noqa: E402


@pytest.fixture(scope="module")
def app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_initial_content(app: QApplication) -> None:
    state = EmptyState(title="T", message="M")
    assert state.title == "T"
    assert state.message == "M"


def test_set_content_replaces(app: QApplication) -> None:
    state = EmptyState(title="T", message="M")
    state.set_content("T2", "M2")
    assert state.title == "T2"
    assert state.message == "M2"


def test_glyph_hidden_by_default(app: QApplication) -> None:
    state = EmptyState(title="T", message="M")
    glyph = state.findChild(type(state._glyph_label), "emptyStateGlyph")  # noqa: SLF001
    assert glyph is not None
    assert not glyph.isVisible()


def test_set_glyph_shows(app: QApplication) -> None:
    state = EmptyState(title="T", message="M", glyph="x")
    glyph = state.findChild(type(state._glyph_label), "emptyStateGlyph")  # noqa: SLF001
    assert glyph is not None
    assert glyph.text() == "x"


def test_action_disabled_by_default(app: QApplication) -> None:
    state = EmptyState(title="T", message="M", action_label="Go")
    assert state.action_button.isVisibleTo(state)
    assert not state.action_button.isEnabled()


def test_action_can_be_enabled(app: QApplication) -> None:
    state = EmptyState(title="T", message="M", action_label="Go")
    state.set_action_enabled(True)
    assert state.action_button.isEnabled()


def test_action_signal_emitted(app: QApplication) -> None:
    state = EmptyState(title="T", message="M", action_label="Go")
    state.set_action_enabled(True)
    received: list[int] = []
    state.action_requested.connect(lambda: received.append(1))
    state.action_button.click()
    assert received == [1]


def test_empty_action_hidden(app: QApplication) -> None:
    state = EmptyState(title="T", message="M")
    assert not state.action_button.isVisible()