"""Tests for the reader page integration with the annotation panel."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

import fitz  # PyMuPDF  # noqa: E402

from academic_platform.application.annotations.service import (  # noqa: E402
    AnnotationService,
)
from academic_platform.application.document_reading.service import (  # noqa: E402
    DocumentReaderService,
)
from academic_platform.infrastructure.database import Database  # noqa: E402
from academic_platform.infrastructure.database.base import Base  # noqa: E402
from academic_platform.infrastructure.database.models import DocumentAsset  # noqa: E402
from academic_platform.infrastructure.repositories.factory import (  # noqa: E402
    _REPOSITORY_REGISTRY,
)
from academic_platform.ui.pages.reader import ReaderPage  # noqa: E402


@pytest.fixture(scope="module")
def app() -> QApplication:
    return QApplication.instance() or QApplication([])


class _ShimmedManager:
    def __init__(self, database: Database) -> None:
        self._database = database
        self._sessions: list = []

    def get(self, key: str):
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


def _make_pdf(path: Path, pages: int = 2) -> None:
    document = fitz.open()
    try:
        for index in range(pages):
            page = document.new_page()
            page.insert_text((72, 72), f"Page {index + 1}")
        document.save(str(path))
    finally:
        document.close()


def test_reader_lists_annotations_on_load(app: QApplication, tmp_path: Path) -> None:
    database = Database.in_memory()
    Base.metadata.create_all(database.engine)
    pdf = tmp_path / "paper.pdf"
    _make_pdf(pdf)
    with database.session() as session:
        session.add(
            DocumentAsset(
                key="doc-1",
                display_name="Paper",
                location=str(pdf.resolve()),
                checksum_sha256="0" * 64,
            )
        )
    manager = _ShimmedManager(database)
    reader_service = DocumentReaderService(manager)  # type: ignore[arg-type]
    annotation_service = AnnotationService(manager)  # type: ignore[arg-type]
    annotation_service.create_note("doc-1", 1, "A note.")
    manager.close_all()

    page = ReaderPage()
    page.attach_service(DocumentReaderService(manager))  # type: ignore[arg-type]
    page.attach_annotation_service(AnnotationService(manager))  # type: ignore[arg-type]
    assert page.load_document("doc-1") is True

    from PySide6.QtWidgets import QListWidget

    listing = page.findChild(QListWidget, "annotationList")
    assert listing is not None
    assert listing.count() == 1
    manager.close_all()
    database.dispose()