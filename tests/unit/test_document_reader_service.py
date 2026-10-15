"""Tests for the document reader service.

The tests build small PDFs with PyMuPDF at test time.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import fitz  # PyMuPDF

from academic_platform.application.document_reading.errors import (
    DocumentReadingError,
    DocumentReadingNotFoundError,
    DocumentReadingUnsupportedError,
)
from academic_platform.application.document_reading.service import (
    DocumentReaderService,
)
from academic_platform.infrastructure.database import Database
from academic_platform.infrastructure.database.base import Base
from academic_platform.infrastructure.database.models import DocumentAsset
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


def _make_pdf(path: Path, pages: int, *, outline: bool = False) -> None:
    document = fitz.open()
    try:
        for index in range(pages):
            page = document.new_page()
            page.insert_text((72, 72), f"Page {index + 1}")
        if outline:
            document.set_toc(
                [
                    [1, "Introduction", 1],
                    [2, "Background", 1],
                    [1, "Methods", 2],
                ]
            )
        document.save(str(path))
    finally:
        document.close()


def _seed_document(database: Database, key: str, path: Path) -> None:
    with database.session() as session:
        session.add(
            DocumentAsset(
                key=key,
                display_name="Paper",
                location=str(path.resolve()),
                checksum_sha256="0" * 64,
            )
        )


def test_open_document_returns_page_count(database: Database, tmp_path: Path) -> None:
    pdf = tmp_path / "paper.pdf"
    _make_pdf(pdf, 3)
    _seed_document(database, "doc-1", pdf)
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = DocumentReaderService(repositories)
        page_count, outline = service.open_document("doc-1")
        assert page_count == 3
        assert outline == ()
        service.close_all()


def test_open_document_returns_outline(database: Database, tmp_path: Path) -> None:
    pdf = tmp_path / "paper.pdf"
    _make_pdf(pdf, 2, outline=True)
    _seed_document(database, "doc-1", pdf)
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = DocumentReaderService(repositories)
        page_count, outline = service.open_document("doc-1")
        assert page_count == 2
        titles = [entry.title for entry in outline]
        assert "Introduction" in titles
        assert "Methods" in titles
        service.close_all()


def test_render_page_returns_png(database: Database, tmp_path: Path) -> None:
    pdf = tmp_path / "paper.pdf"
    _make_pdf(pdf, 1)
    _seed_document(database, "doc-1", pdf)
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = DocumentReaderService(repositories)
        rendered = service.render_page("doc-1", 1, dpi=96)
        assert rendered.page_number == 1
        assert rendered.pixel_width > 0
        assert rendered.pixel_height > 0
        assert rendered.image_bytes.startswith(b"\x89PNG")
        service.close_all()


def test_render_page_caches(database: Database, tmp_path: Path) -> None:
    pdf = tmp_path / "paper.pdf"
    _make_pdf(pdf, 2)
    _seed_document(database, "doc-1", pdf)
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = DocumentReaderService(repositories, cache_size=2)
        first = service.render_page("doc-1", 1, dpi=96)
        second = service.render_page("doc-1", 1, dpi=96)
        # The second call must return the cached instance.
        assert first is second
        service.close_all()


def test_render_page_rejects_invalid_number(database: Database, tmp_path: Path) -> None:
    pdf = tmp_path / "paper.pdf"
    _make_pdf(pdf, 1)
    _seed_document(database, "doc-1", pdf)
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = DocumentReaderService(repositories)
        with pytest.raises(DocumentReadingError):
            service.render_page("doc-1", 5, dpi=96)
        service.close_all()


def test_open_missing_document_raises(database: Database) -> None:
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = DocumentReaderService(repositories)
        with pytest.raises(DocumentReadingNotFoundError):
            service.open_document("missing")


def test_open_missing_file_raises(database: Database) -> None:
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        session.add(
            DocumentAsset(
                key="doc-1",
                display_name="Paper",
                location="/tmp/does-not-exist.pdf",
                checksum_sha256="0" * 64,
            )
        )
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = DocumentReaderService(repositories)
        with pytest.raises(DocumentReadingNotFoundError):
            service.open_document("doc-1")


def test_dpi_is_clamped(database: Database, tmp_path: Path) -> None:
    pdf = tmp_path / "paper.pdf"
    _make_pdf(pdf, 1)
    _seed_document(database, "doc-1", pdf)
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = DocumentReaderService(repositories)
        rendered = service.render_page("doc-1", 1, dpi=10)
        assert rendered.dpi >= 36
        service.close_all()


def test_close_document_releases_cache(database: Database, tmp_path: Path) -> None:
    pdf = tmp_path / "paper.pdf"
    _make_pdf(pdf, 1)
    _seed_document(database, "doc-1", pdf)
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = DocumentReaderService(repositories)
        service.render_page("doc-1", 1, dpi=96)
        assert service._cache  # noqa: SLF001
        service.close_document("doc-1")
        assert not service._cache  # noqa: SLF001