"""Phase D acceptance criteria as automated tests.

The tests are intentionally broader than per-module tests. Each test
exercises a complete workflow end to end, using a temporary directory
and an in-memory SQLite database.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import fitz  # PyMuPDF

from academic_platform.infrastructure.database import Database
from academic_platform.infrastructure.database.base import Base


class _ShimmedManager:
    def __init__(self, database: Database) -> None:
        self._database = database
        self._sessions: list = []

    def get(self, key: str):
        from academic_platform.infrastructure.repositories.factory import (
            _REPOSITORY_REGISTRY,
        )

        session = self._database._session_factory()  # noqa: SLF001
        self._sessions.append(session)
        return _REPOSITORY_REGISTRY[key](session)

    def register_all(self, mapping) -> None:
        return None

    def close_all(self) -> None:
        for session in self._sessions:
            try:
                session.commit()
            except Exception:  # noqa: BLE001
                session.rollback()
            finally:
                session.close()
        self._sessions.clear()


@pytest.fixture()
def database() -> Database:
    db = Database.in_memory()
    Base.metadata.create_all(db.engine)
    yield db
    db.dispose()


def _make_pdf(path: Path, *, title: str, authors: str, year: str, body: str) -> None:
    document = fitz.open()
    try:
        page = document.new_page()
        y = 60.0
        for line in (title, authors, year, "", "Abstract", body):
            page.insert_text((72, y), line)
            y += 16
        document.set_metadata(
            {
                "title": title,
                "author": authors,
                "subject": f"Journal of Synthetic Studies {year}",
                "creationDate": f"D:{year}0101000000Z",
            }
        )
        document.save(str(path))
    finally:
        document.close()


def test_file_storage_round_trip(tmp_path: Path) -> None:
    from academic_platform.infrastructure.file_storage import (
        FileStorage,
        FileStorageConfig,
    )

    source = tmp_path / "source.bin"
    source.write_bytes(b"%PDF-1.4")
    service = FileStorage(
        FileStorageConfig(managed_root=tmp_path / "library", chunk_size_bytes=64)
    )
    stored = service.import_managed_copy(source)
    assert stored.location.exists()
    assert service.verify_managed_copy(
        stored.location, expected_checksum=stored.checksum_sha256
    )


def test_import_persists_document(database: Database, tmp_path: Path) -> None:
    from academic_platform.application.library_import.coordinator import (
        ImportCoordinator,
    )
    from academic_platform.application.library_import.model import (
        ImportCandidateState,
        ImportMode,
    )
    from academic_platform.infrastructure.database.models import DocumentAsset
    from academic_platform.infrastructure.file_storage import (
        FileStorage,
        FileStorageConfig,
    )

    source = tmp_path / "paper.pdf"
    source.write_bytes(b"%PDF-1.4 accepted")
    storage = FileStorage(
        FileStorageConfig(
            managed_root=tmp_path / "managed",
            max_file_size_bytes=1024 * 1024,
            chunk_size_bytes=64,
        )
    )
    manager = _ShimmedManager(database)
    coordinator = ImportCoordinator(
        repositories=manager,  # type: ignore[arg-type]
        storage=storage,
        max_file_size_bytes=1024 * 1024,
    )
    plan = coordinator.prepare([source], ImportMode.MANAGED_COPY)
    assert plan.candidates[0].state is ImportCandidateState.READY
    result = coordinator.import_files(plan)
    manager.close_all()
    assert result.imported_count == 1
    with database.session() as session:
        assert session.query(DocumentAsset).count() == 1


def test_extraction_indexes_and_searches(database: Database, tmp_path: Path) -> None:
    from academic_platform.application.document_extraction.service import (
        DocumentExtractionService,
    )
    from academic_platform.infrastructure.database.models import DocumentAsset
    from academic_platform.infrastructure.full_text_search.query import (
        FtsQueryService,
    )

    pdf = tmp_path / "paper.pdf"
    _make_pdf(
        pdf,
        title="Indexed Paper",
        authors="A. Author",
        year="2023",
        body="Content about measurement invariance across groups.",
    )
    with database.session() as session:
        session.add(
            DocumentAsset(
                key="doc-1",
                display_name="Indexed Paper",
                location=str(pdf.resolve()),
                checksum_sha256="0" * 64,
            )
        )
    manager = _ShimmedManager(database)
    service = DocumentExtractionService(manager, index_enabled=True)  # type: ignore[arg-type]
    outcome = service.extract_document("doc-1")
    manager.close_all()
    assert outcome.chunk_count >= 1
    with database.session() as session:
        results = FtsQueryService(session).search_documents("invariance")
        assert results


def test_reader_renders_pages(database: Database, tmp_path: Path) -> None:
    from academic_platform.application.document_reading import (
        DocumentReaderService,
    )
    from academic_platform.infrastructure.database.models import DocumentAsset

    pdf = tmp_path / "paper.pdf"
    _make_pdf(pdf, title="Reader", authors="A", year="2024", body="body")
    with database.session() as session:
        session.add(
            DocumentAsset(
                key="doc-1",
                display_name="Reader",
                location=str(pdf.resolve()),
                checksum_sha256="0" * 64,
            )
        )
    manager = _ShimmedManager(database)
    service = DocumentReaderService(manager)  # type: ignore[arg-type]
    page_count, _ = service.open_document("doc-1")
    rendered = service.render_page("doc-1", 1)
    service.close_all()
    manager.close_all()
    assert page_count >= 1
    assert rendered.image_bytes.startswith(b"\x89PNG")


def test_annotation_round_trip(database: Database) -> None:
    from academic_platform.application.annotations import (
        AnnotationService,
    )
    from academic_platform.infrastructure.database.models import DocumentAsset
    from academic_platform.infrastructure.full_text_search.query import (
        FtsQueryService,
    )

    with database.session() as session:
        session.add(
            DocumentAsset(
                key="doc-1",
                display_name="Paper",
                location="/tmp/paper.pdf",
                checksum_sha256="0" * 64,
            )
        )
    manager = _ShimmedManager(database)
    service = AnnotationService(manager)  # type: ignore[arg-type]
    view = service.create_note("doc-1", 1, "Content about invariance.")
    manager.close_all()
    assert view.identifier > 0
    with database.session() as session:
        results = FtsQueryService(session).search_notes("invariance")
        assert results


def test_in_document_search_literal(database: Database) -> None:
    from academic_platform.application.document_search import (
        DocumentSearchService,
    )
    from academic_platform.infrastructure.database.models import (
        DocumentAsset,
        DocumentChunk,
    )

    with database.session() as session:
        document = DocumentAsset(
            key="doc-1",
            display_name="Paper",
            location="/tmp/paper.pdf",
            checksum_sha256="0" * 64,
        )
        session.add(document)
        session.flush()
        session.add(
            DocumentChunk(
                document_id=document.id,
                chunk_index=0,
                page_number=1,
                content="The study examined measurement invariance.",
            )
        )
    manager = _ShimmedManager(database)
    service = DocumentSearchService(manager)  # type: ignore[arg-type]
    result = service.search("doc-1", "invariance")
    manager.close_all()
    assert result.match_count == 1


def test_document_linking(database: Database) -> None:
    from academic_platform.application.document_linking import (
        DocumentLinkingService,
    )
    from academic_platform.infrastructure.database.models import (
        Collection,
        DocumentAsset,
        ResearchProject,
    )

    with database.session() as session:
        session.add(
            DocumentAsset(
                key="doc-1",
                display_name="Paper",
                location="/tmp/paper.pdf",
                checksum_sha256="0" * 64,
            )
        )
        session.add(Collection(key="col-1", title="Reading list"))
        session.add(ResearchProject(key="proj-1", title="Study"))
    manager = _ShimmedManager(database)
    service = DocumentLinkingService(manager)  # type: ignore[arg-type]
    service.link_document_to_collection("doc-1", "col-1")
    service.link_document_to_project("doc-1", "proj-1")
    view = service.links_for_document("doc-1")
    manager.close_all()
    assert view.collections
    assert view.projects


def test_assistant_handoff_round_trip(database: Database) -> None:
    from academic_platform.application.assistant_handoff import (
        AssistantHandoffService,
        HandoffStore,
    )
    from academic_platform.infrastructure.database.models import (
        DocumentAsset,
        DocumentMetadata,
    )

    with database.session() as session:
        document = DocumentAsset(
            key="doc-1",
            display_name="Paper",
            location="/tmp/paper.pdf",
            checksum_sha256="0" * 64,
            page_count=3,
        )
        session.add(document)
        session.flush()
        session.add(
            DocumentMetadata(
                document_id=document.id,
                title="Paper",
                authors_json='["A"]',
                year=2020,
            )
        )
    store = HandoffStore()
    manager = _ShimmedManager(database)
    service = AssistantHandoffService(manager, store=store)  # type: ignore[arg-type]
    handoff = service.build_handoff("doc-1", current_page=2)
    manager.close_all()
    assert handoff.title == "Paper"
    assert store.get("doc-1") is handoff


def test_persistence_survives_reopen(tmp_path: Path) -> None:
    from academic_platform.infrastructure.database import (
        Database,
        DatabaseConfiguration,
    )
    from academic_platform.infrastructure.database.base import Base
    from academic_platform.infrastructure.database.models import (
        Annotation,
        DocumentAsset,
        DocumentChunk,
    )

    url = f"sqlite:///{(tmp_path / 'persist.sqlite3').as_posix()}"
    database = Database(DatabaseConfiguration(url=url))
    Base.metadata.create_all(database.engine)
    with database.session() as session:
        document = DocumentAsset(
            key="persist",
            display_name="Persistent",
            location="/tmp/persist.pdf",
            checksum_sha256="0" * 64,
        )
        session.add(document)
        session.flush()
        session.add(
            DocumentChunk(
                document_id=document.id,
                chunk_index=0,
                page_number=1,
                content="Persistent content.",
            )
        )
        session.add(
            Annotation(
                document_id=document.id,
                kind="note",
                page_number=1,
                body="Persistent note.",
            )
        )
    database.dispose()

    reopened = Database(DatabaseConfiguration(url=url))
    try:
        with reopened.session() as session:
            assert session.query(DocumentAsset).count() == 1
            assert session.query(DocumentChunk).count() == 1
            assert session.query(Annotation).count() == 1
    finally:
        reopened.dispose()