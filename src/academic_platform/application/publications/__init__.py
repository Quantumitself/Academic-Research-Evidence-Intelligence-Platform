"""Publication normalization and deduplication.

This subpackage owns the conversion of provider-neutral search hits into
the application's canonical publication representation, and the
deduplication of those publications across providers.

Public surface
--------------
- ``CanonicalPublication`` — the immutable value object describing a
  normalized publication before persistence.
- ``PublicationKey`` — the stable key derived from a DOI or a provider
  identifier.
- ``PublicationKeyError`` — raised when a hit cannot produce a key.
- ``NormalizationResult`` — the outcome of normalizing a batch of hits.
- ``DeduplicationResult`` — the outcome of deduplicating a batch of
  publications.
- ``PublicationNormalizer`` — converts hits into canonical
  publications.
- ``PublicationDeduplicator`` — merges duplicate publications.
- ``PublicationService`` — the application service that persists
  normalized publications through the repository layer.

The subpackage never imports Qt and never imports HTTP clients directly.
It may import from the provider adapter interface (which defines the
``SearchHit`` value object) and from the repository layer.
"""

from academic_platform.application.publications.deduplicator import (
    DeduplicationResult,
    PublicationDeduplicator,
)
from academic_platform.application.publications.errors import (
    PublicationKeyError,
    PublicationNormalizationError,
    PublicationPersistenceError,
)
from academic_platform.application.publications.model import (
    CanonicalPublication,
    PublicationKey,
)
from academic_platform.application.publications.normalizer import (
    NormalizationResult,
    PublicationNormalizer,
)
from academic_platform.application.publications.service import PublicationService

__all__ = [
    "CanonicalPublication",
    "DeduplicationResult",
    "NormalizationResult",
    "PublicationDeduplicator",
    "PublicationKey",
    "PublicationKeyError",
    "PublicationNormalizationError",
    "PublicationNormalizer",
    "PublicationPersistenceError",
    "PublicationService",
]