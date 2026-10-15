"""Tests for the Topic section's integration with the workspace service."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

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
        session.add(
            ResearchProject(key=key, title="Study", topic="Initial")
        )


def test_section_without_service(app: QApplication) -> None:
    section = create_section(AssistantSectionId.TOPIC)
    assert isinstance(section, TopicSection)
    section._subject.setPlainText("Subject")  # noqa: SLF001
    assert "subject" in section.summary().lower()


def test_section_persists_edits(app: QApplication) -> None:
    database = Database.in_memory()
    Base.metadata.create_all(database.engine)
    _seed_project(database)
    manager = _ShimmedManager(database)
    service = TopicWorkspaceService(manager)  # type: ignore[arg-type]
    section = create_section(AssistantSectionId.TOPIC)
    assert isinstance(section, TopicSection)
    section.attach_service(service)
    section.attach_project("study-1")
    section._subject.setPlainText("New subject")  # noqa: SLF001
    section._on_editor_changed(TopicField.BROAD_SUBJECT)  # noqa: SLF001
    manager.close_all()
    with database.session() as session:
        project = session.query(ResearchProject).one()
        assert project.topic == "New subject"
    database.dispose()


def test_section_summary_reports_completeness(app: QApplication) -> None:
    database = Database.in_memory()
    Base.metadata.create_all(database.engine)
    _seed_project(database)
    manager = _ShimmedManager(database)
    service = TopicWorkspaceService(manager)  # type: ignore[arg-type]
    service.attach_project("study-1")
    service.set_fields(
        {
            TopicField.BROAD_SUBJECT: "Subject",
            TopicField.RESEARCH_PROBLEM: "Problem",
        }
    )
    section = create_section(AssistantSectionId.TOPIC)
    assert isinstance(section, TopicSection)
    section.attach_service(service)
    assert "2 /" in section.summary()
    manager.close_all()
    database.dispose()


def test_section_reset_clears_state(app: QApplication) -> None:
    database = Database.in_memory()
    Base.metadata.create_all(database.engine)
    _seed_project(database)
    manager = _ShimmedManager(database)
    service = TopicWorkspaceService(manager)  # type: ignore[arg-type]
    service.attach_project("study-1")
    service.set_field(TopicField.BROAD_SUBJECT, "Subject")
    section = create_section(AssistantSectionId.TOPIC)
    assert isinstance(section, TopicSection)
    section.attach_service(service)
    assert section.summary()
    section.reset()
    assert section.summary() == ""
    manager.close_all()
    database.dispose()