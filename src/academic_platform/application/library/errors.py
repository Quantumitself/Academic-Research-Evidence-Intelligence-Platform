"""Typed errors for the library application service."""

from __future__ import annotations


class LibraryError(RuntimeError):
    """Base class for library service failures."""


class LibraryEntryNotFoundError(LibraryError):
    """Raised when a library entry cannot be found by its key."""