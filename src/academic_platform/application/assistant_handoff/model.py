"""Value objects for the reader → assistant handoff."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class HandoffOptions:
    """User-selectable inclusion options for a handoff.

    Attributes
    ----------
    include_metadata:
        Include the document's extracted metadata (title, authors, year,
        venue, DOI, abstract).
    include_current_page_text:
        Include the current page's extracted text as an excerpt.
    include_annotations:
        Include the document's annotations.
    """

    include_metadata: bool = True
    include_current_page_text: bool = True
    include_annotations: bool = False


@dataclass(frozen=True, slots=True)
class AssistantHandoff:
    """Payload for the research assistant.

    The payload is intentionally read-only. It carries everything the
    assistant needs to answer questions about the current document
    without additional database access.
    """

    document_key: str
    title: str
    authors: tuple[str, ...] = field(default_factory=tuple)
    year: int | None = None
    venue: str | None = None
    doi: str | None = None
    abstract: str | None = None
    current_page: int | None = None
    page_count: int | None = None
    page_text_excerpt: str = ""
    annotations: tuple[str, ...] = field(default_factory=tuple)
    options: HandoffOptions = field(default_factory=HandoffOptions)

    @property
    def has_metadata(self) -> bool:
        return bool(
            self.title
            or self.authors
            or self.year
            or self.venue
            or self.doi
            or self.abstract
        )

    @property
    def has_excerpt(self) -> bool:
        return bool(self.page_text_excerpt.strip())

    @property
    def has_annotations(self) -> bool:
        return bool(self.annotations)

    @property
    def summary(self) -> str:
        parts: list[str] = [self.title or self.document_key]
        if self.year is not None:
            parts.append(str(self.year))
        if self.current_page is not None and self.page_count is not None:
            parts.append(f"page {self.current_page} of {self.page_count}")
        return " · ".join(parts)