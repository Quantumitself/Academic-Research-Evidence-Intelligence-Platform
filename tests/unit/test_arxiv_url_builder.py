"""Tests for the arXiv URL builder."""

from __future__ import annotations

from academic_platform.infrastructure.search_providers.adapter import (
    SearchRequest,
)
from academic_platform.infrastructure.search_providers.arxiv.url_builder import (
    ArxivUrlBuilder,
)


def _builder() -> ArxivUrlBuilder:
    return ArxivUrlBuilder(
        base_url="https://export.arxiv.org",
        endpoint="api/query",
    )


def test_endpoint_url() -> None:
    builder = _builder()
    assert builder.endpoint_url == "https://export.arxiv.org/api/query"


def test_query_only() -> None:
    builder = _builder()
    built = builder.build(SearchRequest(query="machine learning"))
    assert built.params["search_query"] == "all:machine learning"


def test_pagination_parameters() -> None:
    builder = _builder()
    built = builder.build(SearchRequest(query="x", limit=25, offset=50))
    assert built.params["max_results"] == "25"
    assert built.params["start"] == "50"


def test_author_clause() -> None:
    builder = _builder()
    built = builder.build(SearchRequest(query="x", author="Smith"))
    assert "au:Smith" in built.params["search_query"]


def test_year_range_clause() -> None:
    builder = _builder()
    built = builder.build(SearchRequest(query="x", year_from=2010, year_to=2020))
    assert "submittedDate:[201001010000 TO 202012312359]" in built.params["search_query"]


def test_year_from_only_clause() -> None:
    builder = _builder()
    built = builder.build(SearchRequest(query="x", year_from=2010))
    assert "submittedDate:[201001010000 TO 300012312359]" in built.params["search_query"]


def test_year_to_only_clause() -> None:
    builder = _builder()
    built = builder.build(SearchRequest(query="x", year_to=2020))
    assert "submittedDate:[100001010000 TO 202012312359]" in built.params["search_query"]


def test_default_sort_is_relevance() -> None:
    builder = _builder()
    built = builder.build(SearchRequest(query="x"))
    assert built.params["sortBy"] == "relevance"
    assert built.params["sortOrder"] == "descending"


def test_date_desc_sort() -> None:
    builder = _builder()
    built = builder.build(SearchRequest(query="x", sort="date_desc"))
    assert built.params["sortBy"] == "submittedDate"
    assert built.params["sortOrder"] == "descending"


def test_date_asc_sort() -> None:
    builder = _builder()
    built = builder.build(SearchRequest(query="x", sort="date_asc"))
    assert built.params["sortBy"] == "submittedDate"
    assert built.params["sortOrder"] == "ascending"


def test_limit_clamped_to_provider_maximum() -> None:
    builder = _builder()
    built = builder.build(SearchRequest(query="x", limit=5000))
    assert built.params["max_results"] == "2000"


def test_empty_request_yields_empty_query() -> None:
    builder = _builder()
    built = builder.build(SearchRequest())
    assert built.params["search_query"] == ""