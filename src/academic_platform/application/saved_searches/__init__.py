"""Saved-search application service.

This subpackage owns the lifecycle of saved search definitions:

- ``SavedSearch`` — the immutable value object describing a saved search.
- ``SavedSearchService`` — the application service that lists, creates,
  updates, deletes, and marks-executed saved searches.
- ``SavedSearchError`` and ``SavedSearchNotFoundError`` — typed errors.

The subpackage never imports Qt. It may import from the repository layer
and from the schema layer.
"""

from academic_platform.application.saved_searches.errors import (
    SavedSearchError,
    SavedSearchNotFoundError,
)
from academic_platform.application.saved_searches.model import (
    SavedSearch,
)
from academic_platform.application.saved_searches.service import (
    SavedSearchService,
)

__all__ = [
    "SavedSearch",
    "SavedSearchError",
    "SavedSearchNotFoundError",
    "SavedSearchService",
]