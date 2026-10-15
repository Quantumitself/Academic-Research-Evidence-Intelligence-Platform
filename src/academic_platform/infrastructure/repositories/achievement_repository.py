"""Repositories for achievements, unlocks, and the user activity feed."""

from __future__ import annotations

import datetime as dt

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from academic_platform.infrastructure.database.models import (
    Achievement,
    AchievementUnlock,
    UserActivity,
)
from academic_platform.infrastructure.database.schemas import (
    AchievementCreate,
    UserActivityCreate,
)
from academic_platform.infrastructure.repositories.base import Repository
from academic_platform.infrastructure.repositories.errors import RepositoryError


class AchievementRepository(Repository[Achievement]):
    """Repository for the ``achievement`` table."""

    entity = Achievement

    def find_by_key(self, key: str) -> Achievement | None:
        """Return the achievement with the given key, or ``None``."""
        statement = select(Achievement).where(Achievement.key == key).limit(1)
        try:
            return self._session.execute(statement).scalars().first()
        except SQLAlchemyError as exc:
            raise RepositoryError(f"find_by_key failed: {exc}") from exc

    def list_active(self) -> list[Achievement]:
        """Return every active achievement ordered by category, then title."""
        statement = (
            select(Achievement)
            .where(Achievement.active == 1)
            .order_by(Achievement.category, Achievement.title)
        )
        try:
            return list(self._session.execute(statement).scalars().all())
        except SQLAlchemyError as exc:
            raise RepositoryError(f"list_active failed: {exc}") from exc

    def ensure_definition(self, payload: AchievementCreate) -> tuple[Achievement, bool]:
        """Create the achievement if absent; return (achievement, created)."""
        existing = self.find_by_key(payload.key)
        if existing is not None:
            return existing, False
        return self.create(payload), True


class AchievementUnlockRepository(Repository[AchievementUnlock]):
    """Repository for the ``achievement_unlock`` table."""

    entity = AchievementUnlock

    def find_unlock(self, achievement_id: int, user_key: str) -> AchievementUnlock | None:
        """Return the unlock for a specific achievement and user, or ``None``."""
        statement = (
            select(AchievementUnlock)
            .where(
                AchievementUnlock.achievement_id == achievement_id,
                AchievementUnlock.user_key == user_key,
            )
            .limit(1)
        )
        try:
            return self._session.execute(statement).scalars().first()
        except SQLAlchemyError as exc:
            raise RepositoryError(f"find_unlock failed: {exc}") from exc

    def unlock(
        self,
        achievement_id: int,
        user_key: str,
        *,
        trigger_event: str | None = None,
    ) -> tuple[AchievementUnlock, bool]:
        """Record an unlock if not already present.

        Returns ``(unlock, created)``. Creating an unlock is idempotent;
        repeating the call for the same target returns the existing
        unlock with ``created=False``.
        """
        existing = self.find_unlock(achievement_id, user_key)
        if existing is not None:
            return existing, False
        unlock = AchievementUnlock(
            achievement_id=achievement_id,
            user_key=user_key,
            unlocked_at=dt.datetime.now(dt.timezone.utc).replace(tzinfo=None),
            trigger_event=trigger_event,
        )
        return self.add(unlock), True

    def list_for_user(self, user_key: str) -> list[AchievementUnlock]:
        """Return every unlock for a user, newest first."""
        statement = (
            select(AchievementUnlock)
            .where(AchievementUnlock.user_key == user_key)
            .order_by(AchievementUnlock.unlocked_at.desc(), AchievementUnlock.id.desc())
        )
        try:
            return list(self._session.execute(statement).scalars().all())
        except SQLAlchemyError as exc:
            raise RepositoryError(f"list_for_user failed: {exc}") from exc


class UserActivityRepository(Repository[UserActivity]):
    """Repository for the ``user_activity`` table."""

    entity = UserActivity

    def append(
        self,
        activity_kind: str,
        *,
        user_key: str = "system",
        summary: str = "",
        target_type: str | None = None,
        target_identifier: str | None = None,
        payload_json: str | None = None,
        occurred_at: dt.datetime | None = None,
    ) -> UserActivity:
        """Append an activity record.

        The record is validated against the ``UserActivityCreate`` schema
        so that the same validation rules apply everywhere.
        """
        payload = UserActivityCreate(
            user_key=user_key,
            activity_kind=activity_kind,
            summary=summary,
            target_type=target_type,
            target_identifier=target_identifier,
            payload_json=payload_json,
            occurred_at=occurred_at,
        )
        return self.create(payload)

    def list_recent(self, *, limit: int = 50) -> list[UserActivity]:
        """Return the most recent activity entries, newest first."""
        statement = (
            select(UserActivity)
            .order_by(UserActivity.occurred_at.desc(), UserActivity.id.desc())
            .limit(limit)
        )
        try:
            return list(self._session.execute(statement).scalars().all())
        except SQLAlchemyError as exc:
            raise RepositoryError(f"list_recent failed: {exc}") from exc

    def list_for_user(self, user_key: str, *, limit: int = 50) -> list[UserActivity]:
        """Return activity entries for a specific user, newest first."""
        statement = (
            select(UserActivity)
            .where(UserActivity.user_key == user_key)
            .order_by(UserActivity.occurred_at.desc(), UserActivity.id.desc())
            .limit(limit)
        )
        try:
            return list(self._session.execute(statement).scalars().all())
        except SQLAlchemyError as exc:
            raise RepositoryError(f"list_for_user failed: {exc}") from exc

    def update(self, entity: UserActivity, payload) -> UserActivity:  # type: ignore[override]
        raise RepositoryError("User activity records are append-only")

    def update_fields(self, identifier, **changes) -> UserActivity:  # type: ignore[override]
        raise RepositoryError("User activity records are append-only")

    def delete(self, entity: UserActivity) -> None:  # type: ignore[override]
        raise RepositoryError("User activity records are append-only")

    def delete_by_id(self, identifier) -> bool:  # type: ignore[override]
        raise RepositoryError("User activity records are append-only")