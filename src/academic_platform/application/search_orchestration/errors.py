"""Typed errors for the search orchestration subsystem."""

from __future__ import annotations


class SearchOrchestrationError(RuntimeError):
    """Base class for search orchestration failures."""


class SearchOrchestrationConfigurationError(SearchOrchestrationError):
    """Raised when the orchestration request is misconfigured.

    Covers an empty source selection, an empty request, and invalid
    concurrency settings.
    """