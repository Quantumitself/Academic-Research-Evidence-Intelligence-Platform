"""Tests that the document extraction service persists metadata."""

from __future__ import annotations

from pathlib import Path

import pytest

import fitz  # PyMuPDF

from academic_platform.application.document_extraction.service import (
    DocumentExtractionService,
)
from academic_platform.infrastructure.database import Database
from academic_platform.infrastructure.database.base import Base
from academic_platform.infrastructure.database.models import (
    DocumentAsset,
    DocumentMetadata,
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


def _make_pdf(path: Path, body_lines: list[str], metadata: dict[str, str] | None = None) -> None:
    document = fitz.open()
    try:
        page = document.new_page()
        y = 72.0
        for line in body_lines:
            page.insert_text((72, y), line)
            y += 16
        if metadata is not None:
            document.set_metadata(metadata)
        document.save(str(path))
    finally:
        document.close()


def _seed_document(database: Database, path: Path) -> None:
    with database.session() as session:
        session.add(
            DocumentAsset(
                key="doc-1",
                display_name="Paper",
                location=str(path.resolve()),
                checksum_sha256="0" * 64,
            )
        )


def test_metadata_persisted(database: Database, tmp_path: Path) -> None:
    pdf = tmp_path / "paper.pdf"
    _make_pdf(
        pdf,
        body_lines=["A Study"],
        metadata={
            "title": "A Study",
            "author": "A. Author; B. Author",
            "creationDate": "D:20200101",
        },
    )
    _seed_document(database, pdf)
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        DocumentExtractionService(repositories).extract_document("doc-1")
    with database.session() as session:
        row = session.query(DocumentMetadata).one()
        assert row.title == "A Study"
        assert row.year == 2020
        assert row.authors_json is not None
        assert "A. Author" in row.authors_json
        assert row.extraction_method == "pdf_heuristic"
        assert row.extraction_confidence is not None


def test_metadata_reviewed_is_preserved(
    database: Database, tmp_path: Path
) -> None:
    pdf = tmp_path / "paper.pdf"
    _make_pdf(pdf, body_lines=["text"], metadata={"title": "From PDF"})
    _seed_document(database, pdf)
    with database.session() as session:
        row = session.query(DocumentAsset).one()
        session.add(
            DocumentMetadata(
                document_id=row.id,
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