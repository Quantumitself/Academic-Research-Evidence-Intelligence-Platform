"""Tests for the MessageDialog component."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QDialogButtonBox  # noqa: E402

from academic_platform.ui.dialogs.message_dialog import (  # noqa: E402
    MessageDialog,
    MessageKind,
)


@pytest.fixture(scope="module")
def app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_message_rendered(app: QApplication) -> None:
    dialog = MessageDialog("Title", "Body")
    assert dialog.windowTitle() == "Title"


def test_kind_property(app: QApplication) -> None:
    dialog = MessageDialog("T", "M", kind=MessageKind.ERROR)
    assert dialog.property("kind") == "error"


def test_details_hidden_by_default(app: QApplication) -> None:
    dialog = MessageDialog("T", "M", details="diag")
    view = dialog.findChild(type(dialog._details_view), "messageDialogDetails")  # noqa: SLF001
    assert view is not None
    assert not view.isVisible()


def test_details_toggle_shows(app: QApplication) -> None:
    dialog = MessageDialog("T", "M", details="diag")
    dialog._details_toggle.setChecked(True)  # noqa: SLF001
    view = dialog.findChild(type(dialog._details_view), "messageDialogDetails")  # noqa: SLF001
    assert view is not None
    assert view.isVisibleTo(dialog)


def test_copyable_adds_button(app: QApplication) -> None:
    dialog = MessageDialog("T", "M", details="diag", copyable=True)
    from PySide6.QtWidgets import QPushButton

    copy = dialog.findChild(QPushButton, "messageDialogCopy")
    assert copy is not None


def test_no_copy_button_without_details(app: QApplication) -> None:
    dialog = MessageDialog("T", "M", copyable=True)
    from PySide6.QtWidgets import QPushButton

    assert dialog.findChild(QPushButton, "messageDialogCopy") is None


def test_copy_details_to_clipboard(app: QApplication) -> None:
    from PySide6.QtGui import QGuiApplication

    dialog = MessageDialog("T", "M", details="payload", copyable=True)
    from PySide6.QtWidgets import QPushButton

    copy = dialog.findChild(QPushButton, "messageDialogCopy")
    assert copy is not None
    copy.click()
    clipboard = QGuiApplication.clipboard()
    assert clipboard is not None
    assert clipboard.text() == "payload"