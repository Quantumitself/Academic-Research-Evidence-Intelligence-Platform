"""Value objects for the file storage service."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class StorageMode(str, Enum):
    """How a document asset is stored on disk."""

    MANAGED_COPY = "managed_copy"
    REFERENCED_FILE = "referenced_file"


@dataclass(frozen=True, slots=True)
class StoredFile:
    """A file the storage service has recorded.

    Attributes
    ----------
    location:
        The absolute path to the file. For managed copies this is under
        the managed root; for referenced files it is the original path
        the caller supplied.
    mode:
        How the file is stored.
    size_bytes:
        The file's size in bytes at the time the record was produced.
    checksum_sha256:
        The file's SHA-256 checksum in lowercase hexadecimal form.
    original_filename:
        The filename the caller supplied before any renaming. For
        referenced files this equals ``location.name``.
    """

    location: Path
    mode: StorageMode
    size_bytes: int
    checksum_sha256: str
    original_filename: str

    @property
    def is_managed(self) -> bool:
        return self.mode is StorageMode.MANAGED_COPY