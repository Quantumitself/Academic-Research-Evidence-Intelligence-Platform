"""Construction of Europe PMC search URLs and parameters.

Europe PMC exposes a single ``search`` endpoint that accepts a query, a
page size, a cursor mark, and a result type. The application uses
``resultType=core`` so that abstracts and bibliographic metadata are
returned together.

Design decisions
----------------
- The builder produces both a URL and a parameter dictionary.
- Filters that Europe PMC does not support natively are omitted from the
  request. The orchestration layer applies them locally to the returned
  hits.
- Europe PMC uses cursor-based pagination. The initial request omits the
  ``cursorMark`` parameter; subsequent requests pass the ``nextCursorMark``
  returned by the previous response. The builder therefore prefers the
  cursor when the request carries one and does not emit a page number.
- The ``format`` parameter is always ``json``. Older responses returned
  XML; the application uses the JSON representation.
- The year filter uses Europe PMC's search-query syntax. The builder
  appends a ``(FIRST_PDATE:[YYYY-01-01 TO YYYY-12-31])`` clause to the
  query. Europe PMC does not expose dedicated year parameters on the
  search endpoint.
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urljoin

from academic_platform.infrastructure.search_providers.adapter import (
    SearchRequest,
)

_DEFAULT_FORMAT = "json"
_DEFAULT_RESULT_TYPE = "core"


@dataclass(frozen=True, slots=True)
class BuiltRequest:
    """A built URL and parameter set."""

    url: str
    params: dict[str, str]
    sort_descending: bool = True


class EuropePmcUrlBuilder:
    """Build Europe PMC search URLs and parameters."""

    def __init__(
        self,
        *,
        base_url: str,
        endpoint: str,
        result_type: str = _DEFAULT_RESULT_TYPE,
    ) -> None:
        self._base_url = base_url.rstrip("/") + "/"
        self._endpoint = endpoint.lstrip("/")
        self._result_type = result_type

    @property
    def endpoint_url(self) -> str:
        """Return the absolute endpoint URL."""
        return urljoin(self._base_url, self._endpoint)

    def build(self, request: SearchRequest) -> BuiltRequest:
        """Build a Europe PMC request from a provider-neutral request."""
        query = self._compose_query(request)
        params: dict[str, str] = {
            "query": query,
            "format": _DEFAULT_FORMAT,
            "resultType": self._result_type,
            "pageSize": str(min(request.limit, 1000)),
        }
        if request.cursor:
            params["cursorMark"] = request.cursor
        if request.sort == "date_desc":
            params["sort"] = "P_PDATE_D desc"
        elif request.sort == "date_asc":
            params["sort"] = "P_PDATE_D asc"
        return BuiltRequest(
            url=self.endpoint_url,
            params=params,
            sort_descending=request.sort != "date_asc",
        )

    # ------------------------------------------------------------------
    # Query composition
    # ------------------------------------------------------------------
    def _compose_query(self, request: SearchRequest) -> str:
        parts: list[str] = []
        if request.query:
            parts.append(f"({request.query})")
        if request.doi:
            parts.append(f'DOI:"{request.doi.lower()}"')
        if request.year_from is not None and request.year_to is not None:
            parts.append(
                f"(FIRST_PDATE:[{request.year_from}-01-01 TO {request.year_to}-12-31])"
            )
        elif request.year_from is not None:
            parts.append(f"(FIRST_PDATE:[{request.year_from}-01-01 TO 3000-12-31])")
        elif request.year_to is not None:
            parts.append(f"(FIRST_PDATE:[1000-01-01 TO {request.year_to}-12-31])")
        if request.language:
            parts.append(f"LANG:\"{request.language.lower()}\"")
        if request.open_access_only:
            parts.append("OPEN_ACCESS:Y")
        if not parts:
            return ""
        return " AND ".join(parts)