"""Tests for the projects page."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import (  # noqa: E402
    QApplication,
    QComboBox,
    QListWidget,
    QPushButton,
    QTableView,
)

from academic_platform.application.projects.model import ProjectStage  # noqa: E402
from academic_platform.application.projects.service import ProjectService  # noqa: E402
from academic_platform.infrastructure.database import Database  # noqa: E402
from academic_platform.infrastructure.database.base import Base  # noqa: E402
from academic_platform.infrastructure.repositories.factory import (  # noqa: E402
    _REPOSITORY_REGISTRY,
)
from academic_platform.ui.pages.projects import ProjectsPage  # noqa: E402


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


def _service(database: Database) -> ProjectService:
    return ProjectService(_ShimmedManager(database))  # type: ignore[arg-type]


def _empty_database() -> Database:
    database = Database.in_memory()
    Base.metadata.create_all(database.engine)
    return database


def test_page_empty_state(app: QApplication) -> None:
    database = _empty_database()
    page = ProjectsPage()
    page.attach_service(_service(database))
    assert page._model.rowCount() == 0  # noqa: SLF001
    database.dispose()


def test_page_lists_projects(app: QApplication) -> None:
    database = _empty_database()
    service = _service(database)
    service.create_project(key="a", title="Alpha")
    service.create_project(key="b", title="Beta")
    manager = _ShimmedManager(database)
    page = ProjectsPage()
    page.attach_service(ProjectService(manager))  # type: ignore[arg-type]
    assert page._model.rowCount() == 2  # noqa: SLF001
    manager.close_all()
    database.dispose()


def test_page_stage_filter(app: QApplication) -> None:
    database = _empty_database()
    service = _service(database)
    service.create_project(key="a", title="Alpha", stage=ProjectStage.IDEA)
    service.create_project(key="b", title="Beta", stage=ProjectStage.DESIGN)
    manager = _ShimmedManager(database)
    page = ProjectsPage()
    page.attach_service(ProjectService(manager))  # type: ignore[arg-type]
    combo = page.findChild(QComboBox, "projectsStageFilter")
    assert combo is not None
    for index in range(combo.count()):
        if combo.itemData(index) == ProjectStage.DESIGN.value:
            combo.setCurrentIndex(index)
            break
    assert page._model.rowCount() == 1  # noqa: SLF001
    manager.close_all()
    database.dispose()


def test_page_selection_populates_detail(app: QApplication) -> None:
    database = _empty_database()
    manager = _ShimmedManager(database)
    service = ProjectService(manager)  # type: ignore[arg-type]
    service.create_project(key="a", title="Alpha", topic="A topic")
    manager.close_all()
    page = ProjectsPage()
    page.attach_service(ProjectService(manager))  # type: ignore[arg-type]
    page._select_by_key("a")  # noqa: SLF001
    assert page._current_project_key == "a"  # noqa: SLF001
    assert "Alpha" in page._detail_title.text()  # noqa: SLF001
    assert "A topic" in page._detail_topic.text()  # noqa: SLF001
    manager.close_all()
    database.dispose()


def test_page_lists_questions_and_tasks(app: QApplication) -> None:
    database = _empty_database()
    manager = _ShimmedManager(database)
    service = ProjectService(manager)  # type: ignore[arg-type]
    service.create_project(key="a", title="Alpha")
    service.add_question("a", text="What?")
    service.add_task("a", title="Read papers")
    manager.close_all()
    page = ProjectsPage()
    page.attach_service(ProjectService(manager))  # type: ignore[arg-type]
    page._select_by_key("a")  # noqa: SLF001
    questions = page.findChild(QListWidget, "projectsQuestionsList")
    tasks = page.findChild(QListWidget, "projectsTasksList")
    assert questions is not None and questions.count() == 1
    assert tasks is not None and tasks.count() == 1
    manager.close_all()
    database.dispose()


def test_page_buttons_present(app: QApplication) -> None:
    page = ProjectsPage()
    for name in (
        "projectsCreateButton",
        "projectsEditButton",
        "projectsRefreshButton",
        "projectsAddQuestion",
        "projectsAddTask",
    ):
        button = page.findChild(QPushButton, name)
        assert button is not None, name


def test_page_table_present(app: QApplication) -> None:
    page = ProjectsPage()
    table = page.findChild(QTableView, "projectsTable")
    assert table is not None