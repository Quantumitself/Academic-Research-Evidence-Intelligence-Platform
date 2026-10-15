"""Library import application service.

This subpackage owns the import workflow:

- ``ImportMode`` — the two supported storage modes.
- ``ImportCandidate`` — a value object describing one file the user
  selected, its validation state, and any duplicate detection result.
- ``ImportPlan`` — the list of candidates the dialog will present and
  the user will confirm.
- ``ImportCoordinator`` — the application service that validates a
  selection, detects duplicates, and persists confirmed imports through
  the file storage service and the document repository.
- ``ImportError`` and its subclasses — typed errors.

The subpackage never imports Qt. It is used by the import dialog in the
presentation layer.
"""

from academic_platform.application.library_import.coordinator import (
    ImportCoordinator,
)
from academic_platform.application.library_import.errors import (
    ImportError,
    ImportDuplicateError,
    ImportStorageError,
    ImportValidationError,
)
from academic_platform.application.library_import.model import (
    ImportCandidate,
    ImportCandidateState,
    ImportMode,
    ImportPlan,
    ImportResult,
)

__all__ = [
    "ImportCandidate",
    "ImportCandidateState",
    "ImportCoordinator",
    "ImportDuplicateError",
    "ImportError",
    "ImportMode",
    "ImportPlan",
    "ImportResult",
    "ImportStorageError",
    "ImportValidationError",
]