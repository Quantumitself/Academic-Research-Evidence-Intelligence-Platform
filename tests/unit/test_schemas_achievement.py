"""Tests for the achievement and activity Pydantic schemas."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from academic_platform.infrastructure.database.schemas import (
    AchievementCreate,
    AchievementUnlockCreate,
    UserActivityCreate,
)


def test_achievement_create_defaults() -> None:
    payload = AchievementCreate(key="a", title="A")
    assert payload.active is True
    assert payload.category == "general"


def test_achievement_unlock_create_defaults() -> None:
    payload = AchievementUnlockCreate(achievement_id=1, user_key="alice")
    assert payload.unlocked_at is None


def test_activity_create_rejects_bad_kind() -> None:
    with pytest.raises(ValidationError):
        UserActivityCreate(activity_kind="bogus")


def test_activity_create_accepts_valid_kind() -> None:
    payload = UserActivityCreate(activity_kind="project_created")
    assert payload.user_key == "system"