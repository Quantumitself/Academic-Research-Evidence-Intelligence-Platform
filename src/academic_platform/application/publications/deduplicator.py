"""Publication deduplication.

The deduplicator merges canonical publications that refer to the same
underlying work. Deduplication is conservative: two publications are
considered duplicates only when they share a normalized DOI, or when
their normalized keys are equal. Title-only matching is not performed,
because distinct works can share titles and because the same work can
appear under different titles in different sources.

Design decisions
----------------
- DOI equality is the primary deduplication rule. DOIs are normalized
  before comparison.
- Key equality is the secondary rule. Keys are derived from the DOI or
  from the provider identifier; equality of keys therefore reflects
  equality of the underlying identifier.
- The deduplicator does not compare titles, authors, or years. Those
  fields are useful for reporting differences between sources but are
  not reliable identifiers.
- The deduplicator preserves the input order: the first occurrence of a
  duplicate key determines the position of the merged result in the
  output list.
- The deduplicator reports which publications were merged so that
  callers can surface the decision to the user.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from academic_platform.application.publications.model import (
    CanonicalPublication,
)

_logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class MergeRecord:
    """A record of a single merge operation."""

    kept_key: str
    merged_key: str
    merged_providers: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class DeduplicationResult:
    """Outcome of deduplicating a batch of publications."""

    publications: tuple[CanonicalPublication, ...]
    merges: tuple[MergeRecord, ...] = field(default_factory=tuple)
    input_count: int = 0

    @property
    def publication_count(self) -> int:
        return len(self.publications)

    @property
    def merged_count(self) -> int:
        return len(self.merges)


class PublicationDeduplicator:
    """Merge duplicate publications."""

    def deduplicate(
        self,
        publications: list[CanonicalPublication],
    ) -> DeduplicationResult:
        """Deduplicate a batch of canonical publications.

        The input order is preserved: the position of the first
        occurrence of a duplicate group determines where the merged
        result appears in the output.
        """
        order: list[str] = []
        by_key: dict[str, CanonicalPublication] = {}
        merges: list[MergeRecord] = []

        for publication in publications:
            identity = self._identity(publication)
            existing = by_key.get(identity)
            if existing is None:
                by_key[identity] = publication
                order.append(identity)
                continue
            merged = existing.merge(publication)
            by_key[identity] = merged
            merges.append(
                MergeRecord(
                    kept_key=existing.key,
                    merged_key=publication.key,
                    merged_providers=publication.source_providers,
                )
            )

        result: list[CanonicalPublication] = [by_key[k] for k in order]
        return DeduplicationResult(
            publications=tuple(result),
            merges=tuple(merges),
            input_count=len(publications),
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    @staticmethod
    def _identity(publication: CanonicalPublication) -> str:
        # DOI-based identity is the primary rule. When a DOI is present,
        # two publications with the same DOI are duplicates regardless of
        # how their keys were constructed.
        if publication.doi:
            return f"doi:{publication.doi.lower()}"
        # Otherwise, identity is the key, which was derived from the DOI
        # or from the provider identifier.
        return publication.key
