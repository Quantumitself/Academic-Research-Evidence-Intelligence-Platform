"""Typed errors for the file storage subsystem."""

from __future__ import annotations


class FileStorageError(RuntimeError):
    """Base class for file storage failures."""


class FileStorageValidationError(FileStorageError):
    """Raised when an input path or argument fails validation."""


class FileStorageSizeError(FileStorageError):
    """Raised when a file exceeds the configured size limit."""


class FileStorageMissingError(FileStorageError):
    """Raised when a required file is missing."""


class FileStorageExistsError(FileStorageError):
    """Raised when a write would overwrite an existing file.

    The service never overwrites a file silently. A caller that intends
    to replace a file passes an explicit overwrite flag.
    """