"""Canonical publication representation.

A ``CanonicalPublication`` is the application's normalized view of a
scholarly work. It is constructed from one or more provider-neutral
search hits and is the unit the publication service persists.

Design decisions
----------------
- The canonical publication is immutable. Merging two publications
  produces a new instance; the originals are not modified.
- The DOI is stored in a normalized form (lowercase, without the
  ``https://doi.org/`` prefix) when present.
- The key is a stable string derived from the DOI or, when no DOI is
  available, from the earliest provider identifier. The key is the
  primary identifier used across the application: in collection items,
  in audit events, and in external references.
- The ``source_providers`` tuple lists the provider keys that returned
  the publication. It is sorted and de-duplicated.
- Author lists are stored as a tuple of display strings. They are not
  normalized to a bibliographic format; the application stores them as
  the providers reported them and normalizes on display.
- The abstract is stored as-is. The application never rewrites the
  abstract.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace


@dataclass(frozen=True, slots=True)
class PublicationKey:
    """A stable identifier for a publication.

    The key has the form ``doi:<lowercase-doi>`` when a DOI is available,
    or ``<provider>:<identifier>`` otherwise. The form is deterministic
    and is not derived from the title or from author names.
    """

    value: str

    def __post_init__(self) -> None:
        if not self.value:
            raise ValueError("PublicationKey value must not be empty")

    @classmethod
    def from_doi(cls, doi: str) -> "PublicationKey":
        return cls(value=f"doi:{_normalize_doi(doi)}")

    @classmethod
    def from_provider(cls, provider_key: str, identifier: str) -> "PublicationKey":
        if not provider_key or not identifier:
            raise ValueError("provider_key and identifier must not be empty")
        return cls(value=f"{provider_key}:{identifier}")

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class CanonicalPublication:
    """The normalized view of a scholarly work."""

    key: str
    doi: str | None = None
    title: str = ""
    abstract: str = ""
    authors: tuple[str, ...] = ()
    year: int | None = None
    venue: str = ""
    language: str | None = None
    is_open_access: bool = False
    citation_count: int | None = None
    url: str | None = None
    source_providers: tuple[str, ...] = field(default_factory=tuple)
    provider_identifiers: tuple[tuple[str, str], ...] = field(default_factory=tuple)

    def with_provider(
        self,
        provider_key: str,
        identifier: str,
    ) -> "CanonicalPublication":
        """Return a copy that records an additional source provider."""
        providers = tuple(sorted(set(self.source_providers) | {provider_key}))
        identifiers = dict(self.provider_identifiers)
        identifiers.setdefault(provider_key, identifier)
        return replace(
            self,
            source_providers=providers,
            provider_identifiers=tuple(sorted(identifiers.items())),
        )

    def merge(self, other: "CanonicalPublication") -> "CanonicalPublication":
        """Return a copy that fills missing fields from ``other``.

        Fields already present on the receiver are preserved. Fields
        present only on ``other`` are copied. Lists are merged. The
        merged publication records both source provider sets.
        """
        merged_providers = tuple(
            sorted(set(self.source_providers) | set(other.source_providers))
        )
        merged_identifiers = dict(self.provider_identifiers)
        for provider, identifier in other.provider_identifiers:
            merged_identifiers.setdefault(provider, identifier)
        merged_authors = self.authors or other.authors
        return replace(
            self,
            doi=self.doi or other.doi,
            title=self.title or other.title,
            abstract=self.abstract or other.abstract,
            authors=merged_authors,
            year=self.year or other.year,
            venue=self.venue or other.venue,
            language=self.language or other.language,
            is_open_access=self.is_open_access or other.is_open_access,
            citation_count=(
                self.citation_count
                if self.citation_count is not None
                else other.citation_count
            ),
            url=self.url or other.url,
            source_providers=merged_providers,
            provider_identifiers=tuple(sorted(merged_identifiers.items())),
        )


def _normalize_doi(doi: str) -> str:
    """Return the DOI in the canonical form used by the application."""
    cleaned = doi.strip()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if cleaned.lower().startswith(prefix):
            cleaned = cleaned[len(prefix):]
    return cleaned.strip().lower()