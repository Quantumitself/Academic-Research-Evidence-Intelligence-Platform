"""Typed errors for project export."""

from __future__ import annotations


class ProjectExportError(RuntimeError):
    """Base class for project export failures."""


class ProjectExportNotFoundError(ProjectExportError):
    """Raised when the project to export does not exist."""