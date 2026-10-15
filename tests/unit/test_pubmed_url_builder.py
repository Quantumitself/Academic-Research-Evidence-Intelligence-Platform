"""Tests for the PubMed URL builder."""

from __future__ import annotations

from academic_platform.infrastructure.search_providers.adapter import (
    SearchRequest,
)
from academic_platform.infrastructure.search_providers.pubmed.url_builder import (
    PubMedUrlBuilder,
)


def _builder() -> PubMedUrlBuilder:
    return PubMedUrlBuilder(
        base_url="https://eutils.ncbi.nlm.nih.gov",
        search_endpoint="entrez/eutils/esearch.fcgi",
        summary_endpoint="entrez/eutils/esummary.fcgi",
        fetch_endpoint="entrez/eutils/efetch.fcgi",
    )


def test_search_endpoint_url() -> None:
    builder = _builder()
    assert (
        builder.search_endpoint_url
        == "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    )


def test_summary_endpoint_url() -> None:
    builder = _builder()
    assert (
        builder.summary_endpoint_url
        == "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
    )


def test_fetch_endpoint_url() -> None:
    builder = _builder()
    assert (
        builder.fetch_endpoint_url
        == "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
    )


def test_search_request_params() -> None:
    builder = _builder()
    built = builder.build_search(SearchRequest(query="ml", limit=25, offset=50))
    assert built.params["db"] == "pubmed"
    assert built.params["retmode"] == "json"
    assert built.params["term"] == "ml"
    assert built.params["retmax"] == "25"
    assert built.params["retstart"] == "50"


def test_year_range_maps_to_dates() -> None:
    builder = _builder()
    built = builder.build_search(SearchRequest(query="x", year_from=2010, year_to=2020))
    assert built.params["mindate"] == "2010"
    assert built.params["maxdate"] == "2020"
    assert built.params["datetype"] == "pdat"


def test_year_from_only() -> None:
    builder = _builder()
    built = builder.build_search(SearchRequest(query="x", year_from=2010))
    assert built.params["mindate"] == "2010"
    assert "maxdate" not in built.params


def test_year_to_only() -> None:
    builder = _builder()
    built = builder.build_search(SearchRequest(query="x", year_to=2020))
    assert built.params["maxdate"] == "2020"
    assert "mindate" not in built.params


def test_summary_request() -> None:
    builder = _builder()
    built = builder.build_summary(["123", "456"])
    assert built.params["id"] == "123,456"
    assert built.params["db"] == "pubmed"
    assert built.params["retmode"] == "json"


def test_fetch_abstracts_request() -> None:
    builder = _builder()
    built = builder.build_fetch_abstracts(["123"])
    assert built.params["id"] == "123"
    assert built.params["rettype"] == "abstract"
    assert built.params["retmode"] == "json"


def test_limit_clamped_to_provider_maximum() -> None:
    builder = _builder()
    built = builder.build_search(SearchRequest(query="x", limit=50000))
    assert built.params["retmax"] == "10000"