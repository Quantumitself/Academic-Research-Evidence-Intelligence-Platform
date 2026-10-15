"""User profile model.

The application is designed around a single primary user. The
``user_profile`` table holds one row per user profile, identified by a
stable string key. Multiple profiles are permitted so that a single
installation can host more than one researcher without shared state, but
only one profile is active at a time; the active profile key is stored in
``AppSettings``.
"""

from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from academic_platform.infrastructure.database.base import (
    Base,
    TimestampMixin,
    VersionMixin,
)


class UserProfile(Base, TimestampMixin, VersionMixin):
    """A single user profile.

    Attributes
    ----------
    id:
        Surrogate primary key.
    key:
        Stable identifier used in foreign keys and settings. Immutable
        after creation. Lowercase ASCII letters, digits, hyphens, and
        underscores only.
    display_name:
        Free-form name shown in the interface.
    preferred_language:
        Optional BCP 47 language tag overriding the application default.
    institution:
        Optional free-form institution name.
    notes:
        Optional free-form notes about the profile.
    """

    __tablename__ = "user_profile"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    preferred_language: Mapped[str | None] = mapped_column(String(16), nullable=True)
    institution: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(4096), nullable=True)

    def __repr__(self) -> str:
        return f"<UserProfile key={self.key!r}>"