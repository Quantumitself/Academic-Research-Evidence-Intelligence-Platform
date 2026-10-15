"""Tests for the import coordinator's integration with the duplicate detector."""

from __future__ import annotations

from pathlib import Path

import pytest

from academic_platform.application.deduplication.policy import DuplicatePolicy
from academic_platform.application.library_import.coordinator import (
    ImportCoordinator,
)
from academic_platform.application.library_import.model import (
    ImportCandidateState,
    ImportMode,
)
from academic_platform.infrastructure.database import Database
from academic_platform.infrastructure.database.base import Base
from academic_platform.infrastructure.database.models import DocumentAsset
from academic_platform.infrastructure.file_storage import (
    FileStorage,
    FileStorageConfig,
)
from academic_platform.infrastructure.repositories.factory import (
    _REPOSITORY_REGISTRY,
)
from academic_platform.infrastructure.repositories.manager import (
    RepositoryManager,
)


@pytest.fixture()
def database() -> Database:
    db = Database.in_memory()
    Base.metadata.create_all(db.engine)
    yield db
    db.dispose()


def _coordinator(database: Database, tmp_path: Path, **kwargs) -> ImportCoordinator:
    storage = FileStorage(
        FileStorageConfig(
            managed_root=tmp_path / "library",
            max_file_size_bytes=1024 * 1024,
            chunk_size_bytes=64,
        )
    )
    repositories = RepositoryManager(database._session_factory())  # noqa: SLF001
    repositories.register_all(dict(_REPOSITORY_REGISTRY))
    return ImportCoordinator(
        repositories=repositories,
        storage=storage,
        max_file_size_bytes=1024 * 1024,
        **kwargs,
    )


def _pdf(path: Path, payload: bytes) -> Path:
    path.write_bytes(payload)
    return path


def test_first_import_is_ready(database: Database, tmp_path: Path) -> None:
    coordinator = _coordinator(database, tmp_path)
    source = _pdf(tmp_path / "paper.pdf", b"%PDF-1.4 one")
    plan = coordinator.prepare([source], ImportMode.MANAGED_COPY)
    assert plan.candidates[0].state is ImportCandidateState.READY


def test_second_import_is_duplicate(database: Database, tmp_path: Path) -> None:
    coordinator = _coordinator(database, tmp_path)
    source = _pdf(tmp_path / "paper.pdf", b"%PDF-1.4 content")
    first = coordinator.prepare([source], ImportMode.MANAGED_COPY)
    coordinator.import_files(first)

    second = coordinator.prepare([source], ImportMode.MANAGED_COPY)
    candidate = second.candidates[0]
    assert candidate.state is ImportCandidateState.DUPLICATE
    assert candidate.duplicate_signal == "checksum"


def test_duplicate_signal_reported(database: Database, tmp_path: Path) -> None:
    coordinator = _coordinator(database, tmp_path)
    source = _pdf(tmp_path / "paper.pdf", b"%PDF-1.4 report")
    coordinator.import_files(
        coordinator.prepare([source], ImportMode.MANAGED_COPY)
    )
    plan = coordinator.prepare([source], ImportMode.MANAGED_COPY)
    assert plan.candidates[0].duplicate_signal == "checksum"


def test_policy_disables_duplicate_detection(database: Database, tmp_path: Path) -> None:
    # Constructing a policy that disables all signals raises; verify the
    # constructor's safety by expecting the error.
    with pytest.raises(ValueError):
        DuplicatePolicy(
            use_checksum=False, use_doi=False, use_metadata=False
        )


def test_different_files_are_not_duplicates(database: Database, tmp_path: Path) -> None:
    coordinator = _coordinator(database, tmp_path)
    a = _pdf(tmp_path / "a.pdf", b"%PDF-1.4 first")
    b = _pdf(tmp_path / "b.pdf", b"%PDF-1.4 second")
    plan = coordinator.prepare([a, b], ImportMode.MANAGED_COPY)
    assert all(
        candidate.state is ImportCandidateState.READY
        for candidate in plan.candidates
    )