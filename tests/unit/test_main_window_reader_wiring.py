"""Tests for the reader wiring in the main window."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

import fitz  # PyMuPDF  # noqa: E402

from academic_platform.app.configuration import load_runtime_directories  # noqa: E402
from academic_platform.app.settings import SettingsService  # noqa: E402
from academic_platform.infrastructure.database import Database  # noqa: E402
from academic_platform.infrastructure.database.base import Base  # noqa: E402
from academic_platform.infrastructure.database.models import DocumentAsset  # noqa: E402
from academic_platform.ui.main_window import MainWindow  # noqa: E402


@pytest.fixture(scope="module")
def app() -> QApplication:
    return QApplication.instance() or QApplication([])


@pytest.fixture()
def window(app: QApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ACADEMIC_PLATFORM_HOME", str(tmp_path / "home"))
    directories = load_runtime_directories()
    settings = SettingsService(directories.config_file)
    settings.load()
    database = Database.from_path(directories.database_file)
    Base.metadata.create_all(database.engine)
    window = MainWindow(
        directories=directories,
        settings_service=settings,
        database=database,
    )
    yield window, database
    database.dispose()


def test_open_document_switches_to_reader(window, tmp_path: Path) -> None:
    main_window, database = window
    pdf = tmp_path / "paper.pdf"
    document = fitz.open()
    try:
        page = document.new_page()
        page.insert_text((72, 72), "text")
        document.save(str(pdf))
    finally:
        document.close()
    with database.session() as session:
        session.add(
            DocumentAsset(
                key="doc-1",
                display_name="Paper",
                location=str(pdf.resolve()),
                checksum_sha256="0" * 64,
            )
        )
    main_window._on_open_document_requested("doc-1")  # noqa: SLF001
    assert main_window._current_identifier == "reader"  # noqa: SLF001


def test_close_reader_returns_to_library(window) -> None:
    main_window, _ = window
    main_window.navigate_to("library")
    main_window._reader_previous_destination = "library"  # noqa: SLF001
    main_window._on_reader_close_requested()  # noqa: SLF001
    assert main_window._current_identifier == "library"  # noqa: SLF001