"""Value objects for the research-history workspace."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class HistorySearchStatus(str, Enum):
    """The status of a single search run."""

    OK = "ok"
    PARTIAL = "partial"
    FAILED = "failed"
    SKIPPED = "skipped"

    @property
    def display_name(self) -> str:
        return {
            HistorySearchStatus.OK: "Completed",
            HistorySearchStatus.PARTIAL: "Completed with failures",
            HistorySearchStatus.FAILED: "Failed",
            HistorySearchStatus.SKIPPED: "Skipped",
        }[self]


@dataclass(frozen=True, slots=True)
class HistoryQuery:
    """A single search query the workspace proposes or the user records."""

    identifier: str
    text: str
    rationale: str = ""
    is_user_defined: bool = False

    @property
    def display_label(self) -> str:
        prefix = "✎ " if self.is_user_defined else "• "
        return f"{prefix}{self.text}"


@dataclass(frozen=True, slots=True)
class HistoryResult:
    """A single retrieved publication."""

    publication_key: str
    title: str
    authors: tuple[str, ...] = field(default_factory=tuple)
    year: int | None = None
    venue: str = ""
    doi: str | None = None
    abstract: str = ""
    source_providers: tuple[str, ...] = field(default_factory=tuple)
    citation_count: int | None = None

    @property
    def display_label(self) -> str:
        year = self.year if self.year is not None else "?"
        authors = ", ".join(self.authors[:2]) if self.authors else ""
        suffix = f" — {authors}" if authors else ""
        return f"{self.title or '(untitled)'} ({year}){suffix}"


@dataclass(frozen=True, slots=True)
class HistorySearchRun:
    """A single execution of a query against the search service."""

    query_identifier: str
    query_text: str
    status: HistorySearchStatus
    result_keys: tuple[str, ...] = field(default_factory=tuple)
    source_reports: tuple = field(default_factory=tuple)
    message: str = ""
    executed_at: str = ""

    @property
    def result_count(self) -> int:
        return len(self.result_keys)

    @property
    def display_label(self) -> str:
        return (
            f"{self.status.display_name}: {self.query_text!r} "
            f"({self.result_count} result(s))"
        )


@dataclass(frozen=True, slots=True)
class HistoryTimelineBucket:
    """A year-bucketed aggregation of results."""

    year: int
    result_keys: tuple[str, ...] = field(default_factory=tuple)

    @property
    def count(self) -> int:
        return len(self.result_keys)

    @property
    def display_label(self) -> str:
        return f"{self.year}: {self.count} result(s)"


@dataclass(frozen=True, slots=True)
class HistoryTheme:
    """A set of related results grouped by a shared concept."""

    name: str
    result_keys: tuple[str, ...] = field(default_factory=tuple)
    rationale: str = ""

    @property
    def count(self) -> int:
        return len(self.result_keys)

    @property
    def display_label(self) -> str:
        return f"{self.name} ({self.count})"


@dataclass(frozen=True, slots=True)
class ResearchHistoryDraft:
    """An immutable view of the workspace's current state."""

    project_key: str | None
    topic: str = ""
    synonyms: tuple[str, ...] = field(default_factory=tuple)
    queries: tuple[HistoryQuery, ...] = field(default_factory=tuple)
    runs: tuple[HistorySearchRun, ...] = field(default_factory=tuple)
    results: tuple[HistoryResult, ...] = field(default_factory=tuple)
    timeline: tuple[HistoryTimelineBucket, ...] = field(default_factory=tuple)
    themes: tuple[HistoryTheme, ...] = field(default_factory=tuple)
    narrative: str = ""

    @property
    def is_empty(self) -> bool:
        return (
            not self.topic.strip()
            and not self.synonyms
            and not self.queries
            and not self.runs
            and not self.results
        )

    @property
    def result_count(self) -> int:
        return len(self.results)

    @property
    def query_count(self) -> int:
        return len(self.queries)