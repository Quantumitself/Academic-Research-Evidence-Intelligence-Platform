"""arXiv adapter.

The adapter implements the search provider interface against arXiv's
Atom API. It consumes the shared HTTP client infrastructure and uses the
URL builder and response parser defined in this subpackage.

Design decisions
----------------
- The adapter is constructed with an ``HttpClient``. It never constructs
  its own client; the factory used by the search source service builds
  the client from the source's configuration.
- The adapter rejects requests that carry neither a query nor an
  identifier. arXiv requires a query string on the query endpoint.
- arXiv's response content type is ``application/atom+xml``. The HTTP
  client's default content-type allow-list includes ``application/xml``
  and ``text/xml`` but not ``application/atom+xml``. The adapter's
  factory configures the client with an allow-list that includes the
  Atom content type.
- The adapter translates HTTP client exceptions into provider-layer
  exceptions. Callers see only ``ProviderError`` subclasses.
- arXiv does not support cursor pagination. The adapter propagates the
  ``itemsPerPage`` count through ``SearchHit.extra`` metadata on the
  response's status report is not appropriate; the caller derives the
  next offset from the number of hits and the request's ``offset``. The
  adapter therefore does not emit a next cursor.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from academic_platform.infrastructure.http.client import HttpClient
from academic_platform.infrastructure.http.errors import (
    HttpClientConfigurationError,
    HttpClientError,
    HttpClientNetworkError,
    HttpClientRateLimitError,
    HttpClientResponseError,
    HttpClientTimeoutError,
)
from academic_platform.infrastructure.search_providers.adapter import (
    ProviderCapabilities,
    ProviderDescriptor,
    ProviderFilterSupport,
    SearchProviderAdapter,
    SearchRequest,
    SearchResponse,
    SourceStatus,
    SourceStatusReport,
)
from academic_platform.infrastructure.search_providers.arxiv.parser import (
    ArxivResponseParser,
)
from academic_platform.infrastructure.search_providers.arxiv.url_builder import (
    ArxivUrlBuilder,
)
from academic_platform.infrastructure.search_providers.errors import (
    ProviderRequestError,
    ProviderResponseError,
    ProviderUnavailableError,
)

_logger = logging.getLogger(__name__)

_PROVIDER_KEY = "arxiv"
_DISPLAY_NAME = "arXiv"
_BASE_URL = "https://export.arxiv.org"
_ENDPOINT = "api/query"
_DOCUMENTATION_URL = "https://info.arxiv.org/help/api/user-manual.html"
_MAX_RESULTS_PER_PAGE = 2000


class ArxivAdapter(SearchProviderAdapter):
    """Adapter for arXiv's Atom API."""

    def __init__(
        self,
        http_client: HttpClient,
        *,
        base_url: str = _BASE_URL,
        endpoint: str = _ENDPOINT,
    ) -> None:
        self._http_client = http_client
        self._base_url = base_url
        self._endpoint = endpoint
        self._url_builder = ArxivUrlBuilder(base_url=base_url, endpoint=endpoint)
        self._parser = ArxivResponseParser(provider_key=_PROVIDER_KEY)

    # ------------------------------------------------------------------
    # Interface
    # ------------------------------------------------------------------
    @property
    def descriptor(self) -> ProviderDescriptor:
        return ProviderDescriptor(
            key=_PROVIDER_KEY,
            display_name=_DISPLAY_NAME,
            base_url=self._base_url,
            documentation_url=_DOCUMENTATION_URL,
            provider_kind=_PROVIDER_KEY,
            filters=ProviderFilterSupport(
                year_range=True,
                author=True,
                sort_by_relevance=True,
                sort_by_date=True,
            ),
            capabilities=ProviderCapabilities(
                pagination=True,
                cursor_pagination=False,
                abstract_in_results=True,
                citation_counts=False,
                open_access_flag=True,
                requires_api_key=False,
                max_results_per_page=_MAX_RESULTS_PER_PAGE,
            ),
            notes=(
                "arXiv Atom API. Preprints are openly available; the "
                "open-access flag is reported as true for every hit. DOI "
                "lookup is not supported by the query endpoint."
            ),
        )

    def search(self, request: SearchRequest) -> SearchResponse:
        if request.is_empty:
            return SearchResponse(
                provider_key=_PROVIDER_KEY,
                hits=(),
                total=0,
                next_cursor=None,
                status=SourceStatusReport(
                    provider_key=_PROVIDER_KEY,
                    status=SourceStatus.SKIPPED,
                    result_count=0,
                    message="Request is empty; nothing to search.",
                ),
            )

        built = self._url_builder.build(request)
        if not built.params.get("search_query"):
            return SearchResponse(
                provider_key=_PROVIDER_KEY,
                hits=(),
                total=0,
                next_cursor=None,
                status=SourceStatusReport(
                    provider_key=_PROVIDER_KEY,
                    status=SourceStatus.SKIPPED,
                    result_count=0,
                    message="Request produced an empty query.",
                ),
            )

        started = time.monotonic()
        try:
            response = self._http_client.get(built.url, params=built.params)
        except HttpClientTimeoutError as exc:
            raise ProviderUnavailableError(
                f"arXiv request timed out: {exc}"
            ) from exc
        except HttpClientRateLimitError as exc:
            raise ProviderUnavailableError(
                f"arXiv rate limit exceeded: {exc}"
            ) from exc
        except HttpClientNetworkError as exc:
            raise ProviderRequestError(
                f"arXiv network failure: {exc}"
            ) from exc
        except HttpClientConfigurationError as exc:
            raise ProviderRequestError(
                f"arXiv request rejected: {exc}"
            ) from exc
        except HttpClientResponseError as exc:
            raise ProviderResponseError(
                f"arXiv response rejected: {exc}"
            ) from exc
        except HttpClientError as exc:
            raise ProviderRequestError(
                f"arXiv request failed: {exc}"
            ) from exc

        duration_ms = int((time.monotonic() - started) * 1000)
        if not response.is_success:
            raise ProviderResponseError(
                f"arXiv returned status {response.status_code}"
            )

        try:
            hits, total, _items_per_page = self._parser.parse(response.text)
        except ProviderResponseError:
            raise
        except Exception as exc:  # noqa: BLE001 - boundary
            raise ProviderResponseError(
                f"arXiv parser failed: {exc}"
            ) from exc

        return SearchResponse(
            provider_key=_PROVIDER_KEY,
            hits=tuple(hits),
            total=total,
            next_cursor=None,
            status=SourceStatusReport(
                provider_key=_PROVIDER_KEY,
                status=SourceStatus.OK,
                result_count=len(hits),
                message="",
                duration_ms=duration_ms,
            ),
        )

    def test_connection(self) -> SourceStatusReport:
        started = time.monotonic()
        try:
            response = self._http_client.get(
                self._url_builder.endpoint_url,
                params={
                    "search_query": "all:test",
                    "max_results": "1",
                    "start": "0",
                },
            )
        except HttpClientError as exc:
            return SourceStatusReport(
                provider_key=_PROVIDER_KEY,
                status=SourceStatus.FAILED,
                result_count=0,
                message=str(exc),
                duration_ms=int((time.monotonic() - started) * 1000),
            )
        duration_ms = int((time.monotonic() - started) * 1000)
        if not response.is_success:
            return SourceStatusReport(
                provider_key=_PROVIDER_KEY,
                status=SourceStatus.FAILED,
                result_count=0,
                message=f"Status {response.status_code}",
                duration_ms=duration_ms,
            )
        try:
            self._parser.parse(response.text)
        except Exception as exc:  # noqa: BLE001 - boundary
            return SourceStatusReport(
                provider_key=_PROVIDER_KEY,
                status=SourceStatus.FAILED,
                result_count=0,
                message=f"Unparseable response: {exc}",
                duration_ms=duration_ms,
            )
        return SourceStatusReport(
            provider_key=_PROVIDER_KEY,
            status=SourceStatus.OK,
            result_count=0,
            message="",
            duration_ms=duration_ms,
        )

    @property
    def provider_key(self) -> str:
        return _PROVIDER_KEY


def build_arxiv_adapter(config: dict[str, Any]) -> ArxivAdapter:
    """Factory used by the provider registry."""
    from academic_platform.infrastructure.http.config import HttpClientConfig

    base_url = str(config.get("base_url") or _BASE_URL)
    endpoint = str(config.get("endpoint") or _ENDPOINT)
    timeout_seconds = float(config.get("timeout_seconds") or 30.0)
    rate_config = config.get("rate_limit") or {}
    rate_per_second = float(rate_config.get("requests_per_second") or 3.0)
    burst = int(rate_config.get("burst") or 5)

    # arXiv returns application/atom+xml; the client's default allow-list
    # does not include it, so the factory extends the allow-list.
    allowed_content_types = (
        "application/json",
        "application/xml",
        "application/atom+xml",
        "text/xml",
        "text/plain",
    )

    http_config = HttpClientConfig(
        base_url=base_url,
        read_timeout_seconds=timeout_seconds,
        write_timeout_seconds=timeout_seconds,
        rate_limit_per_second=rate_per_second,
        rate_limit_burst=burst,
        allowed_content_types=allowed_content_types,
    )
    client = HttpClient(http_config)
    return ArxivAdapter(client, base_url=base_url, endpoint=endpoint)