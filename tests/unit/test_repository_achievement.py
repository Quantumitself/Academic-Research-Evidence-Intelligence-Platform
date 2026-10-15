"""Tests for the achievement and activity repositories."""

from __future__ import annotations

import pytest

from academic_platform.infrastructure.database import Database
from academic_platform.infrastructure.database.base import Base
from academic_platform.infrastructure.database.schemas import AchievementCreate
from academic_platform.infrastructure.repositories.achievement_repository import (
    AchievementRepository,
    AchievementUnlockRepository,
    UserActivityRepository,
)
from academic_platform.infrastructure.repositories.errors import RepositoryError


@pytest.fixture()
def database() -> Database:
    db = Database.in_memory()
    Base.metadata.create_all(db.engine)
    yield db
    db.dispose()


def test_ensure_definition_idempotent(database: Database) -> None:
    with database.session() as session:
        repo = AchievementRepository(session)
        first, created = repo.ensure_definition(
            AchievementCreate(key="first_project", title="First")
        )
        assert created is True
        second, created = repo.ensure_definition(
            AchievementCreate(key="first_project", title="First (rev)")
        )
        assert created is False
        assert first.id == second.id


def test_unlock_idempotent(database: Database) -> None:
    with database.session() as session:
        repo = AchievementRepository(session)
        achievement, _ = repo.ensure_definition(
            AchievementCreate(key="a", title="A")
        )
        achievement_id = achievement.id
    with database.session() as session:
        repo = AchievementUnlockRepository(session)
        first, created = repo.unlock(achievement_id, "alice")
        assert created is True
        second, created = repo.unlock(achievement_id, "alice")
        assert created is False
        assert first.id == second.id


def test_user_activity_append_and_list(database: Database) -> None:
    with database.session() as session:
        repo = UserActivityRepository(session)
        repo.append("project_created", user_key="alice", summary="Created")
        repo.append("search_executed", user_key="alice", summary="Searched")
        repo.append("app_started", user_key="system", summary="Started")
    with database.session() as session:
        repo = UserActivityRepository(session)
        assert len(repo.list_recent()) == 3
        assert len(repo.list_for_user("alice")) == 2


def test_activity_append_only(database: Database) -> None:
    with database.session() as session:
        repo = UserActivityRepository(session)
        activity = repo.append("app_started")
        with pytest.raises(RepositoryError):
            repo.update(activity, None)
        with pytest.raises(RepositoryError):
            repo.delete(activity)
        with pytest.raises(RepositoryError):
            repo.update_fields(activity.id, summary="x")
        with pytest.raises(RepositoryError):
            repo.delete_by_id(activity.id)