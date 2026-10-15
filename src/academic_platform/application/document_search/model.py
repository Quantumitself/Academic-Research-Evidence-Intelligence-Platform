"""Value objects for the in-document search service."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class DocumentSearchMatch:
    """A single match within a document.

    Attributes
    ----------
    document_key:
        The key of the document the match belongs to.
    page_number:
        1-based page number the match was found on. ``None`` when the
        chunk carrying the match has no page attribution.
    chunk_index:
        Index of the chunk the match was found in.
    start_offset:
        Character offset of the match start within the chunk's content.
    end_offset:
        Character offset of the match end within the chunk's content.
    snippet:
        A short excerpt around the match. Matched terms are wrapped in
        the marker strings configured on the service.
    match_text:
        The matched substring as it appears in the chunk.
    """

    document_key: str
    page_number: int | None
    chunk_index: int
    start_offset: int
    end_offset: int
    snippet: str
    match_text: str

    @property
    def length(self) -> int:
        return max(0, self.end_offset - self.start_offset)


@dataclass(frozen=True, slots=True)
class DocumentSearchResult:
    """Outcome of a search over a single document."""

    document_key: str
    query: str
    matches: tuple[DocumentSearchMatch, ...] = field(default_factory=tuple)
    truncated: bool = False
    message: str = ""

    @property
    def match_count(self) -> int:
        return len(self.matches)

    @property
    def pages_with_matches(self) -> tuple[int, ...]:
        pages = {match.page_number for match in self.matches if match.page_number}
        return tuple(sorted(pages))