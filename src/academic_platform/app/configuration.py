"""Runtime directory resolution.

Design decisions
----------------
- All directories are resolved once at startup and passed explicitly through
  the application. No module re-derives paths from environment variables.
- Windows uses ``%APPDATA%`` for config and data, which respects the
  roaming versus non-roaming semantics of the platform.
- An optional ``ACADEMIC_PLATFORM_HOME`` environment variable relocates the
  entire tree, which is required for portable installs and automated tests.
- Directories are created eagerly. A failure to create a directory is a
  hard startup error, because the application cannot operate without
  storage.
- The configuration file name is centralized here so that later phases
  resolve it through a single function rather than hard-coding the name.

The persistent application settings themselves are managed by
``academic_platform.app.settings``. This module only resolves where the
settings file lives.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

APP_DIRECTORY_NAME = "AcademicResearchPlatform"
APP_CONFIG_FILENAME = "config.toml"
ENV_HOME = "ACADEMIC_PLATFORM_HOME"


class ConfigurationError(RuntimeError):
    """Raised when runtime directories cannot be resolved or created."""


@dataclass(frozen=True, slots=True)
class AppDirectories:
    """Absolute paths used throughout the application."""

    root: Path
    config_dir: Path
    data_dir: Path
    logs_dir: Path
    cache_dir: Path

    @property
    def config_file(self) -> Path:
        """Path to the primary application configuration file."""
        return self.config_dir / APP_CONFIG_FILENAME

    @property
    def database_file(self) -> Path:
        """Path to the primary SQLite database file."""
        return self.data_dir / "academic_platform.sqlite3"

    @property
    def managed_library_dir(self) -> Path:
        """Directory for managed document copies."""
        return self.data_dir / "library"

    @property
    def exports_dir(self) -> Path:
        """Directory for user-generated exports."""
        return self.data_dir / "exports"


def _platform_root() -> Path:
    """Return the platform-appropriate application root directory."""
    override = os.environ.get(ENV_HOME)
    if override:
        return Path(override).expanduser().resolve()

    home = Path.home()
    if sys.platform.startswith("win"):
        base = os.environ.get("APPDATA")
        if base:
            return (Path(base) / APP_DIRECTORY_NAME).resolve()
        return (home / "AppData" / "Roaming" / APP_DIRECTORY_NAME).resolve()
    if sys.platform == "darwin":
        return (home / "Library" / "Application Support" / APP_DIRECTORY_NAME).resolve()
    base = os.environ.get("XDG_CONFIG_HOME")
    if base:
        return (Path(base) / APP_DIRECTORY_NAME).resolve()
    return (home / ".config" / APP_DIRECTORY_NAME).resolve()


def _ensure_directory(path: Path) -> None:
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise ConfigurationError(f"Unable to create directory {path}: {exc}") from exc
    if not path.is_dir():
        raise ConfigurationError(f"Path exists but is not a directory: {path}")


def load_runtime_directories() -> AppDirectories:
    """Resolve and create runtime directories.

    Returns
    -------
    AppDirectories
        Fully resolved and created directory set.

    Raises
    ------
    ConfigurationError
        If any required directory cannot be created.
    """
    root = _platform_root()
    config_dir = root / "config"
    data_dir = root / "data"
    logs_dir = root / "logs"
    cache_dir = root / "cache"

    for directory in (root, config_dir, data_dir, logs_dir, cache_dir):
        _ensure_directory(directory)

    return AppDirectories(
        root=root,
        config_dir=config_dir,
        data_dir=data_dir,
        logs_dir=logs_dir,
        cache_dir=cache_dir,
    )