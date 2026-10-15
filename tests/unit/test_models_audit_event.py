"""Tests for the AuditEvent model."""

from __future__ import annotations

import datetime as dt

import pytest

from academic_platform.infrastructure.database import Database
from academic_platform.infrastructure.database.base import Base
from academic_platform.infrastructure.database.models import AuditEvent


@pytest.fixture()
def database() -> Database:
    db = Database.in_memory()
    Base.metadata.create_all(db.engine)
    yield db
    db.dispose()


def test_append_and_read(database: Database) -> None:
    with database.session() as session:
        event = AuditEvent(
            actor="alice",
            action="project.created",
            target_type="research_project",
            target_identifier="p1",
            summary="Created project",
        )
        session.add(event)
        session.flush()
        identifier = event.id
    with database.session() as session:
        loaded = session.get(AuditEvent, identifier)
        assert loaded is not None
        assert loaded.action == "project.created"
        assert loaded.occurred_at is not None


def test_default_actor_is_system(database: Database) -> None:
    with database.session() as session:
        event = AuditEvent(action="app.started")
        session.add(event)
        session.flush()
    assert event.actor == "system"


def test_payload_round_trip(database: Database) -> None:
    with database.session() as session:
        event = AuditEvent(
            action="project.updated",
            payload_json='{"field": "title"}',
        )
        session.add(event)
        session.flush()
    with database.session() as session:
        loaded = session.get(AuditEvent, event.id)
        assert loaded is not None
        assert loaded.payload_json == '{"field": "title"}'


def test_occurred_at_can_be_overridden(database: Database) -> None:
    past = dt.datetime(2020, 1, 1, 12, 0, 0)
    with database.session() as session:
        event = AuditEvent(action="legacy.import", occurred_at=past)
        session.add(event)
        session.flush()
    with database.session() as session:
        loaded = session.get(AuditEvent, event.id)
        assert loaded is not None
        assert loaded.occurred_at == past