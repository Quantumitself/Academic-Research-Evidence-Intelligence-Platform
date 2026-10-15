"""Tests for the reader page integration with in-document search."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QLineEdit  # noqa: E402

import fitz  # PyMuPDF  # noqa: E402

from academic_platform.application.document_reading.service import (  # noqa: E402
    DocumentReaderService,
)
from academic_platform.application.document_search.service import (  # noqa: E402
    DocumentSearchService,
)
from academic_platform.infrastructure.database import Database  # noqa: E402
from academic_platform.infrastructure.database.base import Base  # noqa: E402
from academic_platform.infrastructure.database.models import (  # noqa: E402
    DocumentAsset,
    DocumentChunk,
)
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


def _make_pdf(path: Path, text: str = "text") -> None:
    document = fitz.open()
    try:
        page = document.new_page()
        page.insert_text((72, 72), text)
        document.save(str(path))
    finally:
        document.close()


def test_reader_search_finds_matches(app: QApplication, tmp_path: Path) -> None:
    database = Database.in_memory()
    Base.metadata.create_all(database.engine)
    pdf = tmp_path / "paper.pdf"
    _make_pdf(pdf, "Content")
    with database.session() as session:
        document = DocumentAsset(
            key="doc-1",
            display_name="Paper",
            location=str(pdf.resolve()),
            checksum_sha256="0" * 64,
        )
        session.add(document)
        session.flush()
        session.add(
            DocumentChunk(
                document_id=document.id,
                chunk_index=0,
                page_number=1,
                content="The study examined measurement invariance across groups.",
            )
        )
    manager = _ShimmedManager(database)
    page = ReaderPage()
    page.attach_service(DocumentReaderService(manager))  # type: ignore[arg-type]
    page.attach_search_service(DocumentSearchService(manager))  # type: ignore[arg-type]
    assert page.load_document("doc-1") is True
    input_widget = page.findChild(QLineEdit, "documentSearchInput")
    assert input_widget is not None
    input_widget.setText("invariance")
    page._search_panel._on_search()  # noqa: SLF001
    from PySide6.QtWidgets import QListWidget

    listing = page.findChild(QListWidget, "documentSearchResults")
    assert listing is not None
    assert listing.count() == 1
    manager.close_all()
    database.dispose()