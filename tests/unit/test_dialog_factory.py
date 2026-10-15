"""Tests for the DialogFactory."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from academic_platform.ui.dialogs.confirm_dialog import ConfirmDialog  # noqa: E402
from academic_platform.ui.dialogs.dialog_factory import DialogFactory  # noqa: E402
from academic_platform.ui.dialogs.form_dialog import (  # noqa: E402
    FormDialog,
    FormField,
    FormFieldKind,
)
from academic_platform.ui.dialogs.message_dialog import (  # noqa: E402
    MessageDialog,
    MessageKind,
)
from academic_platform.ui.dialogs.progress_dialog import ProgressDialog  # noqa: E402
from academic_platform.ui.dialogs.prompt_dialog import PromptDialog  # noqa: E402


@pytest.fixture(scope="module")
def app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_message_dialog_construction(app: QApplication) -> None:
    dialog = DialogFactory.message_dialog(None, "T", "M")
    assert isinstance(dialog, MessageDialog)


def test_message_dialog_error_kind(app: QApplication) -> None:
    dialog = DialogFactory.message_dialog(None, "T", "M", kind=MessageKind.ERROR)
    assert dialog.property("kind") == "error"


def test_confirm_dialog_construction(app: QApplication) -> None:
    dialog = DialogFactory.confirm_dialog(None, "T", "Q")
    assert isinstance(dialog, ConfirmDialog)


def test_prompt_dialog_construction(app: QApplication) -> None:
    dialog = DialogFactory.prompt_dialog(None, "T", "L")
    assert isinstance(dialog, PromptDialog)


def test_form_dialog_construction(app: QApplication) -> None:
    fields = (FormField("a", "A", FormFieldKind.TEXT),)
    dialog = DialogFactory.form_dialog(None, "T", fields)
    assert isinstance(dialog, FormDialog)


def test_progress_dialog_construction(app: QApplication) -> None:
    dialog = DialogFactory.progress_dialog(None, "T", total=5)
    assert isinstance(dialog, ProgressDialog)