"""Typed errors for the OCR subsystem."""

from __future__ import annotations

from academic_platform.infrastructure.document_processing.errors import (
    DocumentProcessingError,
)


class OcrError(DocumentProcessingError):
    """Base class for OCR failures."""


class OcrUnavailableError(OcrError):
    """Raised when the Tesseract binary or the Python wrapper is missing.

    The pipeline does not treat this as a fatal error in the application
    at large. It is raised when a caller explicitly requests OCR and the
    environment does not provide it.
    """


class OcrLanguageError(OcrError):
    """Raised when a requested Tesseract language pack is not installed."""


class OcrPageError(OcrError):
    """Raised when a single page fails during OCR.

    The error carries the page number and the underlying message so that
    the caller can record the failure and continue with the remaining
    pages.
    """

    def __init__(self, message: str, *, page_number: int) -> None:
        super().__init__(message)
        self.page_number = page_number


class OcrTimeoutError(OcrError):
    """Raised when OCR exceeds the configured timeout on a page."""