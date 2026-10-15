"""Construction of PubMed E-utilities URLs and parameters.

PubMed's search workflow uses three endpoints:

- ``esearch.fcgi`` — accepts a query, a ``retmax`` (limit), and a
  ``retstart`` (offset). Returns a list of identifiers and a total count.
- ``esummary.fcgi`` — accepts a comma-separated identifier list. Returns
  bibliographic metadata for each identifier.
- ``efetch.fcgi`` — accepts the same identifier list. Returns full
  records, including abstracts when requested.

The builder produces URLs and parameters for all three endpoints. The
adapter composes the calls.

Design decisions
----------------
- The builder never emits a filter that PubMed does not support natively.
  PubMed's query syntax supports date ranges through ``mindate`` and
  ``maxdate``. The application's year filter maps onto those parameters.
- The ``retmode`` parameter is always ``json``. Older PubMed responses
  returned XML; the application uses the JSON representation.
- The ``db`` parameter is always ``pubmed``.
- The identifier list is joined with commas. PubMed expects this form.
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urljoin

from academic_platform.infrastructure.search_providers.adapter import (
    SearchRequest,
)

_DEFAULT_DB = "pubmed"
_DEFAULT_RETMODE = "json"


@dataclass(frozen=True, slots=True)
class BuiltSearchRequest:
    """A built esearch request."""

    url: str
    params: dict[str, str]


@dataclass(frozen=True, slots=True)
class BuiltSummaryRequest:
    """A built esummary request."""

    url: str
    params: dict[str, str]


@dataclass(frozen=True, slots=True)
class BuiltFetchRequest:
    """A built efetch request."""

    url: str
    params: dict[str, str]


class PubMedUrlBuilder:
    """Build PubMed E-utilities URLs and parameters."""

    def __init__(
        self,
        *,
        base_url: str,
        search_endpoint: str,
        summary_endpoint: str,
        fetch_endpoint: str,
    ) -> None:
        self._base_url = base_url.rstrip("/") + "/"
        self._search_endpoint = search_endpoint.lstrip("/")
        self._summary_endpoint = summary_endpoint.lstrip("/")
        self._fetch_endpoint = fetch_endpoint.lstrip("/")

    @property
    def search_endpoint_url(self) -> str:
        return urljoin(self._base_url, self._search_endpoint)

    @property
    def summary_endpoint_url(self) -> str:
        return urljoin(self._base_url, self._summary_endpoint)

    @property
    def fetch_endpoint_url(self) -> str:
        return urljoin(self._base_url, self._fetch_endpoint)

    def build_search(self, request: SearchRequest) -> BuiltSearchRequest:
        """Build an esearch request from a provider-neutral request."""
        params: dict[str, str] = {
            "db": _DEFAULT_DB,
            "retmode": _DEFAULT_RETMODE,
            "term": request.query or "",
            "retmax": str(min(request.limit, 10000)),
            "retstart": str(request.offset),
        }
        if request.year_from is not None:
            params["mindate"] = str(request.year_from)
            params["datetype"] = "pdat"
        if request.year_to is not None:
            params["maxdate"] = str(request.year_to)
            if "datetype" not in params:
                params["datetype"] = "pdat"
        return BuiltSearchRequest(
            url=self.search_endpoint_url,
            params=params,
        )

    def build_summary(self, identifiers: list[str]) -> BuiltSummaryRequest:
        """Build an esummary request for a list of identifiers."""
        return BuiltSummaryRequest(
            url=self.summary_endpoint_url,
            params={
                "db": _DEFAULT_DB,
                "retmode": _DEFAULT_RETMODE,
                "id": ",".join(identifiers),
            },
        )

    def build_fetch_abstracts(self, identifiers: list[str]) -> BuiltFetchRequest:
        """Build an efetch request for abstracts."""
        return BuiltFetchRequest(
            url=self.fetch_endpoint_url,
            params={
                "db": _DEFAULT_DB,
                "retmode": _DEFAULT_RETMODE,
                "rettype": "abstract",
                "id": ",".join(identifiers),
            },
        )