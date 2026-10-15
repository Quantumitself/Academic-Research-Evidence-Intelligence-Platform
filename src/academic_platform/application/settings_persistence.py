"""Bridge between the file-backed settings service and the database.

The application keeps user-editable settings in ``config.toml`` and a
small set of installation-level values in the ``app_settings`` table. The
two storage locations serve different purposes:

- The configuration file is user-editable, versioned, and portable.
- The database row is protected by the same transactions that protect the
  rest of the user's data and is available before the configuration file
  is parsed.

``SettingsPersistenceBridge`` keeps the database row in sync with the
settings file when they overlap:

- The settings file's ``schema_version`` is mirrored into
  ``app_settings.settings_schema_version`` so that recovery tooling can
  inspect the last known settings schema version even if the file is
  later corrupted.
- The active user key is owned by the bridge, not by the settings file.
  It is stored only in the database so that the active-user selection
  survives a settings reset.

Design decisions
----------------
- The bridge is synchronous and short-lived. It is constructed per unit
  of work and discarded afterward.
- The bridge does not commit. It operates on the session managed by the
  caller's ``unit_of_work`` context.
- The bridge is defensive: it validates inputs and refuses to write
  values that would violate the settings schema.
"""

from __future__ import annotations

import logging

from academic_platform.app.settings import (
    SETTINGS_SCHEMA_VERSION,
    SettingsError,
    SettingsService,
)
from academic_platform.infrastructure.database.models import AppSettings
from academic_platform.infrastructure.repositories.app_settings_repository import (
    AppSettingsRepository,
)
from academic_platform.infrastructure.repositories.errors import RepositoryError
from academic_platform.infrastructure.repositories.user_profile_repository import (
    UserProfileRepository,
)

_logger = logging.getLogger(__name__)


class SettingsPersistenceError(RuntimeError):
    """Raised when the bridge cannot reconcile settings and database state."""


class SettingsPersistenceBridge:
    """Reconciles the settings file and the database settings row."""

    def __init__(
        self,
        settings_service: SettingsService,
        app_settings_repository: AppSettingsRepository,
        user_profile_repository: UserProfileRepository,
    ) -> None:
        self._settings_service = settings_service
        self._app_settings = app_settings_repository
        self._profiles = user_profile_repository

    # ------------------------------------------------------------------
    # Synchronization
    # ------------------------------------------------------------------
    def synchronize(self) -> AppSettings:
        """Reconcile the settings file's schema version with the database.

        Called during startup after the settings service has loaded. The
        bridge reads the singleton row, compares its schema version with
        the settings file's schema version, and updates the row when they
        differ. A settings file with a version newer than the application
        supports is rejected by the settings service before this method is
        reached; the bridge therefore never has to reconcile a downgrade.
        """
        try:
            settings = self._settings_service.settings
        except SettingsError as exc:
            raise SettingsPersistenceError(f"Settings unavailable: {exc}") from exc

        file_version = settings.schema_version
        if file_version > SETTINGS_SCHEMA_VERSION:
            raise SettingsPersistenceError(
                f"Settings schema version {file_version} is newer than "
                f"the application supports ({SETTINGS_SCHEMA_VERSION})."
            )

        try:
            row = self._app_settings.get_singleton()
        except RepositoryError as exc:
            raise SettingsPersistenceError(
                f"Unable to read application settings row: {exc}"
            ) from exc

        if row.settings_schema_version != file_version:
            _logger.info(
                "Updating app_settings.settings_schema_version from %s to %s",
                row.settings_schema_version,
                file_version,
            )
            row = self._app_settings.upsert(settings_schema_version=file_version)
        return row

    # ------------------------------------------------------------------
    # Active user
    # ------------------------------------------------------------------
    def set_active_user(self, key: str | None) -> AppSettings:
        """Set or clear the active user profile.

        When a key is supplied, the profile must exist. When ``None`` is
        supplied, the active user key is cleared. The method never creates
        a profile implicitly; profile creation is the responsibility of the
        profile-management workflow.
        """
        if key is None:
            return self._app_settings.clear_active_user()
        profile = self._profiles.find_by_key(key)
        if profile is None:
            raise SettingsPersistenceError(
                f"Cannot activate unknown user profile {key!r}"
            )
        return self._app_settings.upsert(active_user_key=key)

    def get_active_user_key(self) -> str | None:
        """Return the active user key, or ``None`` when no user is active."""
        row = self._app_settings.get_singleton()
        return row.active_user_key