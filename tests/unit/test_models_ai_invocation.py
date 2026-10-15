"""Tests for the AIInvocation model."""

from __future__ import annotations

import datetime as dt

import pytest

from academic_platform.infrastructure.database import DatabaseError

from academic_platform.infrastructure.database import Database
from academic_platform.infrastructure.database.base import Base
from academic_platform.infrastructure.database.models import AIInvocation


@pytest.fixture()
def database() -> Database:
    db = Database.in_memory()
    Base.metadata.create_all(db.engine)
    yield db
    db.dispose()


def test_append_and_read(database: Database) -> None:
    with database.session() as session:
        invocation = AIInvocation(
            task_key="article_summarization",
            status="ok",
            started_at=dt.datetime(2024, 1, 1, 12, 0, 0),
            provider_key_snapshot="local-llama",
            model_identifier_snapshot="llama-3-8b",
        )
        session.add(invocation)
        session.flush()
        identifier = invocation.id
    with database.session() as session:
        loaded = session.get(AIInvocation, identifier)
        assert loaded is not None
        assert loaded.status == "ok"
        assert loaded.task_key == "article_summarization"


def test_invalid_status_rejected(database: Database) -> None:
    with pytest.raises(DatabaseError):
        with database.session() as session:
            session.add(
                AIInvocation(
                    task_key="t",
                    status="bogus",
                    started_at=dt.datetime(2024, 1, 1),
                )
            )