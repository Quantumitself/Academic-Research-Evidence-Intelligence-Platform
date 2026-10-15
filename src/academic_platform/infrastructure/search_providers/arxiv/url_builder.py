"""Construction of arXiv search URLs and parameters.

arXiv exposes a single ``api/query`` endpoint that accepts a
``search_query`` field expression, a ``start`` offset, a ``max_results``
limit, and a ``sortBy``/``sortOrder`` pair.

Design decisions
----------------
- The builder produces both a URL and a parameter dictionary.
- The ``search_query`` field expression combines clauses with ``AND``.
  Free-text queries use the ``all:`` field prefix. Author, year, and
  category filters use their respective field prefixes.
- Filters that arXiv does not support natively are omitted from the
  request. The orchestration layer applies them locally to the returned
  hits.
- The year range is expressed as a submitted-date range using the
  ``submittedDate:[YYYYMMDDHHMM TO YYYYMMDDHHMM]`` form. arXiv requires
  the full timestamp; the builder uses start-of-year and end-of-year
  boundaries.
- Sorting uses the ``sortBy`` parameter with ``relevance`` or
  ``submittedDate`` and the ``sortOrder`` parameter with ``ascending``
  or ``descending``.
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urljoin

from academic_platform.infrastructure.search_providers.adapter import (
    SearchRequest,
)

_SORT_BY_RELEVANCE = "relevance"
_SORT_BY_SUBMITTED = "submittedDate"

_SORT_BY_MAP = {
    "relevance": _SORT_BY_RELEVANCE,
    "date_desc": _SORT_BY_SUBMITTED,
    "date_asc": _SORT_BY_SUBMITTED,
}


@dataclass(frozen=True, slots=True)
class BuiltRequest:
    """A built URL and parameter set."""

    url: str
    params: dict[str, str]
    sort_descending: bool = True


class ArxivUrlBuilder:
    """Build arXiv query URLs and parameters."""

    def __init__(self, *, base_url: str, endpoint: str) -> None:
        self._base_url = base_url.rstrip("/") + "/"
        self._endpoint = endpoint.lstrip("/")

    @property
    def endpoint_url(self) -> str:
        """Return the absolute endpoint URL."""
        return urljoin(self._base_url, self._endpoint)

    def build(self, request: SearchRequest) -> BuiltRequest:
        """Build an arXiv query from a provider-neutral request."""
        query = self._compose_query(request)
        params: dict[str, str] = {
            "search_query": query,
            "start": str(request.offset),
            "max_results": str(min(request.limit, 2000)),
        }
        sort_key = _SORT_BY_MAP.get(request.sort, _SORT_BY_RELEVANCE)
        params["sortBy"] = sort_key
        params["sortOrder"] = "ascending" if request.sort == "date_asc" else "descending"
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
            parts.append(f"all:{_quote_query(request.query)}")
        if request.doi:
            # arXiv identifies works by their arXiv identifier, not by
            # DOI. DOI lookup is not supported by the query API; the
            # clause is omitted and the orchestration layer applies the
            # filter locally.
            pass
        if request.author:
            parts.append(f"au:{_quote_query(request.author)}")
        if request.year_from is not None or request.year_to is not None:
            start = f"{request.year_from or 1000}01010000"
            end = f"{request.year_to or 3000}12312359"
            parts.append(f"submittedDate:[{start} TO {end}]")
        if request.language:
            # arXiv does not expose a language filter; the clause is
            # omitted and the filter is applied locally.
            pass
        if not parts:
            return ""
        return " AND ".join(parts)


def _quote_query(value: str) -> str:
    # arXiv's query syntax uses a space as an implicit AND. Quoting the
    # entire phrase forces an exact-phrase match, which is too strict for
    # multi-word queries. The builder preserves the query as-is and lets
    # arXiv's parser handle implicit AND semantics.
    return value.strip()