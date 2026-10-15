"""Tests for the LoadingIndicator component."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from academic_platform.ui.components.loading_indicator import LoadingIndicator  # noqa: E402


@pytest.fixture(scope="module")
def app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_default_is_indeterminate(app: QApplication) -> None:
    indicator = LoadingIndicator()
    assert indicator.is_indeterminate
    assert indicator.total == 0


def test_set_determinate(app: QApplication) -> None:
    indicator = LoadingIndicator()
    indicator.set_determinate(10)
    assert not indicator.is_indeterminate
    assert indicator.total == 10
    assert indicator.value == 0


def test_set_determinate_rejects_zero(app: QApplication) -> None:
    indicator = LoadingIndicator()
    with pytest.raises(ValueError):
        indicator.set_determinate(0)


def test_set_progress_clamps(app: QApplication) -> None:
    indicator = LoadingIndicator()
    indicator.set_determinate(10)
    indicator.set_progress(5)
    assert indicator.value == 5
    indicator.set_progress(99)
    assert indicator.value == 10
    indicator.set_progress(-3)
    assert indicator.value == 0


def test_advance(app: QApplication) -> None:
    indicator = LoadingIndicator()
    indicator.set_determinate(5)
    indicator.advance()
    indicator.advance(2)
    assert indicator.value == 3


def test_set_progress_in_indeterminate_is_noop(app: QApplication) -> None:
    indicator = LoadingIndicator()
    indicator.set_progress(3)
    assert indicator.value == 0


def test_message_replaced(app: QApplication) -> None:
    indicator = LoadingIndicator(message="Loading…")
    indicator.set_message("Working…")
    assert indicator.message == "Working…"


def test_switch_back_to_indeterminate(app: QApplication) -> None:
    indicator = LoadingIndicator()
    indicator.set_determinate(4)
    indicator.set_progress(2)
    indicator.set_indeterminate()
    assert indicator.is_indeterminate
    assert indicator.value == 0