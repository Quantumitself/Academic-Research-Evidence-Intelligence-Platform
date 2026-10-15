"""Tests for the milestones panel."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import (  # noqa: E402
    QApplication,
    QComboBox,
    QListWidget,
    QPushButton,
)

from academic_platform.application.tasks.model import (  # noqa: E402
    TaskPriority,
    TaskStatus,
)
from academic_platform.application.tasks.service import TaskService  # noqa: E402
from academic_platform.infrastructure.database import Database  # noqa: E402
from academic_platform.infrastructure.database.base import Base  # noqa: E402
from academic_platform.infrastructure.database.models import ResearchProject  # noqa: E402
from academic_platform.infrastructure.repositories.factory import (  # noqa: E402
    _REPOSITORY_REGISTRY,
)
from academic_platform.ui.pages.projects.milestones_panel import (  # noqa: E402
    MilestonesPanel,
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
        session.add(ResearchProject(key="proj-1", title="Study"))


def test_panel_lists_tasks(app: QApplication) -> None:
    database = Database.in_memory()
    Base.metadata.create_all(database.engine)
    _seed(database)
    manager = _ShimmedManager(database)
    service = TaskService(manager)  # type: ignore[arg-type]
    service.create_task("proj-1", title="A")
    service.create_task("proj-1", title="B")
    manager.close_all()
    panel = MilestonesPanel()
    panel.attach_service(TaskService(manager))  # type: ignore[arg-type]
    panel.set_project("proj-1")
    listing = panel.findChild(QListWidget, "milestonesList")
    assert listing is not None
    assert listing.count() == 2
    manager.close_all()
    database.dispose()


def test_panel_status_filter(app: QApplication) -> None:
    database = Database.in_memory()
    Base.metadata.create_all(database.engine)
    _seed(database)
    manager = _ShimmedManager(database)
    service = TaskService(manager)  # type: ignore[arg-type]
    a = service.create_task("proj-1", title="A")
    service.create_task("proj-1", title="B")
    service.set_status("proj-1", a.identifier, TaskStatus.DONE)
    manager.close_all()
    panel = MilestonesPanel()
    panel.attach_service(TaskService(manager))  # type: ignore[arg-type]
    panel.set_project("proj-1")
    combo = panel.findChild(QComboBox, "milestonesStatusFilter")
    assert combo is not None
    for index in range(combo.count()):
        if combo.itemData(index) == TaskStatus.DONE.value:
            combo.setCurrentIndex(index)
            break
    listing = panel.findChild(QListWidget, "milestonesList")
    assert listing is not None and listing.count() == 1
    manager.close_all()
    database.dispose()


def test_panel_milestones_only_filter(app: QApplication) -> None:
    database = Database.in_memory()
    Base.metadata.create_all(database.engine)
    _seed(database)
    manager = _ShimmedManager(database)
    service = TaskService(manager)  # type: ignore[arg-type]
    service.create_task("proj-1", title="A")
    service.create_task("proj-1", title="B", is_milestone=True)
    manager.close_all()
    panel = MilestonesPanel()
    panel.attach_service(TaskService(manager))  # type: ignore[arg-type]
    panel.set_project("proj-1")
    combo = panel.findChild(QComboBox, "milestonesOnlyFilter")
    assert combo is not None
    combo.setCurrentIndex(1)
    listing = panel.findChild(QListWidget, "milestonesList")
    assert listing is not None and listing.count() == 1
    manager.close_all()
    database.dispose()


def test_panel_buttons_present(app: QApplication) -> None:
    panel = MilestonesPanel()
    for name in (
        "milestonesAddTask",
        "milestonesEditTask",
        "milestonesRemoveTask",
    ):
        button = panel.findChild(QPushButton, name)
        assert button is not None, name