"""Immutable value object describing a saved search.

A saved search carries the query text, the scope, the filter payload, the
target source set, and an optional user-supplied name. It is the unit
the service persists and the presentation layer displays.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class SavedSearch:
    """A reusable search definition."""

    key: str
    name: str = ""
    query_text: str = ""
    scope: str = "all"
    filters: dict[str, Any] = field(default_factory=dict)
    source_keys: tuple[str, ...] = field(default_factory=tuple)
    last_executed_at: str | None = None

    def __post_init__(self) -> None:
        if not self.key:
            raise ValueError("key must not be empty")
        if self.scope not in {"all", "local", "remote"}:
            raise ValueError("scope must be one of: all, local, remote")

    @property
    def display_label(self) -> str:
        """Return a short human-readable label for the search."""
        if self.name:
            return self.name
        if self.query_text:
            return self.query_text
        return self.key