"""Modal progress dialog.

The dialog wraps ``ProgressBar`` in a modal frame with a title, a message,
and an optional cancel button. It is used for operations that block the
caller's workflow and require user visibility.

Design decisions
----------------
- The dialog does not own the operation. The caller updates the progress
  through ``set_value`` and closes the dialog when the work finishes.
- Cancellation is a request, not an enforcement. The dialog emits
  ``cancel_requested``; the caller decides whether to honor it.
- The dialog is modal by default. Callers that prefer non-modal progress
  should use the notification system with a progress indicator instead.
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QDialog,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from academic_platform.ui.components.progress_bar import ProgressBar


class ProgressDialog(QDialog):
    """Modal progress dialog with an optional cancel action."""

    cancel_requested = Signal()

    def __init__(
        self,
        title: str,
        *,
        message: str = "",
        total: int,
        cancellable: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("progressDialog")
        self.setModal(True)
        self.setWindowTitle(title)
        self.setMinimumWidth(440)
        self.setWindowFlag(self.windowFlags() | self.windowFlags().WindowCloseButtonHint, False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(10)

        if message:
            message_label = QLabel(message, self)
            message_label.setObjectName("progressDialogMessage")
            message_label.setWordWrap(True)
            layout.addWidget(message_label)

        self._progress = ProgressBar(
            total=total,
            label="",
            cancellable=cancellable,
            parent=self,
        )
        self._progress.cancel_requested.connect(self.cancel_requested.emit)
        layout.addWidget(self._progress)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def set_value(self, value: int) -> None:
        """Update the current progress."""
        self._progress.set_value(value)

    def advance(self, delta: int = 1) -> None:
        """Advance the current progress."""
        self._progress.advance(delta)

    def set_label(self, label: str) -> None:
        """Replace the progress label."""
        self._progress.set_label(label)

    def set_cancellable(self, cancellable: bool) -> None:
        """Show or hide the cancel button."""
        self._progress.set_cancellable(cancellable)

    def set_cancel_enabled(self, enabled: bool) -> None:
        """Enable or disable the cancel button."""
        self._progress.set_cancel_enabled(enabled)

    @property
    def total(self) -> int:
        return self._progress.total

    @property
    def value(self) -> int:
        return self._progress.value

    # ------------------------------------------------------------------
    # Close handling
    # ------------------------------------------------------------------
    def closeEvent(self, event) -> None:  # noqa: N802 - Qt API
        # Closing the dialog is treated as a cancellation request. The
        # caller decides whether to actually cancel; the dialog only
        # forwards the intent.
        self.cancel_requested.emit()
        super().closeEvent(event)