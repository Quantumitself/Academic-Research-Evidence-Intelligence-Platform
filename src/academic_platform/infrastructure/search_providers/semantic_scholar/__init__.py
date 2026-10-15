"""Semantic Scholar search provider adapter.

This subpackage owns the Semantic Scholar integration. It provides:

- ``SemanticScholarAdapter`` — the adapter implementing the search
  provider interface.
- ``SemanticScholarResponseParser`` — converts Semantic Scholar response
  JSON into provider-neutral ``SearchHit`` objects.
- ``SemanticScholarUrlBuilder`` — constructs request URLs and parameters
  from a ``SearchRequest``.
- Registration of the adapter with the default provider registry.

Semantic Scholar's Graph API is documented at
https://api.semanticscholar.org/api-docs/. The relevance-search endpoint
accepts a query, a limit, an offset, and a year filter. The API also
accepts an ``x-api-key`` header for higher rate limits; the adapter
supports this through the source's credential reference.
"""

from academic_platform.infrastructure.search_providers.semantic_scholar.adapter import (
    SemanticScholarAdapter,
)
from academic_platform.infrastructure.search_providers.semantic_scholar.parser import (
    SemanticScholarResponseParser,
)
from academic_platform.infrastructure.search_providers.semantic_scholar.url_builder import (
    SemanticScholarUrlBuilder,
)

__all__ = [
    "SemanticScholarAdapter",
    "SemanticScholarResponseParser",
    "SemanticScholarUrlBuilder",
]