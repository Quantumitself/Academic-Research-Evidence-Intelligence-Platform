"""Tests for the linking dialog."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QCheckBox, QPushButton  # noqa: E402

from academic_platform.application.document_linking.service import (  # noqa: E402
    DocumentLinkingService,
)
from academic_platform.infrastructure.database import Database  # noqa: E402
from academic_platform.infrastructure.database.base import Base  # noqa: E402
from academic_platform.infrastructure.database.models import (  # noqa: E402
    Collection,
    DocumentAsset,
    ResearchProject,
)
from academic_platform.infrastructure.repositories.factory import (  # noqa: E402
    _REPOSITORY_REGISTRY,
)
from academic_platform.ui.dialogs.link_document_dialog import (  # noqa: E402
    LinkDocumentDialog,
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
        session.add(Collection(key="col-1", title="Reading list"))
        session.add(ResearchProject(key="proj-1", title="Study"))


def test_dialog_lists_collections_and_projects(app: QApplication) -> None:
    database = Database.in_memory()
    Base.metadata.create_all(database.engine)
    _seed(database)
    manager = _ShimmedManager(database)
    service = DocumentLinkingService(manager)  # type: ignore[arg-type]
    dialog = LinkDocumentDialog(service, "doc-1")
    # The Collections tab should have one checkbox.
    assert len(dialog._collection_checkboxes) == 1  # noqa: SLF001
    # The Projects tab should have one checkbox.
    assert len(dialog._project_checkboxes) == 1  # noqa: SLF001
    dialog.close()
    manager.close_all()
    database.dispose()


def test_dialog_apply_links_collection(app: QApplication) -> None:
    database = Database.in_memory()
    Base.metadata.create_all(database.engine)
    _seed(database)
    manager = _ShimmedManager(database)
    service = DocumentLinkingService(manager)  # type: ignore[arg-type]
    dialog = LinkDocumentDialog(service, "doc-1")
    checkbox = dialog._collection_checkboxes["col-1"]  # noqa: SLF001
    checkbox.setChecked(True)
    dialog._on_apply()  # noqa: SLF001
    manager.close_all()
    # Verify the link was created.
    with database.session() as session:
        from academic_platform.infrastructure.database.models import (
            CollectionItem,
        )

        assert session.query(CollectionItem).count() == 1
    database.dispose()


def test_dialog_apply_unlinks_collection(app: QApplication) -> None:
    database = Database.in_memory()
    Base.metadata.create_all(database.engine)
    _seed(database)
    manager = _ShimmedManager(database)
    service = DocumentLinkingService(manager)  # type: ignore[arg-type]
    service.link_document_to_collection("doc-1", "col-1")
    manager.close_all()
    dialog = LinkDocumentDialog(
        DocumentLinkingService(manager), "doc-1"  # type: ignore[arg-type]
    )
    checkbox = dialog._collection_checkboxes["col-1"]  # noqa: SLF001
    checkbox.setChecked(False)
    dialog._on_apply()  # noqa: SLF001
    manager.close_all()
    with database.session() as session:
        from academic_platform.infrastructure.database.models import (
            CollectionItem,
        )

        assert session.query(CollectionItem).count() == 0
    database.dispose()


def test_dialog_apply_links_project(app: QApplication) -> None:
    database = Database.in_memory()
    Base.metadata.create_all(database.engine)
    _seed(database)
    manager = _ShimmedManager(database)
    service = DocumentLinkingService(manager)  # type: ignore[arg-type]
    dialog = LinkDocumentDialog(service, "doc-1")
    checkbox = dialog._project_checkboxes["proj-1"]  # noqa: SLF001
    checkbox.setChecked(True)
    dialog._on_apply()  # noqa: SLF001
    manager.close_all()
    with database.session() as session:
        from academic_platform.infrastructure.database.models import (
            Collection,
        )

        projects = [c for c in session.query(Collection).all() if c.kind == "project"]
        assert projects
    database.dispose()


def test_dialog_buttons_present(app: QApplication) -> None:
    database = Database.in_memory()
    Base.metadata.create_all(database.engine)
    _seed(database)
    manager = _ShimmedManager(database)
    dialog = LinkDocumentDialog(
        DocumentLinkingService(manager), "doc-1"  # type: ignore[arg-type]
    )
    apply_button = dialog.findChild(QPushButton, "linkDialogApply")
    cancel_button = dialog.findChild(QPushButton, "linkDialogCancel")
    assert apply_button is not None
    assert cancel_button is not None
    dialog.close()
    manager.close_all()
    database.dispose()