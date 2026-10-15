"""Typed errors for the document reading service."""

from __future__ import annotations


class DocumentReadingError(RuntimeError):
    """Base class for document reading failures."""


class DocumentReadingNotFoundError(DocumentReadingError):
    """Raised when the document or its file cannot be found."""


class DocumentReadingUnsupportedError(DocumentReadingError):
    """Raised when the document cannot be rendered by the reader."""