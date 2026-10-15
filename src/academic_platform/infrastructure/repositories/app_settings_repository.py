"""Repository for the singleton application settings row.

The ``app_settings`` table holds a single row. The repository guarantees
that the row exists by creating it on first access. All operations target
that single row; there is no way to address a different row through this
repository.
"""

from __future__ import annotations

from academic_platform.infrastructure.database.models import AppSettings
from academic_platform.infrastructure.database.schemas import (
    AppSettingsRead,
    AppSettingsUpsert,
)
from academic_platform.infrastructure.repositories.base import Repository
from academic_platform.infrastructure.repositories.errors import RepositoryError
from sqlalchemy.exc import SQLAlchemyError

_SINGLETON_ID = 1


class AppSettingsRepository(Repository[AppSettings]):
    """Repository for the singleton ``app_settings`` row."""

    entity = AppSettings

    def get_singleton(self) -> AppSettings:
        """Return the singleton row, creating it with defaults when absent."""
        row = self.get(_SINGLETON_ID)
        if row is not None:
            return row
        row = AppSettings(id=_SINGLETON_ID)
        return self.add(row)

    def read(self) -> AppSettingsRead:
        """Return a validated read model of the singleton row."""
        row = self.get_singleton()
        return AppSettingsRead.model_validate(row)

    def upsert(
        self,
        *,
        active_user_key: str | None = None,
        settings_schema_version: int | None = None,
    ) -> AppSettings:
        """Update the singleton row.

        Only the supplied fields are changed. Both fields are optional so
        that callers can update one without touching the other.
        """
        row = self.get_singleton()
        changes: dict[str, object] = {}
        if active_user_key is not None:
            changes["active_user_key"] = active_user_key
        if settings_schema_version is not None:
            changes["settings_schema_version"] = settings_schema_version
        if not changes:
            return row
        for field_name, value in changes.items():
            setattr(row, field_name, value)
        try:
            self._session.flush()
        except SQLAlchemyError as exc:
            raise RepositoryError(f"upsert failed: {exc}") from exc
        return row

    def clear_active_user(self) -> AppSettings:
        """Clear the active user key without removing the singleton row."""
        row = self.get_singleton()
        row.active_user_key = None
        try:
            self._session.flush()
        except SQLAlchemyError as exc:
            raise RepositoryError(f"clear_active_user failed: {exc}") from exc
        return row