"""Tests for the Projects page's export action."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QPushButton  # noqa: E402

from academic_platform.application.project_export.service import (  # noqa: E402
    ProjectExportService,
)
from academic_platform.application.projects.service import (  # noqa: E402
    ProjectService,
)
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


def test_export_button_disabled_initially(app: QApplication) -> None:
    page = ProjectsPage()
    button = page.findChild(QPushButton, "projectsExportButton")
    assert button is not None
    assert not button.isEnabled()


def test_export_button_enabled_after_selection(app: QApplication) -> None:
    database = Database.in_memory()
    Base.metadata.create_all(database.engine)
    manager = _ShimmedManager(database)
    service = ProjectService(manager)  # type: ignore[arg-type]
    service.create_project(key="study-1", title="Study")
    manager.close_all()
    page = ProjectsPage()
    page.attach_service(ProjectService(manager))  # type: ignore[arg-type]
    page.attach_export_service(ProjectExportService(manager))  # type: ignore[arg-type]
    page._select_by_key("study-1")  # noqa: SLF001
    button = page.findChild(QPushButton, "projectsExportButton")
    assert button is not None
    assert button.isEnabled()
    manager.close_all()
    database.dispose()