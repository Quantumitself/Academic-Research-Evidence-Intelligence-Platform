"""Immutable value objects describing the outcome of a search.

The orchestration response carries:

- The per-source outcomes, one entry per selected source.
- The aggregated hits and canonical publications.
- The deduplication result.
- The identifiers of any persisted session and result rows.
- A ``partial`` flag that is True when at least one source failed but at
  least one source succeeded.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from academic_platform.application.publications.deduplicator import (
    DeduplicationResult,
)
from academic_platform.application.publications.model import (
    CanonicalPublication,
)
from academic_platform.infrastructure.search_providers.adapter import (
    SearchHit,
)


class SourceOutcomeStatus(str, Enum):
    """Outcome of executing one source within an orchestration request."""

    OK = "ok"
    FAILED = "failed"
    SKIPPED = "skipped"
    DISABLED = "disabled"


@dataclass(frozen=True, slots=True)
class SourceOutcome:
    """Outcome of executing one source."""

    source_key: str
    provider_key: str
    display_name: str
    status: SourceOutcomeStatus
    result_count: int = 0
    duration_ms: int | None = None
    message: str = ""


@dataclass(frozen=True, slots=True)
class SearchOrchestrationResponse:
    """The aggregated outcome of a search."""

    query: str
    scope: str
    outcomes: tuple[SourceOutcome, ...] = field(default_factory=tuple)
    hits: tuple[SearchHit, ...] = field(default_factory=tuple)
    publications: tuple[CanonicalPublication, ...] = field(default_factory=tuple)
    deduplication: DeduplicationResult | None = None
    session_id: int | None = None
    result_ids: tuple[int, ...] = field(default_factory=tuple)
    partial: bool = False

    @property
    def success_count(self) -> int:
        return sum(
            1 for outcome in self.outcomes if outcome.status is SourceOutcomeStatus.OK
        )

    @property
    def failure_count(self) -> int:
        return sum(
            1
            for outcome in self.outcomes
            if outcome.status is SourceOutcomeStatus.FAILED
        )

    @property
    def total_results(self) -> int:
        return sum(outcome.result_count for outcome in self.outcomes)