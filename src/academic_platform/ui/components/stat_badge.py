"""Compact badge for a single value.

The badge renders a label-value pair (for example "Citations 42") or a
label-only status ("Open access"). It carries a tone that influences
styling: neutral, positive, warning, or danger. Tones are purely visual and
do not encode business rules; callers choose the tone.

Design decisions
----------------
- The badge never interprets its content. It displays what it is given.
- The tone is applied through a dynamic Qt property so that the stylesheet
  can key on it without rebuilding the stylesheet per badge.
- The badge is content-agnostic: the value may be a number, a duration, or
  a short status string.
"""

from __future__ import annotations

from enum import Enum

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QWidget


class StatBadgeTone(str, Enum):
    """Visual tone applied to the badge."""

    NEUTRAL = "neutral"
    POSITIVE = "positive"
    WARNING = "warning"
    DANGER = "danger"


class StatBadge(QFrame):
    """Compact label-value badge with a visual tone."""

    def __init__(
        self,
        label: str,
        value: str = "",
        *,
        tone: StatBadgeTone = StatBadgeTone.NEUTRAL,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("statBadge")
        self.setFrameShape(QFrame.Shape.StyledPanel)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 3, 8, 3)
        layout.setSpacing(6)

        self._label = QLabel(label, self)
        self._label.setObjectName("statBadgeLabel")
        layout.addWidget(self._label)

        self._value = QLabel(value, self)
        self._value.setObjectName("statBadgeValue")
        self._value.setVisible(bool(value))
        layout.addWidget(self._value)

        self._apply_tone(tone)

    # ------------------------------------------------------------------
    # Mutation API
    # ------------------------------------------------------------------
    def set_label(self, label: str) -> None:
        """Replace the label text."""
        self._label.setText(label)

    def set_value(self, value: str) -> None:
        """Replace the value text. An empty string hides the value."""
        self._value.setText(value)
        self._value.setVisible(bool(value))

    def set_tone(self, tone: StatBadgeTone) -> None:
        """Apply a new visual tone."""
        self._apply_tone(tone)

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------
    @property
    def label(self) -> str:
        return self._label.text()

    @property
    def value(self) -> str:
        return self._value.text()

    @property
    def tone(self) -> StatBadgeTone:
        return StatBadgeTone(self.property("tone"))

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _apply_tone(self, tone: StatBadgeTone) -> None:
        self.setProperty("tone", tone.value)
        style = self.style()
        style.unpolish(self)
        style.polish(self)