"""Standalone page header component.

The component renders a title, a subtitle, and a right-aligned actions
region. It is used by dialogs and by any widget that requires a header
outside the ``BasePage`` hierarchy.

Design decisions
----------------
- The header emits no signals. Callers connect their controls directly.
- The header never owns business logic. It renders what it is given.
- The subtitle is hidden when empty so that the header does not reserve
  vertical space for content that does not exist.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)


class PageHeader(QFrame):
    """Title, subtitle, and actions region for a page or dialog."""

    def __init__(
        self,
        title: str,
        subtitle: str = "",
        *,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("pageHeader")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 8)
        layout.setSpacing(12)

        titles = QVBoxLayout()
        titles.setContentsMargins(0, 0, 0, 0)
        titles.setSpacing(4)

        self._title_label = QLabel(title, self)
        self._title_label.setObjectName("pageHeading")
        titles.addWidget(self._title_label)

        self._subtitle_label = QLabel(subtitle, self)
        self._subtitle_label.setObjectName("pageSubtitle")
        self._subtitle_label.setWordWrap(True)
        self._subtitle_label.setVisible(bool(subtitle))
        titles.addWidget(self._subtitle_label)

        layout.addLayout(titles, 1)

        self._actions_container = QWidget(self)
        actions_layout = QHBoxLayout(self._actions_container)
        actions_layout.setContentsMargins(0, 0, 0, 0)
        actions_layout.setSpacing(8)
        layout.addWidget(self._actions_container, 0, Qt.AlignmentFlag.AlignTop)
        self._actions_layout = actions_layout

    # ------------------------------------------------------------------
    # Mutation API
    # ------------------------------------------------------------------
    def set_title(self, title: str) -> None:
        """Replace the displayed title."""
        self._title_label.setText(title)

    def set_subtitle(self, subtitle: str) -> None:
        """Replace the displayed subtitle. An empty string hides it."""
        self._subtitle_label.setText(subtitle)
        self._subtitle_label.setVisible(bool(subtitle))

    def add_action(self, widget: QWidget) -> None:
        """Add a widget to the actions region."""
        self._actions_layout.addWidget(widget)

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------
    @property
    def title(self) -> str:
        return self._title_label.text()

    @property
    def subtitle(self) -> str:
        return self._subtitle_label.text()