"""Repositories for saved search queries, search sessions, and search results."""

from __future__ import annotations

import datetime as dt

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from academic_platform.infrastructure.database.models import (
    SavedSearchQuery,
    SearchResult,
    SearchSession,
)
from academic_platform.infrastructure.repositories.base import Repository
from academic_platform.infrastructure.repositories.errors import RepositoryError


class SavedSearchQueryRepository(Repository[SavedSearchQuery]):
    """Repository for the ``saved_search_query`` table."""

    entity = SavedSearchQuery

    def find_by_key(self, key: str) -> SavedSearchQuery | None:
        """Return the saved query with the given key, or ``None``."""
        statement = (
            select(SavedSearchQuery)
            .where(SavedSearchQuery.key == key)
            .limit(1)
        )
        try:
            return self._session.execute(statement).scalars().first()
        except SQLAlchemyError as exc:
            raise RepositoryError(f"find_by_key failed: {exc}") from exc

    def list_all_ordered(self) -> list[SavedSearchQuery]:
        """Return every saved query ordered by name."""
        statement = select(SavedSearchQuery).order_by(SavedSearchQuery.name)
        try:
            return list(self._session.execute(statement).scalars().all())
        except SQLAlchemyError as exc:
            raise RepositoryError(f"list_all_ordered failed: {exc}") from exc

    def mark_executed(self, query_id: int) -> SavedSearchQuery:
        """Record that a saved query was just executed."""
        query = self.get_or_raise(query_id)
        query.last_executed_at = dt.datetime.now(dt.timezone.utc).isoformat()
        try:
            self._session.flush()
        except SQLAlchemyError as exc:
            raise RepositoryError(f"mark_executed failed: {exc}") from exc
        return query


class SearchSessionRepository(Repository[SearchSession]):
    """Repository for the ``search_session`` table."""

    entity = SearchSession

    def list_recent(self, *, limit: int = 25) -> list[SearchSession]:
        """Return the most recent sessions ordered by execution time."""
        statement = (
            select(SearchSession)
            .order_by(SearchSession.executed_at.desc(), SearchSession.id.desc())
            .limit(limit)
        )
        try:
            return list(self._session.execute(statement).scalars().all())
        except SQLAlchemyError as exc:
            raise RepositoryError(f"list_recent failed: {exc}") from exc

    def list_for_saved_query(self, query_id: int, *, limit: int = 50) -> list[SearchSession]:
        """Return sessions associated with a saved query."""
        statement = (
            select(SearchSession)
            .where(SearchSession.query_id == query_id)
            .order_by(SearchSession.executed_at.desc(), SearchSession.id.desc())
            .limit(limit)
        )
        try:
            return list(self._session.execute(statement).scalars().all())
        except SQLAlchemyError as exc:
            raise RepositoryError(f"list_for_saved_query failed: {exc}") from exc

    def record_outcome(
        self,
        session_id: int,
        *,
        result_count: int,
        partial: bool,
    ) -> SearchSession:
        """Update a session with the outcome of its execution."""
        session_row = self.get_or_raise(session_id)
        session_row.result_count = result_count
        session_row.partial = 1 if partial else 0
        try:
            self._session.flush()
        except SQLAlchemyError as exc:
            raise RepositoryError(f"record_outcome failed: {exc}") from exc
        return session_row


class SearchResultRepository(Repository[SearchResult]):
    """Repository for the ``search_result`` table."""

    entity = SearchResult

    def list_for_session(self, session_id: int) -> list[SearchResult]:
        """Return the results of a session ordered by rank."""
        statement = (
            select(SearchResult)
            .where(SearchResult.session_id == session_id)
            .order_by(SearchResult.rank, SearchResult.id)
        )
        try:
            return list(self._session.execute(statement).scalars().all())
        except SQLAlchemyError as exc:
            raise RepositoryError(f"list_for_session failed: {exc}") from exc

    def add_result(
        self,
        session_id: int,
        publication_id: int,
        provider_key: str,
        *,
        rank: int = 0,
        score: float | None = None,
        source_url: str | None = None,
    ) -> SearchResult:
        """Add a single result to a session."""
        result = SearchResult(
            session_id=session_id,
            publication_id=publication_id,
            provider_key=provider_key,
            rank=rank,
            score=score,
            source_url=source_url,
        )
        return self.add(result)

    def list_publication_ids_for_session(self, session_id: int) -> list[int]:
        """Return the publication identifiers referenced by a session."""
        statement = select(SearchResult.publication_id).where(
            SearchResult.session_id == session_id
        )
        try:
            return [int(row) for row in self._session.execute(statement).scalars().all()]
        except SQLAlchemyError as exc:
            raise RepositoryError(
                f"list_publication_ids_for_session failed: {exc}"
            ) from exc