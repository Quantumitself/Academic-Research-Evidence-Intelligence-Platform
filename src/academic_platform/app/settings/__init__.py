"""Persistent application settings service.

The settings service owns the lifecycle of the user configuration file. It
exposes a typed, immutable view of the current settings and provides atomic,
validated mutation.

Public surface
--------------
- ``SettingsSchema``: the validated configuration model.
- ``SettingsService``: load, save, observe, and reset settings.
- ``SettingsError``: raised for unrecoverable configuration failures.
- ``SETTINGS_SCHEMA_VERSION``: the current on-disk schema version.

The service never imports from ``academic_platform.ui``. It may be used by
headless tooling and by the external API layer.
"""

from academic_platform.app.settings.schema import (
    AISettings,
    AppearanceSettings,
    GeneralSettings,
    LibrarySettings,
    NetworkSettings,
    PrivacySettings,
    SearchSettings,
    SettingsSchema,
    SETTINGS_SCHEMA_VERSION,
    ThemeMode,
)
from academic_platform.app.settings.service import (
    SettingsError,
    SettingsLoadResult,
    SettingsService,
)

__all__ = [
    "AISettings",
    "AppearanceSettings",
    "GeneralSettings",
    "LibrarySettings",
    "NetworkSettings",
    "PrivacySettings",
    "SearchSettings",
    "SETTINGS_SCHEMA_VERSION",
    "SettingsError",
    "SettingsLoadResult",
    "SettingsSchema",
    "SettingsService",
    "ThemeMode",
]