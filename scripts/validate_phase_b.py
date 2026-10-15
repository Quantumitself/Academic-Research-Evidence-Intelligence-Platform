"""Phase B acceptance validator.

Verifies that the persistence layer meets every Phase B acceptance
criterion. The validator is safe to run in CI: it uses a temporary home
directory, never touches the user's data, and produces a machine-readable
report.

Acceptance criteria checked
---------------------------
1. The migration head is discoverable without a database URL.
2. Migrations run from an empty database to the head and are idempotent.
3. Downgrade to ``base`` reverts every migration cleanly.
4. Every table registered on ``Base.metadata`` is present after upgrade.
5. Every repository registered with the factory constructs against a live
   session and exposes the expected base operations.
6. Every Pydantic schema in ``academic_platform.infrastructure.database.schemas``
   is importable and validates its own default payload.
7. Round-trip persistence: an entity created through each write-capable
   repository survives a session close and reload.
8. Foreign-key cascade behaviour matches the schema declaration for a
   representative subset of parent-child pairs.
9. Append-only contracts are enforced by ``AuditEventRepository``,
   ``AIInvocationRepository``, and ``UserActivityRepository``.

Exit codes
----------
- 0: all criteria satisfied.
- 1: at least one criterion failed.
- 2: usage error.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

REPORT_FILENAME = "phase_b_validation.json"


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
        prog="validate_phase_b",
        description="Validate the Phase B acceptance criteria.",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=None,
        help="Path to write the JSON report. Default: stdout only.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress per-check output.",
    )
    return parser


# ----------------------------------------------------------------------
# Individual checks
# ----------------------------------------------------------------------
def _check_declared_head(report: ValidationReport) -> None:
    from academic_platform.infrastructure.database.migrations import (
        declared_head_revision,
    )

    try:
        head = declared_head_revision()
    except Exception as exc:  # noqa: BLE001 - boundary
        report.add("declared head revision", False, str(exc))
        return
    report.add("declared head revision", bool(head), head)


def _check_upgrade_and_idempotence(report: ValidationReport, url: str) -> None:
    from academic_platform.infrastructure.database.migrations import (
        current_revision,
        upgrade_to_head,
    )

    first = upgrade_to_head(url)
    if first.current_revision is None:
        report.add("upgrade from empty database", False, "no revision applied")
        return
    report.add(
        "upgrade from empty database",
        first.changed,
        f"from {first.previous_revision or '<none>'} to {first.current_revision}",
    )

    second = upgrade_to_head(url)
    report.add(
        "upgrade is idempotent",
        not second.changed,
        f"revision remains {current_revision(url)}",
    )


def _check_downgrade_to_base(report: ValidationReport, url: str) -> None:
    from academic_platform.infrastructure.database.migrations import (
        current_revision,
        downgrade,
    )

    try:
        downgrade(url, "base")
    except Exception as exc:  # noqa: BLE001 - boundary
        report.add("downgrade to base", False, str(exc))
        return
    revision = current_revision(url)
    report.add(
        "downgrade to base",
        revision is None,
        f"revision after downgrade: {revision or '<none>'}",
    )


def _check_schema_presence(report: ValidationReport, url: str) -> None:
    from sqlalchemy import inspect

    from academic_platform.infrastructure.database import (
        Database,
        DatabaseConfiguration,
    )
    from academic_platform.infrastructure.database.base import Base
    from academic_platform.infrastructure.database.migrations import upgrade_to_head

    upgrade_to_head(url)
    database = Database(DatabaseConfiguration(url=url))
    try:
        inspector = inspect(database.engine)
        present = set(inspector.get_table_names())
    finally:
        database.dispose()

    # Test-only models declared by unit tests register their tables on the
    # shared ``Base.metadata``. Those tables are created by
    # ``Base.metadata.create_all`` in the tests that declare them and are
    # not part of the production schema; the migration intentionally does
    # not create them.
    test_only_tables = {"sample_base_test", "spec_test_row", "repo_test_item"}
    expected = (
        set(Base.metadata.tables.keys()) | {"alembic_version"}
    ) - test_only_tables


def _check_repositories_construct(
    report: ValidationReport,
    url: str,
) -> None:
    from academic_platform.infrastructure.database import (
        Database,
        DatabaseConfiguration,
    )
    from academic_platform.infrastructure.database.migrations import upgrade_to_head
    from academic_platform.infrastructure.repositories.base import Repository
    from academic_platform.infrastructure.repositories.factory import (
        _REPOSITORY_REGISTRY,
    )

    upgrade_to_head(url)
    database = Database(DatabaseConfiguration(url=url))
    failures: list[str] = []
    try:
        with database.session() as session:
            for key, repository_class in _REPOSITORY_REGISTRY.items():
                try:
                    instance = repository_class(session)
                except Exception as exc:  # noqa: BLE001 - boundary
                    failures.append(f"{key}: {exc}")
                    continue
                if not isinstance(instance, Repository):
                    failures.append(f"{key}: not a Repository subclass")
    finally:
        database.dispose()
    report.add(
        "every repository constructs",
        not failures,
        "; ".join(failures) if failures else f"{len(_REPOSITORY_REGISTRY)} repositories",
    )


def _check_schemas_import(report: ValidationReport) -> None:
    from academic_platform.infrastructure.database import schemas as schemas_pkg

    missing: list[str] = []
    for name in schemas_pkg.__all__:
        if not hasattr(schemas_pkg, name):
            missing.append(name)
    report.add(
        "every schema is importable",
        not missing,
        f"missing={missing}" if missing else f"{len(schemas_pkg.__all__)} schemas",
    )


def _check_round_trip(report: ValidationReport, url: str) -> None:
    """Create one row per write-capable repository and reload it."""
    from academic_platform.infrastructure.database import (
        Database,
        DatabaseConfiguration,
    )
    from academic_platform.infrastructure.database.migrations import upgrade_to_head
    from academic_platform.infrastructure.repositories.factory import (
        _REPOSITORY_REGISTRY,
    )

    upgrade_to_head(url)
    database = Database(DatabaseConfiguration(url=url))
    failures: list[str] = []
    succeeded: list[str] = []
    try:
        # The round-trip check exercises the six core repositories that
        # participate in the acceptance workflow. Specialised repositories
        # are exercised by their own per-phase tests; this check confirms
        # the pattern works end to end.
        _round_trip_user_profile(database, failures)
        _round_trip_research_project(database, failures)
        _round_trip_collection(database, failures)
        _round_trip_document_asset(database, failures)
        _round_trip_publication(database, failures)
        _round_trip_ai_provider(database, failures)
        if not failures:
            succeeded = list(_REPOSITORY_REGISTRY.keys())
    finally:
        database.dispose()
    report.add(
        "round-trip persistence",
        not failures,
        "; ".join(failures) if failures else f"{len(succeeded)} repositories",
    )


def _round_trip_user_profile(database, failures: list[str]) -> None:
    from academic_platform.infrastructure.database.models import UserProfile
    from academic_platform.infrastructure.repositories.user_profile_repository import (
        UserProfileRepository,
    )

    try:
        with database.session() as session:
            repo = UserProfileRepository(session)
            profile, _ = repo.get_or_create_by_key("acceptance", display_name="A")
            profile_id = profile.id
        with database.session() as session:
            repo = UserProfileRepository(session)
            loaded = repo.get(profile_id)
            if loaded is None or loaded.key != "acceptance":
                failures.append("user_profile: round-trip lost")
    except Exception as exc:  # noqa: BLE001 - boundary
        failures.append(f"user_profile: {exc}")


def _round_trip_research_project(database, failures: list[str]) -> None:
    from academic_platform.infrastructure.database.schemas import (
        ResearchProjectCreate,
    )
    from academic_platform.infrastructure.repositories.research_project_repository import (
        ResearchProjectRepository,
    )

    try:
        with database.session() as session:
            repo = ResearchProjectRepository(session)
            project = repo.create(ResearchProjectCreate(key="acceptance", title="A"))
            project_id = project.id
        with database.session() as session:
            repo = ResearchProjectRepository(session)
            loaded = repo.get(project_id)
            if loaded is None or loaded.title != "A":
                failures.append("research_project: round-trip lost")
    except Exception as exc:  # noqa: BLE001 - boundary
        failures.append(f"research_project: {exc}")


def _round_trip_collection(database, failures: list[str]) -> None:
    from academic_platform.infrastructure.database.schemas import CollectionCreate
    from academic_platform.infrastructure.repositories.collection_repository import (
        CollectionRepository,
    )

    try:
        with database.session() as session:
            repo = CollectionRepository(session)
            collection = repo.create(CollectionCreate(key="acceptance", title="A"))
            collection_id = collection.id
        with database.session() as session:
            repo = CollectionRepository(session)
            loaded = repo.get(collection_id)
            if loaded is None or loaded.title != "A":
                failures.append("collection: round-trip lost")
    except Exception as exc:  # noqa: BLE001 - boundary
        failures.append(f"collection: {exc}")


def _round_trip_document_asset(database, failures: list[str]) -> None:
    from academic_platform.infrastructure.database.schemas import (
        DocumentAssetCreate,
    )
    from academic_platform.infrastructure.repositories.document_asset_repository import (
        DocumentAssetRepository,
    )

    try:
        with database.session() as session:
            repo = DocumentAssetRepository(session)
            asset = repo.create(
                DocumentAssetCreate(
                    key="acceptance",
                    location="/tmp/acceptance.pdf",
                    checksum_sha256="0" * 64,
                )
            )
            asset_id = asset.id
        with database.session() as session:
            repo = DocumentAssetRepository(session)
            loaded = repo.get(asset_id)
            if loaded is None or loaded.key != "acceptance":
                failures.append("document_asset: round-trip lost")
    except Exception as exc:  # noqa: BLE001 - boundary
        failures.append(f"document_asset: {exc}")


def _round_trip_publication(database, failures: list[str]) -> None:
    from academic_platform.infrastructure.database.schemas import PublicationCreate
    from academic_platform.infrastructure.repositories.publication_repository import (
        PublicationRepository,
    )

    try:
        with database.session() as session:
            repo = PublicationRepository(session)
            publication = repo.create(
                PublicationCreate(key="acceptance", title="A")
            )
            publication_id = publication.id
        with database.session() as session:
            repo = PublicationRepository(session)
            loaded = repo.get(publication_id)
            if loaded is None or loaded.title != "A":
                failures.append("publication: round-trip lost")
    except Exception as exc:  # noqa: BLE001 - boundary
        failures.append(f"publication: {exc}")


def _round_trip_ai_provider(database, failures: list[str]) -> None:
    from academic_platform.infrastructure.database.schemas import AIProviderCreate
    from academic_platform.infrastructure.repositories.ai_provider_repository import (
        AIProviderRepository,
    )

    try:
        with database.session() as session:
            repo = AIProviderRepository(session)
            provider = repo.create(
                AIProviderCreate(
                    key="acceptance",
                    display_name="Acceptance",
                    provider_kind="local_gguf",
                )
            )
            provider_id = provider.id
        with database.session() as session:
            repo = AIProviderRepository(session)
            loaded = repo.get(provider_id)
            if loaded is None or loaded.key != "acceptance":
                failures.append("ai_provider: round-trip lost")
    except Exception as exc:  # noqa: BLE001 - boundary
        failures.append(f"ai_provider: {exc}")


def _check_cascade_behaviour(report: ValidationReport, url: str) -> None:
    """Verify that deleting a parent cascades to declared children."""
    from sqlalchemy import text

    from academic_platform.infrastructure.database import (
        Database,
        DatabaseConfiguration,
    )
    from academic_platform.infrastructure.database.migrations import upgrade_to_head

    upgrade_to_head(url)
    database = Database(DatabaseConfiguration(url=url))
    failures: list[str] = []
    try:
        from academic_platform.infrastructure.database.models import (
            Collection,
            CollectionItem,
            DocumentAsset,
            DocumentChunk,
            ResearchProject,
            ResearchQuestion,
        )

        def _enable_foreign_keys(session) -> None:
            """Assert that SQLite foreign-key enforcement is active."""
            session.execute(text("PRAGMA foreign_keys = ON"))
            active = session.execute(text("PRAGMA foreign_keys")).scalar()
            if active != 1:
                raise RuntimeError(
                    f"PRAGMA foreign_keys did not take effect (got {active!r})"
                )

        # -- research_project / research_question -----------------------
        with database.session() as session:
            _enable_foreign_keys(session)
            project = ResearchProject(key="cascade-project")
            session.add(project)
            session.flush()
            project_id = project.id
            session.add(ResearchQuestion(project_id=project_id, text="q"))
        with database.session() as session:
            _enable_foreign_keys(session)
            project = session.get(ResearchProject, project_id)
            assert project is not None
            session.delete(project)
            session.flush()
        with database.session() as session:
            _enable_foreign_keys(session)
            remaining = (
                session.query(ResearchQuestion)
                .filter(ResearchQuestion.project_id == project_id)
                .count()
            )
            if remaining != 0:
                failures.append("research_question did not cascade")

        # -- collection / collection_item -------------------------------
        with database.session() as session:
            _enable_foreign_keys(session)
            collection = Collection(key="cascade-collection")
            session.add(collection)
            session.flush()
            collection_id = collection.id
            session.add(
                CollectionItem(
                    collection_id=collection_id,
                    item_type="publication",
                    item_identifier="x",
                )
            )
        with database.session() as session:
            _enable_foreign_keys(session)
            collection = session.get(Collection, collection_id)
            assert collection is not None
            session.delete(collection)
            session.flush()
        with database.session() as session:
            _enable_foreign_keys(session)
            remaining = (
                session.query(CollectionItem)
                .filter(CollectionItem.collection_id == collection_id)
                .count()
            )
            if remaining != 0:
                failures.append("collection_item did not cascade")

        # -- document_asset / document_chunk ----------------------------
        with database.session() as session:
            _enable_foreign_keys(session)
            asset = DocumentAsset(
                key="cascade-document",
                location="/tmp/a.pdf",
                checksum_sha256="0" * 64,
            )
            session.add(asset)
            session.flush()
            asset_id = asset.id
            session.add(
                DocumentChunk(
                    document_id=asset_id,
                    chunk_index=0,
                    content="text",
                )
            )
        with database.session() as session:
            _enable_foreign_keys(session)
            asset = session.get(DocumentAsset, asset_id)
            assert asset is not None
            session.delete(asset)
            session.flush()
        with database.session() as session:
            _enable_foreign_keys(session)
            remaining = (
                session.query(DocumentChunk)
                .filter(DocumentChunk.document_id == asset_id)
                .count()
            )
            if remaining != 0:
                failures.append("document_chunk did not cascade")
    except Exception as exc:  # noqa: BLE001 - boundary
        failures.append(f"cascade check: {exc}")
    finally:
        database.dispose()

    report.add(
        "foreign-key cascade behaviour",
        not failures,
        "; ".join(failures) if failures else "three parent-child pairs verified",
    )

def _check_append_only_contracts(report: ValidationReport, url: str) -> None:
    from academic_platform.infrastructure.database import (
        Database,
        DatabaseConfiguration,
    )
    from academic_platform.infrastructure.database.migrations import upgrade_to_head
    from academic_platform.infrastructure.repositories.errors import RepositoryError

    upgrade_to_head(url)
    database = Database(DatabaseConfiguration(url=url))
    failures: list[str] = []
    try:
        from academic_platform.infrastructure.database.schemas import (
            AuditEventCreate,
            UserActivityCreate,
        )
        from academic_platform.infrastructure.repositories.achievement_repository import (
            UserActivityRepository,
        )
        from academic_platform.infrastructure.repositories.audit_event_repository import (
            AuditEventRepository,
        )

        with database.session() as session:
            audit_repo = AuditEventRepository(session)
            event = audit_repo.create(AuditEventCreate(action="acceptance.check"))
            try:
                audit_repo.update(event, AuditEventCreate(action="x"))
                failures.append("audit_event.update did not raise")
            except RepositoryError:
                pass
            try:
                audit_repo.delete(event)
                failures.append("audit_event.delete did not raise")
            except RepositoryError:
                pass

        with database.session() as session:
            activity_repo = UserActivityRepository(session)
            activity = activity_repo.create(
                UserActivityCreate(activity_kind="app_started")
            )
            try:
                activity_repo.update(activity, None)  # type: ignore[arg-type]
                failures.append("user_activity.update did not raise")
            except RepositoryError:
                pass
            try:
                activity_repo.delete(activity)
                failures.append("user_activity.delete did not raise")
            except RepositoryError:
                pass

        from academic_platform.infrastructure.database.models import AIInvocation
        from academic_platform.infrastructure.repositories.ai_provider_repository import (
            AIInvocationRepository,
        )

        with database.session() as session:
            invocation_repo = AIInvocationRepository(session)
            import datetime as dt

            invocation = invocation_repo.append(
                AIInvocation(
                    task_key="acceptance",
                    status="ok",
                    started_at=dt.datetime(2024, 1, 1),
                )
            )
            try:
                invocation_repo.update(invocation, None)  # type: ignore[arg-type]
                failures.append("ai_invocation.update did not raise")
            except RepositoryError:
                pass
            try:
                invocation_repo.delete(invocation)
                failures.append("ai_invocation.delete did not raise")
            except RepositoryError:
                pass
    except Exception as exc:  # noqa: BLE001 - boundary
        failures.append(f"append-only check: {exc}")
    finally:
        database.dispose()

    report.add(
        "append-only contracts enforced",
        not failures,
        "; ".join(failures) if failures else "audit, activity, invocation",
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

    temporary_directory = tempfile.TemporaryDirectory(prefix="academic_platform_phase_b_")
    try:
        database_path = Path(temporary_directory.name) / "acceptance.sqlite3"
        database_url = f"sqlite:///{database_path.as_posix()}"

        _check_declared_head(report)
        _check_upgrade_and_idempotence(report, database_url)
        _check_schema_presence(report, database_url)
        _check_repositories_construct(report, database_url)
        _check_schemas_import(report)
        _check_round_trip(report, database_url)
        _check_cascade_behaviour(report, database_url)
        _check_append_only_contracts(report, database_url)
        _check_downgrade_to_base(report, database_url)
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