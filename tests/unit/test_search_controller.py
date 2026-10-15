"""Tests for the search controller protocol and its null implementation."""

from __future__ import annotations

from academic_platform.ui.pages.search.search_controller import (
    NullSearchController,
    SourceStatus,
)


def test_null_local_returns_empty_with_status() -> None:
    controller = NullSearchController()
    response = controller.search_local("test")
    assert response.query == "test"
    assert response.entries == ()
    assert response.source_reports
    assert response.source_reports[0].status is SourceStatus.SKIPPED
    assert response.message


def test_null_remote_returns_empty_with_status() -> None:
    controller = NullSearchController()
    response = controller.search_remote("test")
    assert response.query == "test"
    assert response.entries == ()
    assert response.source_reports
    assert response.source_reports[0].status is SourceStatus.SKIPPED


def test_null_controller_does_not_report_partial() -> None:
    controller = NullSearchController()
    assert controller.search_local("x").partial is False
    assert controller.search_remote("x").partial is False