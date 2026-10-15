"""File storage service.

``FileStorage`` is the single component in the application that performs
filesystem operations on document assets. It supports two storage modes:

- **Managed copy.** The file is copied into the managed library root and
  the original is left untouched. This is the default mode because it
  makes the library self-contained and protects against the user moving
  or deleting the original file.
- **Referenced file.** The file remains in place and the application
  stores a reference to it. Missing files are detected and reported; the
  application never deletes a referenced file.

Design decisions
----------------
- Checksums are computed by streaming the file in fixed-size chunks. The
  service never reads a whole file into memory.
- Managed copies use an atomic write: the file is copied to a temporary
  file in the same directory and renamed into place. A crash during the
  copy leaves no partial file under the managed root.
- Filenames for managed copies are derived from the checksum so that
  identical files resolve to the same location. This is deliberate: it
  deduplicates storage and gives the file a stable name.
- The service never overwrites a file silently. A caller that intends
  to replace a file must pass an explicit overwrite flag.
- The service validates every input path. Referenced files must be
  regular files; directories, device files, and sockets are rejected.
- The service never performs network operations and never spawns
  subprocesses.
"""

from __future__ import annotations

import hashlib
import logging
import os
import shutil
import tempfile
from pathlib import Path

from academic_platform.infrastructure.file_storage.config import FileStorageConfig
from academic_platform.infrastructure.file_storage.errors import (
    FileStorageExistsError,
    FileStorageMissingError,
    FileStorageSizeError,
    FileStorageValidationError,
)
from academic_platform.infrastructure.file_storage.model import (
    StorageMode,
    StoredFile,
)

_logger = logging.getLogger(__name__)

_CHECKSUM_SUFFIX_LENGTH = 64
_MANAGED_FILENAME_EXTENSION_FALLBACK = ".bin"


class FileStorage:
    """Filesystem storage for document assets."""

    def __init__(self, config: FileStorageConfig) -> None:
        self._config = config

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------
    @property
    def config(self) -> FileStorageConfig:
        return self._config

    @property
    def managed_root(self) -> Path:
        """Return the managed library root as an absolute path."""
        return self._config.managed_root_absolute

    # ------------------------------------------------------------------
    # Checksum
    # ------------------------------------------------------------------
    def compute_checksum(self, path: Path) -> str:
        """Return the SHA-256 checksum of ``path`` as lowercase hexadecimal.

        The file is streamed in fixed-size chunks; the whole file is
        never read into memory.

        Raises
        ------
        FileStorageValidationError
            If ``path`` is not a regular file.
        FileStorageMissingError
            If ``path`` does not exist.
        """
        resolved = self._validate_regular_file(path)
        hasher = hashlib.sha256()
        try:
            with resolved.open("rb") as handle:
                while True:
                    chunk = handle.read(self._config.chunk_size_bytes)
                    if not chunk:
                        break
                    hasher.update(chunk)
        except OSError as exc:
            raise FileStorageValidationError(
                f"Unable to read {resolved}: {exc}"
            ) from exc
        return hasher.hexdigest()

    # ------------------------------------------------------------------
    # Import
    # ------------------------------------------------------------------
    def import_managed_copy(
        self,
        source: Path,
        *,
        overwrite: bool = False,
    ) -> StoredFile:
        """Copy ``source`` into the managed library and return the record.

        The managed filename is derived from the file's checksum. Two
        imports of identical files resolve to the same managed path; the
        second import is a no-op unless ``overwrite`` is True.

        Raises
        ------
        FileStorageValidationError
            If ``source`` is not a regular file.
        FileStorageMissingError
            If ``source`` does not exist.
        FileStorageSizeError
            If the file exceeds the configured size limit.
        FileStorageExistsError
            If the target exists and ``overwrite`` is False.
        """
        resolved = self._validate_regular_file(source)
        size = self._validate_size(resolved)
        checksum = self.compute_checksum(resolved)
        root = self._config.ensure_managed_root()
        target_directory = self._managed_directory_for(checksum, root)
        target_directory.mkdir(parents=True, exist_ok=True)
        target = target_directory / _managed_filename(checksum, resolved.name)

        if target.exists() and not overwrite:
            existing_checksum = self.compute_checksum(target)
            if existing_checksum == checksum:
                _logger.info(
                    "Managed copy already present at %s (checksum match)", target
                )
                return StoredFile(
                    location=target,
                    mode=StorageMode.MANAGED_COPY,
                    size_bytes=target.stat().st_size,
                    checksum_sha256=checksum,
                    original_filename=resolved.name,
                )
            raise FileStorageExistsError(
                f"Managed target {target} exists with a different checksum"
            )

        self._atomic_copy(resolved, target, overwrite=overwrite)
        final_size = target.stat().st_size
        _logger.info("Imported managed copy: %s -> %s", resolved, target)
        return StoredFile(
            location=target,
            mode=StorageMode.MANAGED_COPY,
            size_bytes=final_size,
            checksum_sha256=checksum,
            original_filename=resolved.name,
        )

    def record_referenced_file(self, source: Path) -> StoredFile:
        """Return the record for a file that remains in place.

        The file is not copied or modified. The service verifies that
        the path points to a regular file, that the file is within the
        size limit, and that a checksum can be computed.

        Raises
        ------
        FileStorageValidationError, FileStorageMissingError,
        FileStorageSizeError
        """
        resolved = self._validate_regular_file(source)
        size = self._validate_size(resolved)
        checksum = self.compute_checksum(resolved)
        return StoredFile(
            location=resolved,
            mode=StorageMode.REFERENCED_FILE,
            size_bytes=size,
            checksum_sha256=checksum,
            original_filename=resolved.name,
        )

    # ------------------------------------------------------------------
    # Verification
    # ------------------------------------------------------------------
    def verify_managed_copy(self, location: Path, *, expected_checksum: str) -> bool:
        """Return True when a managed file matches its expected checksum.

        A missing file returns False rather than raising. The caller
        decides whether that is a recoverable condition.
        """
        if not location.exists():
            return False
        try:
            actual = self.compute_checksum(location)
        except FileStorageError:
            _logger.exception("Unable to verify managed copy %s", location)
            return False
        return actual == expected_checksum

    def verify_referenced_file(self, location: Path) -> bool:
        """Return True when a referenced file is present and readable.

        The method does not compare checksums. Referenced files can be
        legitimately replaced by the user; the application records a new
        checksum when it re-imports the file.
        """
        return location.exists() and location.is_file()

    # ------------------------------------------------------------------
    # Deletion
    # ------------------------------------------------------------------
    def delete_managed_copy(self, location: Path) -> bool:
        """Delete a managed file.

        The method refuses to delete a path outside the managed root.
        Referenced files are never deleted by the application.

        Returns True when a file was deleted and False when it did not
        exist. Raises ``FileStorageValidationError`` when the path is
        outside the managed root.
        """
        root = self._config.managed_root_absolute
        try:
            resolved = location.expanduser().resolve()
        except OSError as exc:
            raise FileStorageValidationError(
                f"Unable to resolve {location}: {exc}"
            ) from exc
        if not _is_within(resolved, root):
            raise FileStorageValidationError(
                f"Refusing to delete a file outside the managed root: {resolved}"
            )
        if not resolved.exists():
            return False
        try:
            resolved.unlink()
        except OSError as exc:
            raise FileStorageValidationError(
                f"Unable to delete {resolved}: {exc}"
            ) from exc
        _logger.info("Deleted managed copy: %s", resolved)
        return True

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _validate_regular_file(self, source: Path) -> Path:
        if not isinstance(source, Path):
            raise FileStorageValidationError("source must be a Path instance")
        try:
            resolved = source.expanduser().resolve()
        except OSError as exc:
            raise FileStorageValidationError(
                f"Unable to resolve {source}: {exc}"
            ) from exc
        if not resolved.exists():
            raise FileStorageMissingError(f"File does not exist: {resolved}")
        if not resolved.is_file():
            raise FileStorageValidationError(
                f"Path is not a regular file: {resolved}"
            )
        return resolved

    def _validate_size(self, path: Path) -> int:
        try:
            size = path.stat().st_size
        except OSError as exc:
            raise FileStorageValidationError(
                f"Unable to stat {path}: {exc}"
            ) from exc
        if size > self._config.max_file_size_bytes:
            raise FileStorageSizeError(
                f"File exceeds the configured limit "
                f"({size} > {self._config.max_file_size_bytes}): {path}"
            )
        return size

    def _managed_directory_for(self, checksum: str, root: Path) -> Path:
        # Two-level fanout keeps any single directory from accumulating
        # too many entries. The first two hex characters form the first
        # level; the next two form the second.
        return root / checksum[:2] / checksum[2:4]

    def _atomic_copy(self, source: Path, target: Path, *, overwrite: bool) -> None:
        target_parent = target.parent
        target_parent.mkdir(parents=True, exist_ok=True)
        file_descriptor, temp_name = tempfile.mkstemp(
            prefix=target.name + ".",
            suffix=".tmp",
            dir=target_parent,
        )
        temp_path = Path(temp_name)
        try:
            with os.fdopen(file_descriptor, "wb") as destination:
                with source.open("rb") as origin:
                    shutil.copyfileobj(
                        origin,
                        destination,
                        length=self._config.chunk_size_bytes,
                    )
                destination.flush()
                os.fsync(destination.fileno())
            if target.exists() and not overwrite:
                # Re-check under a race; the atomic rename below would
                # otherwise overwrite silently.
                temp_path.unlink(missing_ok=True)
                raise FileStorageExistsError(
                    f"Managed target {target} appeared during copy"
                )
            os.replace(temp_path, target)
        except Exception:
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except OSError:
                    pass
            raise


def _managed_filename(checksum: str, original_name: str) -> str:
    """Return the managed filename for a checksum.

    The managed name preserves the original extension so that tools
    inspecting the library can recognize the file type. The extension is
    sanitized: anything after the final dot is kept, limited to a short
    alphanumeric string. Files without a usable extension receive a
    neutral fallback.
    """
    extension = ""
    if "." in original_name:
        candidate = original_name.rsplit(".", 1)[-1].strip().lower()
        if candidate and candidate.isalnum() and len(candidate) <= 16:
            extension = f".{candidate}"
    if not extension:
        extension = _MANAGED_FILENAME_EXTENSION_FALLBACK
    return f"{checksum}{extension}"


def _is_within(candidate: Path, root: Path) -> bool:
    try:
        candidate.relative_to(root)
    except ValueError:
        return False
    return True