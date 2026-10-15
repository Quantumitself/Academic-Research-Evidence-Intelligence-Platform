"""Tests for the import coordinator."""

from __future__ import annotations

from pathlib import Path

import pytest

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


@pytest.fixture()
def coordinator(database: Database, tmp_path: Path):
    storage = FileStorage(
        FileStorageConfig(
            managed_root=tmp_path / "library",
            max_file_size_bytes=1024 * 1024,
            chunk_size_bytes=64,
        )
    )
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        yield ImportCoordinator(repositories, storage)


def _pdf(path: Path, payload: bytes = b"%PDF-1.4 test") -> Path:
    path.write_bytes(payload)
    return path


def test_prepare_ready_file(tmp_path: Path, coordinator: ImportCoordinator) -> None:
    source = _pdf(tmp_path / "paper.pdf")
    plan = coordinator.prepare([source], ImportMode.MANAGED_COPY)
    assert len(plan.candidates) == 1
    candidate = plan.candidates[0]
    assert candidate.state is ImportCandidateState.READY
    assert candidate.size_bytes is not None


def test_prepare_missing_file(tmp_path: Path, coordinator: ImportCoordinator) -> None:
    plan = coordinator.prepare(
        [tmp_path / "missing.pdf"], ImportMode.MANAGED_COPY
    )
    assert plan.candidates[0].state is ImportCandidateState.MISSING


def test_prepare_rejects_unsupported_extension(
    tmp_path: Path, coordinator: ImportCoordinator
) -> None:
    source = tmp_path / "paper.txt"
    source.write_bytes(b"text")
    plan = coordinator.prepare([source], ImportMode.MANAGED_COPY)
    assert plan.candidates[0].state is ImportCandidateState.UNSUPPORTED


def test_prepare_rejects_oversized(
    database: Database, tmp_path: Path
) -> None:
    storage = FileStorage(
        FileStorageConfig(
            managed_root=tmp_path / "library",
            max_file_size_bytes=128,
            chunk_size_bytes=32,
        )
    )
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        coordinator = ImportCoordinator(
            repositories, storage, max_file_size_bytes=128
        )
        source = tmp_path / "big.pdf"
        source.write_bytes(b"x" * 256)
        plan = coordinator.prepare([source], ImportMode.MANAGED_COPY)
        assert plan.candidates[0].state is ImportCandidateState.OVERSIZE


def test_prepare_detects_duplicate(
    tmp_path: Path, database: Database, coordinator: ImportCoordinator
) -> None:
    source = _pdf(tmp_path / "paper.pdf", payload=b"%PDF-1.4 duplicate")
    # Import once.
    plan = coordinator.prepare([source], ImportMode.MANAGED_COPY)
    coordinator.import_files(plan)
    # Prepare again; the second preparation must detect the duplicate.
    plan_again = coordinator.prepare([source], ImportMode.MANAGED_COPY)
    candidate = plan_again.candidates[0]
    assert candidate.state is ImportCandidateState.DUPLICATE
    assert candidate.duplicate_of_document_key is not None


def test_prepare_deduplicates_input_paths(
    tmp_path: Path, coordinator: ImportCoordinator
) -> None:
    source = _pdf(tmp_path / "paper.pdf")
    plan = coordinator.prepare(
        [source, source, source], ImportMode.MANAGED_COPY
    )
    assert len(plan.candidates) == 1


def test_import_files_creates_document(
    tmp_path: Path, database: Database, coordinator: ImportCoordinator
) -> None:
    source = _pdf(tmp_path / "paper.pdf", payload=b"%PDF-1.4 one")
    plan = coordinator.prepare([source], ImportMode.MANAGED_COPY)
    result = coordinator.import_files(plan)
    assert result.imported_count == 1
    assert result.skipped_count == 0
    assert result.failed_count == 0
    with database.session() as session:
        rows = session.query(DocumentAsset).all()
        assert len(rows) == 1
        assert rows[0].storage_mode == "managed_copy"
        assert rows[0].processing_state == "pending"


def test_import_files_reference_mode(
    tmp_path: Path, database: Database, coordinator: ImportCoordinator
) -> None:
    source = _pdf(tmp_path / "paper.pdf", payload=b"%PDF-1.4 ref")
    plan = coordinator.prepare([source], ImportMode.REFERENCED_FILE)
    result = coordinator.import_files(plan)
    assert result.imported_count == 1
    with database.session() as session:
        rows = session.query(DocumentAsset).all()
        assert rows[0].storage_mode == "referenced_file"


def test_import_files_skips_duplicates_by_default(
    tmp_path: Path, database: Database, coordinator: ImportCoordinator
) -> None:
    source = _pdf(tmp_path / "paper.pdf", payload=b"%PDF-1.4 dupe")
    first = coordinator.prepare([source], ImportMode.MANAGED_COPY)
    coordinator.import_files(first)
    second = coordinator.prepare([source], ImportMode.MANAGED_COPY)
    result = coordinator.import_files(second)
    assert result.imported_count == 0
    assert result.skipped_count == 1


def test_import_files_skips_blocked(
    tmp_path: Path, coordinator: ImportCoordinator
) -> None:
    source = tmp_path / "paper.txt"
    source.write_bytes(b"text")
    plan = coordinator.prepare([source], ImportMode.MANAGED_COPY)
    result = coordinator.import_files(plan)
    assert result.imported_count == 0
    assert result.skipped_count == 1


def test_selected_paths_filter(
    tmp_path: Path, coordinator: ImportCoordinator
) -> None:
    a = _pdf(tmp_path / "a.pdf", payload=b"%PDF-1.4 a")
    b = _pdf(tmp_path / "b.pdf", payload=b"%PDF-1.4 b")
    plan = coordinator.prepare([a, b], ImportMode.MANAGED_COPY)
    result = coordinator.import_files(plan, selected_paths=[a.resolve()])
    assert result.imported_count == 1


def test_document_key_stable(tmp_path: Path, coordinator: ImportCoordinator) -> None:
    source = _pdf(tmp_path / "paper.pdf", payload=b"%PDF-1.4 stable")
    plan = coordinator.prepare([source], ImportMode.MANAGED_COPY)
    first = coordinator.import_files(plan)
    # Prepare a second, identical file with a different name.
    another = _pdf(tmp_path / "other.pdf", payload=b"%PDF-1.4 stable")
    second_plan = coordinator.prepare([another], ImportMode.MANAGED_COPY)
    candidate = second_plan.candidates[0]
    assert candidate.state is ImportCandidateState.DUPLICATE
    assert candidate.duplicate_of_document_key == first.imported_document_keys[0]