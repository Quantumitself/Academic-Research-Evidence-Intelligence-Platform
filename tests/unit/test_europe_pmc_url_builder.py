"""Tests for the Europe PMC URL builder."""

from __future__ import annotations

from academic_platform.infrastructure.search_providers.adapter import (
    SearchRequest,
)
from academic_platform.infrastructure.search_providers.europe_pmc.url_builder import (
    EuropePmcUrlBuilder,
)


def _builder() -> EuropePmcUrlBuilder:
    return EuropePmcUrlBuilder(
        base_url="https://www.ebi.ac.uk",
        endpoint="europepmc/webservices/rest/search",
    )


def test_endpoint_url() -> None:
    builder = _builder()
    assert (
        builder.endpoint_url
        == "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
    )


def test_query_only() -> None:
    builder = _builder()
    built = builder.build(SearchRequest(query="machine learning"))
    assert built.params["query"] == "(machine learning)"
    assert built.params["format"] == "json"
    assert built.params["resultType"] == "core"


def test_doi_clause() -> None:
    builder = _builder()
    built = builder.build(SearchRequest(doi="10.1000/XYZ"))
    assert 'DOI:"10.1000/xyz"' in built.params["query"]


def test_year_range_clause() -> None:
    builder = _builder()
    built = builder.build(SearchRequest(query="x", year_from=2010, year_to=2020))
    assert "FIRST_PDATE:[2010-01-01 TO 2020-12-31]" in built.params["query"]


def test_year_from_only_clause() -> None:
    builder = _builder()
    built = builder.build(SearchRequest(query="x", year_from=2010))
    assert "FIRST_PDATE:[2010-01-01 TO 3000-12-31]" in built.params["query"]


def test_year_to_only_clause() -> None:
    builder = _builder()
    built = builder.build(SearchRequest(query="x", year_to=2020))
    assert "FIRST_PDATE:[1000-01-01 TO 2020-12-31]" in built.params["query"]


def test_language_clause() -> None:
    builder = _builder()
    built = builder.build(SearchRequest(query="x", language="en"))
    assert 'LANG:"en"' in built.params["query"]


def test_open_access_clause() -> None:
    builder = _builder()
    built = builder.build(SearchRequest(query="x", open_access_only=True))
    assert "OPEN_ACCESS:Y" in built.params["query"]


def test_cursor_emitted_when_supplied() -> None:
    builder = _builder()
    built = builder.build(SearchRequest(query="x", cursor="cursor-abc"))
    assert built.params["cursorMark"] == "cursor-abc"


def test_cursor_absent_when_not_supplied() -> None:
    builder = _builder()
    built = builder.build(SearchRequest(query="x"))
    assert "cursorMark" not in built.params


def test_sort_date_desc() -> None:
    builder = _builder()
    built = builder.build(SearchRequest(query="x", sort="date_desc"))
    assert built.params["sort"] == "P_PDATE_D desc"


def test_sort_date_asc() -> None:
    builder = _builder()
    built = builder.build(SearchRequest(query="x", sort="date_asc"))
    assert built.params["sort"] == "P_PDATE_D asc"


def test_limit_clamped_to_provider_maximum() -> None:
    builder = _builder()
    built = builder.build(SearchRequest(query="x", limit=5000))
    assert built.params["pageSize"] == "1000"


def test_empty_request_yields_empty_query() -> None:
    builder = _builder()
    built = builder.build(SearchRequest())
    assert built.params["query"] == ""