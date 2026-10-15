"""Settings service.

Responsibilities
----------------
- Locate and load the configuration file.
- Validate the loaded content against the current schema.
- Migrate older on-disk schema versions to the current version.
- Persist changes atomically with a backup of the previous file.
- Notify observers when settings change.
- Provide a safe reset-to-defaults operation.

Design decisions
----------------
- Loading never raises on a missing file; the service creates one with
  defaults on first run.
- Loading raises ``SettingsError`` when the file exists but is corrupt or
  incompatible. The caller decides how to surface the failure.
- Saves are atomic: the content is written to a temporary file in the same
  directory, fsynced, and then renamed over the target. The previous file is
  retained as ``config.toml.bak``.
- The service caches the current settings in memory. All readers see the
  same validated instance until a save occurs.
- Observers are invoked after a successful save, in registration order. An
  observer that raises does not prevent other observers from being notified;
  the exception is logged.
"""

from __future__ import annotations

import logging
import os
import tempfile
import threading
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import tomli_w
import tomllib
from pydantic import ValidationError

from academic_platform.app.settings.schema import (
    SETTINGS_SCHEMA_VERSION,
    SettingsSchema,
)

_logger = logging.getLogger(__name__)

_BACKUP_SUFFIX = ".bak"
_OBSERVER = Callable[[SettingsSchema], None]


class SettingsError(RuntimeError):
    """Raised when the configuration file cannot be loaded or persisted."""


@dataclass(frozen=True, slots=True)
class SettingsLoadResult:
    """Outcome of a settings load operation.

    ``created`` indicates that the file did not exist and was created with
    defaults. ``migrated_from`` records the previous schema version when a
    migration was applied, otherwise ``None``.
    """

    settings: SettingsSchema
    path: Path
    created: bool
    migrated_from: int | None


def _write_atomic(path: Path, content: str) -> None:
    """Write ``content`` to ``path`` atomically.

    The previous file, if any, is preserved as a ``.bak`` sibling. The
    temporary file is created in the same directory so that the final rename
    is atomic on the host filesystem.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    directory = path.parent
    fd, temp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=directory)
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        if path.exists():
            backup = path.with_suffix(path.suffix + _BACKUP_SUFFIX)
            try:
                if backup.exists():
                    backup.unlink()
                path.replace(backup)
            except OSError as exc:
                _logger.warning("Unable to rotate settings backup: %s", exc)
        temp_path.replace(path)
    except Exception:
        # Best-effort cleanup of the temporary file; the original file is
        # untouched at this point unless a partial replace occurred, which
        # the OS guarantees not to happen for a rename within a directory.
        if temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass
        raise


def _migrate(raw: dict[str, Any], from_version: int) -> dict[str, Any]:
    """Return ``raw`` upgraded to the current schema version.

    Migration is intentionally conservative: only transformations that are
    strictly required to reach the current schema are performed. Unknown
    fields are preserved so that Pydantic can surface an informative error
    rather than silently discarding user data.

    Currently no migrations are required because the schema version is 1.
    The function is defined here so that future versions extend a single
    well-tested location rather than scattering migration logic.
    """
    if from_version == SETTINGS_SCHEMA_VERSION:
        return raw
    if from_version < 1:
        raise SettingsError(f"Unsupported settings schema version: {from_version}")
    # Future migrations are applied here in ascending order:
    #   if from_version < 2: raw = _migrate_v1_to_v2(raw)
    #   if from_version < 3: raw = _migrate_v2_to_v3(raw)
    #   ...
    return raw


def _serialize(settings: SettingsSchema) -> str:
    """Serialize ``settings`` to a TOML document."""
    data = settings.model_dump(mode="json")
    # ``tomli_w`` requires a plain dictionary and cannot serialize ``None``.
    # Null values are therefore dropped before writing.
    cleaned = _strip_none(data)
    return tomli_w.dumps(cleaned)


def _strip_none(value: Any) -> Any:
    """Recursively remove ``None`` values from nested dictionaries."""
    if isinstance(value, dict):
        return {key: _strip_none(item) for key, item in value.items() if item is not None}
    if isinstance(value, list):
        return [_strip_none(item) for item in value]
    return value


class SettingsService:
    """Loads, mutates, and persists the application configuration."""

    def __init__(self, config_path: Path) -> None:
        self._path = config_path
        self._lock = threading.RLock()
        self._settings: SettingsSchema | None = None
        self._observers: list[_OBSERVER] = []

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------
    @property
    def path(self) -> Path:
        return self._path

    @property
    def settings(self) -> SettingsSchema:
        """Return the current settings, loading them if necessary."""
        with self._lock:
            if self._settings is None:
                self.load()
            assert self._settings is not None
            return self._settings

    # ------------------------------------------------------------------
    # Observers
    # ------------------------------------------------------------------
    def add_observer(self, observer: _OBSERVER) -> None:
        """Register a callback invoked after each successful save."""
        with self._lock:
            self._observers.append(observer)

    def remove_observer(self, observer: _OBSERVER) -> None:
        """Remove a previously registered observer. No-op if absent."""
        with self._lock:
            if observer in self._observers:
                self._observers.remove(observer)

    # ------------------------------------------------------------------
    # Loading and saving
    # ------------------------------------------------------------------
    def load(self) -> SettingsLoadResult:
        """Load settings from disk, creating defaults when the file is absent.

        Raises
        ------
        SettingsError
            If the file exists but cannot be read, parsed, migrated, or
            validated against the current schema.
        """
        with self._lock:
            if not self._path.exists():
                defaults = SettingsSchema()
                _write_atomic(self._path, _serialize(defaults))
                self._settings = defaults
                _logger.info("Created default settings at %s", self._path)
                return SettingsLoadResult(
                    settings=defaults,
                    path=self._path,
                    created=True,
                    migrated_from=None,
                )

            try:
                with self._path.open("rb") as handle:
                    raw = tomllib.load(handle)
            except OSError as exc:
                raise SettingsError(f"Unable to read settings file {self._path}: {exc}") from exc
            except tomllib.TOMLDecodeError as exc:
                raise SettingsError(
                    f"Settings file {self._path} is not valid TOML: {exc}"
                ) from exc

            if not isinstance(raw, dict):
                raise SettingsError(
                    f"Settings file {self._path} did not parse to a table."
                )

            raw_version = raw.get("schema_version", 1)
            if not isinstance(raw_version, int) or raw_version < 1:
                raise SettingsError(
                    f"Settings file {self._path} has an invalid schema_version."
                )

            migrated_from: int | None = None
            if raw_version != SETTINGS_SCHEMA_VERSION:
                if raw_version > SETTINGS_SCHEMA_VERSION:
                    raise SettingsError(
                        f"Settings file {self._path} was written by a newer "
                        f"application version (schema {raw_version} > "
                        f"{SETTINGS_SCHEMA_VERSION})."
                    )
                raw = _migrate(raw, raw_version)
                migrated_from = raw_version

            raw["schema_version"] = SETTINGS_SCHEMA_VERSION

            try:
                validated = SettingsSchema.model_validate(raw)
            except ValidationError as exc:
                raise SettingsError(
                    f"Settings file {self._path} failed validation: {exc}"
                ) from exc

            self._settings = validated

            if migrated_from is not None:
                _write_atomic(self._path, _serialize(validated))
                _logger.info(
                    "Migrated settings from schema %d to %d",
                    migrated_from,
                    SETTINGS_SCHEMA_VERSION,
                )

            return SettingsLoadResult(
                settings=validated,
                path=self._path,
                created=False,
                migrated_from=migrated_from,
            )

    def save(self, settings: SettingsSchema | None = None) -> SettingsSchema:
        """Persist ``settings`` (or the current settings if omitted).

        The passed instance is validated again to guarantee that it conforms
        to the current schema even if it was constructed programmatically.
        Observers are notified after the file is committed.
        """
        with self._lock:
            candidate = settings or self._settings
            if candidate is None:
                candidate = SettingsSchema()

            try:
                validated = SettingsSchema.model_validate(
                    candidate.model_dump(mode="json")
                )
            except ValidationError as exc:
                raise SettingsError(f"Refusing to save invalid settings: {exc}") from exc

            _write_atomic(self._path, _serialize(validated))
            self._settings = validated
            observers = list(self._observers)

        for observer in observers:
            try:
                observer(validated)
            except Exception:  # noqa: BLE001 - observer isolation
                _logger.exception("Settings observer raised an exception")

        return validated

    def update(self, **changes: Any) -> SettingsSchema:
        """Apply top-level changes and persist.

        The keyword arguments are merged into the current settings dictionary
        at the top level. Nested sections must be provided as full section
        dictionaries; partial section updates are handled by
        ``update_section`` instead.
        """
        with self._lock:
            current = self.settings.model_dump(mode="json")
            current.update(changes)
            try:
                merged = SettingsSchema.model_validate(current)
            except ValidationError as exc:
                raise SettingsError(f"Invalid settings update: {exc}") from exc
        return self.save(merged)

    def update_section(self, section: str, **changes: Any) -> SettingsSchema:
        """Apply changes to a single named section and persist."""
        with self._lock:
            current = self.settings.model_dump(mode="json")
            if section not in current:
                raise SettingsError(f"Unknown settings section: {section}")
            section_data = dict(current[section])
            section_data.update(changes)
            current[section] = section_data
            try:
                merged = SettingsSchema.model_validate(current)
            except ValidationError as exc:
                raise SettingsError(
                    f"Invalid update for settings section {section}: {exc}"
                ) from exc
        return self.save(merged)

    def reset_to_defaults(self) -> SettingsSchema:
        """Replace the current settings with schema defaults and persist."""
        return self.save(SettingsSchema())

    def export_json_schema(self) -> dict[str, Any]:
        """Return the JSON Schema for the settings model."""
        return SettingsSchema.model_json_schema()


def load_settings(config_path: Path) -> SettingsService:
    """Construct a ``SettingsService`` and load its initial state.

    This helper centralizes the pairing of construction and initial load so
    that startup code does not need to remember to call ``load`` explicitly.
    """
    service = SettingsService(config_path)
    service.load()
    return service