"""Tests for the null search provider adapter."""

from __future__ import annotations

from academic_platform.infrastructure.search_providers.adapter import (
    SearchRequest,
    SourceStatus,
)
from academic_platform.infrastructure.search_providers.null_adapter import (
    NullSearchProviderAdapter,
)


def test_descriptor_is_honest() -> None:
    adapter = NullSearchProviderAdapter()
    descriptor = adapter.descriptor
    assert descriptor.provider_kind == "null"
    assert descriptor.capabilities.max_results_per_page == 0


def test_search_returns_skipped_status() -> None:
    adapter = NullSearchProviderAdapter()
    response = adapter.search(SearchRequest(query="anything"))
    assert response.hits == ()
    assert response.status is not None
    assert response.status.status is SourceStatus.SKIPPED
    assert response.status.message


def test_test_connection_returns_skipped() -> None:
    adapter = NullSearchProviderAdapter()
    report = adapter.test_connection()
    assert report.status is SourceStatus.SKIPPED


def test_custom_key_and_message() -> None:
    adapter = NullSearchProviderAdapter(key="custom", message="hello")
    assert adapter.provider_key == "custom"
    report = adapter.test_connection()
    assert report.message == "hello"