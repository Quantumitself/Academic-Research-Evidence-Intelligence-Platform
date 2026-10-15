"""Phase B acceptance criteria as automated tests.

These tests express the acceptance criteria in the same language as the
Phase B acceptance document. They are intentionally broader than the
per-module tests: they exercise the migration pipeline, the repository
factory, and the schema boundary together.

The tests use a temporary home directory and a temporary database file.
They do not touch the user's data.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import inspect

from academic_platform.infrastructure.database import (
    Database,
    DatabaseConfiguration,
)
from academic_platform.infrastructure.database.base import Base
from academic_platform.infrastructure.database.migrations import (
    current_revision,
    declared_head_revision,
    downgrade,
    upgrade_to_head,
)
from tests.unit._migration_head import EXPECTED_HEAD


@pytest.fixture()
def database_url(tmp_path: Path) -> str:
    target = tmp_path / "acceptance.sqlite3"
    target.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{target.as_posix()}"


def test_declared_head_matches_expected_head() -> None:
    assert declared_head_revision() == EXPECTED_HEAD


def test_upgrade_from_empty_reaches_head(database_url: str) -> None:
    result = upgrade_to_head(database_url)
    assert result.current_revision == EXPECTED_HEAD
    assert result.head_revision == EXPECTED_HEAD
    assert result.changed is True
    assert result.up_to_date is True


def test_upgrade_is_idempotent(database_url: str) -> None:
    first = upgrade_to_head(database_url)
    second = upgrade_to_head(database_url)
    assert first.current_revision == second.current_revision
    assert second.changed is False


#: Table names registered by test-only model definitions. These tables are
#: created by ``Base.metadata.create_all`` in the tests that declare them
#: and are not part of the production schema; migrations must not create
#: them.
_TEST_ONLY_TABLES: frozenset[str] = frozenset(
    {"sample_base_test", "spec_test_row", "repo_test_item"}
)


def test_every_registered_table_exists_after_upgrade(database_url: str) -> None:
    upgrade_to_head(database_url)
    database = Database(DatabaseConfiguration(url=database_url))
    try:
        inspector = inspect(database.engine)
        present = set(inspector.get_table_names())
    finally:
        database.dispose()
    for table_name in Base.metadata.tables.keys():
        if table_name in _TEST_ONLY_TABLES:
            continue
        assert table_name in present, table_name


def test_repositories_construct_against_live_session(database_url: str) -> None:
    from academic_platform.infrastructure.repositories.base import Repository
    from academic_platform.infrastructure.repositories.factory import (
        _REPOSITORY_REGISTRY,
    )

    upgrade_to_head(database_url)
    database = Database(DatabaseConfiguration(url=database_url))
    try:
        with database.session() as session:
            for key, repository_class in _REPOSITORY_REGISTRY.items():
                instance = repository_class(session)
                assert isinstance(instance, Repository), key
    finally:
        database.dispose()


def test_every_exported_schema_is_importable() -> None:
    from academic_platform.infrastructure.database import schemas as schemas_pkg

    for name in schemas_pkg.__all__:
        assert hasattr(schemas_pkg, name), name


def test_round_trip_survives_session_close(database_url: str) -> None:
    from academic_platform.infrastructure.database.schemas import (
        ResearchProjectCreate,
    )
    from academic_platform.infrastructure.repositories.research_project_repository import (
        ResearchProjectRepository,
    )

    upgrade_to_head(database_url)
    database = Database(DatabaseConfiguration(url=database_url))
    try:
        with database.session() as session:
            repo = ResearchProjectRepository(session)
            project = repo.create(ResearchProjectCreate(key="rt", title="Rt"))
            project_id = project.id
        with database.session() as session:
            repo = ResearchProjectRepository(session)
            loaded = repo.get(project_id)
            assert loaded is not None
            assert loaded.title == "Rt"
    finally:
        database.dispose()


def test_cascade_delete_of_research_project(database_url: str) -> None:
    from academic_platform.infrastructure.database.models import (
        ResearchProject,
        ResearchQuestion,
    )

    upgrade_to_head(database_url)
    database = Database(DatabaseConfiguration(url=database_url))
    try:
        with database.session() as session:
            project = ResearchProject(key="p")
            session.add(project)
            session.flush()
            session.add(ResearchQuestion(project_id=project.id, text="q"))
        with database.session() as session:
            session.delete(session.get(ResearchProject, 1))
        with database.session() as session:
            assert session.query(ResearchQuestion).count() == 0
    finally:
        database.dispose()


def test_append_only_contract_for_audit_events(database_url: str) -> None:
    from academic_platform.infrastructure.database.schemas import AuditEventCreate
    from academic_platform.infrastructure.repositories.audit_event_repository import (
        AuditEventRepository,
    )
    from academic_platform.infrastructure.repositories.errors import RepositoryError

    upgrade_to_head(database_url)
    database = Database(DatabaseConfiguration(url=database_url))
    try:
        with database.session() as session:
            repo = AuditEventRepository(session)
            event = repo.create(AuditEventCreate(action="x"))
            with pytest.raises(RepositoryError):
                repo.update(event, AuditEventCreate(action="y"))
            with pytest.raises(RepositoryError):
                repo.delete(event)
    finally:
        database.dispose()


def test_downgrade_to_base_then_re_upgrade(database_url: str) -> None:
    upgrade_to_head(database_url)
    downgrade(database_url, "base")
    assert current_revision(database_url) is None
    second = upgrade_to_head(database_url)
    assert second.current_revision == EXPECTED_HEAD