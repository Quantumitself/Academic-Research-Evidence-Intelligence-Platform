"""Reusable empty-state component.

Empty states are used whenever a region has no content to display. They must
explain the situation and, where relevant, what the user can do next.

Design decisions
----------------
- The component is presentation-only. It renders a title, a message, an
  optional glyph, and an optional primary action.
- The primary action is a button; the component exposes it through the
  ``action_requested`` signal. The caller decides whether the signal is
  connected to anything. An unconnected action button is disabled so that
  the UI never presents a live control that does nothing.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class EmptyState(QFrame):
    """Bordered empty-state panel with a title, message, and optional action."""

    action_requested = Signal()

    def __init__(
        self,
        title: str,
        message: str,
        *,
        glyph: str = "",
        action_label: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("emptyState")
        self.setFrameShape(QFrame.Shape.StyledPanel)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 32, 24, 32)
        layout.setSpacing(10)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._glyph_label = QLabel(glyph, self)
        self._glyph_label.setObjectName("emptyStateGlyph")
        self._glyph_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._glyph_label.setVisible(bool(glyph))
        layout.addWidget(self._glyph_label)

        self._title_label = QLabel(title, self)
        self._title_label.setObjectName("emptyStateTitle")
        self._title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._title_label)

        self._message_label = QLabel(message, self)
        self._message_label.setObjectName("emptyStateMessage")
        self._message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._message_label.setWordWrap(True)
        layout.addWidget(self._message_label)

        self._action_button = QPushButton(action_label, self)
        self._action_button.setObjectName("emptyStateAction")
        self._action_button.setVisible(bool(action_label))
        self._action_button.setEnabled(False)
        self._action_button.clicked.connect(self.action_requested.emit)
        layout.addWidget(self._action_button, 0, Qt.AlignmentFlag.AlignCenter)

    # ------------------------------------------------------------------
    # Mutation API
    # ------------------------------------------------------------------
    def set_content(self, title: str, message: str) -> None:
        """Replace the title and message."""
        self._title_label.setText(title)
        self._message_label.setText(message)

    def set_glyph(self, glyph: str) -> None:
        """Replace the decorative glyph. An empty string hides it."""
        self._glyph_label.setText(glyph)
        self._glyph_label.setVisible(bool(glyph))

    def set_action(self, label: str, *, enabled: bool = False) -> None:
        """Install an action button. Empty label hides the button."""
        self._action_button.setText(label)
        self._action_button.setVisible(bool(label))
        self._action_button.setEnabled(bool(label) and enabled)

    def set_action_enabled(self, enabled: bool) -> None:
        """Enable or disable the action button without changing its label."""
        self._action_button.setEnabled(enabled and bool(self._action_button.text()))

    @property
    def action_button(self) -> QPushButton:
        """Return the action button for callers that need to bind shortcuts."""
        return self._action_button

    @property
    def title(self) -> str:
        return self._title_label.text()

    @property
    def message(self) -> str:
        return self._message_label.text()