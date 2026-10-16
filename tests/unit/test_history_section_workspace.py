"""Tests for the Research History section's service integration."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import (  # noqa: E402
    QApplication,
    QListWidget,
    QPushButton,
)

from academic_platform.application.research_history.service import (  # noqa: E402
    ResearchHistoryService,
)
from academic_platform.infrastructure.database import Database  # noqa: E402
from academic_platform.infrastructure.database.base import Base  # noqa: E402
from academic_platform.infrastructure.database.models import (  # noqa: E402
    ResearchProject,
)
from academic_platform.infrastructure.repositories.factory import (  # noqa: E402
    _REPOSITORY_REGISTRY,
)
from academic_platform.ui.pages.research_assistant.section_base import (  # noqa: E402
    AssistantSectionId,
)
from academic_platform.ui.pages.research_assistant.sections import (  # noqa: E402
    create_section,
)
from academic_platform.ui.pages.research_assistant.sections.history_section import (  # noqa: E402
    ResearchHistorySection,
)


@pytest.fixture(scope="module")
def app() -> QApplication:
    return QApplication.instance() or QApplication([])


class _ShimmedManager:
    """A repository manager that shares one session across all calls.

    Sharing the session ensures that entities loaded by one repository
    remain attached when passed to another, and that uncommitted
    writes are visible to subsequent reads.
    """

    def __init__(self, database: Database) -> None:
        self._session = database._session_factory()  # noqa: SLF001

    def get(self, key: str):
        return _REPOSITORY_REGISTRY[key](self._session)

    def register_all(self, mapping) -> None:
        return None

    def close_all(self) -> None:
        try:
            self._session.commit()
        except Exception:  # noqa: BLE001
            self._session.rollback()
        finally:
            self._session.close()


def _seed_project(database: Database, key: str = "study-1") -> None:
    with database.session() as session:
        session.add(
            ResearchProject(key=key, title="Study", topic="Initial topic")
        )


def test_section_renders_topic(app: QApplication) -> None:
    database = Database.in_memory()
    Base.metadata.create_all(database.engine)
    _seed_project(database)
    manager = _ShimmedManager(database)
    service = ResearchHistoryService(manager)  # type: ignore[arg-type]
    service.attach_project("study-1")
    section = create_section(AssistantSectionId.RESEARCH_HISTORY)
    assert isinstance(section, ResearchHistorySection)
    section.attach_service(service, "study-1")
    assert section._topic_input.text() == "Initial topic"  # noqa: SLF001
    manager.close_all()
    database.dispose()


def test_section_add_synonym(app: QApplication) -> None:
    database = Database.in_memory()
    Base.metadata.create_all(database.engine)
    _seed_project(database)
    manager = _ShimmedManager(database)
    service = ResearchHistoryService(manager)  # type: ignore[arg-type]
    service.attach_project("study-1")
    section = create_section(AssistantSectionId.RESEARCH_HISTORY)
    assert isinstance(section, ResearchHistorySection)
    section.attach_service(service, "study-1")
    section._synonym_input.setText("equivalence")  # noqa: SLF001
    section._on_add_synonym()  # noqa: SLF001
    listing = section.findChild(QListWidget, "historySynonymsList")
    assert listing is not None
    assert listing.count() == 1
    manager.close_all()
    database.dispose()


def test_section_add_query(app: QApplication) -> None:
    database = Database.in_memory()
    Base.metadata.create_all(database.engine)
    _seed_project(database)
    manager = _ShimmedManager(database)
    service = ResearchHistoryService(manager)  # type: ignore[arg-type]
    service.attach_project("study-1")
    section = create_section(AssistantSectionId.RESEARCH_HISTORY)
    assert isinstance(section, ResearchHistorySection)
    section.attach_service(service, "study-1")
    section._query_input.setText("custom query")  # noqa: SLF001
    section._on_add_query()  # noqa: SLF001
    assert any(
        q.is_user_defined and q.text == "custom query"
        for q in service.propose_queries("study-1")
    )
    manager.close_all()
    database.dispose()


def test_section_buttons_present(app: QApplication) -> None:
    section = create_section(AssistantSectionId.RESEARCH_HISTORY)
    for name in (
        "historyAddSynonym",
        "historyRemoveSynonym",
        "historyAddQuery",
        "historyRemoveQuery",
        "historyRunAll",
        "historyRunSelected",
        "historyClear",
    ):
        button = section.findChild(QPushButton, name)
        assert button is not None, name


def test_section_summary_reports_state(app: QApplication) -> None:
    database = Database.in_memory()
    Base.metadata.create_all(database.engine)
    _seed_project(database)
    manager = _ShimmedManager(database)
    service = ResearchHistoryService(manager)  # type: ignore[arg-type]
    service.attach_project("study-1")
    service.add_synonym("study-1", "equivalence")
    section = create_section(AssistantSectionId.RESEARCH_HISTORY)
    assert isinstance(section, ResearchHistorySection)
    section.attach_service(service, "study-1")
    assert "synonym" in section.summary().lower()
    manager.close_all()
    database.dispose()