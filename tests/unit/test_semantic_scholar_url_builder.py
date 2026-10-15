"""Tests for the Semantic Scholar URL builder."""

from __future__ import annotations

from academic_platform.infrastructure.search_providers.adapter import (
    SearchRequest,
)
from academic_platform.infrastructure.search_providers.semantic_scholar.url_builder import (
    SemanticScholarUrlBuilder,
)


def _builder() -> SemanticScholarUrlBuilder:
    return SemanticScholarUrlBuilder(
        base_url="https://api.semanticscholar.org",
        endpoint="graph/v1/paper/search",
    )


def test_endpoint_url() -> None:
    builder = _builder()
    assert builder.endpoint_url == "https://api.semanticscholar.org/graph/v1/paper/search"


def test_query_and_pagination() -> None:
    builder = _builder()
    built = builder.build(SearchRequest(query="ml", limit=25, offset=50))
    assert built.params["query"] == "ml"
    assert built.params["limit"] == "25"
    assert built.params["offset"] == "50"
    assert "fields" in built.params


def test_year_filter_single_year() -> None:
    builder = _builder()
    built = builder.build(SearchRequest(query="x", year_from=2020, year_to=2020))
    assert built.params["year"] == "2020"


def test_year_filter_range() -> None:
    builder = _builder()
    built = builder.build(SearchRequest(query="x", year_from=2010, year_to=2020))
    assert built.params["year"] == "2010-2020"


def test_year_filter_open_start() -> None:
    builder = _builder()
    built = builder.build(SearchRequest(query="x", year_to=2020))
    assert built.params["year"] == "-2020"


def test_year_filter_open_end() -> None:
    builder = _builder()
    built = builder.build(SearchRequest(query="x", year_from=2010))
    assert built.params["year"] == "2010-"


def test_year_filter_absent() -> None:
    builder = _builder()
    built = builder.build(SearchRequest(query="x"))
    assert "year" not in built.params


def test_no_sort_parameter() -> None:
    builder = _builder()
    built = builder.build(SearchRequest(query="x", sort="date_desc"))
    assert "sort" not in built.params


def test_limit_clamped_to_provider_maximum() -> None:
    builder = _builder()
    built = builder.build(SearchRequest(query="x", limit=1000))
    assert built.params["limit"] == "100"


def test_fields_listed() -> None:
    builder = _builder()
    built = builder.build(SearchRequest(query="x"))
    assert "paperId" in built.params["fields"]
    assert "externalIds" in built.params["fields"]