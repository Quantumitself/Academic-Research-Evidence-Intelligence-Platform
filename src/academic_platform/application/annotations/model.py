"""Value objects for the annotation service."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class AnnotationKind(str, Enum):
    """Supported annotation kinds."""

    NOTE = "note"
    HIGHLIGHT = "highlight"
    BOOKMARK = "bookmark"


class AnnotationColor(str, Enum):
    """Supported highlight colors."""

    YELLOW = "yellow"
    GREEN = "green"
    BLUE = "blue"
    PINK = "pink"


@dataclass(frozen=True, slots=True)
class AnnotationView:
    """An annotation as seen by the presentation layer."""

    identifier: int
    document_key: str
    kind: AnnotationKind
    page_number: int | None
    body: str
    text_excerpt: str
    anchor: str | None
    color: AnnotationColor | None
    created_at: str
    updated_at: str
    version: int

    @property
    def is_bookmark(self) -> bool:
        return self.kind is AnnotationKind.BOOKMARK

    @property
    def is_highlight(self) -> bool:
        return self.kind is AnnotationKind.HIGHLIGHT

    @property
    def is_note(self) -> bool:
        return self.kind is AnnotationKind.NOTE

    @property
    def display_label(self) -> str:
        if self.kind is AnnotationKind.BOOKMARK:
            return f"Bookmark on page {self.page_number or '?'}"
        if self.kind is AnnotationKind.HIGHLIGHT:
            prefix = (self.text_excerpt or "").strip()
            if prefix:
                return prefix[:80]
            return f"Highlight on page {self.page_number or '?'}"
        body = (self.body or "").strip()
        if body:
            return body[:80]
        return f"Note on page {self.page_number or '?'}"