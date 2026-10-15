"""Specifications for the search session and result repositories."""

from __future__ import annotations

from academic_platform.infrastructure.database.models import (
    SearchResult,
    SearchSession,
)
from academic_platform.infrastructure.repositories.specification import Specification


class SearchSessionByQueryText(Specification[SearchSession]):
    """Matches sessions whose query text contains a fragment."""

    def __init__(self, fragment: str) -> None:
        self._fragment = fragment

    def to_expression(self, entity: type[SearchSession]):
        return entity.query_text.ilike(f"%{self._fragment}%")


class SearchResultBySession(Specification[SearchResult]):
    """Matches results belonging to a session."""

    def __init__(self, session_id: int) -> None:
        self._session_id = session_id

    def to_expression(self, entity: type[SearchResult]):
        return entity.session_id == self._session_id


class SearchResultByProvider(Specification[SearchResult]):
    """Matches results returned by a specific provider."""

    def __init__(self, provider_key: str) -> None:
        self._provider = provider_key

    def to_expression(self, entity: type[SearchResult]):
        return entity.provider_key == self._provider