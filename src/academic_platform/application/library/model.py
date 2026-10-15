"""Value objects for the library application service."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class LibrarySortField(str, Enum):
    """Sortable fields for library listings."""

    DISPLAY_NAME = "display_name"
    ADDED_AT = "created_at"
    UPDATED_AT = "updated_at"
    PROCESSING_STATE = "processing_state"
    SIZE = "size_bytes"


class LibrarySortDirection(str, Enum):
    """Sort directions for library listings."""

    ASCENDING = "asc"
    DESCENDING = "desc"


@dataclass(frozen=True, slots=True)
class LibraryFilter:
    """Filter state accepted by the library list operation.

    Attributes
    ----------
    search_text:
        Optional full-text query. When present, the service consults the
        FTS5 index and returns only entries that match.
    processing_states:
        Optional set of processing states to include.
    extensions:
        Optional set of file extensions to include.
    """

    search_text: str = ""
    processing_states: frozenset[str] = field(default_factory=frozenset)
    extensions: frozenset[str] = field(default_factory=frozenset)

    @property
    def has_search(self) -> bool:
        return bool(self.search_text.strip())

    @property
    def is_empty(self) -> bool:
        return (
            not self.has_search
            and not self.processing_states
            and not self.extensions
        )


@dataclass(frozen=True, slots=True)
class LibraryEntry:
    """An immutable summary of a document in the library."""

    key: str
    display_name: str
    original_filename: str
    storage_mode: str
    location: str
    extension: str
    size_bytes: int
    page_count: int | None
    processing_state: str
    ocr_state: str
    indexing_state: str
    missing: bool
    last_error: str
    created_at: str
    updated_at: str
    title: str | None = None
    authors: tuple[str, ...] = field(default_factory=tuple)
    year: int | None = None
    doi: str | None = None


@dataclass(frozen=True, slots=True)
class LibraryPage:
    """A page of library entries together with pagination metadata."""

    entries: tuple[LibraryEntry, ...] = field(default_factory=tuple)
    total: int = 0
    offset: int = 0
    limit: int = 0

    @property
    def has_more(self) -> bool:
        return self.offset + len(self.entries) < self.total