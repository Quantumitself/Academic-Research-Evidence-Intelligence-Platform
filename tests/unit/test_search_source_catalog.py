"""Tests for the built-in search source catalog."""

from __future__ import annotations

from academic_platform.application.search_sources.catalog import (
    BUILTIN_SOURCES,
    builtin_source_keys,
    find_builtin,
)


def test_catalog_keys_sorted() -> None:
    keys = builtin_source_keys()
    assert keys == tuple(sorted(keys))
    assert len(keys) == len(set(keys))


def test_catalog_contains_expected_sources() -> None:
    keys = set(builtin_source_keys())
    assert {
        "crossref",
        "openalex",
        "semantic_scholar",
        "pubmed",
        "europe_pmc",
        "arxiv",
    } <= keys


def test_catalog_entries_are_builtin() -> None:
    for entry in BUILTIN_SOURCES:
        assert entry.config.source_type == "builtin"


def test_catalog_entries_use_https() -> None:
    for entry in BUILTIN_SOURCES:
        assert entry.config.base_url.startswith("https://")


def test_find_builtin_returns_expected() -> None:
    entry = find_builtin("crossref")
    assert entry is not None
    assert entry.config.provider_key == "crossref"


def test_find_builtin_unknown_returns_none() -> None:
    assert find_builtin("does-not-exist") is None