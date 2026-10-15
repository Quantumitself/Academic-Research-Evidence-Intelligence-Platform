"""Tests for the publication normalizer."""

from __future__ import annotations

import pytest

from academic_platform.application.publications.errors import (
    PublicationKeyError,
    PublicationNormalizationError,
)
from academic_platform.application.publications.normalizer import (
    PublicationNormalizer,
)
from academic_platform.infrastructure.search_providers.adapter import (
    SearchHit,
)


def _hit(**overrides) -> SearchHit:
    defaults = {
        "provider_key": "crossref",
        "provider_identifier": "10.1000/xyz",
        "title": "A Title",
        "doi": "10.1000/XYZ",
        "authors": ("A. Author",),
        "year": 2020,
    }
    defaults.update(overrides)
    return SearchHit(**defaults)


def test_normalize_hit_with_doi() -> None:
    normalizer = PublicationNormalizer()
    publication = normalizer.normalize_hit(_hit())
    assert publication.key == "doi:10.1000/xyz"
    assert publication.doi == "10.1000/xyz"
    assert publication.title == "A Title"
    assert publication.year == 2020
    assert publication.source_providers == ("crossref",)
    assert dict(publication.provider_identifiers) == {"crossref": "10.1000/xyz"}


def test_normalize_hit_without_doi_uses_provider_key() -> None:
    normalizer = PublicationNormalizer()
    publication = normalizer.normalize_hit(_hit(doi=None))
    assert publication.key == "crossref:10.1000/xyz"
    assert publication.doi is None


def test_normalize_rejects_non_hit() -> None:
    normalizer = PublicationNormalizer()
    with pytest.raises(PublicationNormalizationError):
        normalizer.normalize_hit({"provider_key": "x"})  # type: ignore[arg-type]


def test_normalize_rejects_hit_without_identifier() -> None:
    normalizer = PublicationNormalizer()
    with pytest.raises(PublicationKeyError):
        normalizer.normalize_hit(
            SearchHit(provider_key="crossref", provider_identifier="", doi=None)
        )


def test_normalize_batch_preserves_order() -> None:
    normalizer = PublicationNormalizer()
    hits = [
        _hit(doi="10.1000/one", title="First"),
        _hit(doi="10.1000/two", title="Second"),
    ]
    result = normalizer.normalize(hits)
    assert result.publication_count == 2
    assert result.publications[0].title == "First"
    assert result.publications[1].title == "Second"


def test_normalize_batch_reports_skipped() -> None:
    normalizer = PublicationNormalizer()
    hits = [
        _hit(),
        SearchHit(provider_key="crossref", provider_identifier="", doi=None),
    ]
    result = normalizer.normalize(hits)
    assert result.publication_count == 1
    assert result.skipped_count == 1
    assert result.input_count == 2


def test_normalize_doi_normalization() -> None:
    normalizer = PublicationNormalizer()
    publication = normalizer.normalize_hit(
        _hit(doi="https://doi.org/10.1000/ABC")
    )
    assert publication.doi == "10.1000/abc"
    assert publication.key == "doi:10.1000/abc"