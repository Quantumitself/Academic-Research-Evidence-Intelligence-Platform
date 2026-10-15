"""Confirmation dialog.

The dialog renders a title, a question, an optional details pane, an
optional "do not ask again" checkbox, and two buttons: a primary
confirming action and a secondary cancelling action. The dialog returns a
``ConfirmResult`` describing the user's decision.

Design decisions
----------------
- The default button is configurable. Destructive actions should default
  to the cancelling button.
- The "do not ask again" checkbox is only offered when the caller supplies
  a storage key. The dialog never persists the checkbox itself; it returns
  the checkbox state through the result.
- The dialog does not perform the confirmed action. The caller performs it
  after the dialog returns.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QPlainTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)


class ConfirmResult(str, Enum):
    """Outcome of a confirmation dialog."""

    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class ConfirmOutcome:
    """Full outcome of a confirmation dialog."""

    result: ConfirmResult
    do_not_ask_again: bool


class ConfirmDialog(QDialog):
    """Modal confirmation with a configurable default and checkbox."""

    def __init__(
        self,
        title: str,
        question: str,
        *,
        confirm_label: str = "Confirm",
        cancel_label: str = "Cancel",
        destructive: bool = False,
        details: str = "",
        offer_do_not_ask_again: bool = False,
        default_to_confirm: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("confirmDialog")
        self.setModal(True)
        self.setWindowTitle(title)
        self.setMinimumWidth(420)
        if destructive:
            self.setProperty("destructive", True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)

        question_label = QLabel(question, self)
        question_label.setObjectName("confirmDialogQuestion")
        question_label.setWordWrap(True)
        layout.addWidget(question_label)

        self._details_toggle: QToolButton | None = None
        self._details_view: QPlainTextEdit | None = None
        if details:
            self._details_toggle = QToolButton(self)
            self._details_toggle.setObjectName("confirmDialogDetailsToggle")
            self._details_toggle.setText("Show details")
            self._details_toggle.setCheckable(True)
            self._details_toggle.setChecked(False)
            self._details_toggle.setArrowType(Qt.ArrowType.RightArrow)
            self._details_toggle.setAutoRaise(True)
            self._details_toggle.toggled.connect(self._on_details_toggled)
            layout.addWidget(self._details_toggle, 0, Qt.AlignmentFlag.AlignLeft)

            self._details_view = QPlainTextEdit(details, self)
            self._details_view.setObjectName("confirmDialogDetails")
            self._details_view.setReadOnly(True)
            self._details_view.setVisible(False)
            self._details_view.setMinimumHeight(100)
            layout.addWidget(self._details_view)

        self._do_not_ask_checkbox: QCheckBox | None = None
        if offer_do_not_ask_again:
            self._do_not_ask_checkbox = QCheckBox("Do not ask again", self)
            self._do_not_ask_checkbox.setObjectName("confirmDialogDoNotAsk")
            layout.addWidget(self._do_not_ask_checkbox)

        button_box = QDialogButtonBox(self)
        button_box.setObjectName("confirmDialogButtonBox")
        self._confirm_button = button_box.addButton(
            confirm_label, QDialogButtonBox.ButtonRole.AcceptRole
        )
        self._cancel_button = button_box.addButton(
            cancel_label, QDialogButtonBox.ButtonRole.RejectRole
        )
        if destructive:
            self._confirm_button.setObjectName("confirmDialogConfirmDestructive")
        else:
            self._confirm_button.setObjectName("confirmDialogConfirm")
        self._cancel_button.setObjectName("confirmDialogCancel")

        if default_to_confirm:
            self._confirm_button.setDefault(True)
            self._cancel_button.setAutoDefault(False)
        else:
            self._cancel_button.setDefault(True)
            self._confirm_button.setAutoDefault(False)

        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def outcome(self) -> ConfirmOutcome:
        """Return the full outcome of the dialog."""
        confirmed = self.result() == QDialog.DialogCode.Accepted
        do_not_ask = bool(
            self._do_not_ask_checkbox is not None
            and self._do_not_ask_checkbox.isChecked()
        )
        return ConfirmOutcome(
            result=ConfirmResult.CONFIRMED if confirmed else ConfirmResult.CANCELLED,
            do_not_ask_again=do_not_ask,
        )

    @property
    def confirm_button(self):
        return self._confirm_button

    @property
    def cancel_button(self):
        return self._cancel_button

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------
    def _on_details_toggled(self, checked: bool) -> None:
        assert self._details_view is not None
        assert self._details_toggle is not None
        self._details_view.setVisible(checked)
        self._details_toggle.setText("Hide details" if checked else "Show details")
        self._details_toggle.setArrowType(
            Qt.ArrowType.DownArrow if checked else Qt.ArrowType.RightArrow
        )


def ask_confirmation(
    parent: QWidget | None,
    title: str,
    question: str,
    *,
    confirm_label: str = "Confirm",
    cancel_label: str = "Cancel",
    destructive: bool = False,
    details: str = "",
    offer_do_not_ask_again: bool = False,
    default_to_confirm: bool = False,
) -> ConfirmOutcome:
    """Display a modal confirmation and return its outcome."""
    dialog = ConfirmDialog(
        title=title,
        question=question,
        confirm_label=confirm_label,
        cancel_label=cancel_label,
        destructive=destructive,
        details=details,
        offer_do_not_ask_again=offer_do_not_ask_again,
        default_to_confirm=default_to_confirm,
        parent=parent,
    )
    dialog.exec()
    return dialog.outcome()