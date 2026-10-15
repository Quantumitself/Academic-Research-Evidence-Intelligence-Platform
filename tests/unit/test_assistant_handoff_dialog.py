"""Tests for the assistant handoff dialog."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import (  # noqa: E402
    QApplication,
    QCheckBox,
    QPlainTextEdit,
    QPushButton,
)

from academic_platform.application.assistant_handoff.service import (  # noqa: E402
    AssistantHandoffService,
)
from academic_platform.application.assistant_handoff.store import (  # noqa: E402
    HandoffStore,
)
from academic_platform.infrastructure.database import Database  # noqa: E402
from academic_platform.infrastructure.database.base import Base  # noqa: E402
from academic_platform.infrastructure.database.models import (  # noqa: E402
    DocumentAsset,
    DocumentChunk,
    DocumentMetadata,
)
from academic_platform.infrastructure.repositories.factory import (  # noqa: E402
    _REPOSITORY_REGISTRY,
)
from academic_platform.ui.dialogs.assistant_handoff_dialog import (  # noqa: E402
    AssistantHandoffDialog,
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
            page_count=3,
        )
        session.add(document)
        session.flush()
        session.add(
            DocumentMetadata(
                document_id=document.id,
                title="A Study",
                authors_json='["A. Author"]',
                year=2020,
            )
        )
        session.add(
            DocumentChunk(
                document_id=document.id,
                chunk_index=0,
                page_number=1,
                content="Page one content about measurement.",
            )
        )


def test_dialog_renders_preview(app: QApplication) -> None:
    database = Database.in_memory()
    Base.metadata.create_all(database.engine)
    _seed(database)
    manager = _ShimmedManager(database)
    service = AssistantHandoffService(
        manager, store=HandoffStore()  # type: ignore[arg-type]
    )
    dialog = AssistantHandoffDialog(service, "doc-1", current_page=1)
    preview = dialog.findChild(QPlainTextEdit, "handoffDialogPreview")
    assert preview is not None
    assert "A Study" in preview.toPlainText()
    assert "Page one content" in preview.toPlainText()
    dialog.close()
    manager.close_all()
    database.dispose()


def test_dialog_toggle_excerpt_updates_preview(app: QApplication) -> None:
    database = Database.in_memory()
    Base.metadata.create_all(database.engine)
    _seed(database)
    manager = _ShimmedManager(database)
    service = AssistantHandoffService(
        manager, store=HandoffStore()  # type: ignore[arg-type]
    )
    dialog = AssistantHandoffDialog(service, "doc-1", current_page=1)
    checkbox = dialog.findChild(QCheckBox, "handoffIncludeExcerpt")
    assert checkbox is not None
    checkbox.setChecked(False)
    preview = dialog.findChild(QPlainTextEdit, "handoffDialogPreview")
    assert preview is not None
    assert "Page one content" not in preview.toPlainText()
    dialog.close()
    manager.close_all()
    database.dispose()


def test_dialog_send_emits_handoff(app: QApplication) -> None:
    database = Database.in_memory()
    Base.metadata.create_all(database.engine)
    _seed(database)
    manager = _ShimmedManager(database)
    service = AssistantHandoffService(
        manager, store=HandoffStore()  # type: ignore[arg-type]
    )
    dialog = AssistantHandoffDialog(service, "doc-1", current_page=1)
    received: list = []
    dialog.handoff_prepared.connect(lambda handoff: received.append(handoff))
    send_button = dialog.findChild(QPushButton, "handoffDialogSend")
    assert send_button is not None
    send_button.click()
    assert len(received) == 1
    assert received[0].document_key == "doc-1"
    dialog.close()
    manager.close_all()
    database.dispose()


def test_dialog_unknown_document_disables_send(app: QApplication) -> None:
    database = Database.in_memory()
    Base.metadata.create_all(database.engine)
    manager = _ShimmedManager(database)
    service = AssistantHandoffService(
        manager, store=HandoffStore()  # type: ignore[arg-type]
    )
    # The dialog will raise an error internally; ensure the send button
    # is disabled and the dialog does not crash.
    from academic_platform.ui.dialogs import assistant_handoff_dialog as module

    # We suppress the error dialog by not calling exec() and asserting
    # on the send button state.
    dialog = AssistantHandoffDialog(service, "missing", current_page=1)
    send_button = dialog.findChild(QPushButton, "handoffDialogSend")
    assert send_button is not None
    assert not send_button.isEnabled()
    dialog.close()
    manager.close_all()
    database.dispose()