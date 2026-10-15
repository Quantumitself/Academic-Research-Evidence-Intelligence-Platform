"""Tests for the Crossref URL builder."""

from __future__ import annotations

from academic_platform.infrastructure.search_providers.adapter import (
    SearchRequest,
)
from academic_platform.infrastructure.search_providers.crossref.url_builder import (
    CrossrefUrlBuilder,
)


def _builder() -> CrossrefUrlBuilder:
    return CrossrefUrlBuilder(
        base_url="https://api.crossref.org",
        endpoint="works",
    )


def test_endpoint_url() -> None:
    builder = _builder()
    assert builder.endpoint_url == "https://api.crossref.org/works"


def test_query_and_pagination() -> None:
    builder = _builder()
    built = builder.build(SearchRequest(query="machine learning", limit=25, offset=50))
    assert built.url == "https://api.crossref.org/works"
    assert built.params["query"] == "machine learning"
    assert built.params["rows"] == "25"
    assert built.params["offset"] == "50"


def test_default_sort_is_relevance() -> None:
    builder = _builder()
    built = builder.build(SearchRequest(query="x"))
    assert built.params["sort"] == "relevance"
    assert built.params["order"] == "desc"


def test_date_desc_sort() -> None:
    builder = _builder()
    built = builder.build(SearchRequest(query="x", sort="date_desc"))
    assert built.params["sort"] == "deposited"
    assert built.params["order"] == "desc"
    assert built.sort_descending is True


def test_date_asc_sort() -> None:
    builder = _builder()
    built = builder.build(SearchRequest(query="x", sort="date_asc"))
    assert built.params["sort"] == "deposited"
    assert built.params["order"] == "asc"
    assert built.sort_descending is False


def test_year_range_filters() -> None:
    builder = _builder()
    built = builder.build(SearchRequest(query="x", year_from=2010, year_to=2020))
    filters = built.params["filter"]
    assert "from-pub-date:2010-01-01" in filters
    assert "until-pub-date:2020-12-31" in filters


def test_doi_filter() -> None:
    builder = _builder()
    built = builder.build(SearchRequest(doi="10.1000/xyz"))
    assert "doi:10.1000/xyz" in built.params["filter"]


def test_language_filter() -> None:
    builder = _builder()
    built = builder.build(SearchRequest(query="x", language="en"))
    assert "language:en" in built.params["filter"]


def test_open_access_filter_not_pushed_down() -> None:
    builder = _builder()
    built = builder.build(SearchRequest(query="x", open_access_only=True))
    assert "filter" not in built.params


def test_limit_clamped_to_provider_maximum() -> None:
    builder = _builder()
    built = builder.build(SearchRequest(query="x", limit=5000))
    assert built.params["rows"] == "1000"