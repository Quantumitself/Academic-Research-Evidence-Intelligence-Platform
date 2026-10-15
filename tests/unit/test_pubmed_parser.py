"""Tests for the PubMed response parser."""

from __future__ import annotations

import pytest

from academic_platform.infrastructure.search_providers.errors import (
    ProviderResponseError,
)
from academic_platform.infrastructure.search_providers.pubmed.parser import (
    PubMedResponseParser,
)


def _parser() -> PubMedResponseParser:
    return PubMedResponseParser()


def test_parse_search_returns_ids_and_total() -> None:
    payload = {
        "esearchresult": {
            "count": "3",
            "idlist": ["111", "222", "333"],
        }
    }
    identifiers, total = _parser().parse_search(payload)
    assert identifiers == ["111", "222", "333"]
    assert total == 3


def test_parse_search_raises_on_missing_esearchresult() -> None:
    with pytest.raises(ProviderResponseError):
        _parser().parse_search({})


def test_parse_search_raises_on_missing_idlist() -> None:
    with pytest.raises(ProviderResponseError):
        _parser().parse_search({"esearchresult": {"count": "0"}})


def _summary_entry(**overrides) -> dict:
    entry = {
        "uid": "111",
        "title": "A Title",
        "authors": [
            {"name": "Author A"},
            {"name": "Author B"},
        ],
        "pubdate": "2020 Jan",
        "fulljournalname": "Journal of Things",
        "articleids": [{"idtype": "doi", "value": "10.1000/XYZ"}],
        "lang": ["eng"],
        "pubtype": ["Journal Article"],
    }
    entry.update(overrides)
    return entry


def test_parse_summary_entry_order() -> None:
    payload = {
        "result": {
            "uids": ["111", "222"],
            "111": _summary_entry(uid="111", title="First"),
            "222": _summary_entry(uid="222", title="Second"),
        }
    }
    hits = _parser().parse_summary(payload, ["111", "222"])
    assert [hit.provider_identifier for hit in hits] == ["111", "222"]
    assert hits[0].title == "First"


def test_parse_summary_raises_on_error_key() -> None:
    payload = {"result": {"error": "invalid identifier"}}
    with pytest.raises(ProviderResponseError):
        _parser().parse_summary(payload, ["111"])


def test_summary_year_parsed_from_pubdate() -> None:
    payload = {"result": {"uids": ["111"], "111": _summary_entry()}}
    hits = _parser().parse_summary(payload, ["111"])
    assert hits[0].year == 2020


def test_summary_doi_parsed() -> None:
    payload = {"result": {"uids": ["111"], "111": _summary_entry()}}
    hits = _parser().parse_summary(payload, ["111"])
    assert hits[0].doi == "10.1000/xyz"


def test_summary_skips_missing_entry() -> None:
    payload = {"result": {"uids": ["111"]}}
    hits = _parser().parse_summary(payload, ["111"])
    assert hits == []


def test_parse_abstracts_simple_string() -> None:
    payload = {"result": {"uids": ["111"], "111": {"abstract": "Some text."}}}
    abstracts = _parser().parse_abstracts(payload)
    assert abstracts["111"] == "Some text."


def test_parse_abstracts_nested_array() -> None:
    payload = {
        "result": {
            "uids": ["111"],
            "111": {
                "abstracttext": [
                    {"label": "BACKGROUND", "text": "Background text."},
                    {"label": "METHODS", "text": "Methods text."},
                ]
            },
        }
    }
    abstracts = _parser().parse_abstracts(payload)
    assert "BACKGROUND: Background text." in abstracts["111"]
    assert "METHODS: Methods text." in abstracts["111"]


def test_parse_abstracts_strips_markup() -> None:
    payload = {
        "result": {"uids": ["111"], "111": {"abstract": "<b>Bold</b> text."}}
    }
    abstracts = _parser().parse_abstracts(payload)
    assert abstracts["111"] == "Bold text."


def test_merge_abstracts_populates_hits() -> None:
    payload = {"result": {"uids": ["111"], "111": _summary_entry()}}
    hits = _parser().parse_summary(payload, ["111"])
    merged = _parser().merge_abstracts(hits, {"111": "Abstract text."})
    assert merged[0].abstract == "Abstract text."


def test_merge_abstracts_leaves_missing_alone() -> None:
    payload = {"result": {"uids": ["111"], "111": _summary_entry()}}
    hits = _parser().parse_summary(payload, ["111"])
    merged = _parser().merge_abstracts(hits, {})
    assert merged[0].abstract == ""