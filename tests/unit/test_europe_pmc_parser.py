"""Tests for the Europe PMC response parser."""

from __future__ import annotations

import pytest

from academic_platform.infrastructure.search_providers.errors import (
    ProviderResponseError,
)
from academic_platform.infrastructure.search_providers.europe_pmc.parser import (
    EuropePmcResponseParser,
)


def _parser() -> EuropePmcResponseParser:
    return EuropePmcResponseParser()


def _minimal_item(**overrides) -> dict:
    item = {
        "id": "12345678",
        "pmid": "12345678",
        "pmcid": "PMC12345678",
        "doi": "10.1000/XYZ",
        "title": "A Title",
        "abstractText": "An abstract.",
        "authorString": "Author A, Author B",
        "pubYear": "2020",
        "journalInfo": {"journal": {"title": "Journal of Things"}},
        "isOpenAccess": "Y",
        "citedByCount": 42,
        "language": "eng",
    }
    item.update(overrides)
    return item


def test_parse_minimal_response() -> None:
    payload = {
        "hitCount": 1,
        "nextCursorMark": "next-cursor",
        "resultList": {"result": [_minimal_item()]},
    }
    hits, total, next_cursor = _parser().parse(payload)
    assert total == 1
    assert next_cursor == "next-cursor"
    assert len(hits) == 1
    hit = hits[0]
    assert hit.provider_key == "europe_pmc"
    assert hit.provider_identifier == "12345678"
    assert hit.doi == "10.1000/xyz"
    assert hit.title == "A Title"
    assert hit.abstract == "An abstract."
    assert hit.year == 2020
    assert hit.venue == "Journal of Things"
    assert hit.authors == ("Author A", "Author B")
    assert hit.is_open_access is True
    assert hit.citation_count == 42
    assert hit.language == "eng"


def test_parse_raises_on_missing_result_list() -> None:
    with pytest.raises(ProviderResponseError):
        _parser().parse({})


def test_parse_raises_on_missing_results() -> None:
    with pytest.raises(ProviderResponseError):
        _parser().parse({"resultList": {}})


def test_parse_skips_malformed_items() -> None:
    payload = {
        "hitCount": 2,
        "resultList": {"result": [_minimal_item(), "not a dict"]},
    }
    hits, _, _ = _parser().parse(payload)
    assert len(hits) == 1


def test_missing_doi_still_produces_hit() -> None:
    payload = {
        "hitCount": 1,
        "resultList": {"result": [_minimal_item(doi=None)]},
    }
    hits, _, _ = _parser().parse(payload)
    assert hits[0].doi is None
    assert hits[0].provider_identifier == "12345678"


def test_author_string_parsing() -> None:
    payload = {
        "hitCount": 1,
        "resultList": {"result": [_minimal_item(authorString="A, B, C")]},
    }
    hits, _, _ = _parser().parse(payload)
    assert hits[0].authors == ("A", "B", "C")


def test_author_string_ignores_et_al() -> None:
    payload = {
        "hitCount": 1,
        "resultList": {"result": [_minimal_item(authorString="A, B, et al.")]},
    }
    hits, _, _ = _parser().parse(payload)
    assert hits[0].authors == ("A", "B")


def test_author_list_fallback() -> None:
    item = _minimal_item(authorString="")
    item["authorList"] = {
        "author": [
            {"fullName": "A. Author"},
            {"collectiveName": "Consortium"},
        ]
    }
    payload = {"hitCount": 1, "resultList": {"result": [item]}}
    hits, _, _ = _parser().parse(payload)
    assert hits[0].authors == ("A. Author", "Consortium")


def test_open_access_yes_detection() -> None:
    payload = {
        "hitCount": 1,
        "resultList": {"result": [_minimal_item(isOpenAccess="Y")]},
    }
    hits, _, _ = _parser().parse(payload)
    assert hits[0].is_open_access is True


def test_open_access_default_false() -> None:
    payload = {
        "hitCount": 1,
        "resultList": {"result": [_minimal_item(isOpenAccess="N")]},
    }
    hits, _, _ = _parser().parse(payload)
    assert hits[0].is_open_access is False


def test_url_prefers_doi() -> None:
    payload = {
        "hitCount": 1,
        "resultList": {"result": [_minimal_item()]},
    }
    hits, _, _ = _parser().parse(payload)
    assert hits[0].url == "https://doi.org/10.1000/xyz"


def test_url_falls_back_to_europepmc() -> None:
    payload = {
        "hitCount": 1,
        "resultList": {"result": [_minimal_item(doi=None)]},
    }
    hits, _, _ = _parser().parse(payload)
    assert hits[0].url is not None
    assert "europepmc.org" in hits[0].url