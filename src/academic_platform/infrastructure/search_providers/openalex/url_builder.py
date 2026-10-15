"""Construction of OpenAlex search URLs and parameters.

OpenAlex exposes a single ``/works`` endpoint that accepts a search
query, pagination parameters, and a filter expression. Filters are
combined with commas inside a single ``filter`` parameter. OpenAlex also
supports cursor pagination through a ``cursor`` parameter.

Design decisions
----------------
- The builder produces both a URL and a parameter dictionary. The URL is
  always the endpoint URL; the parameters carry the query, pagination,
  sort, and filters.
- Filters that OpenAlex does not support are omitted from the request.
  The orchestration layer applies them locally to the returned hits.
- The builder maps the application's sort modes to OpenAlex's sort keys.
  OpenAlex supports sorting by relevance (the default), by publication
  date, and by citation count. Only date sorts are exposed by the
  application's ``SearchRequest`` at this stage; the builder maps
  ``date_desc`` to ``publication_date:desc`` and ``date_asc`` to
  ``publication_date:asc``.
- The optional ``mailto`` parameter is included when a contact email is
  configured. This places the request in OpenAlex's polite pool, which
  provides better reliability and support.
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urljoin

from academic_platform.infrastructure.search_providers.adapter import (
    SearchRequest,
)

_SORT_MAP = {
    "relevance": "",
    "date_desc": "publication_date:desc",
    "date_asc": "publication_date:asc",
}


@dataclass(frozen=True, slots=True)
class BuiltRequest:
    """A built URL and parameter set."""

    url: str
    params: dict[str, str]


class OpenAlexUrlBuilder:
    """Build OpenAlex search URLs and parameters."""

    def __init__(
        self,
        *,
        base_url: str,
        endpoint: str,
        contact_email: str | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/") + "/"
        self._endpoint = endpoint.lstrip("/")
        self._contact_email = contact_email or ""

    @property
    def endpoint_url(self) -> str:
        """Return the absolute endpoint URL."""
        return urljoin(self._base_url, self._endpoint)

    def build(self, request: SearchRequest) -> BuiltRequest:
        """Build an OpenAlex request from a provider-neutral request."""
        params: dict[str, str] = {}
        if request.query:
            params["search"] = request.query
        params["per-page"] = str(min(request.limit, 200))
        if request.cursor:
            params["cursor"] = request.cursor
        else:
            params["page"] = str((request.offset // max(1, request.limit)) + 1)

        sort_key = _SORT_MAP.get(request.sort, "")
        if sort_key:
            params["sort"] = sort_key

        filters: list[str] = []
        if request.year_from is not None:
            filters.append(f"from_publication_date:{request.year_from}-01-01")
        if request.year_to is not None:
            filters.append(f"to_publication_date:{request.year_to}-12-31")
        if request.doi:
            filters.append(f"doi:{request.doi.lower()}")
        if request.open_access_only:
            filters.append("is_oa:true")
        if request.language:
            filters.append(f"language:{request.language}")
        if filters:
            params["filter"] = ",".join(filters)

        if self._contact_email:
            params["mailto"] = self._contact_email

        return BuiltRequest(url=self.endpoint_url, params=params)