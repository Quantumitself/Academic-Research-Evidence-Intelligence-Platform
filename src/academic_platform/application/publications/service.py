"""Application service that persists normalized publications.

The service reads search hits, normalizes them, deduplicates the result,
and persists the canonical publications through the repository layer.
It is the single entry point the orchestration layer and the
presentation layer use to convert search results into stored publications.

Design decisions
----------------
- The service is idempotent with respect to DOI and key. Persisting the
  same publication twice updates the existing row rather than creating a
  second one.
- The service adds each publication's source provider to the stored
  row's provider list, so that the provenance of a publication reflects
  every provider that has returned it.
- The service does not perform deduplication across separate calls.
  Deduplication is applied within a single call; callers that need
  cross-session deduplication read the existing publications first.
- The service never commits. It runs inside a unit of work supplied by
  the caller.
"""

from __future__ import annotations

import json
import logging

from academic_platform.application.publications.deduplicator import (
    DeduplicationResult,
    PublicationDeduplicator,
)
from academic_platform.application.publications.errors import (
    PublicationPersistenceError,
)
from academic_platform.application.publications.model import (
    CanonicalPublication,
)
from academic_platform.application.publications.normalizer import (
    NormalizationResult,
    PublicationNormalizer,
)
from academic_platform.infrastructure.database.models import Publication
from academic_platform.infrastructure.repositories.errors import (
    RepositoryError,
)
from academic_platform.infrastructure.repositories.manager import (
    RepositoryManager,
)
from academic_platform.infrastructure.search_providers.adapter import (
    SearchHit,
)

_logger = logging.getLogger(__name__)


class PublicationService:
    """Normalize, deduplicate, and persist search hits."""

    def __init__(self, repositories: RepositoryManager) -> None:
        self._repositories = repositories
        self._normalizer = PublicationNormalizer()
        self._deduplicator = PublicationDeduplicator()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def normalize_and_store(
        self,
        hits: list[SearchHit],
    ) -> tuple[NormalizationResult, DeduplicationResult, list[Publication]]:
        """Normalize hits, deduplicate the result, and persist it.

        Returns a tuple ``(normalization, deduplication, stored)``. The
        ``stored`` list contains the persisted ORM rows in the same order
        as the deduplicated publications.
        """
        normalization = self._normalizer.normalize(hits)
        deduplication = self._deduplicator.deduplicate(
            list(normalization.publications)
        )
        stored = self.persist(deduplication.publications)
        return normalization, deduplication, stored

    def persist(
        self,
        publications: tuple[CanonicalPublication, ...],
    ) -> list[Publication]:
        """Persist canonical publications, updating existing rows by DOI or key."""
        repo = self._repositories.get("publication")
        stored: list[Publication] = []
        for publication in publications:
            try:
                row = self._upsert(publication, repo)
            except RepositoryError as exc:
                raise PublicationPersistenceError(
                    f"Unable to persist publication {publication.key!r}: {exc}"
                ) from exc
            stored.append(row)
        return stored

    def find_existing_key(self, publication: CanonicalPublication) -> str | None:
        """Return the key of an existing publication that matches, or None.

        Matching is by DOI when present, otherwise by key. The method
        does not create or update anything.
        """
        repo = self._repositories.get("publication")
        if publication.doi:
            existing = repo.find_by_doi(publication.doi)
            if existing is not None:
                return existing.key
        existing = repo.find_by_key(publication.key)
        return existing.key if existing is not None else None

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _upsert(self, publication: CanonicalPublication, repo) -> Publication:
        existing = self._find_existing(publication, repo)
        if existing is None:
            row = Publication(
                key=publication.key,
                doi=publication.doi,
                title=publication.title,
                authors_json=json.dumps(list(publication.authors)),
                year=publication.year,
                venue=publication.venue,
                abstract=publication.abstract,
                language=publication.language,
                is_open_access=1 if publication.is_open_access else 0,
                citation_count=publication.citation_count,
                source_providers_json=json.dumps(list(publication.source_providers)),
                url=publication.url,
            )
            return repo.add(row)

        self._apply_merge(existing, publication)
        repo.session.flush()
        return existing

    def _find_existing(
        self,
        publication: CanonicalPublication,
        repo,
    ) -> Publication | None:
        if publication.doi:
            existing = repo.find_by_doi(publication.doi)
            if existing is not None:
                return existing
        return repo.find_by_key(publication.key)

    def _apply_merge(
        self,
        row: Publication,
        publication: CanonicalPublication,
    ) -> None:
        # Preserve any fields the row already carries. Fill only the
        # fields that are currently empty. This makes the operation
        # idempotent and preserves user corrections made through the UI.
        if not row.title and publication.title:
            row.title = publication.title
        if not row.abstract and publication.abstract:
            row.abstract = publication.abstract
        if row.year is None and publication.year is not None:
            row.year = publication.year
        if not row.venue and publication.venue:
            row.venue = publication.venue
        if row.language is None and publication.language is not None:
            row.language = publication.language
        if not row.url and publication.url:
            row.url = publication.url
        if (
            row.citation_count is None
            and publication.citation_count is not None
        ):
            row.citation_count = publication.citation_count
        if publication.is_open_access and not row.is_open_access:
            row.is_open_access = 1

        # Merge source provider lists.
        current_providers = _load_json_list(row.source_providers_json)
        for provider in publication.source_providers:
            if provider not in current_providers:
                current_providers.append(provider)
        row.source_providers_json = json.dumps(sorted(current_providers))


def _load_json_list(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except ValueError:
        return []
    if not isinstance(data, list):
        return []
    return [str(item) for item in data]