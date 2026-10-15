"""Document reading application service.

This subpackage owns the loading and page-rendering operations the
reader page consumes. It provides:

- ``DocumentReaderService`` — opens a document, renders pages as images,
  and returns the document outline.
- ``RenderedPage`` — an immutable value object carrying the raster
  image bytes and its dimensions.
- ``DocumentReadingError`` and subclasses — typed errors.

The service never imports Qt. It returns raw image bytes; the
presentation layer converts them into Qt images.
"""

from academic_platform.application.document_reading.errors import (
    DocumentReadingError,
    DocumentReadingNotFoundError,
    DocumentReadingUnsupportedError,
)
from academic_platform.application.document_reading.model import (
    DocumentOutlineEntry,
    RenderedPage,
)
from academic_platform.application.document_reading.service import (
    DocumentReaderService,
)

__all__ = [
    "DocumentOutlineEntry",
    "DocumentReaderService",
    "DocumentReadingError",
    "DocumentReadingNotFoundError",
    "DocumentReadingUnsupportedError",
    "RenderedPage",
]