"""Programmatic Alembic migration runner.

The application invokes migrations at startup so that every run operates
against the schema version it expects. The runner wraps the Alembic
configuration, points it at the application's database URL, and executes
``upgrade`` to the latest revision.

Design decisions
----------------
- The runner reads the URL from ``AppDirectories`` unless the caller
  supplies one explicitly. Explicit URLs are used by tests that bind to an
  in-memory or temporary database.
- The runner does not shell out to the Alembic CLI. Alembic's Python API
  is stable and avoids the overhead of subprocess execution at startup.
- The runner records the previous and resulting revision numbers so that
  callers can log or report the transition.
- The runner is idempotent: running it on an up-to-date database reports
  the same revision as the current and previous revision.
- Failures raise ``DatabaseMigrationError`` with the underlying message
  attached.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError

from academic_platform.infrastructure.database.errors import DatabaseError

_logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[4]
_ALEMBIC_INI = _REPO_ROOT / "alembic.ini"
_MIGRATIONS_DIR = _REPO_ROOT / "migrations"


class DatabaseMigrationError(DatabaseError):
    """Raised when a migration cannot be applied or inspected."""


@dataclass(frozen=True, slots=True)
class MigrationResult:
    """Result of a migration run.

    Attributes
    ----------
    previous_revision:
        The revision the database was at before the run, or ``None`` when
        the database had never been migrated.
    current_revision:
        The revision the database is at after the run.
    head_revision:
        The head revision in the migrations directory. When
        ``previous_revision == current_revision == head_revision`` the
        database was already up to date.
    """

    previous_revision: str | None
    current_revision: str | None
    head_revision: str | None

    @property
    def changed(self) -> bool:
        """Return True when the migration run changed the database."""
        return self.previous_revision != self.current_revision

    @property
    def up_to_date(self) -> bool:
        """Return True when the database is at the current head."""
        return self.current_revision == self.head_revision


def _load_alembic_config(database_url: str) -> Config:
    if not _ALEMBIC_INI.exists():
        raise DatabaseMigrationError(f"alembic.ini not found at {_ALEMBIC_INI}")
    if not _MIGRATIONS_DIR.is_dir():
        raise DatabaseMigrationError(f"migrations directory not found at {_MIGRATIONS_DIR}")
    config = Config(str(_ALEMBIC_INI))
    config.set_main_option("script_location", str(_MIGRATIONS_DIR))
    # The URL is passed through ``Config.set_main_option`` so that the
    # environment module can read it via ``config.get_main_option``. The
    # environment also re-resolves the URL when no override is supplied.
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def _current_revision(database_url: str) -> str | None:
    engine = create_engine(database_url, future=True)
    try:
        with engine.connect() as connection:
            context = MigrationContext.configure(connection)
            return context.get_current_revision()
    except SQLAlchemyError as exc:
        raise DatabaseMigrationError(f"Unable to read current revision: {exc}") from exc
    finally:
        engine.dispose()


def _head_revision(config: Config) -> str | None:
    script = ScriptDirectory.from_config(config)
    return script.get_current_head()

def declared_head_revision() -> str:
    """Return the head revision declared in the migrations directory.

    Unlike ``head_revision``, this function does not require a database
    URL: it inspects the migrations directory only. It is the correct way
    for tests and diagnostics to learn the current head without
    connecting to a database.

    The function delegates to Alembic's ``ScriptDirectory`` so that the
    head is always the same value Alembic itself would compute.
    """
    if not _ALEMBIC_INI.exists():
        raise DatabaseMigrationError(f"alembic.ini not found at {_ALEMBIC_INI}")
    if not _MIGRATIONS_DIR.is_dir():
        raise DatabaseMigrationError(
            f"migrations directory not found at {_MIGRATIONS_DIR}"
        )
    config = Config(str(_ALEMBIC_INI))
    config.set_main_option("script_location", str(_MIGRATIONS_DIR))
    script = ScriptDirectory.from_config(config)
    head = script.get_current_head()
    if head is None:
        raise DatabaseMigrationError("No migration head found")
    return head

def upgrade_to_head(database_url: str) -> MigrationResult:
    """Upgrade the database to the latest revision.

    Parameters
    ----------
    database_url:
        SQLAlchemy URL of the database to migrate.

    Returns
    -------
    MigrationResult
        The transition applied.
    """
    config = _load_alembic_config(database_url)
    previous = _current_revision(database_url)
    head = _head_revision(config)

    if previous == head and head is not None:
        _logger.info("Database already at head revision %s", head)
        return MigrationResult(
            previous_revision=previous,
            current_revision=previous,
            head_revision=head,
        )

    try:
        command.upgrade(config, "head")
    except Exception as exc:  # noqa: BLE001 - Alembic raises a variety of types
        raise DatabaseMigrationError(f"Migration failed: {exc}") from exc

    current = _current_revision(database_url)
    _logger.info(
        "Database migrated from %s to %s (head=%s)",
        previous,
        current,
        head,
    )
    return MigrationResult(
        previous_revision=previous,
        current_revision=current,
        head_revision=head,
    )


def downgrade(database_url: str, revision: str) -> MigrationResult:
    """Downgrade the database to the named revision.

    The target may be a revision identifier or ``"base"`` to revert every
    migration.
    """
    config = _load_alembic_config(database_url)
    previous = _current_revision(database_url)
    head = _head_revision(config)

    try:
        command.downgrade(config, revision)
    except Exception as exc:  # noqa: BLE001 - Alembic raises a variety of types
        raise DatabaseMigrationError(f"Downgrade failed: {exc}") from exc

    current = _current_revision(database_url)
    _logger.info("Database downgraded from %s to %s", previous, current)
    return MigrationResult(
        previous_revision=previous,
        current_revision=current,
        head_revision=head,
    )


def current_revision(database_url: str) -> str | None:
    """Return the current revision of the database, or ``None`` if unmigrated."""
    return _current_revision(database_url)


def head_revision(database_url: str) -> str | None:
    """Return the head revision declared in the migrations directory."""
    config = _load_alembic_config(database_url)
    return _head_revision(config)

def declared_head_revision() -> str:
    """Return the head revision declared in the migrations directory.

    Unlike ``head_revision``, this function does not require a database
    URL: it inspects the migrations directory only. It is the correct way
    for tests and diagnostics to learn the current head without
    connecting to a database.

    The function delegates to Alembic's ``ScriptDirectory`` so that the
    head is always the same value Alembic itself would compute.
    """
    if not _ALEMBIC_INI.exists():
        raise DatabaseMigrationError(f"alembic.ini not found at {_ALEMBIC_INI}")
    if not _MIGRATIONS_DIR.is_dir():
        raise DatabaseMigrationError(
            f"migrations directory not found at {_MIGRATIONS_DIR}"
        )
    config = Config(str(_ALEMBIC_INI))
    config.set_main_option("script_location", str(_MIGRATIONS_DIR))
    script = ScriptDirectory.from_config(config)
    head = script.get_current_head()
    if head is None:
        raise DatabaseMigrationError("No migration head found")
    return head