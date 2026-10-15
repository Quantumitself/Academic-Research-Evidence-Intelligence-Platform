"""Tests for the OpenAlex URL builder."""

from __future__ import annotations

from academic_platform.infrastructure.search_providers.adapter import (
    SearchRequest,
)
from academic_platform.infrastructure.search_providers.openalex.url_builder import (
    OpenAlexUrlBuilder,
)


def _builder(contact_email: str | None = None) -> OpenAlexUrlBuilder:
    return OpenAlexUrlBuilder(
        base_url="https://api.openalex.org",
        endpoint="works",
        contact_email=contact_email,
    )


def test_endpoint_url() -> None:
    builder = _builder()
    assert builder.endpoint_url == "https://api.openalex.org/works"


def test_query_and_pagination() -> None:
    builder = _builder()
    built = builder.build(SearchRequest(query="ml", limit=25, offset=0))
    assert built.params["search"] == "ml"
    assert built.params["per-page"] == "25"
    assert built.params["page"] == "1"


def test_offset_translated_to_page() -> None:
    builder = _builder()
    built = builder.build(SearchRequest(query="ml", limit=25, offset=50))
    assert built.params["page"] == "3"


def test_cursor_overrides_page() -> None:
    builder = _builder()
    built = builder.build(SearchRequest(query="ml", cursor="cursor-abc"))
    assert built.params["cursor"] == "cursor-abc"
    assert "page" not in built.params


def test_default_sort_omits_parameter() -> None:
    builder = _builder()
    built = builder.build(SearchRequest(query="ml"))
    assert "sort" not in built.params


def test_date_desc_sort() -> None:
    builder = _builder()
    built = builder.build(SearchRequest(query="ml", sort="date_desc"))
    assert built.params["sort"] == "publication_date:desc"


def test_date_asc_sort() -> None:
    builder = _builder()
    built = builder.build(SearchRequest(query="ml", sort="date_asc"))
    assert built.params["sort"] == "publication_date:asc"


def test_year_range_filters() -> None:
    builder = _builder()
    built = builder.build(
        SearchRequest(query="ml", year_from=2010, year_to=2020)
    )
    filters = built.params["filter"]
    assert "from_publication_date:2010-01-01" in filters
    assert "to_publication_date:2020-12-31" in filters


def test_doi_filter_lowercased() -> None:
    builder = _builder()
    built = builder.build(SearchRequest(doi="10.1000/XYZ"))
    assert "doi:10.1000/xyz" in built.params["filter"]


def test_open_access_filter() -> None:
    builder = _builder()
    built = builder.build(SearchRequest(query="ml", open_access_only=True))
    assert "is_oa:true" in built.params["filter"]


def test_language_filter() -> None:
    builder = _builder()
    built = builder.build(SearchRequest(query="ml", language="en"))
    assert "language:en" in built.params["filter"]


def test_contact_email_included_when_configured() -> None:
    builder = _builder(contact_email="user@example.invalid")
    built = builder.build(SearchRequest(query="ml"))
    assert built.params["mailto"] == "user@example.invalid"


def test_contact_email_omitted_when_absent() -> None:
    builder = _builder()
    built = builder.build(SearchRequest(query="ml"))
    assert "mailto" not in built.params


def test_limit_clamped_to_provider_maximum() -> None:
    builder = _builder()
    built = builder.build(SearchRequest(query="ml", limit=1000))
    assert built.params["per-page"] == "200"