"""Tests for the AppSettingsRepository."""

from __future__ import annotations

import pytest

from academic_platform.infrastructure.database import Database
from academic_platform.infrastructure.database.base import Base
from academic_platform.infrastructure.repositories.app_settings_repository import (
    AppSettingsRepository,
)


@pytest.fixture()
def database() -> Database:
    db = Database.in_memory()
    Base.metadata.create_all(db.engine)
    yield db
    db.dispose()


def test_get_singleton_creates_row(database: Database) -> None:
    with database.session() as session:
        repo = AppSettingsRepository(session)
        row = repo.get_singleton()
        assert row.id == 1
        assert row.active_user_key is None
        assert row.settings_schema_version == 1


def test_get_singleton_is_idempotent(database: Database) -> None:
    with database.session() as session:
        repo = AppSettingsRepository(session)
        first = repo.get_singleton()
        first_id = first.id
    with database.session() as session:
        repo = AppSettingsRepository(session)
        second = repo.get_singleton()
        assert second.id == first_id


def test_read_returns_validated_model(database: Database) -> None:
    with database.session() as session:
        repo = AppSettingsRepository(session)
        read = repo.read()
        assert read.id == 1
        assert read.settings_schema_version == 1


def test_upsert_updates_active_user(database: Database) -> None:
    with database.session() as session:
        repo = AppSettingsRepository(session)
        repo.upsert(active_user_key="alice")
    with database.session() as session:
        repo = AppSettingsRepository(session)
        row = repo.get_singleton()
        assert row.active_user_key == "alice"


def test_upsert_updates_schema_version(database: Database) -> None:
    with database.session() as session:
        repo = AppSettingsRepository(session)
        repo.upsert(settings_schema_version=5)
    with database.session() as session:
        repo = AppSettingsRepository(session)
        row = repo.get_singleton()
        assert row.settings_schema_version == 5


def test_upsert_with_no_changes_is_noop(database: Database) -> None:
    with database.session() as session:
        repo = AppSettingsRepository(session)
        repo.upsert(active_user_key="alice")
    with database.session() as session:
        repo = AppSettingsRepository(session)
        row = repo.upsert()
        assert row.active_user_key == "alice"


def test_clear_active_user(database: Database) -> None:
    with database.session() as session:
        repo = AppSettingsRepository(session)
        repo.upsert(active_user_key="alice")
    with database.session() as session:
        repo = AppSettingsRepository(session)
        row = repo.clear_active_user()
        assert row.active_user_key is None