"""Europe PMC adapter.

The adapter implements the search provider interface against Europe PMC's
REST API. It consumes the shared HTTP client infrastructure and uses the
URL builder and response parser defined in this subpackage.

Design decisions
----------------
- The adapter is constructed with an ``HttpClient``. It never constructs
  its own client; the factory used by the search source service builds
  the client from the source's configuration.
- The adapter rejects requests that carry neither a query nor an
  identifier. Europe PMC requires a query string.
- The adapter propagates the ``nextCursorMark`` returned by Europe PMC
  through the provider-neutral response so that callers can continue the
  search without re-executing the same query.
- The adapter translates HTTP client exceptions into provider-layer
  exceptions. Callers see only ``ProviderError`` subclasses.
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
from academic_platform.infrastructure.search_providers.errors import (
    ProviderRequestError,
    ProviderResponseError,
    ProviderUnavailableError,
)
from academic_platform.infrastructure.search_providers.europe_pmc.parser import (
    EuropePmcResponseParser,
)
from academic_platform.infrastructure.search_providers.europe_pmc.url_builder import (
    EuropePmcUrlBuilder,
)

_logger = logging.getLogger(__name__)

_PROVIDER_KEY = "europe_pmc"
_DISPLAY_NAME = "Europe PMC"
_BASE_URL = "https://www.ebi.ac.uk"
_ENDPOINT = "europepmc/webservices/rest/search"
_DOCUMENTATION_URL = "https://europepmc.org/RestfulWebService"
_MAX_RESULTS_PER_PAGE = 1000


class EuropePmcAdapter(SearchProviderAdapter):
    """Adapter for Europe PMC's REST API."""

    def __init__(
        self,
        http_client: HttpClient,
        *,
        base_url: str = _BASE_URL,
        endpoint: str = _ENDPOINT,
        result_type: str = "core",
    ) -> None:
        self._http_client = http_client
        self._base_url = base_url
        self._endpoint = endpoint
        self._url_builder = EuropePmcUrlBuilder(
            base_url=base_url,
            endpoint=endpoint,
            result_type=result_type,
        )
        self._parser = EuropePmcResponseParser(provider_key=_PROVIDER_KEY)

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
                open_access=True,
                sort_by_relevance=True,
                sort_by_date=True,
            ),
            capabilities=ProviderCapabilities(
                pagination=True,
                cursor_pagination=True,
                abstract_in_results=True,
                citation_counts=True,
                open_access_flag=True,
                requires_api_key=False,
                max_results_per_page=_MAX_RESULTS_PER_PAGE,
            ),
            notes=(
                "Europe PMC REST API. Uses cursor-based pagination through "
                "cursorMark. The resultType=core response includes abstracts "
                "and bibliographic metadata in a single call."
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
        if not built.params.get("query"):
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
                f"Europe PMC request timed out: {exc}"
            ) from exc
        except HttpClientRateLimitError as exc:
            raise ProviderUnavailableError(
                f"Europe PMC rate limit exceeded: {exc}"
            ) from exc
        except HttpClientNetworkError as exc:
            raise ProviderRequestError(
                f"Europe PMC network failure: {exc}"
            ) from exc
        except HttpClientConfigurationError as exc:
            raise ProviderRequestError(
                f"Europe PMC request rejected: {exc}"
            ) from exc
        except HttpClientResponseError as exc:
            raise ProviderResponseError(
                f"Europe PMC response rejected: {exc}"
            ) from exc
        except HttpClientError as exc:
            raise ProviderRequestError(
                f"Europe PMC request failed: {exc}"
            ) from exc

        duration_ms = int((time.monotonic() - started) * 1000)
        if not response.is_success:
            raise ProviderResponseError(
                f"Europe PMC returned status {response.status_code}"
            )

        try:
            payload = _decode_json(response.text)
        except ValueError as exc:
            raise ProviderResponseError(
                f"Europe PMC returned an unparseable response: {exc}"
            ) from exc

        try:
            hits, total, next_cursor = self._parser.parse(payload)
        except ProviderResponseError:
            raise
        except Exception as exc:  # noqa: BLE001 - boundary
            raise ProviderResponseError(
                f"Europe PMC parser failed: {exc}"
            ) from exc

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
                params={
                    "query": "test",
                    "format": "json",
                    "resultType": "idlist",
                    "pageSize": "1",
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
            payload = _decode_json(response.text)
            # The idlist result type omits resultList; only the top-level
            # structure is validated.
            if not isinstance(payload, dict):
                raise ValueError("response is not a JSON object")
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


def _decode_json(text: str) -> Any:
    import json

    return json.loads(text)


def build_europe_pmc_adapter(config: dict[str, Any]) -> EuropePmcAdapter:
    """Factory used by the provider registry."""
    from academic_platform.infrastructure.http.config import HttpClientConfig

    base_url = str(config.get("base_url") or _BASE_URL)
    endpoint = str(config.get("endpoint") or _ENDPOINT)
    timeout_seconds = float(config.get("timeout_seconds") or 30.0)
    rate_config = config.get("rate_limit") or {}
    rate_per_second = float(rate_config.get("requests_per_second") or 5.0)
    burst = int(rate_config.get("burst") or 10)
    result_type = str(config.get("result_type") or "core")

    http_config = HttpClientConfig(
        base_url=base_url,
        read_timeout_seconds=timeout_seconds,
        write_timeout_seconds=timeout_seconds,
        rate_limit_per_second=rate_per_second,
        rate_limit_burst=burst,
    )
    client = HttpClient(http_config)
    return EuropePmcAdapter(
        client,
        base_url=base_url,
        endpoint=endpoint,
        result_type=result_type,
    )