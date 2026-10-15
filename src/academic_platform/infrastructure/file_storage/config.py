"""Immutable configuration for the file storage service.

The configuration describes where managed copies live, how large a
single file may be, and how filesystem operations should be sequenced.
It is frozen so that the service's behavior cannot be changed after
construction.

Design decisions
----------------
- The managed library root is an absolute directory. It is created on
  first use. All managed copies live under it; the service never writes
  outside it.
- The maximum file size is expressed in bytes. The default is one
  gigabyte; the application's settings schema exposes a per-import limit
  in megabytes that callers use to override this default.
- The chunk size used for streaming operations is a performance knob. It
  does not affect correctness. The default is eight megabytes.
- The checksum algorithm is fixed to SHA-256. The schema stores the
  checksum as a lowercase hexadecimal string; the configuration does not
  allow other algorithms because the schema does not.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from academic_platform.infrastructure.file_storage.errors import (
    FileStorageValidationError,
)

_DEFAULT_CHUNK_SIZE = 8 * 1024 * 1024
_DEFAULT_MAX_FILE_SIZE = 1024 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class FileStorageConfig:
    """Immutable configuration for the file storage service."""

    managed_root: Path
    max_file_size_bytes: int = _DEFAULT_MAX_FILE_SIZE
    chunk_size_bytes: int = _DEFAULT_CHUNK_SIZE
    create_managed_root_on_use: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.managed_root, Path):
            raise FileStorageValidationError(
                "managed_root must be a Path instance"
            )
        if self.max_file_size_bytes <= 0:
            raise FileStorageValidationError(
                "max_file_size_bytes must be positive"
            )
        if self.chunk_size_bytes <= 0:
            raise FileStorageValidationError(
                "chunk_size_bytes must be positive"
            )
        if self.chunk_size_bytes > self.max_file_size_bytes:
            raise FileStorageValidationError(
                "chunk_size_bytes must not exceed max_file_size_bytes"
            )

    @property
    def managed_root_absolute(self) -> Path:
        """Return the managed root as an absolute, resolved path."""
        return self.managed_root.expanduser().resolve()

    def ensure_managed_root(self) -> Path:
        """Create the managed root if it does not exist and return it.

        Raises
        ------
        FileStorageValidationError
            If the root exists but is not a directory, or if it cannot be
            created.
        """
        root = self.managed_root_absolute
        if root.exists():
            if not root.is_dir():
                raise FileStorageValidationError(
                    f"Managed root exists but is not a directory: {root}"
                )
            return root
        if not self.create_managed_root_on_use:
            raise FileStorageValidationError(
                f"Managed root does not exist and creation is disabled: {root}"
            )
        try:
            root.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise FileStorageValidationError(
                f"Unable to create managed root {root}: {exc}"
            ) from exc
        return root