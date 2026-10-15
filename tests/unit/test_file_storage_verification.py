"""Tests for verification and deletion."""

from __future__ import annotations

from pathlib import Path

import pytest

from academic_platform.infrastructure.file_storage import (
    FileStorage,
    FileStorageConfig,
    FileStorageValidationError,
)


def _service(tmp_path: Path) -> FileStorage:
    return FileStorage(
        FileStorageConfig(managed_root=tmp_path / "library", chunk_size_bytes=64)
    )


def test_verify_managed_copy_matches(tmp_path: Path) -> None:
    source = tmp_path / "paper.pdf"
    source.write_bytes(b"%PDF-1.4")
    service = _service(tmp_path)
    stored = service.import_managed_copy(source)
    assert service.verify_managed_copy(
        stored.location, expected_checksum=stored.checksum_sha256
    )


def test_verify_managed_copy_mismatch(tmp_path: Path) -> None:
    source = tmp_path / "paper.pdf"
    source.write_bytes(b"%PDF-1.4")
    service = _service(tmp_path)
    stored = service.import_managed_copy(source)
    assert not service.verify_managed_copy(
        stored.location, expected_checksum="0" * 64
    )


def test_verify_managed_copy_missing(tmp_path: Path) -> None:
    service = _service(tmp_path)
    assert not service.verify_managed_copy(
        tmp_path / "missing.bin", expected_checksum="0" * 64
    )


def test_verify_referenced_file_present(tmp_path: Path) -> None:
    source = tmp_path / "paper.pdf"
    source.write_bytes(b"%PDF-1.4")
    assert _service(tmp_path).verify_referenced_file(source)


def test_verify_referenced_file_missing(tmp_path: Path) -> None:
    assert not _service(tmp_path).verify_referenced_file(tmp_path / "missing.bin")


def test_delete_managed_copy(tmp_path: Path) -> None:
    source = tmp_path / "paper.pdf"
    source.write_bytes(b"%PDF-1.4")
    service = _service(tmp_path)
    stored = service.import_managed_copy(source)
    assert stored.location.exists()
    assert service.delete_managed_copy(stored.location) is True
    assert not stored.location.exists()


def test_delete_managed_copy_missing_is_false(tmp_path: Path) -> None:
    service = _service(tmp_path)
    managed_root = service.managed_root
    managed_root.mkdir(parents=True, exist_ok=True)
    missing = managed_root / "missing.bin"
    assert service.delete_managed_copy(missing) is False


def test_delete_outside_managed_root_rejected(tmp_path: Path) -> None:
    outside = tmp_path / "outside.bin"
    outside.write_bytes(b"data")
    service = _service(tmp_path)
    with pytest.raises(FileStorageValidationError):
        service.delete_managed_copy(outside)


def test_delete_referenced_file_rejected(tmp_path: Path) -> None:
    source = tmp_path / "referenced.bin"
    source.write_bytes(b"data")
    service = _service(tmp_path)
    with pytest.raises(FileStorageValidationError):
        service.delete_managed_copy(source)