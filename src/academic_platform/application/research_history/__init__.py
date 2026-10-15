"""Research-history workspace.

This subpackage owns the search-backed investigation of a topic's
historical development:

- ``HistoryQuery`` — a single search query the workspace proposes or
  the user records.
- ``HistorySearchRun`` — a single execution of a query against the
  search orchestration service.
- ``HistoryResult`` — a single retrieved publication with its
  provenance.
- ``HistoryTimelineBucket`` — a year-bucketed aggregation of results.
- ``HistoryTheme`` — a set of related results grouped by a shared
  concept.
- ``ResearchHistoryService`` — the application service.
- ``ResearchHistoryError`` and subclasses — typed errors.

The service never imports Qt. It composes the search orchestration
service and persists the workspace state in the research project's
metadata.
"""

from academic_platform.application.research_history.errors import (
    ResearchHistoryError,
    ResearchHistoryNotFoundError,
    ResearchHistorySearchError,
    ResearchHistoryValidationError,
)
from academic_platform.application.research_history.model import (
    HistoryQuery,
    HistoryResult,
    HistorySearchRun,
    HistorySearchStatus,
    HistoryTheme,
    HistoryTimelineBucket,
    ResearchHistoryDraft,
)
from academic_platform.application.research_history.service import (
    ResearchHistoryService,
)

__all__ = [
    "HistoryQuery",
    "HistoryResult",
    "HistorySearchRun",
    "HistorySearchStatus",
    "HistoryTheme",
    "HistoryTimelineBucket",
    "ResearchHistoryDraft",
    "ResearchHistoryError",
    "ResearchHistoryNotFoundError",
    "ResearchHistorySearchError",
    "ResearchHistoryService",
    "ResearchHistoryValidationError",
]