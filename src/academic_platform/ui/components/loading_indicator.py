"""Reusable loading indicator.

The indicator supports two modes:

- Indeterminate: a busy bar indicating work of unknown duration.
- Determinate: a progress bar with a known percentage.

The message is always displayed above the bar. The component does not start
or stop work; the caller sets the mode and, in determinate mode, updates the
value.

Design decisions
----------------
- A single widget handles both modes so that callers do not choose between
  two types when they may only know the mode at runtime.
- In determinate mode, ``set_progress`` clamps values to the [0, total]
  range and updates the label.
- The message is preserved when switching modes.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QLabel,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)


class LoadingIndicator(QWidget):
    """Loading indicator with an optional message and determinate progress."""

    def __init__(
        self,
        message: str = "Loading…",
        *,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("loadingIndicator")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._message_label = QLabel(message, self)
        self._message_label.setObjectName("loadingIndicatorMessage")
        self._message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._message_label.setWordWrap(True)
        layout.addWidget(self._message_label)

        self._bar = QProgressBar(self)
        self._bar.setObjectName("loadingIndicatorBar")
        self._bar.setTextVisible(False)
        self._bar.setMinimumWidth(260)
        # Range of (0, 0) selects indeterminate mode in Qt.
        self._bar.setRange(0, 0)
        layout.addWidget(self._bar, 0, Qt.AlignmentFlag.AlignCenter)

        self._total = 0
        self._value = 0

    # ------------------------------------------------------------------
    # Mode and value
    # ------------------------------------------------------------------
    def set_message(self, message: str) -> None:
        """Replace the displayed message."""
        self._message_label.setText(message)

    def set_indeterminate(self) -> None:
        """Switch to indeterminate mode."""
        self._total = 0
        self._value = 0
        self._bar.setRange(0, 0)

    def set_determinate(self, total: int) -> None:
        """Switch to determinate mode with the given total.

        Raises
        ------
        ValueError
            If ``total`` is not a positive integer.
        """
        if total <= 0:
            raise ValueError("total must be a positive integer")
        self._total = total
        self._value = 0
        self._bar.setRange(0, total)
        self._bar.setValue(0)

    def set_progress(self, value: int) -> None:
        """Update the current progress in determinate mode.

        Values outside [0, total] are clamped. Calling this method while in
        indeterminate mode is a no-op.
        """
        if self._total <= 0:
            return
        clamped = max(0, min(int(value), self._total))
        self._value = clamped
        self._bar.setValue(clamped)

    def advance(self, delta: int = 1) -> None:
        """Advance the current progress in determinate mode."""
        self.set_progress(self._value + delta)

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------
    @property
    def message(self) -> str:
        return self._message_label.text()

    @property
    def is_indeterminate(self) -> bool:
        return self._total == 0

    @property
    def total(self) -> int:
        return self._total

    @property
    def value(self) -> int:
        return self._value