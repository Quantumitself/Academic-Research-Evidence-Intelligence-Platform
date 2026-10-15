"""Achievement and user activity models.

An achievement is a milestone that the user unlocks by performing a
meaningful research action. The definition of the achievement is stored
once; the unlock is recorded per user profile with the timestamp. User
activity is an append-only feed of notable actions performed through the
application.

Design decisions
----------------
- Achievement definitions are stored in the database so that they can be
  updated without changing application code. The ``key`` is stable; the
  definition may be revised.
- Unlocks are unique per ``(achievement_id, user_key)``. An achievement
  unlocks once per profile. The unlock records when it happened and, for
  auditability, which application event triggered it.
- Activity entries are append-only. They are not modified or deleted by
  application code. The feed is trimmed by a background task that
  removes old entries according to the configured retention.
- ``activity_kind`` is a closed enumeration. New activity kinds require a
  migration and a corresponding emit site in the application.
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from academic_platform.infrastructure.database.base import (
    Base,
    TimestampMixin,
    VersionMixin,
)

_ACTIVITY_KINDS = (
    "app_started",
    "project_created",
    "project_updated",
    "document_imported",
    "search_executed",
    "collection_created",
    "evidence_extracted",
    "evidence_verified",
    "analysis_run",
    "guide_generated",
    "achievement_unlocked",
    "settings_changed",
)
_ACTIVITY_KIND_CHECK = (
    "activity_kind IN ("
    + ", ".join(f"'{value}'" for value in _ACTIVITY_KINDS)
    + ")"
)


class Achievement(Base, TimestampMixin, VersionMixin):
    """Definition of an achievement."""

    __tablename__ = "achievement"
    __table_args__ = (
        Index("ix_achievement_category", "category"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    category: Mapped[str] = mapped_column(
        String(32), nullable=False, default="general", server_default="general"
    )
    points: Mapped[int] = mapped_column(
        nullable=False, default=0, server_default="0"
    )
    active: Mapped[int] = mapped_column(
        nullable=False, default=1, server_default="1"
    )

    def __repr__(self) -> str:
        return f"<Achievement key={self.key!r}>"


class AchievementUnlock(Base, TimestampMixin):
    """A record that a user profile unlocked an achievement."""

    __tablename__ = "achievement_unlock"
    __table_args__ = (
        UniqueConstraint(
            "achievement_id",
            "user_key",
            name="uq_achievement_unlock_target",
        ),
        Index("ix_achievement_unlock_user", "user_key"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    achievement_id: Mapped[int] = mapped_column(
        ForeignKey("achievement.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_key: Mapped[str] = mapped_column(String(64), nullable=False)
    unlocked_at: Mapped[dt.datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=lambda: dt.datetime.now(dt.timezone.utc).replace(tzinfo=None),
    )
    trigger_event: Mapped[str | None] = mapped_column(String(64), nullable=True)

    def __repr__(self) -> str:
        return (
            f"<AchievementUnlock achievement={self.achievement_id} "
            f"user={self.user_key!r}>"
        )


class UserActivity(Base, TimestampMixin):
    """An append-only record of a notable user action."""

    __tablename__ = "user_activity"
    __table_args__ = (
        CheckConstraint(_ACTIVITY_KIND_CHECK, name="activity_kind_valid"),
        Index("ix_user_activity_occurred_at", "occurred_at"),
        Index("ix_user_activity_user_occurred", "user_key", "occurred_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_key: Mapped[str] = mapped_column(
        String(64), nullable=False, default="system", server_default="system"
    )
    activity_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    summary: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    target_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    target_identifier: Mapped[str | None] = mapped_column(String(128), nullable=True)
    payload_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    occurred_at: Mapped[dt.datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=lambda: dt.datetime.now(dt.timezone.utc).replace(tzinfo=None),
    )

    def __repr__(self) -> str:
        return (
            f"<UserActivity kind={self.activity_kind!r} "
            f"user={self.user_key!r}>"
        )