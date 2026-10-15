"""Result list widget used by the global search page.

The list is a thin widget over a vertical stack of result rows. Each row
renders a single ``SearchResultEntry`` and emits activation and detail
signals. The list is populated by the caller and does not fetch anything.

Design decisions
----------------
- Entries are immutable dataclasses. The list is a view onto a sequence
  supplied by the caller.
- Origins are typed so that callers and tests can assert on the source of
  a result without inspecting strings.
- The list renders an empty state when the entry sequence is empty. The
  empty state is customizable by the caller so that the wording can match
  the surface (local versus remote).
- A busy state is not rendered by the list itself. The caller swaps the
  list for a loading indicator through the page's state stack.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from academic_platform.ui.components.stat_badge import StatBadge, StatBadgeTone


class SearchResultOrigin(str, Enum):
    """Origin of a search result."""

    LOCAL_LIBRARY = "local_library"
    LOCAL_PROJECT = "local_project"
    LOCAL_COLLECTION = "local_collection"
    LOCAL_NOTE = "local_note"
    LOCAL_EVIDENCE = "local_evidence"
    REMOTE_SOURCE = "remote_source"


@dataclass(frozen=True, slots=True)
class SearchResultEntry:
    """A single search result.

    Attributes
    ----------
    identifier:
        Stable identifier used to correlate the entry with a caller-owned
        record. Never displayed.
    title:
        Primary line of the entry.
    subtitle:
        Secondary line. May be empty.
    snippet:
        Optional preview text. May be empty.
    origin:
        Where the result came from.
    source_label:
        Human-readable label of the concrete source (a provider name, a
        project title, a collection name). May be empty.
    score:
        Optional relevance score. Rendered as a badge when present.
    metadata:
        Optional list of (label, value) pairs rendered as small badges.
    """

    identifier: str
    title: str
    subtitle: str = ""
    snippet: str = ""
    origin: SearchResultOrigin = SearchResultOrigin.LOCAL_LIBRARY
    source_label: str = ""
    score: float | None = None
    metadata: tuple[tuple[str, str], ...] = field(default_factory=tuple)


_ORIGIN_LABELS: dict[SearchResultOrigin, str] = {
    SearchResultOrigin.LOCAL_LIBRARY: "Library",
    SearchResultOrigin.LOCAL_PROJECT: "Project",
    SearchResultOrigin.LOCAL_COLLECTION: "Collection",
    SearchResultOrigin.LOCAL_NOTE: "Note",
    SearchResultOrigin.LOCAL_EVIDENCE: "Evidence",
    SearchResultOrigin.REMOTE_SOURCE: "Remote",
}


class _ResultRow(QFrame):
    """Internal row widget. Not part of the public API."""

    activated = Signal(str)
    details_requested = Signal(str)

    def __init__(self, entry: SearchResultEntry, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("searchResultRow")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setProperty("entry", entry)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(6)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(6)

        title = QLabel(entry.title or "(untitled)", self)
        title.setObjectName("searchResultRowTitle")
        title.setWordWrap(True)
        header.addWidget(title, 1)

        header.addWidget(
            StatBadge(
                _ORIGIN_LABELS[entry.origin],
                entry.source_label,
                tone=StatBadgeTone.NEUTRAL,
                parent=self,
            ),
            0,
            Qt.AlignmentFlag.AlignTop,
        )

        if entry.score is not None:
            header.addWidget(
                StatBadge("Score", f"{entry.score:.2f}", parent=self),
                0,
                Qt.AlignmentFlag.AlignTop,
            )
        layout.addLayout(header)

        if entry.subtitle:
            subtitle = QLabel(entry.subtitle, self)
            subtitle.setObjectName("searchResultRowSubtitle")
            subtitle.setWordWrap(True)
            layout.addWidget(subtitle)

        if entry.snippet:
            snippet = QLabel(entry.snippet, self)
            snippet.setObjectName("searchResultRowSnippet")
            snippet.setWordWrap(True)
            snippet.setMaximumHeight(56)
            layout.addWidget(snippet)

        if entry.metadata:
            meta_row = QHBoxLayout()
            meta_row.setContentsMargins(0, 0, 0, 0)
            meta_row.setSpacing(6)
            for label, value in entry.metadata:
                meta_row.addWidget(StatBadge(label, value, parent=self))
            meta_row.addStretch(1)
            layout.addLayout(meta_row)

        actions = QHBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(6)

        self._details_button = QPushButton("Details", self)
        self._details_button.setObjectName("searchResultRowDetails")
        self._details_button.setEnabled(False)
        self._details_button.clicked.connect(
            lambda: self.details_requested.emit(entry.identifier)
        )
        actions.addWidget(self._details_button)
        actions.addStretch(1)
        layout.addLayout(actions)

    def enable_details(self, enabled: bool = True) -> None:
        self._details_button.setEnabled(enabled)

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802 - Qt API
        entry = self.property("entry")
        if entry is not None:
            self.activated.emit(entry.identifier)
        super().mouseDoubleClickEvent(event)


class SearchResultList(QWidget):
    """Vertical list of search result rows with an empty state."""

    entry_activated = Signal(str)
    entry_details_requested = Signal(str)

    def __init__(
        self,
        *,
        empty_title: str = "No results",
        empty_message: str = "No results matched the current query.",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("searchResultList")

        self._empty_title = empty_title
        self._empty_message = empty_message

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(8)

        self._rows: list[_ResultRow] = []
        self._empty_widget: QWidget | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def set_entries(self, entries: list[SearchResultEntry]) -> None:
        """Replace the displayed entries."""
        self._clear()
        if not entries:
            self._show_empty()
            return
        for entry in entries:
            row = _ResultRow(entry, self)
            row.activated.connect(self.entry_activated.emit)
            row.details_requested.connect(self.entry_details_requested.emit)
            row.enable_details()
            self._rows.append(row)
            self._layout.addWidget(row)

    def clear(self) -> None:
        """Remove all entries and show the empty state."""
        self._clear()
        self._show_empty()

    def entry_count(self) -> int:
        """Return the number of displayed entries."""
        return len(self._rows)

    def entries(self) -> list[SearchResultEntry]:
        """Return the entries currently displayed."""
        return [row.property("entry") for row in self._rows if row.property("entry") is not None]

    def set_empty_message(self, title: str, message: str) -> None:
        """Replace the empty-state wording used by future ``set_entries`` calls."""
        self._empty_title = title
        self._empty_message = message

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _clear(self) -> None:
        for row in self._rows:
            self._layout.removeWidget(row)
            row.setParent(None)
            row.deleteLater()
        self._rows.clear()
        if self._empty_widget is not None:
            self._layout.removeWidget(self._empty_widget)
            self._empty_widget.setParent(None)
            self._empty_widget.deleteLater()
            self._empty_widget = None

    def _show_empty(self) -> None:
        from academic_platform.ui.components.empty_state import EmptyState

        state = EmptyState(
            title=self._empty_title,
            message=self._empty_message,
            parent=self,
        )
        self._empty_widget = state
        self._layout.addWidget(state)