"""Tests for the orchestration-backed search controller."""

from __future__ import annotations

from academic_platform.application.search_orchestration.response import (
    SearchOrchestrationResponse,
    SourceOutcome,
    SourceOutcomeStatus,
)
from academic_platform.application.publications.model import (
    CanonicalPublication,
)
from academic_platform.ui.pages.search.orchestration_controller import (
    OrchestrationSearchController,
)
from academic_platform.ui.pages.search.search_controller import (
    SourceStatus,
)


class _StubOrchestrator:
    def __init__(self, response: SearchOrchestrationResponse) -> None:
        self._response = response
        self.calls = 0

    def execute(self, request, *, saved_query_id=None):
        self.calls += 1
        return self._response


def _controller(response: SearchOrchestrationResponse):
    orchestrator = _StubOrchestrator(response)
    controller = OrchestrationSearchController(
        orchestrator_factory=lambda: orchestrator,
        source_service_factory=lambda: orchestrator,
    )
    return controller, orchestrator


def test_search_local_reports_unavailable() -> None:
    response = SearchOrchestrationResponse(query="x", scope="remote")
    controller, _ = _controller(response)
    local = controller.search_local("x")
    assert local.entries == ()
    assert local.source_reports
    assert local.source_reports[0].status is SourceStatus.SKIPPED


def test_search_remote_converts_publications() -> None:
    publication = CanonicalPublication(
        key="doi:x",
        doi="x",
        title="T",
        authors=("A", "B"),
        year=2020,
        venue="J",
        source_providers=("crossref",),
    )
    response = SearchOrchestrationResponse(
        query="x",
        scope="remote",
        outcomes=(
            SourceOutcome(
                source_key="crossref",
                provider_key="crossref",
                display_name="Crossref",
                status=SourceOutcomeStatus.OK,
                result_count=1,
            ),
        ),
        publications=(publication,),
    )
    controller, _ = _controller(response)
    result = controller.search_remote("x")
    assert len(result.entries) == 1
    entry = result.entries[0]
    assert entry.identifier == "doi:x"
    assert entry.title == "T"
    assert "A, B" in entry.subtitle
    assert "2020" in entry.subtitle
    assert result.source_reports[0].status is SourceStatus.OK


def test_search_remote_partial_flag_propagates() -> None:
    response = SearchOrchestrationResponse(
        query="x",
        scope="remote",
        outcomes=(
            SourceOutcome(
                source_key="a",
                provider_key="a",
                display_name="A",
                status=SourceOutcomeStatus.OK,
            ),
            SourceOutcome(
                source_key="b",
                provider_key="b",
                display_name="B",
                status=SourceOutcomeStatus.FAILED,
                message="boom",
            ),
        ),
        partial=True,
    )
    controller, _ = _controller(response)
    result = controller.search_remote("x")
    assert result.partial is True
    assert result.message
    statuses = {report.source_label: report.status for report in result.source_reports}
    assert statuses["A"] is SourceStatus.OK
    assert statuses["B"] is SourceStatus.FAILED


def test_search_remote_orchestrator_failure() -> None:
    def failing_factory():
        raise RuntimeError("boom")

    controller = OrchestrationSearchController(
        orchestrator_factory=failing_factory,
        source_service_factory=failing_factory,
    )
    result = controller.search_remote("x")
    assert result.entries == ()
    assert result.source_reports
    assert result.source_reports[0].status is SourceStatus.FAILED


def test_search_remote_empty_outcomes_ok() -> None:
    response = SearchOrchestrationResponse(query="x", scope="remote")
    controller, _ = _controller(response)
    result = controller.search_remote("x")
    assert result.entries == ()
    assert result.source_reports == ()