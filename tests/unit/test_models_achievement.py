"""Tests for the achievement, unlock, and user activity models."""

from __future__ import annotations

import datetime as dt

import pytest

from academic_platform.infrastructure.database import DatabaseError

from academic_platform.infrastructure.database import Database
from academic_platform.infrastructure.database.base import Base
from academic_platform.infrastructure.database.models import (
    Achievement,
    AchievementUnlock,
    UserActivity,
)


@pytest.fixture()
def database() -> Database:
    db = Database.in_memory()
    Base.metadata.create_all(db.engine)
    yield db
    db.dispose()


def test_achievement_and_unlock(database: Database) -> None:
    with database.session() as session:
        achievement = Achievement(key="first_project", title="First Project")
        session.add(achievement)
        session.flush()
        session.add(
            AchievementUnlock(
                achievement_id=achievement.id,
                user_key="alice",
                unlocked_at=dt.datetime(2024, 1, 1),
            )
        )
    with database.session() as session:
        assert session.query(Achievement).count() == 1
        assert session.query(AchievementUnlock).count() == 1


def test_unlock_unique_per_user(database: Database) -> None:
    with database.session() as session:
        achievement = Achievement(key="a", title="A")
        session.add(achievement)
        session.flush()
        session.add(
            AchievementUnlock(
                achievement_id=achievement.id,
                user_key="alice",
                unlocked_at=dt.datetime(2024, 1, 1),
            )
        )
    with pytest.raises(DatabaseError):
        with database.session() as session:
            session.add(
                AchievementUnlock(
                    achievement_id=1,
                    user_key="alice",
                    unlocked_at=dt.datetime(2024, 1, 2),
                )
            )


def test_activity_kind_enforced(database: Database) -> None:
    with pytest.raises(DatabaseError):
        with database.session() as session:
            session.add(
                UserActivity(
                    activity_kind="bogus",
                    occurred_at=dt.datetime(2024, 1, 1),
                )
            )


def test_activity_default_user_system(database: Database) -> None:
    with database.session() as session:
        activity = UserActivity(
            activity_kind="app_started",
            occurred_at=dt.datetime(2024, 1, 1),
        )
        session.add(activity)
        session.flush()
        assert activity.user_key == "system"