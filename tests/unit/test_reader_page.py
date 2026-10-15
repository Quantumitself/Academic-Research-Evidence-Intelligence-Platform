"""Tests for the reader page."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import (  # noqa: E402
    QApplication,
    QComboBox,
    QListWidget,
    QPushButton,
    QSpinBox,
)

import fitz  # PyMuPDF  # noqa: E402

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


def _make_pdf(path: Path, pages: int, outline: bool = False) -> None:
    document = fitz.open()
    try:
        for index in range(pages):
            page = document.new_page()
            page.insert_text((72, 72), f"Page {index + 1}")
        if outline:
            document.set_toc([[1, "Introduction", 1], [1, "Methods", 2]])
        document.save(str(path))
    finally:
        document.close()


def _seed(database: Database, path: Path) -> None:
    with database.session() as session:
        session.add(
            DocumentAsset(
                key="doc-1",
                display_name="Paper",
                location=str(path.resolve()),
                checksum_sha256="0" * 64,
            )
        )


def test_reader_loads_document(app: QApplication, tmp_path: Path) -> None:
    database = Database.in_memory()
    Base.metadata.create_all(database.engine)
    pdf = tmp_path / "paper.pdf"
    _make_pdf(pdf, 3)
    _seed(database, pdf)
    manager = _ShimmedManager(database)
    page = ReaderPage()
    page.attach_service(DocumentReaderService(manager))  # type: ignore[arg-type]
    assert page.load_document("doc-1") is True
    assert page._page_count == 3  # noqa: SLF001
    assert page._current_page == 1  # noqa: SLF001
    manager.close_all()
    database.dispose()


def test_reader_navigates_pages(app: QApplication, tmp_path: Path) -> None:
    database = Database.in_memory()
    Base.metadata.create_all(database.engine)
    pdf = tmp_path / "paper.pdf"
    _make_pdf(pdf, 3)
    _seed(database, pdf)
    manager = _ShimmedManager(database)
    page = ReaderPage()
    page.attach_service(DocumentReaderService(manager))  # type: ignore[arg-type]
    page.load_document("doc-1")
    page._on_next_page()  # noqa: SLF001
    assert page._current_page == 2  # noqa: SLF001
    page._on_last_page()  # noqa: SLF001
    assert page._current_page == 3  # noqa: SLF001
    page._on_first_page()  # noqa: SLF001
    assert page._current_page == 1  # noqa: SLF001
    manager.close_all()
    database.dispose()


def test_reader_zoom_changes_dpi(app: QApplication, tmp_path: Path) -> None:
    database = Database.in_memory()
    Base.metadata.create_all(database.engine)
    pdf = tmp_path / "paper.pdf"
    _make_pdf(pdf, 1)
    _seed(database, pdf)
    manager = _ShimmedManager(database)
    page = ReaderPage()
    page.attach_service(DocumentReaderService(manager))  # type: ignore[arg-type]
    page.load_document("doc-1")
    combo = page.findChild(QComboBox, "readerZoomCombo")
    assert combo is not None
    combo.setCurrentIndex(2)
    assert page._current_dpi == combo.currentData()  # noqa: SLF001
    manager.close_all()
    database.dispose()


def test_reader_outline_populated(app: QApplication, tmp_path: Path) -> None:
    database = Database.in_memory()
    Base.metadata.create_all(database.engine)
    pdf = tmp_path / "paper.pdf"
    _make_pdf(pdf, 2, outline=True)
    _seed(database, pdf)
    manager = _ShimmedManager(database)
    page = ReaderPage()
    page.attach_service(DocumentReaderService(manager))  # type: ignore[arg-type]
    page.load_document("doc-1")
    outline = page.findChild(QListWidget, "readerOutlineList")
    assert outline is not None
    assert outline.count() == 2
    manager.close_all()
    database.dispose()


def test_reader_close_emits_signal(app: QApplication, tmp_path: Path) -> None:
    database = Database.in_memory()
    Base.metadata.create_all(database.engine)
    pdf = tmp_path / "paper.pdf"
    _make_pdf(pdf, 1)
    _seed(database, pdf)
    manager = _ShimmedManager(database)
    page = ReaderPage()
    page.attach_service(DocumentReaderService(manager))  # type: ignore[arg-type]
    page.load_document("doc-1")
    received: list[bool] = []
    page.close_requested.connect(lambda: received.append(True))
    page._on_close()  # noqa: SLF001
    assert received == [True]
    assert page._document_key == ""  # noqa: SLF001
    manager.close_all()
    database.dispose()


def test_reader_navigation_buttons_present(app: QApplication) -> None:
    page = ReaderPage()
    for name in (
        "readerFirstButton",
        "readerPreviousButton",
        "readerNextButton",
        "readerLastButton",
        "readerCloseButton",
    ):
        button = page.findChild(QPushButton, name)
        assert button is not None, name