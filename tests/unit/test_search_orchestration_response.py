"""Tests for the orchestration response value objects."""

from __future__ import annotations

from academic_platform.application.search_orchestration.response import (
    SearchOrchestrationResponse,
    SourceOutcome,
    SourceOutcomeStatus,
)


def test_response_counts() -> None:
    response = SearchOrchestrationResponse(
        query="x",
        scope="remote",
        outcomes=(
            SourceOutcome(
                source_key="a",
                provider_key="a",
                display_name="A",
                status=SourceOutcomeStatus.OK,
                result_count=3,
            ),
            SourceOutcome(
                source_key="b",
                provider_key="b",
                display_name="B",
                status=SourceOutcomeStatus.FAILED,
            ),
        ),
    )
    assert response.success_count == 1
    assert response.failure_count == 1
    assert response.total_results == 3


def test_response_empty_defaults() -> None:
    response = SearchOrchestrationResponse(query="x", scope="remote")
    assert response.outcomes == ()
    assert response.hits == ()
    assert response.publications == ()
    assert response.session_id is None
    assert response.partial is False