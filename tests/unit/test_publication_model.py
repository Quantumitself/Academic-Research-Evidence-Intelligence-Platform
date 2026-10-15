"""Tests for the canonical publication model."""

from __future__ import annotations

import pytest

from academic_platform.application.publications.model import (
    CanonicalPublication,
    PublicationKey,
)


def test_key_from_doi_normalizes_prefix() -> None:
    key = PublicationKey.from_doi("https://doi.org/10.1000/XYZ")
    assert key.value == "doi:10.1000/xyz"


def test_key_from_provider() -> None:
    key = PublicationKey.from_provider("crossref", "10.1000/xyz")
    assert key.value == "crossref:10.1000/xyz"


def test_key_rejects_empty() -> None:
    with pytest.raises(ValueError):
        PublicationKey(value="")


def test_key_from_provider_rejects_empty() -> None:
    with pytest.raises(ValueError):
        PublicationKey.from_provider("", "id")


def test_with_provider_records_source() -> None:
    publication = CanonicalPublication(key="doi:x", doi="x")
    updated = publication.with_provider("crossref", "id-1")
    assert updated.source_providers == ("crossref",)
    assert updated.provider_identifiers == (("crossref", "id-1"),)


def test_with_provider_dedupes() -> None:
    publication = CanonicalPublication(key="doi:x", doi="x")
    first = publication.with_provider("crossref", "id-1")
    second = first.with_provider("crossref", "id-1")
    assert second.source_providers == ("crossref",)


def test_merge_fills_missing_fields() -> None:
    a = CanonicalPublication(key="doi:x", doi="x", title="T")
    b = CanonicalPublication(
        key="doi:x",
        doi="x",
        abstract="A",
        year=2020,
        source_providers=("openalex",),
    )
    merged = a.merge(b)
    assert merged.title == "T"
    assert merged.abstract == "A"
    assert merged.year == 2020
    assert merged.source_providers == ("openalex",)


def test_merge_prefers_existing_field() -> None:
    a = CanonicalPublication(key="doi:x", doi="x", title="A")
    b = CanonicalPublication(key="doi:x", doi="x", title="B")
    merged = a.merge(b)
    assert merged.title == "A"


def test_merge_unions_providers_and_identifiers() -> None:
    a = CanonicalPublication(
        key="doi:x",
        doi="x",
        source_providers=("crossref",),
        provider_identifiers=(("crossref", "id-1"),),
    )
    b = CanonicalPublication(
        key="doi:x",
        doi="x",
        source_providers=("openalex",),
        provider_identifiers=(("openalex", "W1"),),
    )
    merged = a.merge(b)
    assert merged.source_providers == ("crossref", "openalex")
    assert dict(merged.provider_identifiers) == {
        "crossref": "id-1",
        "openalex": "W1",
    }