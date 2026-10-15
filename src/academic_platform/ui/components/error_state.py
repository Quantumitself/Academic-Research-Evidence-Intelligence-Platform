"""Reusable error-state component.

Error states communicate a failure that the user may need to act on. They
are visually distinct from empty states and always carry an explicit message.
An optional retry action is provided for recoverable failures.

Design decisions
----------------
- The component never invents error content. The caller supplies the
  user-facing message; technical diagnostics belong in logs.
- Retry is exposed as a signal. Callers decide whether to connect it; an
  unconnected retry button is disabled.
- The error message is selectable so that users can copy it into a bug
  report.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class ErrorState(QFrame):
    """Bordered error panel with a message and optional retry."""

    retry_requested = Signal()

    def __init__(
        self,
        message: str,
        *,
        retryable: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("errorState")
        self.setFrameShape(QFrame.Shape.StyledPanel)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(8)

        self._glyph_label = QLabel("\u26A0", self)
        self._glyph_label.setObjectName("errorStateGlyph")
        header.addWidget(self._glyph_label, 0, Qt.AlignmentFlag.AlignTop)

        self._message_label = QLabel(message, self)
        self._message_label.setObjectName("errorStateMessage")
        self._message_label.setWordWrap(True)
        self._message_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        header.addWidget(self._message_label, 1)

        layout.addLayout(header)

        self._retry_button = QPushButton("Retry", self)
        self._retry_button.setObjectName("errorStateRetry")
        self._retry_button.setVisible(retryable)
        self._retry_button.setEnabled(False)
        self._retry_button.clicked.connect(self.retry_requested.emit)
        layout.addWidget(self._retry_button, 0, Qt.AlignmentFlag.AlignRight)

    # ------------------------------------------------------------------
    # Mutation API
    # ------------------------------------------------------------------
    def set_message(self, message: str) -> None:
        """Replace the displayed message."""
        self._message_label.setText(message)

    def set_retryable(self, retryable: bool) -> None:
        """Show or hide the retry button."""
        self._retry_button.setVisible(retryable)

    def set_retry_enabled(self, enabled: bool) -> None:
        """Enable the retry button once a handler is attached."""
        self._retry_button.setEnabled(enabled)

    @property
    def retry_button(self) -> QPushButton:
        return self._retry_button

    @property
    def message(self) -> str:
        return self._message_label.text()