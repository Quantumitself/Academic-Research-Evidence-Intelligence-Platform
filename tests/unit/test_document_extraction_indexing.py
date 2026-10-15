"""Tests that document extraction updates the FTS index."""

from __future__ import annotations

from pathlib import Path

import pytest

import fitz  # PyMuPDF

from academic_platform.application.document_extraction.service import (
    DocumentExtractionService,
)
from academic_platform.infrastructure.database import Database
from academic_platform.infrastructure.database.base import Base
from academic_platform.infrastructure.database.models import DocumentAsset
from academic_platform.infrastructure.full_text_search.query import (
    FtsQueryService,
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


def _make_pdf(path: Path, text: str) -> None:
    document = fitz.open()
    try:
        page = document.new_page()
        page.insert_text((72, 72), text)
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


def test_extraction_indexes_chunks(database: Database, tmp_path: Path) -> None:
    pdf = tmp_path / "paper.pdf"
    _make_pdf(pdf, "Content about invariance in measurement.")
    _seed_document(database, pdf)
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        DocumentExtractionService(repositories, index_enabled=True).extract_document(
            "doc-1"
        )
    with database.session() as session:
        service = FtsQueryService(session)
        results = service.search_documents("invariance")
        assert results
        assert results[0].identifier == "doc-1"


def test_extraction_skips_indexing_when_disabled(
    database: Database, tmp_path: Path
) -> None:
    pdf = tmp_path / "paper.pdf"
    _make_pdf(pdf, "Content about invariance in measurement.")
    _seed_document(database, pdf)
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        DocumentExtractionService(
            repositories, index_enabled=False
        ).extract_document("doc-1")
    with database.session() as session:
        service = FtsQueryService(session)
        results = service.search_documents("invariance")
        assert results == []