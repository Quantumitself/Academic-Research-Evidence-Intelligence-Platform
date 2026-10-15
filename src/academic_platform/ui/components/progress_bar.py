"""Reusable determinate progress bar.

The component is intended for long-running operations with known totals,
such as file imports, batch extractions, or analysis runs. It exposes a
``cancel_requested`` signal; the caller decides whether cancellation is
honored.

Design decisions
----------------
- The value is always clamped to [0, total].
- The label is optional. When omitted, the bar renders without text.
- The cancel button is hidden unless the caller installs it.
- The component does not own the operation; it reflects the caller's
  progress reports and emits a cancel request.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class ProgressBar(QWidget):
    """Determinate progress bar with an optional label and cancel button."""

    cancel_requested = Signal()

    def __init__(
        self,
        total: int,
        *,
        label: str = "",
        cancellable: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        if total <= 0:
            raise ValueError("total must be a positive integer")
        self.setObjectName("progressBar")
        self._total = total
        self._value = 0

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self._label = QLabel(label, self)
        self._label.setObjectName("progressBarLabel")
        self._label.setVisible(bool(label))
        layout.addWidget(self._label)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)

        self._bar = QProgressBar(self)
        self._bar.setObjectName("progressBarTrack")
        self._bar.setRange(0, total)
        self._bar.setValue(0)
        row.addWidget(self._bar, 1)

        self._cancel_button = QPushButton("Cancel", self)
        self._cancel_button.setObjectName("progressBarCancel")
        self._cancel_button.setVisible(cancellable)
        self._cancel_button.clicked.connect(self.cancel_requested.emit)
        row.addWidget(self._cancel_button, 0, Qt.AlignmentFlag.AlignRight)

        layout.addLayout(row)

    # ------------------------------------------------------------------
    # Mutation API
    # ------------------------------------------------------------------
    def set_value(self, value: int) -> None:
        """Set the current progress, clamped to [0, total]."""
        clamped = max(0, min(int(value), self._total))
        self._value = clamped
        self._bar.setValue(clamped)

    def advance(self, delta: int = 1) -> None:
        """Advance the current progress."""
        self.set_value(self._value + delta)

    def set_label(self, label: str) -> None:
        """Replace the label. An empty string hides the label."""
        self._label.setText(label)
        self._label.setVisible(bool(label))

    def set_cancellable(self, cancellable: bool) -> None:
        """Show or hide the cancel button."""
        self._cancel_button.setVisible(cancellable)

    def set_cancel_enabled(self, enabled: bool) -> None:
        """Enable or disable the cancel button."""
        self._cancel_button.setEnabled(enabled)

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------
    @property
    def total(self) -> int:
        return self._total

    @property
    def value(self) -> int:
        return self._value

    @property
    def is_complete(self) -> bool:
        return self._value >= self._total

    @property
    def cancel_button(self) -> QPushButton:
        return self._cancel_button