"""Phase E acceptance criteria as automated tests.

The tests are intentionally broader than per-module tests. Each test
exercises a complete workflow end to end, using a temporary directory
and an in-memory SQLite database.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import pytest

from academic_platform.infrastructure.database import Database
from academic_platform.infrastructure.database.base import Base


class _ShimmedManager:
    """A repository manager sharing one session across all repositories.

    Sharing the session ensures that entities loaded by one repository
    remain attached when passed to another. Committing is explicit via
    ``close_all``.
    """

    def __init__(self, database) -> None:
        self._database = database
        self._session = database._session_factory()  # noqa: SLF001

    def get(self, key: str):
        from academic_platform.infrastructure.repositories.factory import (
            _REPOSITORY_REGISTRY,
        )

        return _REPOSITORY_REGISTRY[key](self._session)

    def register_all(self, mapping: dict) -> None:
        return None

    def close_all(self) -> None:
        try:
            self._session.commit()
        except Exception:  # noqa: BLE001
            self._session.rollback()
        finally:
            self._session.close()


@pytest.fixture()
def database() -> Database:
    db = Database.in_memory()
    Base.metadata.create_all(db.engine)
    yield db
    db.dispose()


def test_project_full_lifecycle(database: Database) -> None:
    from academic_platform.application.projects import (
        ProjectService,
        ProjectStage,
    )

    manager = _ShimmedManager(database)
    service = ProjectService(manager)  # type: ignore[arg-type]
    project = service.create_project(key="p1", title="P1")
    service.add_question("p1", text="Q", is_primary=True)
    service.add_task("p1", title="T")
    service.update_project("p1", stage=ProjectStage.ANALYSIS)
    service.delete_project("p1")
    manager.close_all()
    assert project.key == "p1"


def test_collection_full_lifecycle(database: Database) -> None:
    from academic_platform.application.collections import (
        CollectionKind,
        CollectionService,
    )

    manager = _ShimmedManager(database)
    service = CollectionService(manager)  # type: ignore[arg-type]
    service.create_collection(
        key="c1", title="C1", kind=CollectionKind.MANUAL
    )
    a = service.add_item("c1", item_type="publication", item_identifier="p1")
    b = service.add_item("c1", item_type="publication", item_identifier="p2")
    service.reorder_items("c1", [b.identifier, a.identifier])
    items = service.list_items("c1")
    assert [i.item_identifier for i in items] == ["p2", "p1"]
    manager.close_all()


def test_smart_collection_end_to_end(database: Database) -> None:
    from academic_platform.application.collections import (
        CollectionKind,
        CollectionService,
    )
    from academic_platform.infrastructure.database.models import DocumentAsset

    with database.session() as session:
        session.add(
            DocumentAsset(
                key="a",
                display_name="Alpha",
                location="/tmp/a.pdf",
                checksum_sha256="0" * 64,
                processing_state="extracted",
            )
        )
        session.add(
            DocumentAsset(
                key="b",
                display_name="Beta",
                location="/tmp/b.epub",
                checksum_sha256="1" * 64,
                processing_state="pending",
            )
        )
    manager = _ShimmedManager(database)
    service = CollectionService(manager)  # type: ignore[arg-type]
    service.create_collection(
        key="smart-1",
        kind=CollectionKind.SMART,
        filter_json='{"processing_states": ["extracted"]}',
    )
    items = service.list_items("smart-1")
    assert [item.item_identifier for item in items] == ["a"]
    manager.close_all()


def test_task_workflow_end_to_end(database: Database) -> None:
    from academic_platform.application.tasks import (
        TaskPriority,
        TaskService,
        TaskStatus,
    )
    from academic_platform.infrastructure.database.models import ResearchProject

    with database.session() as session:
        session.add(ResearchProject(key="p1", title="P"))
    manager = _ShimmedManager(database)
    service = TaskService(manager)  # type: ignore[arg-type]
    a = service.create_task("p1", title="A")
    service.set_status("p1", a.identifier, TaskStatus.DONE)
    service.set_priority("p1", a.identifier, TaskPriority.HIGH)
    summary = service.progress_summary("p1")
    assert summary.total == 1
    assert summary.done == 1
    manager.close_all()


def test_task_overdue_detection(database: Database) -> None:
    from academic_platform.application.tasks import TaskService
    from academic_platform.infrastructure.database.models import ResearchProject

    with database.session() as session:
        session.add(ResearchProject(key="p1", title="P"))
    past = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=2)
    manager = _ShimmedManager(database)
    service = TaskService(manager)  # type: ignore[arg-type]
    service.create_task("p1", title="Overdue", due_at=past)
    summary = service.progress_summary("p1")
    assert summary.overdue == 1
    manager.close_all()


def test_project_export_round_trip(database: Database, tmp_path: Path) -> None:
    from academic_platform.application.project_export import (
        ExportFormat,
        ProjectExportService,
    )
    from academic_platform.application.projects import ProjectService

    manager = _ShimmedManager(database)
    projects = ProjectService(manager)  # type: ignore[arg-type]
    projects.create_project(key="p1", title="P")
    projects.add_question("p1", text="Q")
    manager.close_all()

    manager = _ShimmedManager(database)
    service = ProjectExportService(manager)  # type: ignore[arg-type]
    output = tmp_path / "out.json"
    service.export("p1", output)
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["project"]["key"] == "p1"
    assert payload["research_questions"]
    manager.close_all()
    assert ExportFormat.JSON.extension == ".json"


def test_audit_trail_spanning_services(database: Database) -> None:
    from academic_platform.application.collections import CollectionService
    from academic_platform.application.projects import ProjectService
    from academic_platform.application.tasks import TaskService
    from academic_platform.infrastructure.database.models import AuditEvent

    manager = _ShimmedManager(database)
    ProjectService(manager).create_project(key="p1", actor="alice")  # type: ignore[arg-type]
    manager.close_all()
    manager = _ShimmedManager(database)
    CollectionService(manager).create_collection(key="c1", actor="alice")  # type: ignore[arg-type]
    manager.close_all()
    manager = _ShimmedManager(database)
    TaskService(manager).create_task("p1", title="T", actor="alice")  # type: ignore[arg-type]
    manager.close_all()
    with database.session() as session:
        actions = {event.action for event in session.query(AuditEvent).all()}
    assert "project.created" in actions
    assert "collection.created" in actions
    assert "task.created" in actions


def test_persistence_round_trip(tmp_path: Path) -> None:
    from academic_platform.infrastructure.database import (
        Database,
        DatabaseConfiguration,
    )
    from academic_platform.infrastructure.database.base import Base
    from academic_platform.infrastructure.database.models import (
        ResearchProject,
    )

    url = f"sqlite:///{(tmp_path / 'persist.sqlite3').as_posix()}"
    database = Database(DatabaseConfiguration(url=url))
    Base.metadata.create_all(database.engine)
    with database.session() as session:
        session.add(ResearchProject(key="p1", title="Persistent"))
    database.dispose()

    reopened = Database(DatabaseConfiguration(url=url))
    try:
        with reopened.session() as session:
            assert session.query(ResearchProject).count() == 1
    finally:
        reopened.dispose()