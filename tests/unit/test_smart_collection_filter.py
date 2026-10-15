"""Tests for the smart-collection filter model."""

from __future__ import annotations

import pytest

from academic_platform.application.smart_collections.errors import (
    SmartCollectionFilterError,
)
from academic_platform.application.smart_collections.filter import (
    SmartCollectionFilter,
)


def test_empty_payload_yields_empty_filter() -> None:
    filter_state = SmartCollectionFilter.from_json(None)
    assert filter_state.is_empty


def test_empty_string_yields_empty_filter() -> None:
    assert SmartCollectionFilter.from_json("   ").is_empty


def test_invalid_json_raises() -> None:
    with pytest.raises(SmartCollectionFilterError):
        SmartCollectionFilter.from_json("{not json}")


def test_non_object_payload_raises() -> None:
    with pytest.raises(SmartCollectionFilterError):
        SmartCollectionFilter.from_json("[1, 2, 3]")


def test_unknown_field_rejected() -> None:
    with pytest.raises(SmartCollectionFilterError) as exc:
        SmartCollectionFilter.from_json('{"unknown": 1}')
    assert "unknown" in str(exc.value)


def test_year_range_parsed() -> None:
    filter_state = SmartCollectionFilter.from_json(
        '{"year_from": 2010, "year_to": 2020}'
    )
    assert filter_state.year_from == 2010
    assert filter_state.year_to == 2020


def test_year_range_inversion_rejected() -> None:
    with pytest.raises(SmartCollectionFilterError):
        SmartCollectionFilter.from_json(
            '{"year_from": 2020, "year_to": 2010}'
        )


def test_year_from_as_string_parsed() -> None:
    filter_state = SmartCollectionFilter.from_json('{"year_from": "2010"}')
    assert filter_state.year_from == 2010


def test_processing_states_parsed() -> None:
    filter_state = SmartCollectionFilter.from_json(
        '{"processing_states": ["extracted", "indexed"]}'
    )
    assert filter_state.processing_states == frozenset({"extracted", "indexed"})


def test_extensions_normalized_to_lowercase() -> None:
    filter_state = SmartCollectionFilter.from_json(
        '{"extensions": [".PDF", ".EPUB"]}'
    )
    assert filter_state.extensions == frozenset({".pdf", ".epub"})


def test_storage_modes_parsed() -> None:
    filter_state = SmartCollectionFilter.from_json(
        '{"storage_modes": ["managed_copy"]}'
    )
    assert filter_state.storage_modes == frozenset({"managed_copy"})


def test_missing_boolean_parsed() -> None:
    filter_state = SmartCollectionFilter.from_json('{"missing": true}')
    assert filter_state.missing is True


def test_missing_boolean_rejects_non_boolean() -> None:
    with pytest.raises(SmartCollectionFilterError):
        SmartCollectionFilter.from_json('{"missing": "maybe"}')


def test_title_contains_parsed() -> None:
    filter_state = SmartCollectionFilter.from_json(
        '{"title_contains": "measurement"}'
    )
    assert filter_state.title_contains == "measurement"


def test_author_contains_parsed() -> None:
    filter_state = SmartCollectionFilter.from_json(
        '{"author_contains": "smith"}'
    )
    assert filter_state.author_contains == "smith"


def test_has_annotations_parsed() -> None:
    filter_state = SmartCollectionFilter.from_json('{"has_annotations": true}')
    assert filter_state.has_annotations is True


def test_has_doi_parsed() -> None:
    filter_state = SmartCollectionFilter.from_json('{"has_doi": false}')
    assert filter_state.has_doi is False


def test_to_dict_round_trip() -> None:
    filter_state = SmartCollectionFilter(
        year_from=2010,
        year_to=2020,
        processing_states=frozenset({"extracted"}),
        extensions=frozenset({".pdf"}),
        missing=False,
        title_contains="x",
        has_doi=True,
    )
    payload = filter_state.to_dict()
    restored = SmartCollectionFilter.from_dict(payload)
    assert restored.year_from == 2010
    assert restored.year_to == 2020
    assert restored.processing_states == frozenset({"extracted"})
    assert restored.extensions == frozenset({".pdf"})
    assert restored.missing is False
    assert restored.title_contains == "x"
    assert restored.has_doi is True