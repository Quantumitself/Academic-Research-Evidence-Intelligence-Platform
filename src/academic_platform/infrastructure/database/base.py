"""Declarative base and shared mixins.

Every ORM model in the application inherits from ``Base``. The base
provides:

- A naming convention for constraints so that migrations produce stable
  identifiers.
- A ``metadata`` object that Alembic's environment imports for
  autogeneration.
- Shared mixins for the behavior that every model requires: identity,
  timestamps, and versioning.

Design decisions
----------------
- The naming convention is applied through the metadata so that every
  constraint produced by the ORM has a deterministic name. SQLite does
  not require this, but stable names make migrations readable and
  reversible.
- Primary keys are integer ``id`` columns with autoincrement. Integer
  identifiers are compact, fast to index, and sufficient for a
  single-user desktop application. External systems that require opaque
  identifiers are given a separate ``uuid`` column where relevant; that
  column is introduced per model rather than forced on every table.
- Timestamps are stored as naive UTC ``datetime`` values. SQLite has no
  native timestamp type; using ``DateTime`` with naive UTC values avoids
  ambiguity across platforms.
- The ``version`` mixin exists for optimistic concurrency control on
  models that are edited by the user. It is opt-in per model.
- FTS5 virtual tables are not ORM models and are not registered on
  ``Base.metadata``. SQLAlchemy's ``Table`` construct does not support
  virtual tables; they are created with raw DDL. ``ensure_fts_tables``
  is the single entry point for creating them.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from sqlalchemy import DateTime, Integer, MetaData, event
from sqlalchemy.orm import DeclarativeBase, Mapped, declared_attr, mapped_column

# Naming convention applied to every constraint and index produced by the
# ORM. The tokens are SQLAlchemy placeholders; the convention yields stable
# names such as ``pk_app_settings`` and ``ix_app_settings_key``.
NAMING_CONVENTION: dict[str, str] = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Declarative base for every ORM model in the application."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)

    def to_dict(self) -> dict[str, Any]:
        """Return a plain dictionary of the model's loaded column values.

        Relationships are not included. The method is intended for
        diagnostics and logging, not for serialization; use the
        corresponding Pydantic schema for boundary serialization.
        """
        return {
            column.name: getattr(self, column.name)
            for column in self.__table__.columns
        }

    def __repr__(self) -> str:
        identifier = getattr(self, "id", None)
        return f"<{type(self).__name__} id={identifier!r}>"


class TimestampMixin:
    """Adds ``created_at`` and ``updated_at`` columns to a model.

    Both columns are timezone-naive UTC. ``created_at`` is set once on
    insert; ``updated_at`` is set on insert and refreshed on every update.
    """

    @declared_attr.directive
    def created_at(cls) -> Mapped[dt.datetime]:  # noqa: N805 - SQLAlchemy directive
        return mapped_column(
            DateTime,
            nullable=False,
            default=lambda: dt.datetime.now(dt.timezone.utc).replace(tzinfo=None),
            doc="UTC timestamp when the row was created.",
        )

    @declared_attr.directive
    def updated_at(cls) -> Mapped[dt.datetime]:  # noqa: N805 - SQLAlchemy directive
        return mapped_column(
            DateTime,
            nullable=False,
            default=lambda: dt.datetime.now(dt.timezone.utc).replace(tzinfo=None),
            onupdate=lambda: dt.datetime.now(dt.timezone.utc).replace(tzinfo=None),
            doc="UTC timestamp of the last update.",
        )


class VersionMixin:
    """Adds an integer ``version`` column for optimistic concurrency.

    The column starts at 1 and is incremented by SQLAlchemy on update
    through the ``onupdate`` callback. Callers that need to detect
    concurrent modification compare the loaded version with the version
    in the database before saving.
    """

    @declared_attr.directive
    def version(cls) -> Mapped[int]:  # noqa: N805 - SQLAlchemy directive
        return mapped_column(
            Integer,
            nullable=False,
            default=1,
            server_default="1",
            doc="Monotonically increasing version counter.",
        )


#: Module-level alias for the metadata object so that Alembic's
#: environment can import it directly. The alias refers to the same
#: ``MetaData`` instance as ``Base.metadata``; mutating one mutates the
#: other.
metadata = Base.metadata


# Import models for their side effect of registering tables on
# ``Base.metadata``. The import is deferred to the end of the module to
# avoid a circular import: models import ``Base`` from this module.
def _register_models() -> None:
    """Import every model module so that tables are registered.

    The import has no other effect. It is guarded against repeated
    execution and against environments in which the models package is not
    yet present.
    """
    try:
        from academic_platform.infrastructure.database import models  # noqa: F401
    except ImportError:
        # Models are optional at this stage. If the package is absent the
        # metadata simply contains no tables, which is valid for a
        # baseline migration environment.
        return


_register_models()

from sqlalchemy import event


@event.listens_for(Base.metadata, "after_create")
def _create_fts_tables_after_metadata_create(target, connection, **kw) -> None:
    """Create the FTS5 virtual tables whenever ``Base.metadata`` is created.

    ``Base.metadata.create_all(engine)`` emits ordinary ``CREATE TABLE``
    statements for the ORM models. FTS5 virtual tables are not ORM
    models and are not registered on the metadata, so they must be
    created separately. This listener runs after the ordinary tables
    are created and issues the FTS5 ``CREATE VIRTUAL TABLE`` statements
    on the same connection.
    """
    from academic_platform.infrastructure.database.models import fts as _fts

    for table_name, columns in (
        (_fts.FTS_DOCUMENTS_TABLE, _fts.FTS_DOCUMENTS_COLUMNS),
        (_fts.FTS_PUBLICATIONS_TABLE, _fts.FTS_PUBLICATIONS_COLUMNS),
        (_fts.FTS_NOTES_TABLE, _fts.FTS_NOTES_COLUMNS),
    ):
        column_definitions = ", ".join(f'"{column}"' for column in columns)
        statement = (
            f'CREATE VIRTUAL TABLE IF NOT EXISTS "{table_name}" '
            f"USING fts5({column_definitions});"
        )
        connection.exec_driver_sql(statement)

# ----------------------------------------------------------------------
# FTS5 virtual tables
# ----------------------------------------------------------------------
def _create_fts_tables(connection) -> None:
    """Create every FTS5 virtual table on the given connection.

    FTS5 tables cannot be declared through SQLAlchemy's ``Table``
    construct; they require raw ``CREATE VIRTUAL TABLE`` DDL. The
    function is idempotent: each table is created only when it does not
    already exist.

    Parameters
    ----------
    connection:
        A SQLAlchemy connection. The function uses ``exec_driver_sql``
        so that the DDL is emitted verbatim.
    """
    from academic_platform.infrastructure.database.models import fts as _fts

    for table_name, columns in (
        (_fts.FTS_DOCUMENTS_TABLE, _fts.FTS_DOCUMENTS_COLUMNS),
        (_fts.FTS_PUBLICATIONS_TABLE, _fts.FTS_PUBLICATIONS_COLUMNS),
        (_fts.FTS_NOTES_TABLE, _fts.FTS_NOTES_COLUMNS),
    ):
        column_definitions = ", ".join(f'"{column}"' for column in columns)
        statement = (
            f'CREATE VIRTUAL TABLE IF NOT EXISTS "{table_name}" '
            f"USING fts5({column_definitions});"
        )
        connection.exec_driver_sql(statement)


def ensure_fts_tables(engine) -> None:
    """Create the FTS5 virtual tables on the given engine.

    Callers invoke this after ``Base.metadata.create_all`` so that the
    virtual tables exist alongside the ordinary tables. The function is
    idempotent.
    """
    with engine.begin() as connection:
        _create_fts_tables(connection)