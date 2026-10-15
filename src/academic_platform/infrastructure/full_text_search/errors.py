"""Typed errors for the full-text search subsystem."""

from __future__ import annotations


class FtsError(RuntimeError):
    """Base class for full-text search failures."""


class FtsIndexError(FtsError):
    """Raised when indexing an entity fails."""


class FtsQueryError(FtsError):
    """Raised when executing an FTS5 query fails."""


class FtsRebuildError(FtsError):
    """Raised when rebuilding the index fails."""