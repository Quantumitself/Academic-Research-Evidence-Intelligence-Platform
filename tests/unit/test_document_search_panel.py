"""Tests for the in-document search panel."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import (  # noqa: E402
    QApplication,
    QCheckBox,
    QLineEdit,
    QListWidget,
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
from academic_platform.ui.pages.reader.search_panel import (  # noqa: E402
    DocumentSearchPanel,
)


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
                content="The study examined measurement Invariance across groups.",
            )
        )


def test_panel_renders_matches(app: QApplication) -> None:
    database = Database.in_memory()
    Base.metadata.create_all(database.engine)
    _seed(database)
    manager = _ShimmedManager(database)
    panel = DocumentSearchPanel()
    panel.attach_service(DocumentSearchService(manager))  # type: ignore[arg-type]
    panel.set_document("doc-1")
    input_widget = panel.findChild(QLineEdit, "documentSearchInput")
    assert input_widget is not None
    input_widget.setText("invariance")
    panel._on_search()  # noqa: SLF001
    listing = panel.findChild(QListWidget, "documentSearchResults")
    assert listing is not None
    assert listing.count() == 1
    manager.close_all()
    database.dispose()


def test_panel_case_sensitive_toggle(app: QApplication) -> None:
    database = Database.in_memory()
    Base.metadata.create_all(database.engine)
    _seed(database)
    manager = _ShimmedManager(database)
    panel = DocumentSearchPanel()
    panel.attach_service(DocumentSearchService(manager))  # type: ignore[arg-type]
    panel.set_document("doc-1")
    input_widget = panel.findChild(QLineEdit, "documentSearchInput")
    case_checkbox = panel.findChild(QCheckBox, "documentSearchCaseSensitive")
    assert input_widget is not None and case_checkbox is not None
    case_checkbox.setChecked(True)
    input_widget.setText("invariance")
    panel._on_search()  # noqa: SLF001
    listing = panel.findChild(QListWidget, "documentSearchResults")
    assert listing is not None
    assert listing.count() == 0
    manager.close_all()
    database.dispose()


def test_panel_clear_emits_signal(app: QApplication) -> None:
    database = Database.in_memory()
    Base.metadata.create_all(database.engine)
    _seed(database)
    manager = _ShimmedManager(database)
    panel = DocumentSearchPanel()
    panel.attach_service(DocumentSearchService(manager))  # type: ignore[arg-type]
    panel.set_document("doc-1")
    received: list[int] = []
    panel.search_cleared.connect(lambda: received.append(1))
    panel._on_clear()  # noqa: SLF001
    assert received
    manager.close_all()
    database.dispose()


def test_panel_empty_query_no_results(app: QApplication) -> None:
    database = Database.in_memory()
    Base.metadata.create_all(database.engine)
    _seed(database)
    manager = _ShimmedManager(database)
    panel = DocumentSearchPanel()
    panel.attach_service(DocumentSearchService(manager))  # type: ignore[arg-type]
    panel.set_document("doc-1")
    panel._on_search()  # noqa: SLF001
    listing = panel.findChild(QListWidget, "documentSearchResults")
    assert listing is not None
    assert listing.count() == 0
    manager.close_all()
    database.dispose()