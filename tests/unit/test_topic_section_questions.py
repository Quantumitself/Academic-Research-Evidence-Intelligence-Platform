"""Tests for the Topic section's clarifying-questions panel."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import (  # noqa: E402
    QApplication,
    QListWidget,
    QPushButton,
)
from PySide6.QtCore import Qt  # noqa: E402

from academic_platform.application.topic_workspace.model import (  # noqa: E402
    TopicField,
)
from academic_platform.application.topic_workspace.service import (  # noqa: E402
    TopicWorkspaceService,
)
from academic_platform.infrastructure.database import Database  # noqa: E402
from academic_platform.infrastructure.database.base import Base  # noqa: E402
from academic_platform.infrastructure.database.models import ResearchProject  # noqa: E402
from academic_platform.infrastructure.repositories.factory import (  # noqa: E402
    _REPOSITORY_REGISTRY,
)
from academic_platform.ui.pages.research_assistant.section_base import (  # noqa: E402
    AssistantSectionId,
)
from academic_platform.ui.pages.research_assistant.sections import (  # noqa: E402
    create_section,
)
from academic_platform.ui.pages.research_assistant.sections.topic_section import (  # noqa: E402
    TopicSection,
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


def _seed_project(database: Database, key: str = "study-1") -> None:
    with database.session() as session:
        session.add(ResearchProject(key=key, title="Study"))


def test_questions_panel_renders_empty_draft(app: QApplication) -> None:
    database = Database.in_memory()
    Base.metadata.create_all(database.engine)
    _seed_project(database)
    manager = _ShimmedManager(database)
    service = TopicWorkspaceService(manager)  # type: ignore[arg-type]
    service.attach_project("study-1")
    section = create_section(AssistantSectionId.TOPIC)
    assert isinstance(section, TopicSection)
    section.attach_service(service)
    listing = section.findChild(QListWidget, "topicQuestionsList")
    assert listing is not None
    assert listing.count() >= 1
    manager.close_all()
    database.dispose()


def test_questions_panel_updates_when_draft_changes(app: QApplication) -> None:
    database = Database.in_memory()
    Base.metadata.create_all(database.engine)
    _seed_project(database)
    manager = _ShimmedManager(database)
    service = TopicWorkspaceService(manager)  # type: ignore[arg-type]
    service.attach_project("study-1")
    section = create_section(AssistantSectionId.TOPIC)
    assert isinstance(section, TopicSection)
    section.attach_service(service)
    listing = section.findChild(QListWidget, "topicQuestionsList")
    assert listing is not None
    initial = listing.count()
    service.set_field(TopicField.BROAD_SUBJECT, "A specific subject")
    section._refresh_questions()  # noqa: SLF001
    assert listing.count() <= initial
    manager.close_all()
    database.dispose()


def test_dismiss_question_removes_it(app: QApplication) -> None:
    database = Database.in_memory()
    Base.metadata.create_all(database.engine)
    _seed_project(database)
    manager = _ShimmedManager(database)
    service = TopicWorkspaceService(manager)  # type: ignore[arg-type]
    service.attach_project("study-1")
    section = create_section(AssistantSectionId.TOPIC)
    assert isinstance(section, TopicSection)
    section.attach_service(service)
    listing = section.findChild(QListWidget, "topicQuestionsList")
    assert listing is not None and listing.count() > 0
    listing.setCurrentRow(0)
    dismissed = listing.item(0).data(Qt.ItemDataRole.UserRole)
    assert dismissed is not None
    section._on_dismiss_question()  # noqa: SLF001
    remaining_identifiers = {
        listing.item(index).data(Qt.ItemDataRole.UserRole).identifier
        for index in range(listing.count())
    }
    assert dismissed.identifier not in remaining_identifiers
    manager.close_all()
    database.dispose()


def test_refresh_button_present(app: QApplication) -> None:
    section = create_section(AssistantSectionId.TOPIC)
    button = section.findChild(QPushButton, "topicQuestionsRefresh")
    assert button is not None


def test_focus_and_dismiss_buttons_present(app: QApplication) -> None:
    section = create_section(AssistantSectionId.TOPIC)
    for name in ("topicQuestionsFocusField", "topicQuestionsDismiss"):
        button = section.findChild(QPushButton, name)
        assert button is not None, name