"""Typed errors for the document extraction service."""

from __future__ import annotations


class DocumentExtractionError(RuntimeError):
    """Base class for document extraction failures."""


class DocumentNotFoundError(DocumentExtractionError):
    """Raised when the requested document does not exist in the library."""