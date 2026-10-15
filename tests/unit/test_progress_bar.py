"""Tests for the ProgressBar component."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from academic_platform.ui.components.progress_bar import ProgressBar  # noqa: E402


@pytest.fixture(scope="module")
def app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_zero_total_rejected(app: QApplication) -> None:
    with pytest.raises(ValueError):
        ProgressBar(total=0)


def test_initial_state(app: QApplication) -> None:
    bar = ProgressBar(total=10)
    assert bar.total == 10
    assert bar.value == 0
    assert not bar.is_complete


def test_set_value_clamps(app: QApplication) -> None:
    bar = ProgressBar(total=10)
    bar.set_value(20)
    assert bar.value == 10
    bar.set_value(-3)
    assert bar.value == 0


def test_advance(app: QApplication) -> None:
    bar = ProgressBar(total=3)
    bar.advance()
    bar.advance(2)
    assert bar.value == 3
    assert bar.is_complete


def test_cancel_hidden_by_default(app: QApplication) -> None:
    bar = ProgressBar(total=3)
    assert not bar.cancel_button.isVisible()


def test_cancel_visible_when_cancellable(app: QApplication) -> None:
    bar = ProgressBar(total=3, cancellable=True)
    assert bar.cancel_button.isVisibleTo(bar)
    assert bar.cancel_button.isEnabled()


def test_cancel_signal(app: QApplication) -> None:
    bar = ProgressBar(total=3, cancellable=True)
    received: list[int] = []
    bar.cancel_requested.connect(lambda: received.append(1))
    bar.cancel_button.click()
    assert received == [1]


def test_set_label_toggles_visibility(app: QApplication) -> None:
    bar = ProgressBar(total=3, label="Working")
    label = bar.findChild(type(bar._label), "progressBarLabel")  # noqa: SLF001
    assert label is not None
    assert label.isVisibleTo(bar)
    bar.set_label("")
    assert not label.isVisibleTo(bar)