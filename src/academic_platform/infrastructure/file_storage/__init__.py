"""File storage abstraction for the personal library.

This subpackage owns everything that touches the filesystem for document
assets:

- ``FileStorageConfig`` — immutable configuration describing the managed
  library root and file-size limits.
- ``FileStorage`` — the service that resolves paths, computes checksums,
  copies files into the managed library, records referenced files, and
  detects missing files.
- ``StoredFile`` — a value object describing a file the storage service
  knows about.
- ``FileStorageError`` and its subclasses — typed errors.

The subpackage never imports Qt. It is used by the application layer
through a narrow interface; the presentation layer never touches the
filesystem directly.
"""

from academic_platform.infrastructure.file_storage.config import FileStorageConfig
from academic_platform.infrastructure.file_storage.errors import (
    FileStorageError,
    FileStorageExistsError,
    FileStorageMissingError,
    FileStorageSizeError,
    FileStorageValidationError,
)
from academic_platform.infrastructure.file_storage.model import StorageMode, StoredFile
from academic_platform.infrastructure.file_storage.service import FileStorage

__all__ = [
    "FileStorage",
    "FileStorageConfig",
    "FileStorageError",
    "FileStorageExistsError",
    "FileStorageMissingError",
    "FileStorageSizeError",
    "FileStorageValidationError",
    "StorageMode",
    "StoredFile",
]