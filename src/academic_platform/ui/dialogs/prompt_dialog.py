"""Single-line text prompt dialog.

The dialog renders a label, a line edit, an optional validation function,
and OK/Cancel buttons. The OK button is disabled while validation fails.
Validation is provided by the caller as a callable that returns either
``None`` (valid) or a user-facing message describing the problem.

Design decisions
----------------
- Validation is synchronous and local. Callers that require asynchronous
  validation (for example, checking a remote identifier) should perform
  that check after the dialog closes and reopen the dialog on failure.
- The initial value is preserved if the dialog is cancelled. The caller
  reads ``value()`` only when the dialog is accepted.
- The dialog trims surrounding whitespace by default. Callers that need
  to preserve whitespace pass ``trim=False``.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

Validator = Callable[[str], "str | None"]


class PromptDialog(QDialog):
    """Single-line text prompt with optional validation."""

    def __init__(
        self,
        title: str,
        label: str,
        *,
        initial: str = "",
        placeholder: str = "",
        validator: Validator | None = None,
        trim: bool = True,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("promptDialog")
        self.setModal(True)
        self.setWindowTitle(title)
        self.setMinimumWidth(420)

        self._validator = validator
        self._trim = trim

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(10)

        label_widget = QLabel(label, self)
        label_widget.setObjectName("promptDialogLabel")
        label_widget.setWordWrap(True)
        layout.addWidget(label_widget)

        self._input = QLineEdit(initial, self)
        self._input.setObjectName("promptDialogInput")
        self._input.setPlaceholderText(placeholder)
        self._input.textChanged.connect(self._on_text_changed)
        layout.addWidget(self._input)

        self._error_label = QLabel("", self)
        self._error_label.setObjectName("promptDialogError")
        self._error_label.setWordWrap(True)
        self._error_label.setVisible(False)
        layout.addWidget(self._error_label)

        button_box = QDialogButtonBox(self)
        button_box.setObjectName("promptDialogButtonBox")
        self._ok_button = button_box.addButton(QDialogButtonBox.StandardButton.Ok)
        self._cancel_button = button_box.addButton(QDialogButtonBox.StandardButton.Cancel)
        self._ok_button.setObjectName("promptDialogOk")
        self._cancel_button.setObjectName("promptDialogCancel")
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        self._revalidate()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def value(self) -> str:
        """Return the current input value, honoring the trim policy."""
        text = self._input.text()
        return text.strip() if self._trim else text

    def set_value(self, value: str) -> None:
        """Replace the input value and revalidate."""
        self._input.setText(value)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------
    def _on_text_changed(self, _text: str) -> None:
        self._revalidate()

    def _revalidate(self) -> None:
        if self._validator is None:
            self._error_label.setVisible(False)
            self._ok_button.setEnabled(True)
            return
        problem = self._validator(self.value())
        if problem is None:
            self._error_label.setVisible(False)
            self._ok_button.setEnabled(True)
        else:
            self._error_label.setText(problem)
            self._error_label.setVisible(True)
            self._ok_button.setEnabled(False)


def ask_text(
    parent: QWidget | None,
    title: str,
    label: str,
    *,
    initial: str = "",
    placeholder: str = "",
    validator: Validator | None = None,
    trim: bool = True,
) -> str | None:
    """Display a modal text prompt. Returns the value or None if cancelled."""
    dialog = PromptDialog(
        title=title,
        label=label,
        initial=initial,
        placeholder=placeholder,
        validator=validator,
        trim=trim,
        parent=parent,
    )
    if dialog.exec() == QDialog.DialogCode.Accepted:
        return dialog.value()
    return None