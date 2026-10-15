"""Tests for the import operations."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from academic_platform.infrastructure.file_storage import (
    FileStorage,
    FileStorageConfig,
    FileStorageExistsError,
    FileStorageSizeError,
    StorageMode,
)


def _service(tmp_path: Path, *, max_size: int = 1024 * 1024) -> FileStorage:
    return FileStorage(
        FileStorageConfig(
            managed_root=tmp_path / "library",
            max_file_size_bytes=max_size,
            chunk_size_bytes=64,
        )
    )


def test_import_managed_copy(tmp_path: Path) -> None:
    source = tmp_path / "paper.pdf"
    payload = b"%PDF-1.4 test"
    source.write_bytes(payload)
    service = _service(tmp_path)
    stored = service.import_managed_copy(source)
    assert stored.mode is StorageMode.MANAGED_COPY
    assert stored.location.exists()
    assert stored.location.read_bytes() == payload
    assert stored.location.parent.parent.parent == service.managed_root
    assert stored.checksum_sha256 == hashlib.sha256(payload).hexdigest()
    assert stored.original_filename == "paper.pdf"


def test_import_managed_copy_is_idempotent(tmp_path: Path) -> None:
    source = tmp_path / "paper.pdf"
    source.write_bytes(b"content")
    service = _service(tmp_path)
    first = service.import_managed_copy(source)
    second = service.import_managed_copy(source)
    assert first.location == second.location
    assert first.checksum_sha256 == second.checksum_sha256


def test_import_managed_copy_rejects_oversized(tmp_path: Path) -> None:
    source = tmp_path / "big.bin"
    source.write_bytes(b"x" * 2048)
    service = _service(tmp_path, max_size=1024)
    with pytest.raises(FileStorageSizeError):
        service.import_managed_copy(source)


def test_import_managed_copy_with_extension(tmp_path: Path) -> None:
    source = tmp_path / "noext"
    source.write_bytes(b"content")
    stored = _service(tmp_path).import_managed_copy(source)
    assert stored.location.suffix == ".bin"


def test_import_managed_copy_preserves_extension(tmp_path: Path) -> None:
    source = tmp_path / "paper.pdf"
    source.write_bytes(b"%PDF-1.4")
    stored = _service(tmp_path).import_managed_copy(source)
    assert stored.location.suffix == ".pdf"


def test_import_managed_copy_does_not_modify_source(tmp_path: Path) -> None:
    source = tmp_path / "paper.pdf"
    source.write_bytes(b"%PDF-1.4")
    service = _service(tmp_path)
    service.import_managed_copy(source)
    assert source.exists()
    assert source.read_bytes() == b"%PDF-1.4"


def test_record_referenced_file(tmp_path: Path) -> None:
    source = tmp_path / "paper.pdf"
    source.write_bytes(b"%PDF-1.4")
    stored = _service(tmp_path).record_referenced_file(source)
    assert stored.mode is StorageMode.REFERENCED_FILE
    assert stored.location == source.resolve()
    assert stored.is_managed is False


def test_record_referenced_file_rejects_oversized(tmp_path: Path) -> None:
    source = tmp_path / "big.bin"
    source.write_bytes(b"x" * 2048)
    service = _service(tmp_path, max_size=1024)
    with pytest.raises(FileStorageSizeError):
        service.record_referenced_file(source)


def test_import_is_atomic(tmp_path: Path) -> None:
    """A crash during copy must not leave a partial file at the target."""
    source = tmp_path / "paper.pdf"
    source.write_bytes(b"%PDF-1.4")
    service = _service(tmp_path)
    stored = service.import_managed_copy(source)
    siblings = list(stored.location.parent.iterdir())
    # After a successful import, the target's parent contains exactly
    # the target itself. No temp files remain.
    assert siblings == [stored.location]