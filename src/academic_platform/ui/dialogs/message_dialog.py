"""Informational message dialog.

The dialog renders a title, a primary message, and an expandable details
pane. It is used for informational messages, warnings, and errors that do
not require a decision. Confirmations use ``ConfirmDialog``.

Design decisions
----------------
- The details pane is hidden by default. It contains technical diagnostics
  that are useful for issue reports but should not distract the user.
- The dialog supports an optional "copy details" button. When present, the
  button copies the details text to the system clipboard. The clipboard
  action is local to the dialog; no signal is emitted.
- The dialog is modal by default. Callers that need a non-modal message
  should use the notification system instead.
"""

from __future__ import annotations

from enum import Enum

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)


class MessageKind(str, Enum):
    """Visual and semantic kind of the message."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class MessageDialog(QDialog):
    """Informational message dialog with an optional details pane."""

    def __init__(
        self,
        title: str,
        message: str,
        *,
        kind: MessageKind = MessageKind.INFO,
        details: str = "",
        copyable: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("messageDialog")
        self.setModal(True)
        self.setWindowTitle(title)
        self.setMinimumWidth(420)
        self.setProperty("kind", kind.value)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)

        kind_label = QLabel(kind.value.upper(), self)
        kind_label.setObjectName("messageDialogKind")
        layout.addWidget(kind_label)

        message_label = QLabel(message, self)
        message_label.setObjectName("messageDialogMessage")
        message_label.setWordWrap(True)
        message_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        layout.addWidget(message_label)

        self._details = details
        self._details_toggle: QToolButton | None = None
        self._details_view: QPlainTextEdit | None = None
        if details:
            self._details_toggle = QToolButton(self)
            self._details_toggle.setObjectName("messageDialogDetailsToggle")
            self._details_toggle.setText("Show details")
            self._details_toggle.setCheckable(True)
            self._details_toggle.setChecked(False)
            self._details_toggle.setArrowType(Qt.ArrowType.RightArrow)
            self._details_toggle.setAutoRaise(True)
            self._details_toggle.toggled.connect(self._on_details_toggled)
            layout.addWidget(self._details_toggle, 0, Qt.AlignmentFlag.AlignLeft)

            self._details_view = QPlainTextEdit(details, self)
            self._details_view.setObjectName("messageDialogDetails")
            self._details_view.setReadOnly(True)
            self._details_view.setVisible(False)
            self._details_view.setMinimumHeight(120)
            layout.addWidget(self._details_view)

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok, self)
        button_box.setObjectName("messageDialogButtonBox")
        button_box.accepted.connect(self.accept)
        layout.addWidget(button_box)

        if copyable and details:
            copy_button = QPushButton("Copy details", self)
            copy_button.setObjectName("messageDialogCopy")
            copy_button.clicked.connect(self._copy_details)
            button_box.addButton(copy_button, QDialogButtonBox.ButtonRole.ActionRole)

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

    def _copy_details(self) -> None:
        clipboard = QGuiApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(self._details)

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------
    @property
    def details(self) -> str:
        return self._details


def show_message(
    parent: QWidget | None,
    title: str,
    message: str,
    *,
    kind: MessageKind = MessageKind.INFO,
    details: str = "",
    copyable: bool = False,
) -> None:
    """Display a modal message dialog.

    Convenience wrapper used by callers that do not need to keep a
    reference to the dialog. The dialog is destroyed after it is closed.
    """
    dialog = MessageDialog(
        title=title,
        message=message,
        kind=kind,
        details=details,
        copyable=copyable,
        parent=parent,
    )
    dialog.exec()