"""Tests for the document extraction service."""

from __future__ import annotations

from pathlib import Path

import pytest

import fitz  # PyMuPDF

from academic_platform.application.document_extraction.service import (
    DocumentExtractionService,
    ExtractionOutcome,
)
from academic_platform.application.document_extraction.errors import (
    DocumentNotFoundError,
)
from academic_platform.infrastructure.database import Database
from academic_platform.infrastructure.database.base import Base
from academic_platform.infrastructure.database.models import (
    DocumentAsset,
    DocumentChunk,
    DocumentMetadata,
)
from academic_platform.infrastructure.document_processing import (
    PdfExtractorConfig,
    PdfTextExtractor,
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
def service(database: Database):
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        yield DocumentExtractionService(repositories)


def _make_pdf(path: Path, pages: list[str]) -> None:
    document = fitz.open()
    try:
        for text in pages:
            page = document.new_page()
            if text:
                page.insert_text((72, 72), text)
        document.save(str(path))
    finally:
        document.close()


def _seed_document(database: Database, path: Path) -> int:
    with database.session() as session:
        row = DocumentAsset(
            key="doc-1",
            display_name="Paper",
            location=str(path.resolve()),
            checksum_sha256="0" * 64,
            storage_mode="managed_copy",
        )
        session.add(row)
        session.flush()
        return row.id


def test_extract_persists_chunks(database: Database, tmp_path: Path) -> None:
    pdf = tmp_path / "paper.pdf"
    _make_pdf(pdf, ["First page.", "Second page."])
    _seed_document(database, pdf)
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = DocumentExtractionService(repositories)
        outcome = service.extract_document("doc-1")
        assert isinstance(outcome, ExtractionOutcome)
        assert outcome.chunk_count == 2
    with database.session() as session:
        chunks = session.query(DocumentChunk).all()
        assert len(chunks) == 2
        assert chunks[0].page_number == 1
        assert "First page." in chunks[0].content


def test_extract_persists_metadata(database: Database, tmp_path: Path) -> None:
    pdf = tmp_path / "paper.pdf"
    _make_pdf(pdf, ["text"])
    # Set metadata after the file is written.
    document = fitz.open(str(pdf))
    document.set_metadata({"title": "Title", "author": "A; B"})
    document.saveIncr()
    document.close()
    _seed_document(database, pdf)
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        DocumentExtractionService(repositories).extract_document("doc-1")
    with database.session() as session:
        row = session.query(DocumentMetadata).one()
        assert row.title == "Title"
        assert row.extraction_method == "pdf_heuristic"


def test_extraction_advances_state(database: Database, tmp_path: Path) -> None:
    pdf = tmp_path / "paper.pdf"
    _make_pdf(pdf, ["text"])
    _seed_document(database, pdf)
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        DocumentExtractionService(repositories).extract_document("doc-1")
    with database.session() as session:
        row = session.query(DocumentAsset).one()
        assert row.processing_state == "extracted"
        assert row.processing_version == 2
        assert row.page_count == 1
        assert row.last_error is None


def test_missing_file_marks_failed(database: Database, tmp_path: Path) -> None:
    _seed_document(database, tmp_path / "not-there.pdf")
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = DocumentExtractionService(repositories)
        from academic_platform.application.document_extraction.errors import (
            DocumentExtractionError,
        )

        with pytest.raises(DocumentExtractionError):
            service.extract_document("doc-1")
    with database.session() as session:
        row = session.query(DocumentAsset).one()
        assert row.processing_state == "failed"
        assert row.last_error


def test_unknown_document_raises(database: Database) -> None:
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = DocumentExtractionService(repositories)
        with pytest.raises(DocumentNotFoundError):
            service.extract_document("missing")


def test_reviewed_metadata_preserved(database: Database, tmp_path: Path) -> None:
    pdf = tmp_path / "paper.pdf"
    _make_pdf(pdf, ["text"])
    _seed_document(database, pdf)
    with database.session() as session:
        row = DocumentAsset
        document_id = session.query(DocumentAsset).one().id
        session.add(
            DocumentMetadata(
                document_id=document_id,
                title="User Edited",
                reviewed_by_user=1,
            )
        )
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        DocumentExtractionService(repositories).extract_document("doc-1")
    with database.session() as session:
        row = session.query(DocumentMetadata).one()
        assert row.title == "User Edited"


def test_replaces_chunks_on_re_extraction(database: Database, tmp_path: Path) -> None:
    pdf = tmp_path / "paper.pdf"
    _make_pdf(pdf, ["first", "second", "third"])
    _seed_document(database, pdf)
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = DocumentExtractionService(repositories)
        service.extract_document("doc-1")
    # Replace the PDF with fewer pages.
    pdf.unlink()
    _make_pdf(pdf, ["only"])
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = DocumentExtractionService(repositories)
        service.extract_document("doc-1")
    with database.session() as session:
        chunks = session.query(DocumentChunk).all()
        assert len(chunks) == 1