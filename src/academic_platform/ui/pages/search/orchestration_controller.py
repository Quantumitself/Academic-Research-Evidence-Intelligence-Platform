"""Search controller that delegates to the orchestration service.

The controller implements the ``SearchController`` protocol introduced in
Phase 10 and bridges it to the application-layer ``SearchOrchestrator``.
It is synchronous at the interface boundary: the orchestrator executes
its work on a bounded thread pool, and the controller returns a
``SearchResponse`` once the orchestrator has completed. The presentation
layer is responsible for executing the controller on a worker thread so
that the UI remains responsive; that responsibility is handled by the
``SearchWorker`` in a separate module.
"""

from __future__ import annotations

import logging

from academic_platform.application.search_orchestration.errors import (
    SearchOrchestrationError,
)
from academic_platform.application.search_orchestration.orchestrator import (
    SearchOrchestrator,
)
from academic_platform.application.search_orchestration.request import (
    SearchOrchestrationRequest,
    SourceSelection,
)
from academic_platform.application.search_orchestration.response import (
    SearchOrchestrationResponse,
    SourceOutcome,
    SourceOutcomeStatus,
)
from academic_platform.application.search_sources.service import (
    SearchSourceService,
)
from academic_platform.infrastructure.search_providers.adapter import (
    SearchHit,
    SearchRequest,
)
from academic_platform.ui.pages.search.result_list import (
    SearchResultEntry,
    SearchResultOrigin,
)
from academic_platform.ui.pages.search.search_controller import (
    SearchResponse,
    SourceReport,
    SourceStatus,
)

_logger = logging.getLogger(__name__)


class OrchestrationSearchController:
    """Search controller backed by the orchestration service.

    The controller is constructed with a factory that yields an
    orchestrator and a source service bound to a live session. The
    factory is invoked per search call so that every search runs in its
    own transaction boundary. This is the same pattern used by the
    search source service itself: the application layer receives a fresh
    repository manager per unit of work.
    """

    def __init__(
        self,
        orchestrator_factory,
        source_service_factory,
    ) -> None:
        self._orchestrator_factory = orchestrator_factory
        self._source_service_factory = source_service_factory

    # ------------------------------------------------------------------
    # SearchController interface
    # ------------------------------------------------------------------
    def search_local(self, query: str) -> SearchResponse:
        """Execute a local search.

        The local surface is not yet backed by the library's full-text
        index. The controller reports honestly that local search is not
        yet available and returns no entries.
        """
        return SearchResponse(
            query=query,
            entries=(),
            source_reports=(
                SourceReport(
                    source_label="Local library",
                    status=SourceStatus.SKIPPED,
                    error_message=(
                        "Local full-text search is not yet available. "
                        "It will be enabled once the library is populated."
                    ),
                ),
            ),
            partial=False,
            message=(
                "Local search will be available once the library is populated."
            ),
        )

    def search_remote(self, query: str) -> SearchResponse:
        """Execute a remote search through the orchestration service."""
        try:
            orchestrator = self._orchestrator_factory()
        except Exception as exc:  # noqa: BLE001 - boundary
            _logger.exception("Unable to construct the search orchestrator")
            return SearchResponse(
                query=query,
                entries=(),
                source_reports=(
                    SourceReport(
                        source_label="Academic sources",
                        status=SourceStatus.FAILED,
                        error_message=f"Orchestrator unavailable: {exc}",
                    ),
                ),
                partial=False,
                message="Remote search is not available. Check the log for details.",
            )

        try:
            orchestration_request = SearchOrchestrationRequest(
                search_request=SearchRequest(query=query, limit=50),
                selection=SourceSelection(all_enabled=True),
                session_scope="remote",
                record_session=True,
            )
            result = orchestrator.execute(orchestration_request)
        except SearchOrchestrationError as exc:
            _logger.warning("Search orchestration failed: %s", exc)
            return SearchResponse(
                query=query,
                entries=(),
                source_reports=(
                    SourceReport(
                        source_label="Academic sources",
                        status=SourceStatus.SKIPPED,
                        error_message=str(exc),
                    ),
                ),
                partial=False,
                message=str(exc),
            )
        except Exception as exc:  # noqa: BLE001 - boundary
            _logger.exception("Unexpected error during search orchestration")
            return SearchResponse(
                query=query,
                entries=(),
                source_reports=(
                    SourceReport(
                        source_label="Academic sources",
                        status=SourceStatus.FAILED,
                        error_message=f"Unexpected error: {exc}",
                    ),
                ),
                partial=False,
                message="Remote search failed unexpectedly.",
            )

        return self._to_search_response(query, result)

    # ------------------------------------------------------------------
    # Conversion helpers
    # ------------------------------------------------------------------
    def _to_search_response(
        self,
        query: str,
        result: SearchOrchestrationResponse,
    ) -> SearchResponse:
        entries = tuple(
            self._to_entry(publication)
            for publication in result.publications
        )
        reports = tuple(self._to_report(outcome) for outcome in result.outcomes)
        return SearchResponse(
            query=query,
            entries=entries,
            source_reports=reports,
            partial=result.partial,
            message=(
                "Some sources did not respond. Results may be incomplete."
                if result.partial
                else ""
            ),
        )

    def _to_entry(self, publication) -> SearchResultEntry:
        subtitle_parts: list[str] = []
        if publication.authors:
            subtitle_parts.append(", ".join(publication.authors))
        if publication.year is not None:
            subtitle_parts.append(str(publication.year))
        subtitle = " · ".join(subtitle_parts)

        metadata: list[tuple[str, str]] = []
        if publication.venue:
            metadata.append(("Venue", publication.venue))
        if publication.doi:
            metadata.append(("DOI", publication.doi))
        if publication.is_open_access:
            metadata.append(("Access", "Open"))
        if publication.citation_count is not None:
            metadata.append(("Citations", str(publication.citation_count)))
        for provider in publication.source_providers:
            metadata.append(("Source", provider))

        return SearchResultEntry(
            identifier=publication.key,
            title=publication.title or "(untitled)",
            subtitle=subtitle,
            snippet=publication.abstract or "",
            origin=SearchResultOrigin.REMOTE_SOURCE,
            source_label=(
                publication.source_providers[0]
                if publication.source_providers
                else ""
            ),
            score=None,
            metadata=tuple(metadata),
        )

    def _to_report(self, outcome: SourceOutcome) -> SourceReport:
        status_map = {
            SourceOutcomeStatus.OK: SourceStatus.OK,
            SourceOutcomeStatus.FAILED: SourceStatus.FAILED,
            SourceOutcomeStatus.SKIPPED: SourceStatus.SKIPPED,
            SourceOutcomeStatus.DISABLED: SourceStatus.DISABLED,
        }
        return SourceReport(
            source_label=outcome.display_name or outcome.source_key,
            status=status_map.get(outcome.status, SourceStatus.SKIPPED),
            result_count=outcome.result_count,
            error_message=outcome.message,
        )