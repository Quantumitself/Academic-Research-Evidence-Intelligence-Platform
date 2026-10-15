"""Tests for the AuditEventRepository."""

from __future__ import annotations

import datetime as dt

import pytest

from academic_platform.infrastructure.database import Database
from academic_platform.infrastructure.database.base import Base
from academic_platform.infrastructure.database.schemas import AuditEventCreate
from academic_platform.infrastructure.repositories.audit_event_repository import (
    AuditEventRepository,
)
from academic_platform.infrastructure.repositories.errors import RepositoryError
from academic_platform.infrastructure.repositories.pagination import PageRequest


@pytest.fixture()
def database() -> Database:
    db = Database.in_memory()
    Base.metadata.create_all(db.engine)
    yield db
    db.dispose()


def test_append_creates_event(database: Database) -> None:
    with database.session() as session:
        repo = AuditEventRepository(session)
        event = repo.append("project.created", actor="alice", summary="Created")
        assert event.id is not None
        assert event.action == "project.created"
        assert event.actor == "alice"


def test_append_defaults_to_system_actor(database: Database) -> None:
    with database.session() as session:
        repo = AuditEventRepository(session)
        event = repo.append("app.started")
        assert event.actor == "system"


def test_append_many(database: Database) -> None:
    with database.session() as session:
        repo = AuditEventRepository(session)
        events = repo.append_many(
            [
                AuditEventCreate(action="a"),
                AuditEventCreate(action="b"),
            ]
        )
        assert len(events) == 2
        assert all(event.id is not None for event in events)


def test_recent_returns_newest_first(database: Database) -> None:
    with database.session() as session:
        repo = AuditEventRepository(session)
        repo.append(
            "older",
            occurred_at=dt.datetime(2020, 1, 1, 12, 0, 0),
        )
        repo.append(
            "newer",
            occurred_at=dt.datetime(2024, 1, 1, 12, 0, 0),
        )
    with database.session() as session:
        repo = AuditEventRepository(session)
        recent = repo.recent()
        assert [event.action for event in recent] == ["newer", "older"]


def test_for_actor_filters(database: Database) -> None:
    with database.session() as session:
        repo = AuditEventRepository(session)
        repo.append("a", actor="alice")
        repo.append("b", actor="bob")
    with database.session() as session:
        repo = AuditEventRepository(session)
        alice = repo.for_actor("alice")
        assert [event.action for event in alice] == ["a"]


def test_find_page_ordered(database: Database) -> None:
    with database.session() as session:
        repo = AuditEventRepository(session)
        for index in range(25):
            repo.append(
                f"event-{index:02d}",
                occurred_at=dt.datetime(2024, 1, 1, 12, 0, index),
            )
    with database.session() as session:
        repo = AuditEventRepository(session)
        page = repo.find_page_ordered(PageRequest(page=1, size=10))
        assert page.total == 25
        assert len(page.items) == 10
        # Newest first.
        assert page.items[0].action == "event-24"


def test_update_is_forbidden(database: Database) -> None:
    with database.session() as session:
        repo = AuditEventRepository(session)
        event = repo.append("a")
        with pytest.raises(RepositoryError):
            repo.update(event, AuditEventCreate(action="b"))


def test_delete_is_forbidden(database: Database) -> None:
    with database.session() as session:
        repo = AuditEventRepository(session)
        event = repo.append("a")
        with pytest.raises(RepositoryError):
            repo.delete(event)


def test_delete_by_id_is_forbidden(database: Database) -> None:
    with database.session() as session:
        repo = AuditEventRepository(session)
        repo.append("a")
        with pytest.raises(RepositoryError):
            repo.delete_by_id(1)


def test_update_fields_is_forbidden(database: Database) -> None:
    with database.session() as session:
        repo = AuditEventRepository(session)
        repo.append("a")
        with pytest.raises(RepositoryError):
            repo.update_fields(1, action="b")