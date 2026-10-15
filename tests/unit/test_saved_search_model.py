"""Tests for the saved-search model."""

from __future__ import annotations

import pytest

from academic_platform.application.saved_searches.model import SavedSearch


def test_defaults() -> None:
    search = SavedSearch(key="a")
    assert search.scope == "all"
    assert search.filters == {}
    assert search.source_keys == ()


def test_rejects_empty_key() -> None:
    with pytest.raises(ValueError):
        SavedSearch(key="")


def test_rejects_bad_scope() -> None:
    with pytest.raises(ValueError):
        SavedSearch(key="a", scope="bogus")


def test_display_label_prefers_name() -> None:
    search = SavedSearch(key="a", name="My search", query_text="ml")
    assert search.display_label == "My search"


def test_display_label_falls_back_to_query() -> None:
    search = SavedSearch(key="a", query_text="ml")
    assert search.display_label == "ml"


def test_display_label_falls_back_to_key() -> None:
    search = SavedSearch(key="a")
    assert search.display_label == "a"