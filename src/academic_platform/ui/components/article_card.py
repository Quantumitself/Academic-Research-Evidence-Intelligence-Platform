"""Publication summary card.

Displays the bibliographic metadata of a publication together with its
source provenance (which search providers returned it) and a compact action
row. The card emits typed signals for every action; the caller wires them
to application services.

Design decisions
----------------
- The card is presentation-only. It never fetches or stores publications.
- The card accepts a plain data payload rather than a domain object so that
  it can be used before the domain layer exists. The payload is a
  ``PublicationSummary`` dataclass defined here; later phases may add an
  adapter from the domain model.
- Source provenance is rendered as small chips. The set of sources is
  supplied by the caller.
- Actions are grouped in a single row. Every action button is disabled
  until the caller connects the corresponding signal. This prevents a
  live control that does nothing.
"""

from __future__ import annotations

from dataclasses import dataclass, field

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


@dataclass(frozen=True, slots=True)
class PublicationSummary:
    """Presentation payload for a publication card.

    Fields mirror the subset of bibliographic metadata the card renders.
    Unknown or unavailable fields are empty strings; the card hides empty
    rows.
    """

    identifier: str
    title: str
    authors: str = ""
    year: str = ""
    venue: str = ""
    abstract: str = ""
    doi: str = ""
    source_providers: tuple[str, ...] = field(default_factory=tuple)
    is_open_access: bool = False
    citation_count: int | None = None


class ArticleCard(QFrame):
    """Publication summary card."""

    activated = Signal(str)
    save_requested = Signal(str)
    open_requested = Signal(str)
    details_requested = Signal(str)

    def __init__(
        self,
        publication: PublicationSummary,
        *,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("articleCard")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self._publication = publication

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)

        # Title row
        title = QLabel(publication.title or "(untitled)", self)
        title.setObjectName("articleCardTitle")
        title.setWordWrap(True)
        layout.addWidget(title)

        # Authors and year row
        authors_line = self._format_authors_line(publication.authors, publication.year)
        if authors_line:
            authors = QLabel(authors_line, self)
            authors.setObjectName("articleCardAuthors")
            authors.setWordWrap(True)
            layout.addWidget(authors)

        # Venue
        if publication.venue:
            venue = QLabel(publication.venue, self)
            venue.setObjectName("articleCardVenue")
            venue.setWordWrap(True)
            layout.addWidget(venue)

        # Abstract (truncated visually by the card; full text lives in the reader)
        if publication.abstract:
            abstract = QLabel(publication.abstract, self)
            abstract.setObjectName("articleCardAbstract")
            abstract.setWordWrap(True)
            abstract.setMaximumHeight(64)
            layout.addWidget(abstract)

        # Badges row: DOI, open access, citation count, sources
        badges_row = QHBoxLayout()
        badges_row.setContentsMargins(0, 0, 0, 0)
        badges_row.setSpacing(6)
        if publication.doi:
            badges_row.addWidget(StatBadge("DOI", publication.doi, parent=self))
        if publication.is_open_access:
            badges_row.addWidget(
                StatBadge("Access", "Open", tone=StatBadgeTone.POSITIVE, parent=self)
            )
        if publication.citation_count is not None:
            badges_row.addWidget(
                StatBadge("Citations", str(publication.citation_count), parent=self)
            )
        for provider in publication.source_providers:
            badges_row.addWidget(StatBadge(provider, "", parent=self))
        badges_row.addStretch(1)
        layout.addLayout(badges_row)

        # Actions row
        actions = QHBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(6)

        self._open_button = QPushButton("Open", self)
        self._open_button.setObjectName("articleCardOpen")
        self._open_button.setEnabled(False)
        self._open_button.clicked.connect(
            lambda: self.open_requested.emit(publication.identifier)
        )
        actions.addWidget(self._open_button)

        self._save_button = QPushButton("Save", self)
        self._save_button.setObjectName("articleCardSave")
        self._save_button.setEnabled(False)
        self._save_button.clicked.connect(
            lambda: self.save_requested.emit(publication.identifier)
        )
        actions.addWidget(self._save_button)

        self._details_button = QPushButton("Details", self)
        self._details_button.setObjectName("articleCardDetails")
        self._details_button.setEnabled(False)
        self._details_button.clicked.connect(
            lambda: self.details_requested.emit(publication.identifier)
        )
        actions.addWidget(self._details_button)

        actions.addStretch(1)
        layout.addLayout(actions)

        self.setCursor(Qt.CursorShape.PointingHandCursor)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def enable_open(self, enabled: bool = True) -> None:
        """Enable the Open button once the caller has connected the signal."""
        self._open_button.setEnabled(enabled)

    def enable_save(self, enabled: bool = True) -> None:
        """Enable the Save button once the caller has connected the signal."""
        self._save_button.setEnabled(enabled)

    def enable_details(self, enabled: bool = True) -> None:
        """Enable the Details button once the caller has connected the signal."""
        self._details_button.setEnabled(enabled)

    @property
    def identifier(self) -> str:
        return self._publication.identifier

    @property
    def publication(self) -> PublicationSummary:
        return self._publication

    # ------------------------------------------------------------------
    # Mouse interaction
    # ------------------------------------------------------------------
    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802 - Qt API
        self.activated.emit(self._publication.identifier)
        super().mouseDoubleClickEvent(event)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    @staticmethod
    def _format_authors_line(authors: str, year: str) -> str:
        if authors and year:
            return f"{authors} · {year}"
        return authors or year