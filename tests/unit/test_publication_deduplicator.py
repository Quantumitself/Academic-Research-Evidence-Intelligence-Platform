"""Tests for the publication deduplicator."""

from __future__ import annotations

from academic_platform.application.publications.deduplicator import (
    PublicationDeduplicator,
)
from academic_platform.application.publications.model import (
    CanonicalPublication,
)


def test_no_duplicates_preserved() -> None:
    dedup = PublicationDeduplicator()
    pubs = [
        CanonicalPublication(key="doi:a", doi="a"),
        CanonicalPublication(key="doi:b", doi="b"),
    ]
    result = dedup.deduplicate(pubs)
    assert result.publication_count == 2
    assert result.merged_count == 0


def test_duplicate_by_doi_merged() -> None:
    dedup = PublicationDeduplicator()
    pubs = [
        CanonicalPublication(key="doi:x", doi="x", title="T"),
        CanonicalPublication(key="crossref:1", doi="x", abstract="A"),
    ]
    result = dedup.deduplicate(pubs)
    assert result.publication_count == 1
    assert result.merged_count == 1
    merged = result.publications[0]
    assert merged.title == "T"
    assert merged.abstract == "A"


def test_duplicate_by_key_when_no_doi() -> None:
    dedup = PublicationDeduplicator()
    pubs = [
        CanonicalPublication(key="crossref:1", title="T"),
        CanonicalPublication(key="crossref:1", abstract="A"),
    ]
    result = dedup.deduplicate(pubs)
    assert result.publication_count == 1
    assert result.merged_count == 1


def test_order_of_first_occurrence_preserved() -> None:
    dedup = PublicationDeduplicator()
    pubs = [
        CanonicalPublication(key="doi:a", doi="a"),
        CanonicalPublication(key="doi:b", doi="b"),
        CanonicalPublication(key="doi:a", doi="a", abstract="A"),
    ]
    result = dedup.deduplicate(pubs)
    assert [pub.key for pub in result.publications] == ["doi:a", "doi:b"]


def test_merge_record_reports_source() -> None:
    dedup = PublicationDeduplicator()
    pubs = [
        CanonicalPublication(key="doi:x", doi="x", source_providers=("crossref",)),
        CanonicalPublication(
            key="doi:x", doi="x", source_providers=("openalex",)
        ),
    ]
    result = dedup.deduplicate(pubs)
    assert result.merged_count == 1
    record = result.merges[0]
    assert record.merged_providers == ("openalex",)


def test_provider_union_in_merged_result() -> None:
    dedup = PublicationDeduplicator()
    pubs = [
        CanonicalPublication(
            key="doi:x", doi="x", source_providers=("crossref",)
        ),
        CanonicalPublication(
            key="doi:x", doi="x", source_providers=("openalex",)
        ),
    ]
    result = dedup.deduplicate(pubs)
    assert result.publications[0].source_providers == ("crossref", "openalex")


def test_empty_input() -> None:
    dedup = PublicationDeduplicator()
    result = dedup.deduplicate([])
    assert result.publication_count == 0
    assert result.input_count == 0