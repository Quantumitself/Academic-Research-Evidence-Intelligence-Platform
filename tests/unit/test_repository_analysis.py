"""Tests for the analysis repositories."""

from __future__ import annotations

import datetime as dt

import pytest

from academic_platform.infrastructure.database import Database
from academic_platform.infrastructure.database.base import Base
from academic_platform.infrastructure.database.models import (
    AnalysisInput,
    AnalysisRun,
)
from academic_platform.infrastructure.database.schemas import (
    AnalysisInputCreate,
    AnalysisRunCreate,
)
from academic_platform.infrastructure.repositories.analysis_repository import (
    AnalysisInputRepository,
    AnalysisRunRepository,
)


@pytest.fixture()
def database() -> Database:
    db = Database.in_memory()
    Base.metadata.create_all(db.engine)
    yield db
    db.dispose()


def test_create_and_mark_finished(database: Database) -> None:
    with database.session() as session:
        repo = AnalysisRunRepository(session)
        run = repo.create(
            AnalysisRunCreate(
                analysis_type="descriptive",
                status="running",
                started_at=dt.datetime(2024, 1, 1, 12, 0, 0),
            )
        )
        run_id = run.id
    with database.session() as session:
        repo = AnalysisRunRepository(session)
        updated = repo.mark_finished(
            run_id,
            status="succeeded",
            finished_at=dt.datetime(2024, 1, 1, 12, 0, 1),
            duration_ms=1000,
            result_json='{"mean": 3.14}',
            warnings_json="[]",
        )
        assert updated.status == "succeeded"
        assert updated.result_json == '{"mean": 3.14}'


def test_list_recent(database: Database) -> None:
    with database.session() as session:
        repo = AnalysisRunRepository(session)
        for index in range(3):
            repo.create(
                AnalysisRunCreate(
                    analysis_type="descriptive",
                    status="succeeded",
                    started_at=dt.datetime(2024, 1, 1, 12, index, 0),
                )
            )
    with database.session() as session:
        repo = AnalysisRunRepository(session)
        recent = repo.list_recent(limit=2)
        assert len(recent) == 2


def test_list_for_type(database: Database) -> None:
    with database.session() as session:
        repo = AnalysisRunRepository(session)
        repo.create(
            AnalysisRunCreate(
                analysis_type="descriptive",
                status="succeeded",
                started_at=dt.datetime(2024, 1, 1),
            )
        )
        repo.create(
            AnalysisRunCreate(
                analysis_type="t_test",
                status="succeeded",
                started_at=dt.datetime(2024, 1, 1),
            )
        )
    with database.session() as session:
        repo = AnalysisRunRepository(session)
        assert len(repo.list_for_type("t_test")) == 1


def test_input_add_and_list(database: Database) -> None:
    with database.session() as session:
        repo = AnalysisRunRepository(session)
        run = repo.create(
            AnalysisRunCreate(
                analysis_type="descriptive",
                status="running",
                started_at=dt.datetime(2024, 1, 1),
            )
        )
        run_id = run.id
    with database.session() as session:
        input_repo = AnalysisInputRepository(session)
        input_repo.create(
            AnalysisInputCreate(
                analysis_run_id=run_id,
                input_key="mean",
                value_kind="number",
                value_text="3.14",
            )
        )
        input_repo.create(
            AnalysisInputCreate(
                analysis_run_id=run_id,
                input_key="n",
                value_kind="integer",
                value_text="120",
            )
        )
    with database.session() as session:
        input_repo = AnalysisInputRepository(session)
        inputs = input_repo.list_for_run(run_id)
        assert [i.input_key for i in inputs] == ["mean", "n"]


def test_add_inputs_requires_matching_run(database: Database) -> None:
    from academic_platform.infrastructure.repositories.errors import (
        RepositoryError,
    )

    with database.session() as session:
        repo = AnalysisRunRepository(session)
        run = repo.create(
            AnalysisRunCreate(
                analysis_type="descriptive",
                status="running",
                started_at=dt.datetime(2024, 1, 1),
            )
        )
    with database.session() as session:
        input_repo = AnalysisInputRepository(session)
        bogus = [
            AnalysisInput(
                analysis_run_id=run.id + 999,
                input_key="k",
                value_kind="number",
                value_text="1",
            )
        ]
        with pytest.raises(RepositoryError):
            input_repo.add_inputs(run.id, bogus)