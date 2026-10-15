"""Tests for the ProgressDialog component."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from academic_platform.ui.dialogs.progress_dialog import ProgressDialog  # noqa: E402


@pytest.fixture(scope="module")
def app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_initial_progress(app: QApplication) -> None:
    dialog = ProgressDialog("Working", total=10)
    assert dialog.total == 10
    assert dialog.value == 0


def test_set_value_clamps(app: QApplication) -> None:
    dialog = ProgressDialog("Working", total=10)
    dialog.set_value(20)
    assert dialog.value == 10


def test_advance(app: QApplication) -> None:
    dialog = ProgressDialog("Working", total=3)
    dialog.advance()
    dialog.advance(2)
    assert dialog.value == 3


def test_cancel_signal(app: QApplication) -> None:
    dialog = ProgressDialog("Working", total=3, cancellable=True)
    received: list[int] = []
    dialog.cancel_requested.connect(lambda: received.append(1))
    dialog._progress.cancel_button.click()  # noqa: SLF001
    assert received == [1]


def test_close_emits_cancel(app: QApplication) -> None:
    dialog = ProgressDialog("Working", total=3)
    received: list[int] = []
    dialog.cancel_requested.connect(lambda: received.append(1))
    dialog.close()
    assert received == [1]