"""Tests for checksum computation."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from academic_platform.infrastructure.file_storage import (
    FileStorage,
    FileStorageConfig,
    FileStorageMissingError,
    FileStorageValidationError,
)


def _service(tmp_path: Path) -> FileStorage:
    return FileStorage(
        FileStorageConfig(managed_root=tmp_path / "library", chunk_size_bytes=64)
    )


def test_compute_checksum(tmp_path: Path) -> None:
    source = tmp_path / "file.bin"
    payload = b"hello world"
    source.write_bytes(payload)
    expected = hashlib.sha256(payload).hexdigest()
    assert _service(tmp_path).compute_checksum(source) == expected


def test_compute_checksum_streams_large_file(tmp_path: Path) -> None:
    source = tmp_path / "large.bin"
    payload = b"x" * (256 * 1024)
    source.write_bytes(payload)
    expected = hashlib.sha256(payload).hexdigest()
    assert _service(tmp_path).compute_checksum(source) == expected


def test_compute_checksum_missing_file(tmp_path: Path) -> None:
    with pytest.raises(FileStorageMissingError):
        _service(tmp_path).compute_checksum(tmp_path / "missing.bin")


def test_compute_checksum_rejects_directory(tmp_path: Path) -> None:
    directory = tmp_path / "dir"
    directory.mkdir()
    with pytest.raises(FileStorageValidationError):
        _service(tmp_path).compute_checksum(directory)


def test_compute_checksum_rejects_non_path(tmp_path: Path) -> None:
    with pytest.raises(FileStorageValidationError):
        _service(tmp_path).compute_checksum("not-a-path")  # type: ignore[arg-type]