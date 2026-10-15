"""Tests for the orchestration request value objects."""

from __future__ import annotations

import pytest

from academic_platform.application.search_orchestration.request import (
    SearchOrchestrationRequest,
    SourceSelection,
)
from academic_platform.infrastructure.search_providers.adapter import (
    SearchRequest,
)


def test_source_selection_defaults_all_enabled() -> None:
    selection = SourceSelection()
    assert selection.all_enabled is True
    assert selection.source_keys == ()


def test_source_selection_rejects_empty_when_not_all_enabled() -> None:
    with pytest.raises(ValueError):
        SourceSelection(all_enabled=False, source_keys=())


def test_source_selection_accepts_explicit_keys() -> None:
    selection = SourceSelection(all_enabled=False, source_keys=("crossref",))
    assert selection.source_keys == ("crossref",)


def test_request_defaults() -> None:
    request = SearchOrchestrationRequest(
        search_request=SearchRequest(query="ml"),
    )
    assert request.max_concurrency == 4
    assert request.record_session is True
    assert request.session_scope == "remote"


def test_request_rejects_low_concurrency() -> None:
    with pytest.raises(ValueError):
        SearchOrchestrationRequest(
            search_request=SearchRequest(query="ml"),
            max_concurrency=0,
        )


def test_request_rejects_high_concurrency() -> None:
    with pytest.raises(ValueError):
        SearchOrchestrationRequest(
            search_request=SearchRequest(query="ml"),
            max_concurrency=17,
        )


def test_request_rejects_empty_search() -> None:
    with pytest.raises(ValueError):
        SearchOrchestrationRequest(search_request=SearchRequest())


def test_request_rejects_bad_scope() -> None:
    with pytest.raises(ValueError):
        SearchOrchestrationRequest(
            search_request=SearchRequest(query="ml"),
            session_scope="bogus",
        )