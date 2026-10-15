"""Tests for the ConfirmDialog component."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QCheckBox  # noqa: E402

from academic_platform.ui.dialogs.confirm_dialog import (  # noqa: E402
    ConfirmDialog,
    ConfirmResult,
)


@pytest.fixture(scope="module")
def app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_destructive_property_set(app: QApplication) -> None:
    dialog = ConfirmDialog("T", "Q", destructive=True)
    assert dialog.property("destructive") is True


def test_default_confirm_when_requested(app: QApplication) -> None:
    dialog = ConfirmDialog("T", "Q", default_to_confirm=True)
    assert dialog.confirm_button.isDefault()


def test_default_cancel_by_default(app: QApplication) -> None:
    dialog = ConfirmDialog("T", "Q")
    assert dialog.cancel_button.isDefault()


def test_do_not_ask_offered(app: QApplication) -> None:
    dialog = ConfirmDialog("T", "Q", offer_do_not_ask_again=True)
    checkbox = dialog.findChild(QCheckBox, "confirmDialogDoNotAsk")
    assert checkbox is not None


def test_do_not_ask_absent_by_default(app: QApplication) -> None:
    dialog = ConfirmDialog("T", "Q")
    checkbox = dialog.findChild(QCheckBox, "confirmDialogDoNotAsk")
    assert checkbox is None


def test_outcome_cancelled_when_rejected(app: QApplication) -> None:
    dialog = ConfirmDialog("T", "Q")
    dialog.reject()
    outcome = dialog.outcome()
    assert outcome.result is ConfirmResult.CANCELLED
    assert outcome.do_not_ask_again is False


def test_outcome_confirmed_with_checkbox(app: QApplication) -> None:
    dialog = ConfirmDialog("T", "Q", offer_do_not_ask_again=True)
    checkbox = dialog.findChild(QCheckBox, "confirmDialogDoNotAsk")
    assert checkbox is not None
    checkbox.setChecked(True)
    dialog.accept()
    outcome = dialog.outcome()
    assert outcome.result is ConfirmResult.CONFIRMED
    assert outcome.do_not_ask_again is True