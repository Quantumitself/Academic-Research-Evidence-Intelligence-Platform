"""Tests for the OpenAlex response parser."""

from __future__ import annotations

import pytest

from academic_platform.infrastructure.search_providers.errors import (
    ProviderResponseError,
)
from academic_platform.infrastructure.search_providers.openalex.parser import (
    OpenAlexResponseParser,
)


def _parser() -> OpenAlexResponseParser:
    return OpenAlexResponseParser()


def _minimal_item(**overrides) -> dict:
    item = {
        "id": "https://openalex.org/W1234567890",
        "doi": "https://doi.org/10.1000/XYZ",
        "title": "A Title",
        "publication_year": 2020,
        "authorships": [
            {"author": {"display_name": "A. Author"}},
            {"author": {"display_name": "B. Author"}},
        ],
        "primary_location": {"source": {"display_name": "Journal of Things"}},
        "open_access": {"is_oa": True},
        "cited_by_count": 42,
        "language": "en",
        "type": "article",
        "relevance_score": 1.5,
    }
    item.update(overrides)
    return item


def test_parse_minimal_response() -> None:
    payload = {
        "meta": {"count": 1, "next_cursor": "cursor-abc"},
        "results": [_minimal_item()],
    }
    hits, total, next_cursor = _parser().parse(payload)
    assert total == 1
    assert next_cursor == "cursor-abc"
    assert len(hits) == 1
    hit = hits[0]
    assert hit.provider_key == "openalex"
    assert hit.provider_identifier == "W1234567890"
    assert hit.doi == "10.1000/xyz"
    assert hit.title == "A Title"
    assert hit.year == 2020
    assert hit.venue == "Journal of Things"
    assert hit.authors == ("A. Author", "B. Author")
    assert hit.is_open_access is True
    assert hit.citation_count == 42
    assert hit.language == "en"
    assert hit.score == 1.5


def test_parse_raises_on_missing_results() -> None:
    with pytest.raises(ProviderResponseError):
        _parser().parse({})


def test_parse_returns_no_cursor_when_absent() -> None:
    payload = {"meta": {"count": 0}, "results": []}
    _, total, next_cursor = _parser().parse(payload)
    assert total == 0
    assert next_cursor is None


def test_parse_skips_malformed_items() -> None:
    payload = {
        "meta": {"count": 2},
        "results": [_minimal_item(), "not a dict"],
    }
    hits, _, _ = _parser().parse(payload)
    assert len(hits) == 1


def test_abstract_reconstructed_from_inverted_index() -> None:
    inverted = {
        "An": [0],
        "important": [1],
        "finding.": [2],
    }
    payload = {
        "meta": {"count": 1},
        "results": [_minimal_item(abstract_inverted_index=inverted)],
    }
    hits, _, _ = _parser().parse(payload)
    assert hits[0].abstract == "An important finding."


def test_venue_falls_back_to_host_venue() -> None:
    item = _minimal_item()
    item.pop("primary_location")
    item["host_venue"] = {"display_name": "Legacy Venue"}
    payload = {"meta": {"count": 1}, "results": [item]}
    hits, _, _ = _parser().parse(payload)
    assert hits[0].venue == "Legacy Venue"


def test_open_access_default_false() -> None:
    payload = {
        "meta": {"count": 1},
        "results": [_minimal_item(open_access={"is_oa": False})],
    }
    hits, _, _ = _parser().parse(payload)
    assert hits[0].is_open_access is False


def test_missing_doi_still_produces_hit() -> None:
    payload = {
        "meta": {"count": 1},
        "results": [_minimal_item(doi=None)],
    }
    hits, _, _ = _parser().parse(payload)
    assert hits[0].doi is None
    assert hits[0].provider_identifier == "W1234567890"


def test_url_prefers_doi_when_present() -> None:
    payload = {"meta": {"count": 1}, "results": [_minimal_item()]}
    hits, _, _ = _parser().parse(payload)
    assert hits[0].url == "https://doi.org/10.1000/XYZ"


def test_url_falls_back_to_openalex_id() -> None:
    payload = {
        "meta": {"count": 1},
        "results": [_minimal_item(doi=None)],
    }
    hits, _, _ = _parser().parse(payload)
    assert hits[0].url == "https://openalex.org/W1234567890"