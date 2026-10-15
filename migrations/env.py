"""Alembic environment.

The environment is constructed programmatically rather than through the
Alembic CLI. The database URL is read from the application's runtime
configuration so that migrations always target the same database as the
running application. The ``alembic.ini`` file intentionally leaves
``sqlalchemy.url`` blank; setting it there would create a second source of
truth.

Design decisions
----------------
- The URL is resolved once per migration run through
  ``resolve_database_url``. If an override is supplied (for example when a
  test constructs an in-memory database), the override takes precedence.
- ``target_metadata`` is imported lazily from
  ``academic_platform.infrastructure.database.base``. The base module is
  introduced in a subsequent phase; the import is guarded so that this
  environment is usable before any models exist.
- ``compare_type`` and ``compare_server_default`` are enabled so that
  autogenerate detects type and default changes as well as additions and
  removals.
- ``render_as_batch`` is enabled because SQLite does not support most
  ``ALTER TABLE`` operations. Batch mode rewrites the table inside a
  transaction, which SQLite does support.
- Offline mode is supported for reproducibility. Offline mode emits the
  SQL that would be executed without connecting to the database.
"""

from __future__ import annotations

import logging
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

from academic_platform.app.configuration import AppDirectories, load_runtime_directories

_logger = logging.getLogger("alembic.env")

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def resolve_database_url(override: str | None = None) -> str:
    """Return the database URL to migrate.

    Precedence: the explicit override, then the URL set on the Alembic
    configuration (via ``config.set_main_option``), then the URL derived
    from the runtime directories.
    """
    if override:
        return override
    configured = config.get_main_option("sqlalchemy.url")
    if configured:
        return configured
    directories: AppDirectories = load_runtime_directories()
    path = directories.database_file
    path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{path.as_posix()}"


def _load_target_metadata():
    """Return the SQLAlchemy ``MetaData`` object holding the schema.

    The base module is introduced in a subsequent phase. Until it exists,
    this function returns ``None`` so that the migration environment is
    usable for the baseline revision. Once the base module is present, it
    is imported and its ``metadata`` attribute is returned.
    """
    try:
        from academic_platform.infrastructure.database.base import metadata
    except ImportError:
        _logger.info("Database base module not present; using None as target metadata")
        return None
    return metadata


target_metadata = _load_target_metadata()


def run_migrations_offline() -> None:
    """Run migrations in offline mode.

    Offline mode writes the SQL statements that would be executed to the
    configured output. It does not connect to the database, which makes it
    suitable for review and for generating migration scripts to inspect.
    """
    url = resolve_database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against a live database connection."""
    url = resolve_database_url()
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = url

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        future=True,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
            render_as_batch=True,
        )
        with context.begin_transaction():
            context.run_migrations()

    connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()