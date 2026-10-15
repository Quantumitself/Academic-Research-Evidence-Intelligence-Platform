"""Repository for search sources."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from academic_platform.infrastructure.database.models import SearchSource
from academic_platform.infrastructure.repositories.base import Repository
from academic_platform.infrastructure.repositories.errors import RepositoryError


class SearchSourceRepository(Repository[SearchSource]):
    """Repository for the ``search_source`` table."""

    entity = SearchSource

    def find_by_key(self, key: str) -> SearchSource | None:
        """Return the source with the given key, or ``None``."""
        statement = select(SearchSource).where(SearchSource.key == key).limit(1)
        try:
            return self._session.execute(statement).scalars().first()
        except SQLAlchemyError as exc:
            raise RepositoryError(f"find_by_key failed: {exc}") from exc

    def find_by_provider_key(self, provider_key: str) -> SearchSource | None:
        """Return the source with the given provider identifier, or ``None``."""
        statement = (
            select(SearchSource)
            .where(SearchSource.provider_key == provider_key)
            .limit(1)
        )
        try:
            return self._session.execute(statement).scalars().first()
        except SQLAlchemyError as exc:
            raise RepositoryError(f"find_by_provider_key failed: {exc}") from exc

    def list_enabled(self) -> list[SearchSource]:
        """Return every enabled source ordered by display name."""
        statement = (
            select(SearchSource)
            .where(SearchSource.enabled == 1)
            .order_by(SearchSource.display_name)
        )
        try:
            return list(self._session.execute(statement).scalars().all())
        except SQLAlchemyError as exc:
            raise RepositoryError(f"list_enabled failed: {exc}") from exc

    def list_all_ordered(self) -> list[SearchSource]:
        """Return every source ordered by display name."""
        statement = select(SearchSource).order_by(SearchSource.display_name)
        try:
            return list(self._session.execute(statement).scalars().all())
        except SQLAlchemyError as exc:
            raise RepositoryError(f"list_all_ordered failed: {exc}") from exc

    def set_enabled(self, source_id: int, enabled: bool) -> SearchSource:
        """Enable or disable a source and return the refreshed row."""
        source = self.get_or_raise(source_id)
        source.enabled = 1 if enabled else 0
        try:
            self._session.flush()
        except SQLAlchemyError as exc:
            raise RepositoryError(f"set_enabled failed: {exc}") from exc
        return source

    def record_test_result(
        self,
        source_id: int,
        *,
        tested_at: str | None,
        error: str | None,
    ) -> SearchSource:
        """Record the outcome of a connectivity test."""
        source = self.get_or_raise(source_id)
        source.last_tested_at = tested_at
        source.last_error = error
        try:
            self._session.flush()
        except SQLAlchemyError as exc:
            raise RepositoryError(f"record_test_result failed: {exc}") from exc
        return source