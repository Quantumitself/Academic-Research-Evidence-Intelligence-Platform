"""OpenAlex search provider adapter.

This subpackage owns the OpenAlex integration. It provides:

- ``OpenAlexAdapter`` — the adapter implementing the search provider
  interface.
- ``OpenAlexResponseParser`` — converts OpenAlex response JSON into
  provider-neutral ``SearchHit`` objects.
- ``OpenAlexUrlBuilder`` — constructs request URLs and parameters from a
  ``SearchRequest``.
- Registration of the adapter with the default provider registry.

OpenAlex's REST API is documented at
https://docs.openalex.org/api-entities/works. OpenAlex recommends
including a contact email in the ``mailto`` query parameter for the
polite pool. The adapter accepts a contact email through its
configuration; when absent, requests use the common pool.
"""

from academic_platform.infrastructure.search_providers.openalex.adapter import (
    OpenAlexAdapter,
)
from academic_platform.infrastructure.search_providers.openalex.parser import (
    OpenAlexResponseParser,
)
from academic_platform.infrastructure.search_providers.openalex.url_builder import (
    OpenAlexUrlBuilder,
)

__all__ = [
    "OpenAlexAdapter",
    "OpenAlexResponseParser",
    "OpenAlexUrlBuilder",
]