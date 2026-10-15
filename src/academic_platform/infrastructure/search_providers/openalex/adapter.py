"""OpenAlex adapter.

The adapter implements the search provider interface against OpenAlex's
REST API. It consumes the shared HTTP client infrastructure and uses the
URL builder and response parser defined in this subpackage.

Design decisions
----------------
- The adapter is constructed with an ``HttpClient``. It never constructs
  its own client; the factory used by the search source service builds
  the client from the source's configuration.
- The adapter rejects requests that carry neither a query nor an
  identifier. OpenAlex requires a search query or a filter for search;
  identifier lookup uses the ``filter=doi:`` parameter.
- The adapter translates HTTP client exceptions into provider-layer
  exceptions. Callers see only ``ProviderError`` subclasses.
- The adapter's ``test_connection`` issues a minimal request against the
  endpoint and interprets the response. It returns a status report
  rather than raising for transient failures.
- OpenAlex supports cursor pagination. The adapter propagates the
  ``next_cursor`` from the response so that callers can continue the
  search without re-executing the same query.
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
from academic_platform.infrastructure.search_providers.openalex.parser import (
    OpenAlexResponseParser,
)
from academic_platform.infrastructure.search_providers.openalex.url_builder import (
    OpenAlexUrlBuilder,
)

_logger = logging.getLogger(__name__)

_PROVIDER_KEY = "openalex"
_DISPLAY_NAME = "OpenAlex"
_BASE_URL = "https://api.openalex.org"
_ENDPOINT = "works"
_DOCUMENTATION_URL = "https://docs.openalex.org/api-entities/works"
_MAX_RESULTS_PER_PAGE = 200


class OpenAlexAdapter(SearchProviderAdapter):
    """Adapter for the OpenAlex REST API."""

    def __init__(
        self,
        http_client: HttpClient,
        *,
        base_url: str = _BASE_URL,
        endpoint: str = _ENDPOINT,
        contact_email: str | None = None,
    ) -> None:
        self._http_client = http_client
        self._base_url = base_url
        self._endpoint = endpoint
        self._url_builder = OpenAlexUrlBuilder(
            base_url=base_url,
            endpoint=endpoint,
            contact_email=contact_email,
        )
        self._parser = OpenAlexResponseParser(provider_key=_PROVIDER_KEY)

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
                "OpenAlex REST API. Abstracts are reconstructed from the "
                "inverted index returned by OpenAlex. A contact email places "
                "requests in OpenAlex's polite pool."
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
                f"OpenAlex request timed out: {exc}"
            ) from exc
        except HttpClientRateLimitError as exc:
            raise ProviderUnavailableError(
                f"OpenAlex rate limit exceeded: {exc}"
            ) from exc
        except HttpClientNetworkError as exc:
            raise ProviderRequestError(
                f"OpenAlex network failure: {exc}"
            ) from exc
        except HttpClientConfigurationError as exc:
            raise ProviderRequestError(
                f"OpenAlex request rejected: {exc}"
            ) from exc
        except HttpClientResponseError as exc:
            raise ProviderResponseError(
                f"OpenAlex response rejected: {exc}"
            ) from exc
        except HttpClientError as exc:
            raise ProviderRequestError(
                f"OpenAlex request failed: {exc}"
            ) from exc

        duration_ms = int((time.monotonic() - started) * 1000)
        if not response.is_success:
            raise ProviderResponseError(
                f"OpenAlex returned status {response.status_code}"
            )

        try:
            payload = _decode_json(response.text)
        except ValueError as exc:
            raise ProviderResponseError(
                f"OpenAlex returned an unparseable response: {exc}"
            ) from exc

        try:
            hits, total, next_cursor = self._parser.parse(payload)
        except ProviderResponseError:
            raise
        except Exception as exc:  # noqa: BLE001 - boundary
            raise ProviderResponseError(
                f"OpenAlex parser failed: {exc}"
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
                params={"per-page": "1", "search": "test"},
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

    @property
    def provider_key(self) -> str:
        return _PROVIDER_KEY


def _decode_json(text: str) -> Any:
    import json

    return json.loads(text)


def build_openalex_adapter(config: dict[str, Any]) -> OpenAlexAdapter:
    """Factory used by the provider registry.

    The configuration dictionary is the one produced by the source
    resolver. It carries the source's base URL, endpoint, timeout, and
    rate-limit parameters. The factory constructs a fresh HTTP client
    per call.
    """
    from academic_platform.infrastructure.http.config import HttpClientConfig

    base_url = str(config.get("base_url") or _BASE_URL)
    endpoint = str(config.get("endpoint") or _ENDPOINT)
    timeout_seconds = float(config.get("timeout_seconds") or 30.0)
    rate_config = config.get("rate_limit") or {}
    rate_per_second = float(rate_config.get("requests_per_second") or 10.0)
    burst = int(rate_config.get("burst") or 20)
    contact_email = config.get("contact_email")
    if not isinstance(contact_email, str) or not contact_email.strip():
        contact_email = None

    http_config = HttpClientConfig(
        base_url=base_url,
        read_timeout_seconds=timeout_seconds,
        write_timeout_seconds=timeout_seconds,
        rate_limit_per_second=rate_per_second,
        rate_limit_burst=burst,
    )
    client = HttpClient(http_config)
    return OpenAlexAdapter(
        client,
        base_url=base_url,
        endpoint=endpoint,
        contact_email=contact_email,
    )