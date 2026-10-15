"""Tests for the annotation panel widget."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QListWidget, QPushButton  # noqa: E402

from academic_platform.application.annotations.service import (  # noqa: E402
    AnnotationService,
)
from academic_platform.infrastructure.database import Database  # noqa: E402
from academic_platform.infrastructure.database.base import Base  # noqa: E402
from academic_platform.infrastructure.database.models import DocumentAsset  # noqa: E402
from academic_platform.infrastructure.repositories.factory import (  # noqa: E402
    _REPOSITORY_REGISTRY,
)
from academic_platform.ui.pages.reader.annotation_panel import (  # noqa: E402
    AnnotationPanel,
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
        session.add(
            DocumentAsset(
                key="doc-1",
                display_name="Paper",
                location="/tmp/paper.pdf",
                checksum_sha256="0" * 64,
            )
        )


def test_panel_lists_annotations(app: QApplication) -> None:
    database = Database.in_memory()
    Base.metadata.create_all(database.engine)
    _seed(database)
    manager = _ShimmedManager(database)
    service = AnnotationService(manager)  # type: ignore[arg-type]
    service.create_note("doc-1", 1, "First note.")
    manager.close_all()
    panel = AnnotationPanel()
    panel.attach_service(AnnotationService(manager))  # type: ignore[arg-type]
    panel.set_document("doc-1", 1)
    listing = panel.findChild(QListWidget, "annotationList")
    assert listing is not None
    assert listing.count() == 1
    manager.close_all()
    database.dispose()


def test_panel_add_buttons_disabled_without_document(app: QApplication) -> None:
    panel = AnnotationPanel()
    for name in ("annotationAddNote", "annotationAddHighlight", "annotationAddBookmark"):
        button = panel.findChild(QPushButton, name)
        assert button is not None
        assert not button.isEnabled()