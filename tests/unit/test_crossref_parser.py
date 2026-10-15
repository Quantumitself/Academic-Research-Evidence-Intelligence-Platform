"""Tests for the Crossref response parser."""

from __future__ import annotations

import pytest

from academic_platform.infrastructure.search_providers.crossref.parser import (
    CrossrefResponseParser,
)
from academic_platform.infrastructure.search_providers.errors import (
    ProviderResponseError,
)


def _parser() -> CrossrefResponseParser:
    return CrossrefResponseParser()


def _minimal_item(**overrides) -> dict:
    item = {
        "DOI": "10.1000/XYZ",
        "title": ["A Title"],
        "author": [
            {"given": "A.", "family": "Author"},
            {"given": "B.", "family": "Author"},
        ],
        "issued": {"date-parts": [[2020, 1, 1]]},
        "container-title": ["Journal of Things"],
        "URL": "https://doi.org/10.1000/xyz",
        "is-referenced-by-count": 12,
        "language": "en",
        "type": "journal-article",
    }
    item.update(overrides)
    return item


def test_parse_minimal_response() -> None:
    payload = {"message": {"total-results": 1, "items": [_minimal_item()]}}
    hits, total, cursor = _parser().parse(payload)
    assert total == 1
    assert cursor is None
    assert len(hits) == 1
    hit = hits[0]
    assert hit.provider_key == "crossref"
    assert hit.provider_identifier == "10.1000/xyz"
    assert hit.doi == "10.1000/xyz"
    assert hit.title == "A Title"
    assert hit.year == 2020
    assert hit.venue == "Journal of Things"
    assert hit.authors == ("A. Author", "B. Author")
    assert hit.citation_count == 12
    assert hit.language == "en"
    assert hit.url == "https://doi.org/10.1000/xyz"


def test_parse_raises_on_missing_message() -> None:
    with pytest.raises(ProviderResponseError):
        _parser().parse({})


def test_parse_raises_on_missing_items() -> None:
    with pytest.raises(ProviderResponseError):
        _parser().parse({"message": {}})


def test_parse_skips_malformed_items() -> None:
    payload = {
        "message": {
            "total-results": 2,
            "items": [
                _minimal_item(),
                "not a dict",
            ],
        }
    }
    hits, _, _ = _parser().parse(payload)
    assert len(hits) == 1


def test_parse_handles_missing_doi() -> None:
    payload = {
        "message": {
            "items": [
                _minimal_item(DOI=None),
            ]
        }
    }
    hits, _, _ = _parser().parse(payload)
    assert len(hits) == 1
    assert hits[0].doi is None


def test_parse_skips_items_without_identifier() -> None:
    payload = {
        "message": {
            "items": [
                _minimal_item(DOI="", URL=""),
            ]
        }
    }
    hits, _, _ = _parser().parse(payload)
    assert hits == []


def test_abstract_extraction_strips_jats() -> None:
    abstract = "<jats:p>An <jats:italic>important</jats:italic> finding.</jats:p>"
    payload = {"message": {"items": [_minimal_item(abstract=abstract)]}}
    hits, _, _ = _parser().parse(payload)
    assert "important" in hits[0].abstract
    assert "<" not in hits[0].abstract


def test_open_access_detection() -> None:
    license_block = [{"URL": "https://creativecommons.org/licenses/by/4.0/"}]
    payload = {"message": {"items": [_minimal_item(license=license_block)]}}
    hits, _, _ = _parser().parse(payload)
    assert hits[0].is_open_access is True


def test_open_access_default_false() -> None:
    payload = {"message": {"items": [_minimal_item()]}}
    hits, _, _ = _parser().parse(payload)
    assert hits[0].is_open_access is False


def test_year_from_published_print_when_issued_missing() -> None:
    item = _minimal_item()
    item.pop("issued")
    item["published-print"] = {"date-parts": [[2019, 6, 1]]}
    payload = {"message": {"items": [item]}}
    hits, _, _ = _parser().parse(payload)
    assert hits[0].year == 2019