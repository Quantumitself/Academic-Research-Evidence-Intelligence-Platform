"""Publication normalization.

The normalizer converts provider-neutral ``SearchHit`` objects into the
application's canonical ``CanonicalPublication`` representation. It is
the single place that decides how a hit becomes a publication.

Design decisions
----------------
- The normalizer never invents data. Missing fields are left empty
  rather than filled from unrelated sources.
- The normalizer derives the key from the DOI when present. When the
  DOI is absent, the key is derived from the provider key and the
  provider identifier. A hit without a DOI and without a provider
  identifier cannot be normalized and is skipped with a warning.
- The normalizer does not merge duplicate hits. Deduplication is a
  separate, explicit step. This keeps the normalizer deterministic: the
  same hit produces the same publication on every call.
- The normalizer preserves the provider key and provider identifier so
  that provenance is not lost.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from academic_platform.application.publications.errors import (
    PublicationKeyError,
    PublicationNormalizationError,
)
from academic_platform.application.publications.model import (
    CanonicalPublication,
    PublicationKey,
)
from academic_platform.infrastructure.search_providers.adapter import (
    SearchHit,
)

_logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class NormalizationResult:
    """Outcome of normalizing a batch of hits."""

    publications: tuple[CanonicalPublication, ...]
    skipped: tuple[str, ...] = field(default_factory=tuple)
    input_count: int = 0

    @property
    def publication_count(self) -> int:
        return len(self.publications)

    @property
    def skipped_count(self) -> int:
        return len(self.skipped)


class PublicationNormalizer:
    """Convert provider-neutral hits into canonical publications."""

    def normalize_hit(self, hit: SearchHit) -> CanonicalPublication:
        """Normalize a single hit.

        Raises
        ------
        PublicationKeyError
            If the hit cannot produce a stable key.
        PublicationNormalizationError
            If the hit is not a ``SearchHit``.
        """
        if not isinstance(hit, SearchHit):
            raise PublicationNormalizationError(
                f"Expected a SearchHit, got {type(hit).__name__}"
            )
        key = self._key_for(hit)
        doi = _normalize_doi(hit.doi) if hit.doi else None
        return CanonicalPublication(
            key=str(key),
            doi=doi,
            title=hit.title,
            abstract=hit.abstract,
            authors=tuple(hit.authors),
            year=hit.year,
            venue=hit.venue,
            language=hit.language,
            is_open_access=hit.is_open_access,
            citation_count=hit.citation_count,
            url=hit.url,
            source_providers=(hit.provider_key,),
            provider_identifiers=((hit.provider_key, hit.provider_identifier),),
        )

    def normalize(self, hits: list[SearchHit]) -> NormalizationResult:
        """Normalize a batch of hits, preserving input order.

        Hits that cannot produce a key are skipped and reported in the
        ``skipped`` tuple. The tuple contains a short description of each
        skipped hit, not the hit itself, so that the result does not
        retain references to potentially large payloads.
        """
        publications: list[CanonicalPublication] = []
        skipped: list[str] = []
        for index, hit in enumerate(hits):
            try:
                publications.append(self.normalize_hit(hit))
            except PublicationKeyError as exc:
                _logger.warning(
                    "Skipping hit %d (provider=%s): %s",
                    index,
                    getattr(hit, "provider_key", "?"),
                    exc,
                )
                skipped.append(
                    f"index {index}: provider={getattr(hit, 'provider_key', '?')}"
                )
            except PublicationNormalizationError as exc:
                _logger.warning("Skipping hit %d: %s", index, exc)
                skipped.append(f"index {index}: {exc}")
        return NormalizationResult(
            publications=tuple(publications),
            skipped=tuple(skipped),
            input_count=len(hits),
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _key_for(self, hit: SearchHit) -> PublicationKey:
        if hit.doi:
            normalized = _normalize_doi(hit.doi)
            if normalized:
                return PublicationKey.from_doi(normalized)
        if hit.provider_key and hit.provider_identifier:
            return PublicationKey.from_provider(
                hit.provider_key, hit.provider_identifier
            )
        raise PublicationKeyError(
            "Hit has neither a DOI nor a provider identifier"
        )


def _normalize_doi(doi: str) -> str:
    cleaned = doi.strip()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if cleaned.lower().startswith(prefix):
            cleaned = cleaned[len(prefix):]
    return cleaned.strip().lower()