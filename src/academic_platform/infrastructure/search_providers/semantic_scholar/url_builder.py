"""Construction of Semantic Scholar search URLs and parameters.

Semantic Scholar exposes a ``graph/v1/paper/search`` endpoint that
accepts a query, a limit, an offset, a year filter, and a publication
type or venue filter. The endpoint returns a ``data`` array and a
``total`` count; the application's ``SearchRequest`` maps onto its
parameters directly.

Design decisions
----------------
- The builder produces both a URL and a parameter dictionary.
- Filters that Semantic Scholar does not support natively are omitted
  from the request. The orchestration layer applies them locally to the
  returned hits.
- The year filter is expressed as a single ``year`` parameter with
  either ``YYYY``, ``YYYY-YYYY``, or ``YYYY-`` forms. The builder emits
  the narrowest form the request supports.
- Sorting is not exposed by Semantic Scholar's search endpoint; the
  builder omits the ``sort`` parameter and the adapter applies the
  requested order locally.
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urljoin

from academic_platform.infrastructure.search_providers.adapter import (
    SearchRequest,
)

_FIELDS = (
    "paperId",
    "externalIds",
    "title",
    "abstract",
    "year",
    "venue",
    "authors",
    "openAccessPdf",
    "citationCount",
)


@dataclass(frozen=True, slots=True)
class BuiltRequest:
    """A built URL and parameter set."""

    url: str
    params: dict[str, str]
    sort_descending: bool = True


class SemanticScholarUrlBuilder:
    """Build Semantic Scholar search URLs and parameters."""

    def __init__(self, *, base_url: str, endpoint: str) -> None:
        self._base_url = base_url.rstrip("/") + "/"
        self._endpoint = endpoint.lstrip("/")

    @property
    def endpoint_url(self) -> str:
        """Return the absolute endpoint URL."""
        return urljoin(self._base_url, self._endpoint)

    def build(self, request: SearchRequest) -> BuiltRequest:
        """Build a Semantic Scholar request from a provider-neutral request."""
        params: dict[str, str] = {}
        if request.query:
            params["query"] = request.query
        params["limit"] = str(min(request.limit, 100))
        params["offset"] = str(request.offset)
        params["fields"] = ",".join(_FIELDS)

        year_filter = _year_filter(request.year_from, request.year_to)
        if year_filter:
            params["year"] = year_filter
        if request.open_access_only:
            # Semantic Scholar exposes an open-access PDF filter through a
            # separate endpoint. The application's semantics are broader,
            # so the filter is applied locally.
            pass
        if request.venue:
            # Semantic Scholar supports venue filtering on some endpoints
            # but not on the relevance-search endpoint used here.
            pass

        return BuiltRequest(
            url=self.endpoint_url,
            params=params,
            sort_descending=request.sort != "date_asc",
        )


def _year_filter(year_from: int | None, year_to: int | None) -> str:
    if year_from is not None and year_to is not None:
        if year_from == year_to:
            return str(year_from)
        return f"{year_from}-{year_to}"
    if year_from is not None:
        return f"{year_from}-"
    if year_to is not None:
        return f"-{year_to}"
    return ""