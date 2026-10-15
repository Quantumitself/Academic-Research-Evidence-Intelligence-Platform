"""Tests for the library page."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QPushButton  # noqa: E402

from academic_platform.application.library.service import LibraryService  # noqa: E402
from academic_platform.infrastructure.database import Database  # noqa: E402
from academic_platform.infrastructure.database.base import Base  # noqa: E402
from academic_platform.infrastructure.database.models import DocumentAsset  # noqa: E402
from academic_platform.infrastructure.repositories.factory import (  # noqa: E402
    _REPOSITORY_REGISTRY,
)
from academic_platform.infrastructure.repositories.manager import (  # noqa: E402
    RepositoryManager,
)
from academic_platform.ui.pages.library import LibraryPage  # noqa: E402


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


def _seed(database: Database) -> None:
    with database.session() as session:
        session.add(
            DocumentAsset(
                key="a",
                display_name="Alpha",
                original_filename="Alpha.pdf",
                location="/tmp/alpha.pdf",
                checksum_sha256="0" * 64,
                processing_state="extracted",
            )
        )


def test_library_page_empty_state(app: QApplication) -> None:
    database = Database.in_memory()
    Base.metadata.create_all(database.engine)
    manager = _ShimmedManager(database)
    page = LibraryPage()
    page.attach_service(LibraryService(manager))  # type: ignore[arg-type]
    from PySide6.QtWidgets import QLabel

    # The page's body stack holds the empty state as the visible widget
    # when there are no entries.
    assert page._model.rowCount() == 0  # noqa: SLF001
    manager.close_all()
    database.dispose()


def test_library_page_lists_documents(app: QApplication) -> None:
    database = Database.in_memory()
    Base.metadata.create_all(database.engine)
    _seed(database)
    manager = _ShimmedManager(database)
    page = LibraryPage()
    page.attach_service(LibraryService(manager))  # type: ignore[arg-type]
    assert page._model.rowCount() == 1  # noqa: SLF001
    manager.close_all()
    database.dispose()


def test_library_page_search_filters(app: QApplication) -> None:
    database = Database.in_memory()
    Base.metadata.create_all(database.engine)
    _seed(database)
    manager = _ShimmedManager(database)
    page = LibraryPage()
    page.attach_service(LibraryService(manager))  # type: ignore[arg-type]
    page._search_input.setText("nothing")  # noqa: SLF001
    page._apply_search()  # noqa: SLF001
    assert page._model.rowCount() == 0  # noqa: SLF001
    manager.close_all()
    database.dispose()


def test_library_page_refresh_button_present(app: QApplication) -> None:
    page = LibraryPage()
    button = page.findChild(QPushButton, "libraryRefreshButton")
    assert button is not None
    assert button.isEnabled()


def test_library_page_import_button_present(app: QApplication) -> None:
    page = LibraryPage()
    button = page.findChild(QPushButton, "libraryImportButton")
    assert button is not None
    assert button.isEnabled()


def test_library_page_reports_missing_service(app: QApplication) -> None:
    page = LibraryPage()
    # Refreshing without a service must not crash.
    page.refresh()