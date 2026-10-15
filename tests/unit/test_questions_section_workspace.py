"""Tests for the Research Questions section's service integration."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import (  # noqa: E402
    QApplication,
    QListWidget,
    QPushButton,
)

from academic_platform.application.research_questions.service import (  # noqa: E402
    ResearchQuestionWorkspaceService,
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
from academic_platform.ui.pages.research_assistant.sections.questions_section import (  # noqa: E402
    ResearchQuestionsSection,
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
        session.add(ResearchProject(key=key, title="Study", topic="Topic"))


def test_section_persists_primary_question(app: QApplication) -> None:
    database = Database.in_memory()
    Base.metadata.create_all(database.engine)
    _seed_project(database)
    manager = _ShimmedManager(database)
    service = ResearchQuestionWorkspaceService(manager)  # type: ignore[arg-type]
    service.attach_project("study-1")
    section = create_section(AssistantSectionId.RESEARCH_QUESTIONS)
    assert isinstance(section, ResearchQuestionsSection)
    section.attach_service(service)
    section._primary.setPlainText("What is the effect?")  # noqa: SLF001
    section._on_field_changed()  # noqa: SLF001
    manager.close_all()
    with database.session() as session:
        from academic_platform.infrastructure.database.models import (
            ResearchQuestion,
        )

        rows = session.query(ResearchQuestion).all()
        assert any(r.text == "What is the effect?" for r in rows)
    database.dispose()


def test_section_adds_secondary_questions(app: QApplication) -> None:
    database = Database.in_memory()
    Base.metadata.create_all(database.engine)
    _seed_project(database)
    manager = _ShimmedManager(database)
    service = ResearchQuestionWorkspaceService(manager)  # type: ignore[arg-type]
    service.attach_project("study-1")
    section = create_section(AssistantSectionId.RESEARCH_QUESTIONS)
    assert isinstance(section, ResearchQuestionsSection)
    section.attach_service(service)
    section._entry_input.setText("A sub question?")  # noqa: SLF001
    section._on_add_entry()  # noqa: SLF001
    listing = section.findChild(QListWidget, "questionsEntryList")
    assert listing is not None
    assert listing.count() == 1
    manager.close_all()
    database.dispose()


def test_section_validation_label_renders(app: QApplication) -> None:
    database = Database.in_memory()
    Base.metadata.create_all(database.engine)
    _seed_project(database)
    manager = _ShimmedManager(database)
    service = ResearchQuestionWorkspaceService(manager)  # type: ignore[arg-type]
    service.attach_project("study-1")
    section = create_section(AssistantSectionId.RESEARCH_QUESTIONS)
    assert isinstance(section, ResearchQuestionsSection)
    section.attach_service(service)
    from PySide6.QtWidgets import QLabel

    label = section.findChild(QLabel, "questionsValidation")
    assert label is not None
    assert label.text()
    manager.close_all()
    database.dispose()


def test_section_buttons_present(app: QApplication) -> None:
    section = create_section(AssistantSectionId.RESEARCH_QUESTIONS)
    for name in (
        "questionsAddEntry",
        "questionsPromoteEntry",
        "questionsEditEntry",
        "questionsRemoveEntry",
    ):
        button = section.findChild(QPushButton, name)
        assert button is not None, name


def test_section_summary_reports_state(app: QApplication) -> None:
    database = Database.in_memory()
    Base.metadata.create_all(database.engine)
    _seed_project(database)
    manager = _ShimmedManager(database)
    service = ResearchQuestionWorkspaceService(manager)  # type: ignore[arg-type]
    service.attach_project("study-1")
    service.set_primary_question("What is the effect?")
    section = create_section(AssistantSectionId.RESEARCH_QUESTIONS)
    assert isinstance(section, ResearchQuestionsSection)
    section.attach_service(service)
    assert "primary" in section.summary().lower()
    manager.close_all()
    database.dispose()