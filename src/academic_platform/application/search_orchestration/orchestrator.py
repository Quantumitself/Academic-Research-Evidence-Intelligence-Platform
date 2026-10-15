"""Search orchestration service.

The orchestrator executes a provider-neutral search request across the
selected sources, aggregates the results, deduplicates the merged hits,
and — when requested — persists the outcome through the repository
layer.

Design decisions
----------------
- Adapters are executed on a bounded thread pool. The pool size is
  driven by the request's ``max_concurrency``. Each adapter runs on its
  own thread; the orchestrator does not share mutable state across
  threads beyond the future collection.
- Failures are isolated per source. A failure in one adapter never
  aborts the whole search; the outcome records the failure and the
  remaining sources proceed.
- The orchestrator is the only place that composes the source registry,
  the provider registry, the publication service, and the repository
  layer. Callers supply a ``RepositoryManager``, a
  ``SearchSourceService``, and a ``ProviderRegistry``; the orchestrator
  obtains everything else from those.
- The orchestrator never commits. It runs inside a unit of work
  supplied by the caller.
- When persistence is requested, the orchestrator records one
  ``SearchSession`` row, one ``SearchResult`` row per deduplicated
  publication, and one ``Publication`` row per publication. Session and
  result rows are recorded only after the search has completed, so a
  failure during search never leaves a partial session in the database.
"""

from __future__ import annotations

import logging
import time
from concurrent.futures import Future, ThreadPoolExecutor, as_completed

from academic_platform.application.publications.model import (
    CanonicalPublication,
)
from academic_platform.application.publications.service import (
    PublicationService,
)
from academic_platform.application.search_orchestration.errors import (
    SearchOrchestrationConfigurationError,
    SearchOrchestrationError,
)
from academic_platform.application.search_orchestration.request import (
    SearchOrchestrationRequest,
)
from academic_platform.application.search_orchestration.response import (
    SearchOrchestrationResponse,
    SourceOutcome,
    SourceOutcomeStatus,
)
from academic_platform.application.search_sources.errors import (
    SourceError,
    SourceNotFoundError,
)
from academic_platform.application.search_sources.service import (
    SearchSourceService,
)
from academic_platform.application.search_sources.source_config import (
    SourceRecord,
)
from academic_platform.infrastructure.database.models import (
    SavedSearchQuery,
    SearchSession,
)
from academic_platform.infrastructure.repositories.errors import (
    RepositoryError,
)
from academic_platform.infrastructure.repositories.manager import (
    RepositoryManager,
)
from academic_platform.infrastructure.search_providers.adapter import (
    SearchHit,
    SearchRequest,
    SearchResponse,
    SourceStatus,
    SourceStatusReport,
)
from academic_platform.infrastructure.search_providers.errors import (
    ProviderError,
)
from academic_platform.infrastructure.search_providers.registry import (
    ProviderRegistry,
)
from academic_platform.application.saved_searches.model import SavedSearch
from academic_platform.application.search_orchestration.request import (
    SourceSelection as _SourceSelection,
)
from academic_platform.infrastructure.search_providers.adapter import (
    SearchRequest as _SearchRequest,
)


_logger = logging.getLogger(__name__)


class SearchOrchestrator:
    """Execute searches across multiple sources and aggregate the results."""

    def __init__(
        self,
        repositories: RepositoryManager,
        source_service: SearchSourceService,
        provider_registry: ProviderRegistry,
    ) -> None:
        self._repositories = repositories
        self._source_service = source_service
        self._provider_registry = provider_registry
        self._publications = PublicationService(repositories)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def execute(
        self,
        request: SearchOrchestrationRequest,
        *,
        saved_query_id: int | None = None,
    ) -> SearchOrchestrationResponse:
        """Execute a search request across the selected sources.

        Parameters
        ----------
        request:
            The orchestration request.
        saved_query_id:
            Optional identifier of the saved search query this execution
            corresponds to. Recorded on the ``SearchSession`` row when
            persistence is requested.
        """
        sources = self._resolve_sources(request)
        if not sources:
            raise SearchOrchestrationConfigurationError(
                "No enabled sources matched the selection"
            )

        started = time.monotonic()
        hits_by_source, outcomes = self._execute_all(sources, request)
        hits = _merge_hits_in_order(sources, hits_by_source)

        if not request.record_session:
            deduplication = _empty_deduplication(hits)
            return SearchOrchestrationResponse(
                query=request.search_request.query,
                scope=request.session_scope,
                outcomes=tuple(outcomes),
                hits=tuple(hits),
                publications=deduplication.publications,
                deduplication=deduplication,
                session_id=None,
                result_ids=(),
                partial=_is_partial(outcomes),
            )

        session_id, result_ids, publications = self._record_outcome(
            request=request,
            sources=sources,
            hits=hits,
            outcomes=outcomes,
            saved_query_id=saved_query_id,
        )

        deduplication = _empty_deduplication(hits)
        deduplication = type(deduplication)(
            publications=publications,
            merges=deduplication.merges,
            input_count=deduplication.input_count,
        )

        _logger.info(
            "Search completed: %d sources, %d hits, %d unique publications, %.2fs",
            len(sources),
            len(hits),
            len(publications),
            time.monotonic() - started,
        )

        return SearchOrchestrationResponse(
            query=request.search_request.query,
            scope=request.session_scope,
            outcomes=tuple(outcomes),
            hits=tuple(hits),
            publications=publications,
            deduplication=deduplication,
            session_id=session_id,
            result_ids=tuple(result_ids),
            partial=_is_partial(outcomes),
        )

    # ------------------------------------------------------------------
    # Source resolution
    # ------------------------------------------------------------------
    def _resolve_sources(
        self,
        request: SearchOrchestrationRequest,
    ) -> list[SourceRecord]:
        if request.selection.all_enabled:
            return list(self._source_service.list_enabled())
        resolved: list[SourceRecord] = []
        for key in request.selection.source_keys:
            try:
                record = self._source_service.get_by_key(key)
            except SourceNotFoundError:
                _logger.warning("Source %s was selected but is not configured", key)
                continue
            if not record.config.enabled:
                _logger.info("Source %s was selected but is disabled", key)
                continue
            resolved.append(record)
        return resolved

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------
    def _execute_all(
        self,
        sources: list[SourceRecord],
        request: SearchOrchestrationRequest,
    ) -> tuple[dict[str, list[SearchHit]], list[SourceOutcome]]:
        hits_by_source: dict[str, list[SearchHit]] = {}
        outcomes: list[SourceOutcome] = []

        with ThreadPoolExecutor(max_workers=request.max_concurrency) as executor:
            futures: dict[Future, SourceRecord] = {}
            for source in sources:
                future = executor.submit(self._execute_source, source, request)
                futures[future] = source

            for future in as_completed(futures):
                source = futures[future]
                outcome, hits = self._collect_future(source, future)
                outcomes.append(outcome)
                hits_by_source[source.key] = hits

        outcomes.sort(key=lambda o: o.display_name.lower())
        return hits_by_source, outcomes

    def _execute_source(
        self,
        source: SourceRecord,
        request: SearchOrchestrationRequest,
    ) -> tuple[SourceOutcome, list[SearchHit]]:
        started = time.monotonic()
        try:
            adapter = self._source_service.resolver.resolve(source.config)
        except SourceError as exc:
            return (
                SourceOutcome(
                    source_key=source.key,
                    provider_key=source.config.provider_key,
                    display_name=source.config.display_name,
                    status=SourceOutcomeStatus.FAILED,
                    message=f"Unable to resolve provider: {exc}",
                    duration_ms=0,
                ),
                [],
            )

        provider_request = _bind_source_to_request(request.search_request, source)
        try:
            response: SearchResponse = adapter.search(provider_request)
        except ProviderError as exc:
            return (
                SourceOutcome(
                    source_key=source.key,
                    provider_key=source.config.provider_key,
                    display_name=source.config.display_name,
                    status=SourceOutcomeStatus.FAILED,
                    message=str(exc),
                    duration_ms=int((time.monotonic() - started) * 1000),
                ),
                [],
            )
        except Exception as exc:  # noqa: BLE001 - defensive boundary
            _logger.exception(
                "Adapter %s raised an unexpected exception", source.key
            )
            return (
                SourceOutcome(
                    source_key=source.key,
                    provider_key=source.config.provider_key,
                    display_name=source.config.display_name,
                    status=SourceOutcomeStatus.FAILED,
                    message=f"Unexpected error: {exc}",
                    duration_ms=int((time.monotonic() - started) * 1000),
                ),
                [],
            )

        status_report = response.status or SourceStatusReport(
            provider_key=source.config.provider_key,
            status=SourceStatus.OK,
        )
        hits = list(response.hits)
        outcome_status = _translate_status(status_report.status)
        return (
            SourceOutcome(
                source_key=source.key,
                provider_key=source.config.provider_key,
                display_name=source.config.display_name,
                status=outcome_status,
                result_count=len(hits),
                duration_ms=status_report.duration_ms
                if status_report.duration_ms is not None
                else int((time.monotonic() - started) * 1000),
                message=status_report.message,
            ),
            hits,
        )

    def _collect_future(
        self,
        source: SourceRecord,
        future: Future,
    ) -> tuple[SourceOutcome, list[SearchHit]]:
        try:
            return future.result()
        except Exception as exc:  # noqa: BLE001 - defensive boundary
            _logger.exception(
                "Source %s raised during execution", source.key
            )
            return (
                SourceOutcome(
                    source_key=source.key,
                    provider_key=source.config.provider_key,
                    display_name=source.config.display_name,
                    status=SourceOutcomeStatus.FAILED,
                    message=f"Unexpected error: {exc}",
                    duration_ms=None,
                ),
                [],
            )

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------
    def _record_outcome(
        self,
        *,
        request: SearchOrchestrationRequest,
        sources: list[SourceRecord],
        hits: list[SearchHit],
        outcomes: list[SourceOutcome],
        saved_query_id: int | None,
    ) -> tuple[int, list[int], tuple[CanonicalPublication, ...]]:
        import datetime as dt
        import json

        session_repo = self._repositories.get("search_session")
        result_repo = self._repositories.get("search_result")

        partial = _is_partial(outcomes)
        source_reports = [
            {
                "source_key": outcome.source_key,
                "provider_key": outcome.provider_key,
                "display_name": outcome.display_name,
                "status": outcome.status.value,
                "result_count": outcome.result_count,
                "duration_ms": outcome.duration_ms,
                "message": outcome.message,
            }
            for outcome in outcomes
        ]

        session_row = SearchSession(
            query_id=saved_query_id,
            query_text=request.search_request.query,
            scope=request.session_scope,
            executed_at=dt.datetime.now(dt.timezone.utc).replace(tzinfo=None),
            source_reports_json=json.dumps(source_reports),
            partial=1 if partial else 0,
            result_count=len(hits),
            message="",
        )
        try:
            session_repo.add(session_row)
        except RepositoryError as exc:
            raise SearchOrchestrationError(
                f"Unable to record search session: {exc}"
            ) from exc

        deduplication = self._deduplicate_hits(hits)
        try:
            publications = self._publications.persist(deduplication.publications)
        except RepositoryError as exc:
            raise SearchOrchestrationError(
                f"Unable to persist publications: {exc}"
            ) from exc

        publication_by_key = {
            publication.key: row for publication, row in zip(
                deduplication.publications, publications
            )
        }

        result_ids: list[int] = []
        for rank, publication in enumerate(deduplication.publications):
            row = publication_by_key.get(publication.key)
            if row is None:
                continue
            try:
                result = result_repo.add_result(
                    session_id=session_row.id,
                    publication_id=row.id,
                    provider_key=publication.source_providers[0]
                    if publication.source_providers
                    else "unknown",
                    rank=rank,
                    score=None,
                    source_url=publication.url,
                )
            except RepositoryError as exc:
                _logger.warning(
                    "Unable to record search result for %s: %s",
                    publication.key,
                    exc,
                )
                continue
            result_ids.append(result.id)

        return session_row.id, result_ids, deduplication.publications

    def _deduplicate_hits(self, hits: list[SearchHit]):
        from academic_platform.application.publications.deduplicator import (
            PublicationDeduplicator,
        )
        from academic_platform.application.publications.normalizer import (
            PublicationNormalizer,
        )

        normalizer = PublicationNormalizer()
        normalization = normalizer.normalize(hits)
        deduplicator = PublicationDeduplicator()
        return deduplicator.deduplicate(list(normalization.publications))


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
def _bind_source_to_request(
    request: SearchRequest,
    source: SourceRecord,
) -> SearchRequest:
    """Return a copy of the request bounded by the source's configured limit."""
    limit = min(request.limit, source.config.result_limit)
    return SearchRequest(
        query=request.query,
        limit=limit,
        offset=request.offset,
        cursor=request.cursor,
        year_from=request.year_from,
        year_to=request.year_to,
        author=request.author,
        venue=request.venue,
        doi=request.doi,
        open_access_only=request.open_access_only,
        language=request.language,
        sort=request.sort,
        extra=dict(request.extra),
    )


def _translate_status(status: SourceStatus) -> SourceOutcomeStatus:
    if status is SourceStatus.OK:
        return SourceOutcomeStatus.OK
    if status is SourceStatus.FAILED:
        return SourceOutcomeStatus.FAILED
    if status is SourceStatus.DISABLED:
        return SourceOutcomeStatus.DISABLED
    return SourceOutcomeStatus.SKIPPED


def _merge_hits_in_order(
    sources: list[SourceRecord],
    hits_by_source: dict[str, list[SearchHit]],
) -> list[SearchHit]:
    ordered: list[SearchHit] = []
    for source in sources:
        ordered.extend(hits_by_source.get(source.key, []))
    return ordered


def _is_partial(outcomes: list[SourceOutcome]) -> bool:
    has_ok = any(o.status is SourceOutcomeStatus.OK for o in outcomes)
    has_failure = any(o.status is SourceOutcomeStatus.FAILED for o in outcomes)
    return has_ok and has_failure


def _empty_deduplication(hits: list[SearchHit]):
    from academic_platform.application.publications.deduplicator import (
        DeduplicationResult,
    )

    return DeduplicationResult(
        publications=(),
        merges=(),
        input_count=len(hits),
    )

def build_request_from_saved_search(
    saved: SavedSearch,
    *,
    limit: int = 50,
    session_scope: str | None = None,
) -> SearchOrchestrationRequest:
    """Construct an orchestration request from a saved search.

    The saved search's ``source_keys`` are honoured when present;
    otherwise every enabled source is targeted. The saved search's
    ``query_text`` becomes the free-text query, and its filter payload is
    used to populate the provider-neutral ``SearchRequest`` fields that
    the saved search supports.
    """
    if not saved.query_text.strip():
        raise ValueError("saved search has no query text")
    filters = saved.filters or {}
    search_request = _SearchRequest(
        query=saved.query_text,
        limit=limit,
        offset=int(filters.get("offset", 0) or 0),
        year_from=_optional_int(filters.get("year_from")),
        year_to=_optional_int(filters.get("year_to")),
        author=_optional_str(filters.get("author")),
        venue=_optional_str(filters.get("venue")),
        doi=_optional_str(filters.get("doi")),
        open_access_only=bool(filters.get("open_access_only", False)),
        language=_optional_str(filters.get("language")),
        sort=_sort_from_filters(filters),
    )
    if saved.source_keys:
        selection = _SourceSelection(
            all_enabled=False,
            source_keys=tuple(saved.source_keys),
        )
    else:
        selection = _SourceSelection(all_enabled=True)
    scope = session_scope or saved.scope or "remote"
    if scope not in {"local", "remote", "all"}:
        scope = "remote"
    return SearchOrchestrationRequest(
        search_request=search_request,
        selection=selection,
        session_scope=scope,
    )


def _optional_int(value) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _optional_str(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _sort_from_filters(filters: dict) -> str:
    value = filters.get("sort")
    if isinstance(value, str) and value in {"relevance", "date_desc", "date_asc"}:
        return value
    return "relevance"