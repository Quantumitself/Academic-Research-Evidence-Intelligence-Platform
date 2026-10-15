"""Search controller.

The controller mediates between the search page and its data sources. It
is defined by a protocol so that the page does not depend on the concrete
implementations of local and remote search. The application provides a
controller when the search subsystem is available; until then, the page
uses a ``NullSearchController`` that returns empty results and honest
status messages.

Design decisions
----------------
- Controllers are synchronous at the interface boundary. Long-running
  work is the controller's responsibility; the controller may block on a
  worker thread but must not block the UI thread. The protocol exposes
  only the result of a search, not the mechanics.
- Controllers return a ``SearchResponse`` value that carries the entries,
  the status per source, and a total count. The page renders the response
  verbatim and never interprets the underlying data.
- Controllers must not mutate their inputs. They may be called repeatedly
  with the same query and must return equivalent results when the
  underlying data has not changed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol

from academic_platform.ui.pages.search.result_list import SearchResultEntry


class SourceStatus(str, Enum):
    """Status of a source after a search."""

    OK = "ok"
    FAILED = "failed"
    SKIPPED = "skipped"
    DISABLED = "disabled"


@dataclass(frozen=True, slots=True)
class SourceReport:
    """Per-source status report returned by a controller."""

    source_label: str
    status: SourceStatus
    result_count: int = 0
    error_message: str = ""


@dataclass(frozen=True, slots=True)
class SearchResponse:
    """Result of a search request."""

    query: str
    entries: tuple[SearchResultEntry, ...] = field(default_factory=tuple)
    source_reports: tuple[SourceReport, ...] = field(default_factory=tuple)
    partial: bool = False
    message: str = ""


class SearchController(Protocol):
    """Protocol implemented by search controllers."""

    def search_local(self, query: str) -> SearchResponse:
        """Execute a local search and return its response."""

    def search_remote(self, query: str) -> SearchResponse:
        """Execute a remote search and return its response."""


class NullSearchController:
    """Controller that returns empty responses with honest status.

    Used before the local and remote search subsystems are available. The
    controller reports that no sources were queried, which the page renders
    as an empty state with an explanatory message.
    """

    def search_local(self, query: str) -> SearchResponse:
        return SearchResponse(
            query=query,
            entries=(),
            source_reports=(
                SourceReport(
                    source_label="Local library",
                    status=SourceStatus.SKIPPED,
                    error_message="Local search is not yet available.",
                ),
            ),
            partial=False,
            message="Local search will be available once the library is populated.",
        )

    def search_remote(self, query: str) -> SearchResponse:
        return SearchResponse(
            query=query,
            entries=(),
            source_reports=(
                SourceReport(
                    source_label="Academic sources",
                    status=SourceStatus.SKIPPED,
                    error_message="Remote search is not yet available.",
                ),
            ),
            partial=False,
            message=(
                "Remote search will be available once at least one academic "
                "source is enabled."
            ),
        )