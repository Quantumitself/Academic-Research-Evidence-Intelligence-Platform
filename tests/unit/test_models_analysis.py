"""Tests for the analysis models."""

from __future__ import annotations

import datetime as dt

import pytest

from academic_platform.infrastructure.database import DatabaseError

from academic_platform.infrastructure.database import Database
from academic_platform.infrastructure.database.base import Base
from academic_platform.infrastructure.database.models import (
    AnalysisInput,
    AnalysisRun,
)


@pytest.fixture()
def database() -> Database:
    db = Database.in_memory()
    Base.metadata.create_all(db.engine)
    yield db
    db.dispose()


def test_create_analysis_run(database: Database) -> None:
    with database.session() as session:
        run = AnalysisRun(
            analysis_type="descriptive",
            status="running",
            started_at=dt.datetime(2024, 1, 1, 12, 0, 0),
        )
        session.add(run)
        session.flush()
        identifier = run.id
    with database.session() as session:
        loaded = session.get(AnalysisRun, identifier)
        assert loaded is not None
        assert loaded.inputs_count == 0


def test_invalid_analysis_type_rejected(database: Database) -> None:
    with pytest.raises(DatabaseError):
        with database.session() as session:
            session.add(
                AnalysisRun(
                    analysis_type="bogus",
                    status="running",
                    started_at=dt.datetime(2024, 1, 1),
                )
            )



def test_invalid_status_rejected(database: Database) -> None:
    with pytest.raises(DatabaseError):
        with database.session() as session:
            session.add(
                AnalysisRun(
                    analysis_type="descriptive",
                    status="bogus",
                    started_at=dt.datetime(2024, 1, 1),
                )
            )


def test_input_cascade_delete(database: Database) -> None:
    with database.session() as session:
        run = AnalysisRun(
            analysis_type="descriptive",
            status="running",
            started_at=dt.datetime(2024, 1, 1),
        )
        session.add(run)
        session.flush()
        session.add(
            AnalysisInput(
                analysis_run_id=run.id,
                input_key="mean",
                value_kind="number",
                value_text="3.14",
            )
        )
    with database.session() as session:
        run = session.get(AnalysisRun, 1)
        assert run is not None
        session.delete(run)
    with database.session() as session:
        assert session.query(AnalysisInput).count() == 0