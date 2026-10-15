"""Project export.

This subpackage serializes a research project and its related entities
to self-contained JSON and Markdown documents:

- ``ExportFormat`` — the supported output formats.
- ``ExportOptions`` — the user-selectable inclusion options.
- ``ExportResult`` — the outcome of an export.
- ``ProjectExportService`` — the application service.
- ``ProjectExportError`` and subclasses — typed errors.

The service never imports Qt. It reads through the project, question,
task, collection, and document repositories. It writes to a file the
caller supplies.
"""

from academic_platform.application.project_export.errors import (
    ProjectExportError,
    ProjectExportNotFoundError,
)
from academic_platform.application.project_export.model import (
    ExportFormat,
    ExportOptions,
    ExportResult,
    ExportSection,
)
from academic_platform.application.project_export.service import (
    ProjectExportService,
)

__all__ = [
    "ExportFormat",
    "ExportOptions",
    "ExportResult",
    "ExportSection",
    "ProjectExportError",
    "ProjectExportNotFoundError",
    "ProjectExportService",
]