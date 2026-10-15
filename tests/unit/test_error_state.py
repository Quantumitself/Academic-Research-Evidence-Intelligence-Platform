"""Tests for the ErrorState component."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from academic_platform.ui.components.error_state import ErrorState  # noqa: E402


@pytest.fixture(scope="module")
def app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_message_preserved(app: QApplication) -> None:
    state = ErrorState(message="Boom")
    assert state.message == "Boom"


def test_set_message_replaces(app: QApplication) -> None:
    state = ErrorState(message="Boom")
    state.set_message("Different")
    assert state.message == "Different"


def test_retry_hidden_by_default(app: QApplication) -> None:
    state = ErrorState(message="Boom")
    assert not state.retry_button.isVisible()


def test_retry_visible_when_retryable(app: QApplication) -> None:
    state = ErrorState(message="Boom", retryable=True)
    assert state.retry_button.isVisibleTo(state)
    assert not state.retry_button.isEnabled()


def test_retry_enabled_and_emitted(app: QApplication) -> None:
    state = ErrorState(message="Boom", retryable=True)
    state.set_retry_enabled(True)
    received: list[int] = []
    state.retry_requested.connect(lambda: received.append(1))
    state.retry_button.click()
    assert received == [1]


def test_set_retryable_toggles_visibility(app: QApplication) -> None:
    state = ErrorState(message="Boom")
    state.set_retryable(True)
    assert state.retry_button.isVisibleTo(state)
    state.set_retryable(False)
    assert not state.retry_button.isVisibleTo(state)