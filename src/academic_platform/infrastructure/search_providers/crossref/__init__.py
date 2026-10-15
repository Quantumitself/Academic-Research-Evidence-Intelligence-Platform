"""Crossref search provider adapter.

This subpackage owns the Crossref integration. It provides:

- ``CrossrefAdapter`` — the adapter implementing the search provider
  interface.
- ``CrossrefResponseParser`` — the module that converts Crossref's
  response JSON into provider-neutral ``SearchHit`` objects.
- ``CrossrefUrlBuilder`` — the module that constructs request URLs and
  parameters from a ``SearchRequest``.
- Registration of the adapter with the default provider registry.

Crossref's REST API is documented at
https://api.crossref.org/swagger-ui/index.html. Requests must include a
descriptive User-Agent that identifies the application and provides a
contact address; the adapter therefore relies on the shared HTTP client
infrastructure's default user agent.
"""

from academic_platform.infrastructure.search_providers.crossref.adapter import (
    CrossrefAdapter,
)
from academic_platform.infrastructure.search_providers.crossref.parser import (
    CrossrefResponseParser,
)
from academic_platform.infrastructure.search_providers.crossref.url_builder import (
    CrossrefUrlBuilder,
)

__all__ = [
    "CrossrefAdapter",
    "CrossrefResponseParser",
    "CrossrefUrlBuilder",
]