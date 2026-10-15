"""Null search provider adapter.

The null adapter is used before any concrete provider is registered. It
reports honestly that the provider is not configured and returns no
results. It exists so that the orchestration layer and the search page
can run without any concrete adapter installed, and so that tests have a
deterministic baseline.
"""

from __future__ import annotations

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

_NULL_KEY = "null"
_NULL_DISPLAY_NAME = "No source configured"
_NULL_BASE_URL = "about:blank"
_NULL_DOCUMENTATION_URL = "about:blank"


class NullSearchProviderAdapter(SearchProviderAdapter):
    """Adapter that reports the absence of a configured provider."""

    def __init__(
        self,
        *,
        key: str = _NULL_KEY,
        message: str = (
            "No search provider is configured. Enable an academic source in "
            "Settings to search remote literature."
        ),
    ) -> None:
        self._key = key
        self._message = message

    @property
    def descriptor(self) -> ProviderDescriptor:
        return ProviderDescriptor(
            key=self._key,
            display_name=_NULL_DISPLAY_NAME,
            base_url=_NULL_BASE_URL,
            documentation_url=_NULL_DOCUMENTATION_URL,
            provider_kind="null",
            filters=ProviderFilterSupport(),
            capabilities=ProviderCapabilities(
                pagination=False,
                abstract_in_results=False,
                max_results_per_page=0,
            ),
            notes="Placeholder adapter used when no provider is registered.",
        )

    def search(self, request: SearchRequest) -> SearchResponse:
        return SearchResponse(
            provider_key=self._key,
            hits=(),
            total=None,
            next_cursor=None,
            status=SourceStatusReport(
                provider_key=self._key,
                status=SourceStatus.SKIPPED,
                result_count=0,
                message=self._message,
            ),
        )

    def test_connection(self) -> SourceStatusReport:
        return SourceStatusReport(
            provider_key=self._key,
            status=SourceStatus.SKIPPED,
            result_count=0,
            message=self._message,
        )