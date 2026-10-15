"""Persisted application settings model.

This table stores a small set of installation-level values that do not
belong in the user-editable configuration file:

- The active user profile key.
- The schema version of the settings file that last wrote to the database.

The user-editable settings themselves live in ``config.toml`` and are
managed by ``academic_platform.app.settings.SettingsService``. This table
is deliberately narrow: it holds only values that the application must be
able to read before the settings file is available, or that must be tied
to the database for referential reasons.

Design decisions
----------------
- The table holds a single row. A ``key`` column with a unique constraint
  and a ``singleton`` primary key derived from a constant makes the
  single-row invariant explicit.
- Values are stored as text. Typed accessors on the repository (added in
  a later phase) convert to and from the appropriate Python type.
"""

from __future__ import annotations

from sqlalchemy import CheckConstraint, String
from sqlalchemy.orm import Mapped, mapped_column

from academic_platform.infrastructure.database.base import Base, TimestampMixin

_SINGLETON_ID = 1


class AppSettings(Base, TimestampMixin):
    """Installation-level settings stored in the database.

    Exactly one row exists. The ``id`` column is constrained to the value
    ``1`` so that a second row cannot be inserted accidentally.
    """

    __tablename__ = "app_settings"
    __table_args__ = (
        CheckConstraint("id = 1", name="single_row"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    active_user_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    settings_schema_version: Mapped[int] = mapped_column(nullable=False, default=1)

    def __repr__(self) -> str:
        return f"<AppSettings active_user={self.active_user_key!r}>"