"""Typed errors for the saved-search service."""

from __future__ import annotations


class SavedSearchError(RuntimeError):
    """Base class for saved-search failures."""


class SavedSearchNotFoundError(SavedSearchError):
    """Raised when a saved search cannot be found by its key."""