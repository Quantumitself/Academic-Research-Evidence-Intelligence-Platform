"""Typed errors for the document processing subsystem."""

from __future__ import annotations


class DocumentProcessingError(RuntimeError):
    """Base class for document processing failures."""


class PdfMissingError(DocumentProcessingError):
    """Raised when the requested PDF does not exist on disk."""


class PdfNotReadableError(DocumentProcessingError):
    """Raised when the PDF exists but cannot be read.

    Covers permission failures, corrupted files, and format errors that
    the underlying PDF library reports at open time.
    """


class PdfEncryptedError(DocumentProcessingError):
    """Raised when the PDF is encrypted and requires a password.

    The application never attempts to bypass encryption. A password
    prompt is delivered in a later phase; at this stage encrypted PDFs
    are rejected with a descriptive error.
    """


class PdfUnsupportedError(DocumentProcessingError):
    """Raised when the file's content is not a supported PDF.

    Covers files with a PDF extension whose content is not a PDF, and
    PDFs that use features the extractor does not handle.
    """


class PdfExtractionError(DocumentProcessingError):
    """Raised when extraction fails partway through a document.

    The error carries the number of pages successfully extracted so
    that the caller can persist a partial result if it chooses to.
    """

    def __init__(self, message: str, *, pages_extracted: int = 0) -> None:
        super().__init__(message)
        self.pages_extracted = pages_extracted