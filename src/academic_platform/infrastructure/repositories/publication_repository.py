"""Repository for publications."""

from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from academic_platform.infrastructure.database.models import Publication
from academic_platform.infrastructure.repositories.base import Repository
from academic_platform.infrastructure.repositories.errors import RepositoryError


class PublicationRepository(Repository[Publication]):
    """Repository for the ``publication`` table."""

    entity = Publication

    def find_by_key(self, key: str) -> Publication | None:
        """Return the publication with the given key, or ``None``."""
        statement = select(Publication).where(Publication.key == key).limit(1)
        try:
            return self._session.execute(statement).scalars().first()
        except SQLAlchemyError as exc:
            raise RepositoryError(f"find_by_key failed: {exc}") from exc

    def find_by_doi(self, doi: str) -> Publication | None:
        """Return the publication with the given DOI, or ``None``."""
        statement = select(Publication).where(Publication.doi == doi).limit(1)
        try:
            return self._session.execute(statement).scalars().first()
        except SQLAlchemyError as exc:
            raise RepositoryError(f"find_by_doi failed: {exc}") from exc

    def add_source_provider(self, publication: Publication, provider_key: str) -> Publication:
        """Add a provider identifier to a publication's provider list.

        The list is stored as a JSON array of strings. Adding a provider
        that is already present is a no-op.
        """
        providers = self._load_providers(publication)
        if provider_key in providers:
            return publication
        providers.append(provider_key)
        publication.source_providers_json = json.dumps(providers)
        try:
            self._session.flush()
        except SQLAlchemyError as exc:
            raise RepositoryError(f"add_source_provider failed: {exc}") from exc
        return publication

    def list_recent(self, *, limit: int = 25) -> list[Publication]:
        """Return the most recently created publications."""
        statement = (
            select(Publication)
            .order_by(Publication.created_at.desc())
            .limit(limit)
        )
        try:
            return list(self._session.execute(statement).scalars().all())
        except SQLAlchemyError as exc:
            raise RepositoryError(f"list_recent failed: {exc}") from exc

    @staticmethod
    def _load_providers(publication: Publication) -> list[str]:
        raw = publication.source_providers_json or "[]"
        try:
            data = json.loads(raw)
        except ValueError:
            return []
        if not isinstance(data, list):
            return []
        return [str(item) for item in data]