"""Tests that verify atomic behaviour under failure."""

from __future__ import annotations

from pathlib import Path

import pytest

from academic_platform.infrastructure.file_storage import (
    FileStorage,
    FileStorageConfig,
)


class _FailingCopy:
    """A context manager that raises after the first chunk is written."""

    def __init__(self, directory: Path) -> None:
        self._directory = directory

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


def test_atomic_copy_leaves_no_partial_file(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "paper.pdf"
    source.write_bytes(b"%PDF-1.4")

    service = FileStorage(
        FileStorageConfig(
            managed_root=tmp_path / "library", chunk_size_bytes=64
        )
    )

    import shutil as _shutil

    original = _shutil.copyfileobj

    def _explode(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(_shutil, "copyfileobj", _explode)

    with pytest.raises(RuntimeError):
        service.import_managed_copy(source)

    monkeypatch.setattr(_shutil, "copyfileobj", original)

    root = service.managed_root
    # The managed root and its fan-out directories may exist after a
    # failed copy, but no partial file must remain under them. Only
    # directories are acceptable.
    if root.exists():
        leftover = [p for p in root.rglob("*") if p.is_file()]
        assert leftover == []