"""Typed errors for the library import subsystem."""

from __future__ import annotations


class ImportError(RuntimeError):
    """Base class for library import failures."""


class ImportValidationError(ImportError):
    """Raised when a candidate fails validation before import begins."""


class ImportDuplicateError(ImportError):
    """Raised when a candidate duplicates an existing library record.

    The error is informational: the dialog reports it to the user and
    lets the user decide whether to proceed.
    """


class ImportStorageError(ImportError):
    """Raised when the file storage service cannot complete an import."""