"""PubMed adapter.

The adapter implements the search provider interface against PubMed's
E-utilities API. It composes three calls — esearch, esummary, and
efetch — internally so that callers see a single provider-neutral
response.

Design decisions
----------------
- The adapter is constructed with an ``HttpClient``. It never constructs
  its own client; the factory used by the search source service builds
  the client from the source's configuration.
- The adapter rejects requests that carry neither a query nor an
  identifier. PubMed's esearch endpoint requires a query term.
- The adapter composes esearch and esummary in a single ``search`` call.
  When the esummary response carries no abstracts, the adapter issues a
  second efetch call to obtain them. When the efetch call fails, the
  adapter returns hits without abstracts rather than failing the whole
  search; abstracts are optional.
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
from academic_platform.infrastructure.search_providers.pubmed.parser import (
    PubMedResponseParser,
)
from academic_platform.infrastructure.search_providers.pubmed.url_builder import (
    PubMedUrlBuilder,
)

_logger = logging.getLogger(__name__)

_PROVIDER_KEY = "pubmed"
_DISPLAY_NAME = "PubMed"
_BASE_URL = "https://eutils.ncbi.nlm.nih.gov"
_SEARCH_ENDPOINT = "entrez/eutils/esearch.fcgi"
_SUMMARY_ENDPOINT = "entrez/eutils/esummary.fcgi"
_FETCH_ENDPOINT = "entrez/eutils/efetch.fcgi"
_DOCUMENTATION_URL = "https://www.ncbi.nlm.nih.gov/books/NBK25501/"
_MAX_RESULTS_PER_PAGE = 10000


class PubMedAdapter(SearchProviderAdapter):
    """Adapter for PubMed's E-utilities API."""

    def __init__(
        self,
        http_client: HttpClient,
        *,
        base_url: str = _BASE_URL,
        search_endpoint: str = _SEARCH_ENDPOINT,
        summary_endpoint: str = _SUMMARY_ENDPOINT,
        fetch_endpoint: str = _FETCH_ENDPOINT,
        fetch_abstracts: bool = True,
    ) -> None:
        self._http_client = http_client
        self._base_url = base_url
        self._search_endpoint = search_endpoint
        self._summary_endpoint = summary_endpoint
        self._fetch_endpoint = fetch_endpoint
        self._fetch_abstracts = fetch_abstracts
        self._url_builder = PubMedUrlBuilder(
            base_url=base_url,
            search_endpoint=search_endpoint,
            summary_endpoint=summary_endpoint,
            fetch_endpoint=fetch_endpoint,
        )
        self._parser = PubMedResponseParser(provider_key=_PROVIDER_KEY)

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
                sort_by_relevance=True,
                sort_by_date=False,
            ),
            capabilities=ProviderCapabilities(
                pagination=True,
                cursor_pagination=False,
                abstract_in_results=True,
                citation_counts=False,
                open_access_flag=False,
                requires_api_key=False,
                max_results_per_page=_MAX_RESULTS_PER_PAGE,
            ),
            notes=(
                "PubMed E-utilities. The adapter composes esearch, esummary, "
                "and efetch internally. Abstracts are fetched in a second "
                "call; a failure in the abstract fetch returns hits without "
                "abstracts rather than failing the search."
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

        started = time.monotonic()
        identifiers, total = self._execute_search(request)
        if not identifiers:
            return SearchResponse(
                provider_key=_PROVIDER_KEY,
                hits=(),
                total=total or 0,
                next_cursor=None,
                status=SourceStatusReport(
                    provider_key=_PROVIDER_KEY,
                    status=SourceStatus.OK,
                    result_count=0,
                    message="",
                    duration_ms=int((time.monotonic() - started) * 1000),
                ),
            )

        hits = self._execute_summary(identifiers)
        if self._fetch_abstracts:
            abstracts = self._fetch_abstracts_or_empty(identifiers)
            hits = self._parser.merge_abstracts(hits, abstracts)

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
                duration_ms=int((time.monotonic() - started) * 1000),
            ),
        )

    def test_connection(self) -> SourceStatusReport:
        started = time.monotonic()
        try:
            response = self._http_client.get(
                self._url_builder.search_endpoint_url,
                params={
                    "db": "pubmed",
                    "retmode": "json",
                    "term": "test",
                    "retmax": "1",
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
            self._parser.parse_search(payload)
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

    # ------------------------------------------------------------------
    # Composition helpers
    # ------------------------------------------------------------------
    def _execute_search(
        self,
        request: SearchRequest,
    ) -> tuple[list[str], int | None]:
        built = self._url_builder.build_search(request)
        response = self._issue_get(built.url, built.params)
        payload = self._decode(response)
        try:
            return self._parser.parse_search(payload)
        except ProviderResponseError:
            raise
        except Exception as exc:  # noqa: BLE001 - boundary
            raise ProviderResponseError(
                f"PubMed search parser failed: {exc}"
            ) from exc

    def _execute_summary(self, identifiers: list[str]):
        built = self._url_builder.build_summary(identifiers)
        response = self._issue_get(built.url, built.params)
        payload = self._decode(response)
        try:
            return self._parser.parse_summary(payload, identifiers)
        except ProviderResponseError:
            raise
        except Exception as exc:  # noqa: BLE001 - boundary
            raise ProviderResponseError(
                f"PubMed summary parser failed: {exc}"
            ) from exc

    def _fetch_abstracts_or_empty(self, identifiers: list[str]) -> dict[str, str]:
        built = self._url_builder.build_fetch_abstracts(identifiers)
        try:
            response = self._issue_get(built.url, built.params)
            payload = self._decode(response)
            return self._parser.parse_abstracts(payload)
        except (ProviderError,) as exc:
            _logger.warning(
                "PubMed abstract fetch failed; hits will have empty abstracts: %s",
                exc,
            )
            return {}

    def _issue_get(self, url: str, params: dict[str, str]):
        try:
            response = self._http_client.get(url, params=params)
        except HttpClientTimeoutError as exc:
            raise ProviderUnavailableError(
                f"PubMed request timed out: {exc}"
            ) from exc
        except HttpClientRateLimitError as exc:
            raise ProviderUnavailableError(
                f"PubMed rate limit exceeded: {exc}"
            ) from exc
        except HttpClientNetworkError as exc:
            raise ProviderRequestError(
                f"PubMed network failure: {exc}"
            ) from exc
        except HttpClientConfigurationError as exc:
            raise ProviderRequestError(
                f"PubMed request rejected: {exc}"
            ) from exc
        except HttpClientResponseError as exc:
            raise ProviderResponseError(
                f"PubMed response rejected: {exc}"
            ) from exc
        except HttpClientError as exc:
            raise ProviderRequestError(
                f"PubMed request failed: {exc}"
            ) from exc
        if not response.is_success:
            raise ProviderResponseError(
                f"PubMed returned status {response.status_code}"
            )
        return response

    def _decode(self, response) -> Any:
        try:
            return _decode_json(response.text)
        except ValueError as exc:
            raise ProviderResponseError(
                f"PubMed returned an unparseable response: {exc}"
            ) from exc


from academic_platform.infrastructure.search_providers.errors import (  # noqa: E402
    ProviderError,
)


def _decode_json(text: str) -> Any:
    import json

    return json.loads(text)


def build_pubmed_adapter(config: dict[str, Any]) -> PubMedAdapter:
    """Factory used by the provider registry.

    The configuration dictionary is the one produced by the source
    resolver. The factory constructs a fresh HTTP client per call.
    """
    from academic_platform.infrastructure.http.config import HttpClientConfig

    base_url = str(config.get("base_url") or _BASE_URL)
    search_endpoint = str(config.get("endpoint") or _SEARCH_ENDPOINT)
    timeout_seconds = float(config.get("timeout_seconds") or 30.0)
    rate_config = config.get("rate_limit") or {}
    rate_per_second = float(rate_config.get("requests_per_second") or 3.0)
    burst = int(rate_config.get("burst") or 5)
    fetch_abstracts = bool(config.get("fetch_abstracts", True))

    http_config = HttpClientConfig(
        base_url=base_url,
        read_timeout_seconds=timeout_seconds,
        write_timeout_seconds=timeout_seconds,
        rate_limit_per_second=rate_per_second,
        rate_limit_burst=burst,
    )
    client = HttpClient(http_config)
    return PubMedAdapter(
        client,
        base_url=base_url,
        search_endpoint=search_endpoint,
        summary_endpoint=_SUMMARY_ENDPOINT,
        fetch_endpoint=_FETCH_ENDPOINT,
        fetch_abstracts=fetch_abstracts,
    )