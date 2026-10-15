"""Crossref adapter.

The adapter implements the search provider interface against Crossref's
REST API. It consumes the shared HTTP client infrastructure and uses the
URL builder and response parser defined in this subpackage.

Design decisions
----------------
- The adapter is constructed with an ``HttpClient``. It never constructs
  its own client; the factory used by the search source service builds
  the client from the source's configuration.
- The adapter rejects requests that carry neither a query nor an
  identifier. Crossref requires a query parameter for search; identifier
  lookup uses the ``filter=doi:`` parameter.
- The adapter translates HTTP client exceptions into provider-layer
  exceptions. Callers see only ``ProviderError`` subclasses.
- The adapter's ``test_connection`` issues a minimal request against the
  endpoint and interprets the response. It returns a status report
  rather than raising for transient failures.
- Rate limits are enforced by the HTTP client. The adapter does not
  implement its own rate limiting.
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
    SearchHit,
    SearchProviderAdapter,
    SearchRequest,
    SearchResponse,
    SourceStatus,
    SourceStatusReport,
)
from academic_platform.infrastructure.search_providers.crossref.parser import (
    CrossrefResponseParser,
)
from academic_platform.infrastructure.search_providers.crossref.url_builder import (
    CrossrefUrlBuilder,
)
from academic_platform.infrastructure.search_providers.errors import (
    ProviderRequestError,
    ProviderResponseError,
    ProviderUnavailableError,
)

_logger = logging.getLogger(__name__)

_PROVIDER_KEY = "crossref"
_DISPLAY_NAME = "Crossref"
_BASE_URL = "https://api.crossref.org"
_ENDPOINT = "works"
_DOCUMENTATION_URL = "https://api.crossref.org/swagger-ui/index.html"
_MAX_RESULTS_PER_PAGE = 1000


class CrossrefAdapter(SearchProviderAdapter):
    """Adapter for the Crossref REST API."""

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
        self._url_builder = CrossrefUrlBuilder(
            base_url=base_url,
            endpoint=endpoint,
        )
        self._parser = CrossrefResponseParser(provider_key=_PROVIDER_KEY)

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
                doi=True,
                language=True,
                sort_by_relevance=True,
                sort_by_date=True,
            ),
            capabilities=ProviderCapabilities(
                pagination=True,
                cursor_pagination=False,
                abstract_in_results=True,
                citation_counts=True,
                open_access_flag=False,
                requires_api_key=False,
                max_results_per_page=_MAX_RESULTS_PER_PAGE,
            ),
            notes=(
                "Crossref REST API. Abstracts are returned as JATS XML and "
                "are converted to plain text by the adapter."
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
        started = time.monotonic()
        try:
            response = self._http_client.get(built.url, params=built.params)
        except HttpClientTimeoutError as exc:
            raise ProviderUnavailableError(
                f"Crossref request timed out: {exc}"
            ) from exc
        except HttpClientRateLimitError as exc:
            raise ProviderUnavailableError(
                f"Crossref rate limit exceeded: {exc}"
            ) from exc
        except HttpClientNetworkError as exc:
            raise ProviderRequestError(
                f"Crossref network failure: {exc}"
            ) from exc
        except HttpClientConfigurationError as exc:
            raise ProviderRequestError(
                f"Crossref request rejected: {exc}"
            ) from exc
        except HttpClientResponseError as exc:
            raise ProviderResponseError(
                f"Crossref response rejected: {exc}"
            ) from exc
        except HttpClientError as exc:
            raise ProviderRequestError(
                f"Crossref request failed: {exc}"
            ) from exc

        duration_ms = int((time.monotonic() - started) * 1000)
        if not response.is_success:
            raise ProviderResponseError(
                f"Crossref returned status {response.status_code}"
            )

        try:
            payload = _decode_json(response.text)
        except ValueError as exc:
            raise ProviderResponseError(
                f"Crossref returned an unparseable response: {exc}"
            ) from exc

        try:
            hits, total, next_cursor = self._parser.parse(payload)
        except ProviderResponseError:
            raise
        except Exception as exc:  # noqa: BLE001 - boundary
            raise ProviderResponseError(
                f"Crossref parser failed: {exc}"
            ) from exc

        if request.sort == "date_asc":
            hits = list(reversed(hits))

        return SearchResponse(
            provider_key=_PROVIDER_KEY,
            hits=tuple(hits),
            total=total,
            next_cursor=next_cursor,
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
                params={"rows": "1", "query": "test"},
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
            payload = _decode_json(response.text)
            self._parser.parse(payload)
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

    # ------------------------------------------------------------------
    # Convenience accessors used by the registry
    # ------------------------------------------------------------------
    @property
    def provider_key(self) -> str:
        return _PROVIDER_KEY


def _decode_json(text: str) -> Any:
    import json

    return json.loads(text)


def build_crossref_adapter(config: dict[str, Any]) -> CrossrefAdapter:
    """Factory used by the provider registry.

    The configuration dictionary is the one produced by the source
    resolver. It carries the source's base URL, endpoint, timeout, and
    rate-limit parameters. The factory builds a dedicated HTTP client
    for the adapter.

    The factory constructs a fresh HTTP client per call. Adapters that
    share a client across calls are constructed directly rather than
    through this factory.
    """
    from academic_platform.infrastructure.http.config import HttpClientConfig

    base_url = str(config.get("base_url") or _BASE_URL)
    endpoint = str(config.get("endpoint") or _ENDPOINT)
    timeout_seconds = float(config.get("timeout_seconds") or 30.0)
    rate_config = config.get("rate_limit") or {}
    rate_per_second = float(rate_config.get("requests_per_second") or 5.0)
    burst = int(rate_config.get("burst") or 10)

    http_config = HttpClientConfig(
        base_url=base_url,
        read_timeout_seconds=timeout_seconds,
        write_timeout_seconds=timeout_seconds,
        rate_limit_per_second=rate_per_second,
        rate_limit_burst=burst,
    )
    client = HttpClient(http_config)
    return CrossrefAdapter(client, base_url=base_url, endpoint=endpoint)