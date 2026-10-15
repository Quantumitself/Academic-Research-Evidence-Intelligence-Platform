"""In-document search application service.

This subpackage exposes search over a single document's extracted text.
It provides:

- ``DocumentSearchMatch`` — an immutable value object describing a single
  match within a document.
- ``DocumentSearchResult`` — the outcome of a query.
- ``DocumentSearchService`` — the application service that searches a
  document's stored chunks.
- ``DocumentSearchError`` and subclasses — typed errors.

The service never imports Qt and never reads the PDF file. It searches
the persisted ``document_chunk`` rows so that results reflect exactly
what the indexer and extractor produced.
"""

from academic_platform.application.document_search.errors import (
    DocumentSearchError,
    DocumentSearchNotFoundError,
)
from academic_platform.application.document_search.model import (
    DocumentSearchMatch,
    DocumentSearchResult,
)
from academic_platform.application.document_search.service import (
    DocumentSearchService,
)

__all__ = [
    "DocumentSearchError",
    "DocumentSearchMatch",
    "DocumentSearchNotFoundError",
    "DocumentSearchResult",
    "DocumentSearchService",
]