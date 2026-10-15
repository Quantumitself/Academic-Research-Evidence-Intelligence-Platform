"""Tests for the title comparison panel."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import (  # noqa: E402
    QApplication,
    QListWidget,
    QPushButton,
)

from academic_platform.application.title_builder.model import (  # noqa: E402
    TitleState,
)
from academic_platform.application.title_builder.service import (  # noqa: E402
    TitleBuilderService,
)
from academic_platform.application.topic_workspace.model import (  # noqa: E402
    TopicDraft,
    TopicField,
)
from academic_platform.infrastructure.database import Database  # noqa: E402
from academic_platform.infrastructure.database.base import Base  # noqa: E402
from academic_platform.infrastructure.database.models import ResearchProject  # noqa: E402
from academic_platform.infrastructure.repositories.factory import (  # noqa: E402
    _REPOSITORY_REGISTRY,
)
from academic_platform.ui.pages.research_assistant.sections.title_comparison_panel import (  # noqa: E402
    TitleComparisonPanel,
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


def _draft(**overrides) -> TopicDraft:
    values = {field.value: "" for field in TopicField}
    values.update(overrides)
    return TopicDraft(project_key="study-1", values=values)


def test_panel_lists_candidates(app: QApplication) -> None:
    database = Database.in_memory()
    Base.metadata.create_all(database.engine)
    _seed_project(database)
    manager = _ShimmedManager(database)
    service = TitleBuilderService(manager)  # type: ignore[arg-type]
    service.generate_for_project(
        "study-1", _draft(broad_subject="remote work")
    )
    manager.close_all()
    panel = TitleComparisonPanel()
    panel.attach_service(
        TitleBuilderService(manager), "study-1"  # type: ignore[arg-type]
    )
    listing = panel.findChild(QListWidget, "titleComparisonList")
    assert listing is not None
    assert listing.count() > 0
    manager.close_all()
    database.dispose()


def test_panel_accept_writes_state(app: QApplication) -> None:
    database = Database.in_memory()
    Base.metadata.create_all(database.engine)
    _seed_project(database)
    manager = _ShimmedManager(database)
    service = TitleBuilderService(manager)  # type: ignore[arg-type]
    candidates = service.generate_for_project(
        "study-1", _draft(broad_subject="remote work")
    )
    manager.close_all()
    panel = TitleComparisonPanel()
    panel.attach_service(
        TitleBuilderService(manager), "study-1"  # type: ignore[arg-type]
    )
    listing = panel.findChild(QListWidget, "titleComparisonList")
    assert listing is not None
    listing.setCurrentRow(0)
    accept_button = panel.findChild(QPushButton, "titleComparisonAccept")
    assert accept_button is not None
    accept_button.click()
    manager.close_all()
    # Reopen the service and confirm one accepted candidate.
    service = TitleBuilderService(manager)  # type: ignore[arg-type]
    accepted = service.list_accepted("study-1")
    assert accepted
    database.dispose()


def test_panel_use_emits_signal(app: QApplication) -> None:
    database = Database.in_memory()
    Base.metadata.create_all(database.engine)
    _seed_project(database)
    manager = _ShimmedManager(database)
    service = TitleBuilderService(manager)  # type: ignore[arg-type]
    service.generate_for_project(
        "study-1", _draft(broad_subject="remote work")
    )
    manager.close_all()
    panel = TitleComparisonPanel()
    panel.attach_service(
        TitleBuilderService(manager), "study-1"  # type: ignore[arg-type]
    )
    listing = panel.findChild(QListWidget, "titleComparisonList")
    assert listing is not None
    listing.setCurrentRow(0)
    received: list[str] = []
    panel.working_title_selected.connect(received.append)
    use_button = panel.findChild(QPushButton, "titleComparisonUse")
    assert use_button is not None
    use_button.click()
    assert received
    manager.close_all()
    database.dispose()


def test_panel_buttons_present(app: QApplication) -> None:
    panel = TitleComparisonPanel()
    for name in (
        "titleComparisonRefresh",
        "titleComparisonAccept",
        "titleComparisonReject",
        "titleComparisonArchive",
        "titleComparisonRestore",
        "titleComparisonEdit",
        "titleComparisonUse",
    ):
        button = panel.findChild(QPushButton, name)
        assert button is not None, name


def test_panel_actions_disabled_without_selection(app: QApplication) -> None:
    panel = TitleComparisonPanel()
    for name in (
        "titleComparisonAccept",
        "titleComparisonReject",
        "titleComparisonArchive",
        "titleComparisonRestore",
        "titleComparisonEdit",
        "titleComparisonUse",
    ):
        button = panel.findChild(QPushButton, name)
        assert button is not None
        assert not button.isEnabled()