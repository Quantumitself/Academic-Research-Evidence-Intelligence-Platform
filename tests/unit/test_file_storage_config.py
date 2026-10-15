"""Tests for the file storage configuration value object."""

from __future__ import annotations

from pathlib import Path

import pytest

from academic_platform.infrastructure.file_storage.config import (
    FileStorageConfig,
)
from academic_platform.infrastructure.file_storage.errors import (
    FileStorageValidationError,
)


def test_defaults() -> None:
    config = FileStorageConfig(managed_root=Path("/tmp/library"))
    assert config.max_file_size_bytes > 0
    assert config.chunk_size_bytes > 0


def test_rejects_non_path_root() -> None:
    with pytest.raises(FileStorageValidationError):
        FileStorageConfig(managed_root="/tmp/library")  # type: ignore[arg-type]


def test_rejects_nonpositive_size() -> None:
    with pytest.raises(FileStorageValidationError):
        FileStorageConfig(managed_root=Path("/tmp"), max_file_size_bytes=0)


def test_rejects_chunk_larger_than_max() -> None:
    with pytest.raises(FileStorageValidationError):
        FileStorageConfig(
            managed_root=Path("/tmp"),
            max_file_size_bytes=1024,
            chunk_size_bytes=4096,
        )


def test_ensure_creates_root(tmp_path: Path) -> None:
    target = tmp_path / "library"
    config = FileStorageConfig(managed_root=target)
    resolved = config.ensure_managed_root()
    assert resolved == target.resolve()
    assert resolved.is_dir()


def test_ensure_rejects_file_root(tmp_path: Path) -> None:
    target = tmp_path / "not-a-dir"
    target.write_text("hi", encoding="utf-8")
    config = FileStorageConfig(managed_root=target)
    with pytest.raises(FileStorageValidationError):
        config.ensure_managed_root()


def test_ensure_respects_creation_flag(tmp_path: Path) -> None:
    target = tmp_path / "library"
    config = FileStorageConfig(
        managed_root=target,
        create_managed_root_on_use=False,
    )
    with pytest.raises(FileStorageValidationError):
        config.ensure_managed_root()