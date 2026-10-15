"""arXiv search provider adapter.

This subpackage owns the arXiv integration. It provides:

- ``ArxivAdapter`` — the adapter implementing the search provider
  interface.
- ``ArxivResponseParser`` — parses arXiv Atom responses into
  provider-neutral ``SearchHit`` objects.
- ``ArxivUrlBuilder`` — constructs request URLs and parameters from a
  ``SearchRequest``.
- Registration of the adapter with the default provider registry.

arXiv's API is documented at
https://info.arxiv.org/help/api/user-manual.html. The query endpoint
accepts a ``search_query`` field expression, a ``max_results``, a
``start`` offset, and a ``sortBy`` parameter. Responses are Atom XML.
"""

from academic_platform.infrastructure.search_providers.arxiv.adapter import (
    ArxivAdapter,
)
from academic_platform.infrastructure.search_providers.arxiv.parser import (
    ArxivResponseParser,
)
from academic_platform.infrastructure.search_providers.arxiv.url_builder import (
    ArxivUrlBuilder,
)

__all__ = [
    "ArxivAdapter",
    "ArxivResponseParser",
    "ArxivUrlBuilder",
]