"""Europe PMC search provider adapter.

This subpackage owns the Europe PMC integration. It provides:

- ``EuropePmcAdapter`` — the adapter implementing the search provider
  interface.
- ``EuropePmcResponseParser`` — parses Europe PMC responses into
  provider-neutral ``SearchHit`` objects.
- ``EuropePmcUrlBuilder`` — constructs request URLs and parameters from
  a ``SearchRequest``.
- Registration of the adapter with the default provider registry.

Europe PMC's REST API is documented at
https://europepmc.org/RestfulWebService. The search endpoint accepts a
``query`` parameter, a ``pageSize``, a ``cursorMark``, and a ``resultType``.
The application uses ``resultType=core`` to obtain abstracts alongside
bibliographic metadata in a single call.
"""

from academic_platform.infrastructure.search_providers.europe_pmc.adapter import (
    EuropePmcAdapter,
)
from academic_platform.infrastructure.search_providers.europe_pmc.parser import (
    EuropePmcResponseParser,
)
from academic_platform.infrastructure.search_providers.europe_pmc.url_builder import (
    EuropePmcUrlBuilder,
)

__all__ = [
    "EuropePmcAdapter",
    "EuropePmcResponseParser",
    "EuropePmcUrlBuilder",
]