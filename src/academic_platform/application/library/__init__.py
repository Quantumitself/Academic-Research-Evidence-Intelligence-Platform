"""Library application service.

This subpackage exposes the personal library as an application-layer
service. It provides:

- ``LibraryEntry`` — an immutable summary of a single document.
- ``LibraryFilter`` — the filter state accepted by the list operation.
- ``LibraryService`` — the application service that lists, filters,
  loads, and deletes library documents.

The service never imports Qt. It reads through the document repository
and the FTS5 query service. It never touches the filesystem directly.
"""

from academic_platform.application.library.errors import (
    LibraryError,
    LibraryEntryNotFoundError,
)
from academic_platform.application.library.model import (
    LibraryEntry,
    LibraryFilter,
    LibraryPage as LibraryPageResult,
)
from academic_platform.application.library.service import LibraryService

__all__ = [
    "LibraryEntry",
    "LibraryEntryNotFoundError",
    "LibraryError",
    "LibraryFilter",
    "LibraryPage",
    "LibraryPageResult",
    "LibraryService",
]