"""Construction of Crossref search URLs and parameters.

Crossref exposes a single ``/works`` endpoint that accepts a query, a
rows and offset parameter, and a filter expression. Filters are combined
with commas inside a single ``filter`` parameter.

Design decisions
----------------
- The builder produces both a URL and a parameter dictionary. The URL is
  always the endpoint URL; the parameters carry the query, pagination,
  sort, and filters.
- Filters that Crossref does not support are omitted from the request.
  The orchestration layer applies them locally to the returned hits.
- The builder never raises on an unsupported filter; it omits it. The
  orchestration layer reads the adapter's ``filter_support`` to decide
  what to do.
- Sort keys are mapped to Crossref's identifiers. Crossref supports
  sorting by relevance (default) and by publication date.
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urljoin

from academic_platform.infrastructure.search_providers.adapter import (
    SearchRequest,
)

_SORT_RELEVANCE = "relevance"
_SORT_DEPOSIT = "deposited"
_SORT_INDEXED = "indexed"

_SORT_MAP = {
    "relevance": _SORT_RELEVANCE,
    "date_desc": _SORT_DEPOSIT,
    "date_asc": _SORT_DEPOSIT,
}


@dataclass(frozen=True, slots=True)
class BuiltRequest:
    """A built URL and parameter set."""

    url: str
    params: dict[str, str]
    sort_descending: bool = True


class CrossrefUrlBuilder:
    """Build Crossref search URLs and parameters."""

    def __init__(self, *, base_url: str, endpoint: str) -> None:
        self._base_url = base_url.rstrip("/") + "/"
        self._endpoint = endpoint.lstrip("/")

    @property
    def endpoint_url(self) -> str:
        """Return the absolute endpoint URL."""
        return urljoin(self._base_url, self._endpoint)

    def build(self, request: SearchRequest) -> BuiltRequest:
        """Build a Crossref request from a provider-neutral request.

        Parameters
        ----------
        request:
            The provider-neutral search request.

        Returns
        -------
        BuiltRequest
            The endpoint URL, parameter dictionary, and the direction of
            the requested date sort. The caller uses the direction to
            reverse the results when ``date_asc`` was requested.
        """
        params: dict[str, str] = {}
        if request.query:
            params["query"] = request.query
        params["rows"] = str(min(request.limit, 1000))
        params["offset"] = str(request.offset)

        sort_key = _SORT_MAP.get(request.sort, _SORT_RELEVANCE)
        params["sort"] = sort_key
        params["order"] = "asc" if request.sort == "date_asc" else "desc"

        filters: list[str] = []
        if request.year_from is not None:
            filters.append(f"from-pub-date:{request.year_from}-01-01")
        if request.year_to is not None:
            filters.append(f"until-pub-date:{request.year_to}-12-31")
        if request.doi:
            filters.append(f"doi:{request.doi}")
        if request.open_access_only:
            # Crossref's open-access filter is expressed through the
            # license filter. The application's semantics differ, so the
            # filter is applied locally instead of being pushed down.
            pass
        if request.language:
            filters.append(f"language:{request.language}")
        if filters:
            params["filter"] = ",".join(filters)

        return BuiltRequest(
            url=self.endpoint_url,
            params=params,
            sort_descending=request.sort != "date_asc",
        )