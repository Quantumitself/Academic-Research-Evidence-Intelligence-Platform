"""Typed errors for the in-document search service."""

from __future__ import annotations


class DocumentSearchError(RuntimeError):
    """Base class for in-document search failures."""


class DocumentSearchNotFoundError(DocumentSearchError):
    """Raised when the target document does not exist in the library."""