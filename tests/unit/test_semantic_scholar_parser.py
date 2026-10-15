"""Tests for the Semantic Scholar response parser."""

from __future__ import annotations

import pytest

from academic_platform.infrastructure.search_providers.errors import (
    ProviderResponseError,
)
from academic_platform.infrastructure.search_providers.semantic_scholar.parser import (
    SemanticScholarResponseParser,
)


def _parser() -> SemanticScholarResponseParser:
    return SemanticScholarResponseParser()


def _minimal_item(**overrides) -> dict:
    item = {
        "paperId": "abc123",
        "externalIds": {"DOI": "10.1000/XYZ"},
        "title": "A Title",
        "abstract": "An abstract.",
        "year": 2020,
        "venue": "Journal of Things",
        "authors": [{"name": "A. Author"}, {"name": "B. Author"}],
        "openAccessPdf": {"url": "https://example.invalid/pdf"},
        "citationCount": 42,
    }
    item.update(overrides)
    return item


def test_parse_minimal_response() -> None:
    payload = {"total": 1, "data": [_minimal_item()]}
    hits, total, cursor = _parser().parse(payload)
    assert total == 1
    assert cursor is None
    assert len(hits) == 1
    hit = hits[0]
    assert hit.provider_key == "semantic_scholar"
    assert hit.provider_identifier == "abc123"
    assert hit.doi == "10.1000/xyz"
    assert hit.title == "A Title"
    assert hit.abstract == "An abstract."
    assert hit.year == 2020
    assert hit.venue == "Journal of Things"
    assert hit.authors == ("A. Author", "B. Author")
    assert hit.is_open_access is True
    assert hit.citation_count == 42


def test_parse_raises_on_missing_data() -> None:
    with pytest.raises(ProviderResponseError):
        _parser().parse({})


def test_parse_skips_malformed_items() -> None:
    payload = {"total": 2, "data": [_minimal_item(), "not a dict"]}
    hits, _, _ = _parser().parse(payload)
    assert len(hits) == 1


def test_missing_doi_still_produces_hit() -> None:
    payload = {
        "total": 1,
        "data": [_minimal_item(externalIds={})],
    }
    hits, _, _ = _parser().parse(payload)
    assert hits[0].doi is None
    assert hits[0].provider_identifier == "abc123"


def test_missing_paper_id_skips_item() -> None:
    payload = {
        "total": 1,
        "data": [_minimal_item(paperId="")],
    }
    hits, _, _ = _parser().parse(payload)
    assert hits == []


def test_open_access_default_false() -> None:
    payload = {
        "total": 1,
        "data": [_minimal_item(openAccessPdf=None)],
    }
    hits, _, _ = _parser().parse(payload)
    assert hits[0].is_open_access is False


def test_url_prefers_doi() -> None:
    payload = {"total": 1, "data": [_minimal_item()]}
    hits, _, _ = _parser().parse(payload)
    assert hits[0].url == "https://doi.org/10.1000/xyz"


def test_url_falls_back_to_semantic_scholar_page() -> None:
    payload = {
        "total": 1,
        "data": [_minimal_item(externalIds={})],
    }
    hits, _, _ = _parser().parse(payload)
    assert hits[0].url is not None
    assert "semanticscholar.org" in hits[0].url