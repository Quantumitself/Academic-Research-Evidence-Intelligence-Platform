"""PubMed search provider adapter.

This subpackage owns the PubMed integration. It provides:

- ``PubMedAdapter`` — the adapter implementing the search provider
  interface.
- ``PubMedResponseParser`` — parses esummary and efetch responses into
  provider-neutral ``SearchHit`` objects.
- ``PubMedUrlBuilder`` — constructs esearch, esummary, and efetch URLs
  from a ``SearchRequest`` and a list of identifiers.
- Registration of the adapter with the default provider registry.

PubMed's search is exposed through the NCBI E-utilities API. The
documented endpoints used by the adapter are:

- ``esearch.fcgi`` — returns identifiers matching a query.
- ``esummary.fcgi`` — returns metadata for a set of identifiers.
- ``efetch.fcgi`` — returns full records (used for abstracts).

The adapter relies on ``esummary`` for bibliographic metadata and on
``efetch`` for abstracts. It composes the two calls so that the returned
``SearchHit`` objects carry the fields the application uses.
"""

from academic_platform.infrastructure.search_providers.pubmed.adapter import (
    PubMedAdapter,
)
from academic_platform.infrastructure.search_providers.pubmed.parser import (
    PubMedResponseParser,
)
from academic_platform.infrastructure.search_providers.pubmed.url_builder import (
    PubMedUrlBuilder,
)

__all__ = [
    "PubMedAdapter",
    "PubMedResponseParser",
    "PubMedUrlBuilder",
]