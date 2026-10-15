"""Tests for the search provider adapter interface and value objects."""

from __future__ import annotations

import pytest

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


def test_search_request_defaults() -> None:
    request = SearchRequest(query="machine learning")
    assert request.limit == 50
    assert request.offset == 0
    assert request.sort == "relevance"
    assert request.extra == {}


def test_search_request_rejects_bad_limit() -> None:
    with pytest.raises(ValueError):
        SearchRequest(query="x", limit=0)


def test_search_request_rejects_negative_offset() -> None:
    with pytest.raises(ValueError):
        SearchRequest(query="x", offset=-1)


def test_search_request_rejects_year_range_inversion() -> None:
    with pytest.raises(ValueError):
        SearchRequest(query="x", year_from=2024, year_to=2000)


def test_search_request_rejects_bad_sort() -> None:
    with pytest.raises(ValueError):
        SearchRequest(query="x", sort="bogus")


def test_search_request_identifier_only() -> None:
    request = SearchRequest(doi="10.1000/xyz")
    assert request.has_identifier
    assert not request.is_empty


def test_search_request_extra_identifier() -> None:
    request = SearchRequest(extra={"identifier": "abc"})
    assert request.has_identifier


def test_search_request_empty_is_empty() -> None:
    request = SearchRequest()
    assert request.is_empty


def test_search_hit_defaults() -> None:
    hit = SearchHit(provider_key="crossref", provider_identifier="x")
    assert hit.title == ""
    assert hit.authors == ()
    assert hit.is_open_access is False


def test_source_status_report_defaults() -> None:
    report = SourceStatusReport(provider_key="crossref", status=SourceStatus.OK)
    assert report.result_count == 0
    assert report.message == ""


def test_search_response_defaults() -> None:
    response = SearchResponse(provider_key="crossref")
    assert response.hits == ()
    assert response.total is None
    assert response.next_cursor is None


def test_descriptor_value_object() -> None:
    descriptor = ProviderDescriptor(
        key="crossref",
        display_name="Crossref",
        base_url="https://api.crossref.org",
        documentation_url="https://api.crossref.org/swagger-ui/index.html",
        provider_kind="crossref",
    )
    assert descriptor.filters == ProviderFilterSupport()
    assert descriptor.capabilities == ProviderCapabilities()