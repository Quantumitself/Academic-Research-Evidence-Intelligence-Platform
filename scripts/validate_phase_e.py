"""Phase E acceptance validator.

Verifies that the research project management pipeline meets every
Phase E acceptance criterion. The validator runs entirely offline,
against a temporary directory and an in-memory SQLite database. It
never touches the user's data and never contacts the network.

Acceptance criteria checked
---------------------------
1. The project service creates, reads, updates, and deletes projects
   and manages their research questions.
2. The project service manages tasks through its task operations.
3. The project service creates and synchronizes the project-linked
   collection.
4. The collection service creates, reads, updates, deletes, and lists
   collections.
5. The collection service manages items: add, remove, reorder, and
   note updates.
6. The collection service enforces the collection kind and the
   project-link invariant.
7. Smart collections parse their filter payload, reject malformed
   payloads, and evaluate correctly against the library.
8. The task service manages task status, priority, and milestones.
9. The task service computes progress summaries with overdue detection.
10. The project export service writes JSON and Markdown documents with
    independent selectable sections.
11. The project export service refuses to overwrite an existing file
    unless the caller requests it.
12. Audit events are recorded for every project, collection, and task
    mutation.
13. Persistence survives a database reopen: every entity written by
    the harness is present after the database is reopened.

Exit codes
----------
- 0: all criteria satisfied.
- 1: at least one criterion failed.
- 2: usage error.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

REPORT_FILENAME = "phase_e_validation.json"


@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str


@dataclass
class ValidationReport:
    checks: list[CheckResult] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(check.ok for check in self.checks)

    def add(self, name: str, ok: bool, detail: str = "") -> None:
        self.checks.append(CheckResult(name=name, ok=ok, detail=detail))

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "checks": [asdict(check) for check in self.checks],
        }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="validate_phase_e",
        description="Validate the Phase E acceptance criteria.",
    )
    parser.add_argument("--report", type=Path, default=None)
    parser.add_argument("--quiet", action="store_true")
    return parser


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
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


# ----------------------------------------------------------------------
# Checks
# ----------------------------------------------------------------------
def _check_project_crud(report: ValidationReport, database) -> None:
    from academic_platform.application.projects import (
        ProjectService,
        ProjectStage,
    )

    try:
        manager = _ShimmedManager(database)
        service = ProjectService(manager)  # type: ignore[arg-type]
        project = service.create_project(
            key="study-1", title="Study One", topic="Measurement"
        )
        assert project.key == "study-1"
        assert project.stage is ProjectStage.IDEA
        updated = service.update_project(
            "study-1", title="Study One (rev)", stage=ProjectStage.DESIGN
        )
        assert updated.title == "Study One (rev)"
        assert updated.stage is ProjectStage.DESIGN
        service.add_question("study-1", text="What is the effect?")
        questions = service.list_questions("study-1")
        assert len(questions) == 1
        service.delete_project("study-1")
        remaining = service.list_projects()
        assert remaining == []
        manager.close_all()
    except Exception as exc:  # noqa: BLE001 - boundary
        report.add("project CRUD", False, str(exc))
        return
    report.add("project CRUD", True, "create, update, question, delete")


def _check_project_question_management(report: ValidationReport, database) -> None:
    from academic_platform.application.projects import ProjectService

    try:
        manager = _ShimmedManager(database)
        service = ProjectService(manager)  # type: ignore[arg-type]
        service.create_project(key="study-q")
        a = service.add_question("study-q", text="A")
        b = service.add_question("study-q", text="B")
        service.set_primary_question("study-q", b.identifier)
        questions = service.list_questions("study-q")
        primaries = [q for q in questions if q.is_primary]
        assert len(primaries) == 1
        assert primaries[0].text == "B"
        service.remove_question("study-q", a.identifier)
        assert len(service.list_questions("study-q")) == 1
        manager.close_all()
    except Exception as exc:  # noqa: BLE001 - boundary
        report.add("project question management", False, str(exc))
        return
    report.add(
        "project question management",
        True,
        "primary flag and removal verified",
    )


def _check_project_task_operations(report: ValidationReport, database) -> None:
    from academic_platform.application.projects import ProjectService

    try:
        manager = _ShimmedManager(database)
        service = ProjectService(manager)  # type: ignore[arg-type]
        service.create_project(key="study-t")
        task = service.add_task("study-t", title="Read papers")
        tasks = service.list_tasks("study-t")
        assert [t.title for t in tasks] == ["Read papers"]
        open_tasks = service.list_open_tasks("study-t")
        assert len(open_tasks) == 1
        service.update_task("study-t", task.identifier, completed=True)
        assert service.list_open_tasks("study-t") == []
        service.remove_task("study-t", task.identifier)
        assert service.list_tasks("study-t") == []
        manager.close_all()
    except Exception as exc:  # noqa: BLE001 - boundary
        report.add("project task operations", False, str(exc))
        return
    report.add(
        "project task operations",
        True,
        "add, list, complete, remove verified",
    )


def _check_project_collection(report: ValidationReport, database) -> None:
    from academic_platform.application.projects import ProjectService
    from academic_platform.infrastructure.database.models import Collection

    try:
        manager = _ShimmedManager(database)
        service = ProjectService(manager)  # type: ignore[arg-type]
        service.create_project(key="study-c", title="Study C")
        service.update_project("study-c", title="Study C (rev)")
        manager.close_all()
        with database.session() as session:
            collection = (
                session.query(Collection)
                .filter(Collection.key == "project-study-c")
                .one_or_none()
            )
            assert collection is not None
            assert "Study C (rev)" in collection.title
    except Exception as exc:  # noqa: BLE001 - boundary
        report.add("project collection", False, str(exc))
        return
    report.add("project collection", True, "created and title synchronized")


def _check_collection_crud(report: ValidationReport, database) -> None:
    from academic_platform.application.collections import (
        CollectionKind,
        CollectionService,
    )

    try:
        manager = _ShimmedManager(database)
        service = CollectionService(manager)  # type: ignore[arg-type]
        service.create_collection(
            key="reading-list",
            title="Reading list",
            kind=CollectionKind.MANUAL,
        )
        collections = service.list_collections()
        assert any(c.key == "reading-list" for c in collections)
        updated = service.update_collection(
            "reading-list", title="Reading list (rev)"
        )
        assert updated.title == "Reading list (rev)"
        service.delete_collection("reading-list")
        assert all(c.key != "reading-list" for c in service.list_collections())
        manager.close_all()
    except Exception as exc:  # noqa: BLE001 - boundary
        report.add("collection CRUD", False, str(exc))
        return
    report.add("collection CRUD", True, "create, update, list, delete")


def _check_collection_items(report: ValidationReport, database) -> None:
    from academic_platform.application.collections import CollectionService

    try:
        manager = _ShimmedManager(database)
        service = CollectionService(manager)  # type: ignore[arg-type]
        service.create_collection(key="c1", title="C1")
        first = service.add_item(
            "c1", item_type="publication", item_identifier="pub-1"
        )
        second = service.add_item(
            "c1", item_type="publication", item_identifier="pub-2"
        )
        service.update_item("c1", first.identifier, note="Important")
        items = service.list_items("c1")
        assert [i.item_identifier for i in items] == ["pub-1", "pub-2"]
        service.reorder_items("c1", [second.identifier, first.identifier])
        items = service.list_items("c1")
        assert [i.item_identifier for i in items] == ["pub-2", "pub-1"]
        service.remove_item("c1", first.identifier)
        items = service.list_items("c1")
        assert [i.item_identifier for i in items] == ["pub-2"]
        manager.close_all()
    except Exception as exc:  # noqa: BLE001 - boundary
        report.add("collection items", False, str(exc))
        return
    report.add(
        "collection items",
        True,
        "add, note, reorder, remove verified",
    )


def _check_collection_invariants(report: ValidationReport, database) -> None:
    from academic_platform.application.collections import (
        CollectionKind,
        CollectionService,
    )
    from academic_platform.application.collections.errors import (
        CollectionValidationError,
    )
    from academic_platform.infrastructure.database.models import ResearchProject

    try:
        with database.session() as session:
            session.add(ResearchProject(key="proj-inv", title="Inv"))
        manager = _ShimmedManager(database)
        service = CollectionService(manager)  # type: ignore[arg-type]
        # Project-linked collections require a project key.
        rejected = False
        try:
            service.create_collection(
                key="pc", kind=CollectionKind.PROJECT
            )
        except CollectionValidationError:
            rejected = True
        assert rejected
        # Non-project collections reject a project key.
        rejected = False
        try:
            service.create_collection(
                key="manual-1",
                kind=CollectionKind.MANUAL,
                project_key="proj-inv",
            )
        except CollectionValidationError:
            rejected = True
        assert rejected
        # Smart collections require a filter payload.
        rejected = False
        try:
            service.create_collection(
                key="smart-1", kind=CollectionKind.SMART
            )
        except CollectionValidationError:
            rejected = True
        assert rejected
        manager.close_all()
    except Exception as exc:  # noqa: BLE001 - boundary
        report.add("collection invariants", False, str(exc))
        return
    report.add(
        "collection invariants",
        True,
        "kind and project-link enforced",
    )


def _check_smart_collections(report: ValidationReport, database) -> None:
    from academic_platform.application.collections import (
        CollectionKind,
        CollectionService,
    )
    from academic_platform.application.smart_collections import (
        SmartCollectionFilter,
        SmartCollectionFilterError,
    )
    from academic_platform.infrastructure.database.models import (
        DocumentAsset,
    )

    try:
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
        # Parser rejects malformed payloads.
        rejected = False
        try:
            SmartCollectionFilter.from_json('{"unknown": 1}')
        except SmartCollectionFilterError:
            rejected = True
        assert rejected
        manager = _ShimmedManager(database)
        service = CollectionService(manager)  # type: ignore[arg-type]
        service.create_collection(
            key="smart-1",
            kind=CollectionKind.SMART,
            filter_json='{"extensions": [".pdf"]}',
        )
        items = service.list_items("smart-1")
        assert [item.item_identifier for item in items] == ["a"]
        evaluated = service.evaluate_smart_collection("smart-1")
        assert [item.item_identifier for item in evaluated] == ["a"]
        manager.close_all()
    except Exception as exc:  # noqa: BLE001 - boundary
        report.add("smart collections", False, str(exc))
        return
    report.add(
        "smart collections",
        True,
        "parser rejects unknown fields; evaluator filters",
    )


def _check_task_workflow(report: ValidationReport, database) -> None:
    from academic_platform.application.tasks import (
        TaskPriority,
        TaskService,
        TaskStatus,
    )
    from academic_platform.infrastructure.database.models import ResearchProject

    try:
        with database.session() as session:
            session.add(ResearchProject(key="proj-t", title="Study"))
        manager = _ShimmedManager(database)
        service = TaskService(manager)  # type: ignore[arg-type]
        a = service.create_task("proj-t", title="A")
        b = service.create_task(
            "proj-t", title="B", is_milestone=True
        )
        service.set_status("proj-t", a.identifier, TaskStatus.DONE)
        service.set_priority(
            "proj-t", b.identifier, TaskPriority.HIGH
        )
        assert service.list_tasks_by_status(
            "proj-t", TaskStatus.DONE
        )[0].title == "A"
        assert service.list_milestones("proj-t")[0].title == "B"
        manager.close_all()
    except Exception as exc:  # noqa: BLE001 - boundary
        report.add("task workflow", False, str(exc))
        return
    report.add(
        "task workflow",
        True,
        "status, priority, milestone verified",
    )


def _check_task_progress(report: ValidationReport, database) -> None:
    from academic_platform.application.tasks import (
        TaskService,
        TaskStatus,
    )
    from academic_platform.infrastructure.database.models import ResearchProject

    try:
        with database.session() as session:
            session.add(ResearchProject(key="proj-p", title="Study"))
        past = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=1)
        manager = _ShimmedManager(database)
        service = TaskService(manager)  # type: ignore[arg-type]
        a = service.create_task("proj-p", title="A", due_at=past)
        b = service.create_task(
            "proj-p", title="B", is_milestone=True
        )
        service.set_status("proj-p", a.identifier, TaskStatus.DONE)
        summary = service.progress_summary("proj-p")
        assert summary.total == 2
        assert summary.done == 1
        assert summary.milestones_total == 1
        assert summary.overdue == 0  # a is done so not overdue
        assert summary.completion_ratio == pytest_approx(0.5)
        assert b.identifier > 0
        manager.close_all()
    except Exception as exc:  # noqa: BLE001 - boundary
        report.add("task progress", False, str(exc))
        return
    report.add(
        "task progress",
        True,
        "counts, milestones, and overdue detection verified",
    )


def pytest_approx(value: float, tol: float = 1e-6):
    """Local approximate comparator without importing pytest."""

    class _Approx:
        def __init__(self, target: float, tolerance: float) -> None:
            self.target = target
            self.tolerance = tolerance

        def __eq__(self, other: object) -> bool:
            if not isinstance(other, (int, float)):
                return NotImplemented
            return abs(float(other) - self.target) <= self.tolerance

        def __repr__(self) -> str:
            return f"≈{self.target}"

    return _Approx(value, tol)


def _check_project_export(report: ValidationReport, tmp_path: Path, database) -> None:
    from academic_platform.application.project_export import (
        ExportFormat,
        ExportOptions,
        ExportSection,
        ProjectExportService,
    )
    from academic_platform.application.projects import ProjectService

    try:
        manager = _ShimmedManager(database)
        projects = ProjectService(manager)  # type: ignore[arg-type]
        projects.create_project(key="export-1", title="Export Study")
        projects.add_question("export-1", text="Does it work?")
        manager.close_all()

        manager = _ShimmedManager(database)
        service = ProjectExportService(manager)  # type: ignore[arg-type]
        json_path = tmp_path / "export.json"
        result = service.export("export-1", json_path)
        assert json_path.exists()
        assert result.format is ExportFormat.JSON
        payload = json.loads(json_path.read_text(encoding="utf-8"))
        assert payload["project"]["key"] == "export-1"
        assert payload["research_questions"]

        markdown_path = tmp_path / "export.md"
        result_md = service.export(
            "export-1",
            markdown_path,
            options=ExportOptions(
                format=ExportFormat.MARKDOWN,
                sections=frozenset(
                    {
                        ExportSection.PROJECT_FIELDS,
                        ExportSection.RESEARCH_QUESTIONS,
                    }
                ),
            ),
        )
        assert markdown_path.exists()
        assert result_md.format is ExportFormat.MARKDOWN
        text = markdown_path.read_text(encoding="utf-8")
        assert "# Export Study" in text
        assert "## Research questions" in text
        assert "## Tasks" not in text
        manager.close_all()
    except Exception as exc:  # noqa: BLE001 - boundary
        report.add("project export", False, str(exc))
        return
    report.add(
        "project export",
        True,
        "JSON and Markdown with section filtering verified",
    )


def _check_project_export_overwrite(report: ValidationReport, tmp_path: Path, database) -> None:
    from academic_platform.application.project_export import (
        ProjectExportError,
        ProjectExportService,
    )
    from academic_platform.application.projects import ProjectService

    try:
        manager = _ShimmedManager(database)
        projects = ProjectService(manager)  # type: ignore[arg-type]
        projects.create_project(key="overwrite-1", title="Overwrite")
        manager.close_all()

        target = tmp_path / "existing.json"
        target.write_text("existing", encoding="utf-8")

        manager = _ShimmedManager(database)
        service = ProjectExportService(manager)  # type: ignore[arg-type]
        blocked = False
        try:
            service.export("overwrite-1", target)
        except ProjectExportError:
            blocked = True
        assert blocked
        service.export("overwrite-1", target, overwrite=True)
        payload = json.loads(target.read_text(encoding="utf-8"))
        assert payload["project"]["key"] == "overwrite-1"
        manager.close_all()
    except Exception as exc:  # noqa: BLE001 - boundary
        report.add("project export overwrite", False, str(exc))
        return
    report.add(
        "project export overwrite",
        True,
        "refused without flag, succeeded with flag",
    )


def _check_audit_events(report: ValidationReport, database) -> None:
    from academic_platform.application.collections import CollectionService
    from academic_platform.application.projects import ProjectService
    from academic_platform.application.tasks import TaskService
    from academic_platform.infrastructure.database.models import AuditEvent

    try:
        manager = _ShimmedManager(database)
        projects = ProjectService(manager)  # type: ignore[arg-type]
        projects.create_project(key="audit-1", actor="alice")
        projects.add_question("audit-1", text="Q", actor="alice")
        manager.close_all()

        manager = _ShimmedManager(database)
        collections = CollectionService(manager)  # type: ignore[arg-type]
        collections.create_collection(key="audit-c", actor="alice")
        collections.add_item(
            "audit-c",
            item_type="publication",
            item_identifier="pub-1",
            actor="alice",
        )
        manager.close_all()

        manager = _ShimmedManager(database)
        tasks = TaskService(manager)  # type: ignore[arg-type]
        task = tasks.create_task("audit-1", title="T", actor="alice")
        tasks.set_status(
            "audit-1",
            task.identifier,
            __import__(
                "academic_platform.application.tasks", fromlist=["TaskStatus"]
            ).TaskStatus.DONE,
            actor="alice",
        )
        manager.close_all()

        with database.session() as session:
            actions = {event.action for event in session.query(AuditEvent).all()}
        required = {
            "project.created",
            "project.question_added",
            "collection.created",
            "collection.item_added",
            "task.created",
            "task.status_changed",
        }
        missing = required - actions
        assert not missing, f"missing audit actions: {sorted(missing)}"
    except Exception as exc:  # noqa: BLE001 - boundary
        report.add("audit events", False, str(exc))
        return
    report.add(
        "audit events",
        True,
        "project, collection, and task mutations recorded",
    )


def _check_persistence_survives_reopen(
    report: ValidationReport,
    tmp_path: Path,
) -> None:
    from academic_platform.infrastructure.database import (
        Database,
        DatabaseConfiguration,
    )
    from academic_platform.infrastructure.database.base import Base
    from academic_platform.infrastructure.database.models import (
        Collection,
        CollectionItem,
        ResearchProject,
        ResearchQuestion,
        ResearchTask,
    )

    try:
        database_path = tmp_path / "persistence.sqlite3"
        url = f"sqlite:///{database_path.as_posix()}"

        database = Database(DatabaseConfiguration(url=url))
        Base.metadata.create_all(database.engine)
        with database.session() as session:
            project = ResearchProject(key="persist-1", title="Persistent")
            session.add(project)
            session.flush()
            session.add(
                ResearchQuestion(
                    project_id=project.id,
                    text="Q",
                    kind="main",
                )
            )
            task = ResearchTask(
                project_id=project.id,
                title="T",
                position=0,
            )
            task.status = "open"
            task.priority = "normal"
            task.is_milestone = 0
            task.notes = ""
            session.add(task)
            collection = Collection(
                key="project-persist-1",
                title="Persistent — documents",
                kind="project",
                project_id=project.id,
            )
            session.add(collection)
            session.flush()
            session.add(
                CollectionItem(
                    collection_id=collection.id,
                    item_type="document",
                    item_identifier="doc-1",
                    position=0,
                )
            )
        database.dispose()

        reopened = Database(DatabaseConfiguration(url=url))
        try:
            with reopened.session() as session:
                assert session.query(ResearchProject).count() == 1
                assert session.query(ResearchQuestion).count() == 1
                assert session.query(ResearchTask).count() == 1
                assert session.query(Collection).count() == 1
                assert session.query(CollectionItem).count() == 1
        finally:
            reopened.dispose()
    except Exception as exc:  # noqa: BLE001 - boundary
        report.add("persistence survives reopen", False, str(exc))
        return
    report.add(
        "persistence survives reopen",
        True,
        "projects, questions, tasks, collections, items verified",
    )


# ----------------------------------------------------------------------
# Orchestration
# ----------------------------------------------------------------------
def _print_report(report: ValidationReport, quiet: bool) -> None:
    if quiet:
        return
    width = max((len(check.name) for check in report.checks), default=0)
    for check in report.checks:
        status = "OK  " if check.ok else "FAIL"
        detail = f" — {check.detail}" if check.detail else ""
        print(f"[{status}] {check.name.ljust(width)}{detail}")


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    report = ValidationReport()
    temporary_directory = tempfile.TemporaryDirectory(
        prefix="academic_platform_phase_e_"
    )
    try:
        tmp_path = Path(temporary_directory.name)
        from academic_platform.infrastructure.database import Database
        from academic_platform.infrastructure.database.base import Base

        database = Database.in_memory()
        Base.metadata.create_all(database.engine)
        try:
            _check_project_crud(report, database)
            _check_project_question_management(report, database)
            _check_project_task_operations(report, database)
            _check_project_collection(report, database)
            _check_collection_crud(report, database)
            _check_collection_items(report, database)
            _check_collection_invariants(report, database)
            _check_smart_collections(report, database)
            _check_task_workflow(report, database)
            _check_task_progress(report, database)
            _check_project_export(report, tmp_path, database)
            _check_project_export_overwrite(report, tmp_path, database)
            _check_audit_events(report, database)
            _check_persistence_survives_reopen(report, tmp_path)
        finally:
            database.dispose()
    finally:
        temporary_directory.cleanup()

    _print_report(report, args.quiet)

    if args.report is not None:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(
            json.dumps(report.to_dict(), indent=2, sort_keys=True),
            encoding="utf-8",
        )

    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())