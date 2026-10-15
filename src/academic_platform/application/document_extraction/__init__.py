"""Document extraction application service.

This subpackage wraps the concrete extractors in an application-layer
service that the presentation layer and the background pipeline use. It
adds:

- Extraction of a stored document asset by key.
- Persistence of extracted text chunks into the ``document_chunk``
  table.
- Persistence of extracted metadata into the ``document_metadata``
  table.
- Advancement of the document asset's processing state.

The service never imports Qt. It may import the file storage service and
the repository layer.
"""

from academic_platform.application.document_extraction.errors import (
    DocumentExtractionError,
    DocumentNotFoundError,
)
from academic_platform.application.document_extraction.service import (
    DocumentExtractionService,
    ExtractionOutcome,
)

__all__ = [
    "DocumentExtractionError",
    "DocumentExtractionService",
    "DocumentNotFoundError",
    "ExtractionOutcome",
]