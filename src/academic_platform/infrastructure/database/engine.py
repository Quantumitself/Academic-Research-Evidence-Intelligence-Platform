"""Engine and session factory wrapper.

``Database`` owns a SQLAlchemy engine, a session factory bound to the
engine, and the lifecycle of both. It exposes:

- ``session()`` — a factory context manager yielding a session within a
  transaction.
- ``session_scope()`` — an alias that is preferred at call sites for
  readability.
- ``health_check()`` — a lightweight check that the engine can execute a
  statement against the bound database.
- ``dispose()`` — releases the engine and its pool.
- ``vacuum()`` — runs ``VACUUM`` against the bound database.

Design decisions
----------------
- Sessions are created per unit of work. Long-lived sessions accumulate
  state and delay write flushes; the application uses short-lived sessions
  inside ``with database.session() as session:`` blocks.
- The session factory disables ``expire_on_commit``. The application does
  not rely on lazy attribute refresh after commit, and disabling the
  behavior prevents accidental implicit IO on detached instances.
- ``autoflush`` is enabled. Flushing before queries keeps result sets
  consistent with the in-memory unit of work.
- The engine is created with ``future=True`` so that SQLAlchemy 2.x
  semantics are used regardless of the installed minor version.
- Connection PRAGMAs are applied on every new DBAPI connection so that
  pooled or newly created connections are configured consistently.
- A ``connect`` event listener logs the first successful connection at
  INFO level and every subsequent connection at DEBUG level. No SQL text is
  logged unless ``echo`` is enabled.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool, StaticPool

from academic_platform.infrastructure.database.config import DatabaseConfiguration
from academic_platform.infrastructure.database.errors import (
    DatabaseConfigurationError,
    DatabaseError,
)
from academic_platform.application.projects.errors import ProjectError
from academic_platform.application.collections.errors import CollectionError


_logger = logging.getLogger(__name__)

_PRAGMA_BUSY_TIMEOUT = "PRAGMA busy_timeout = {value}"
_PRAGMA_JOURNAL_MODE = "PRAGMA journal_mode = {value}"
_PRAGMA_SYNCHRONOUS = "PRAGMA synchronous = {value}"
_PRAGMA_FOREIGN_KEYS = "PRAGMA foreign_keys = ON"

def _is_application_error(exc: BaseException) -> bool:
    """Return True when the exception belongs to a typed application hierarchy.

    Application errors are preserved by the session context manager so
    that callers can catch them by their declared type. Foreign errors
    (SQLAlchemy, sqlite3, ValueError, ...) are wrapped in ``DatabaseError``.
    """
    from academic_platform.infrastructure.repositories.errors import RepositoryError

    if isinstance(exc, (CollectionError, DatabaseError, ProjectError, RepositoryError)):
        return True
    return False

class Database:
    """Engine and session factory wrapper."""

    def __init__(self, configuration: DatabaseConfiguration) -> None:
        self._configuration = configuration
        self._engine = self._create_engine(configuration)
        self._session_factory = sessionmaker(
            bind=self._engine,
            autoflush=True,
            expire_on_commit=False,
            future=True,
        )
        self._connected_once = False

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------
    @classmethod
    def from_path(cls, path, **overrides) -> "Database":
        """Construct a file-backed database from a filesystem path."""
        from pathlib import Path as _Path

        resolved = _Path(path)
        resolved.parent.mkdir(parents=True, exist_ok=True)
        return cls(DatabaseConfiguration.for_file(resolved, **overrides))

    @classmethod
    def in_memory(cls, **overrides) -> "Database":
        """Construct an in-memory database. Intended for tests."""
        return cls(DatabaseConfiguration.for_memory(**overrides))

    def _create_engine(self, configuration: DatabaseConfiguration) -> Engine:
        try:
            if configuration.is_memory:
                poolclass = StaticPool
                connect_args = {"check_same_thread": False}
            else:
                poolclass = NullPool
                connect_args = {"check_same_thread": False}
            engine = create_engine(
                configuration.url,
                echo=configuration.echo,
                future=True,
                poolclass=poolclass,
                connect_args=connect_args,
            )
        except SQLAlchemyError as exc:
            raise DatabaseConfigurationError(
                f"Unable to create database engine for {configuration.url!r}: {exc}"
            ) from exc

        self._install_connection_hooks(engine, configuration)
        return engine

    def _install_connection_hooks(
        self,
        engine: Engine,
        configuration: DatabaseConfiguration,
    ) -> None:
        @event.listens_for(engine, "connect")
        def _on_connect(dbapi_connection, _connection_record) -> None:  # noqa: ANN001 - SQLAlchemy callback
            cursor = dbapi_connection.cursor()
            try:
                cursor.execute(_PRAGMA_BUSY_TIMEOUT.format(value=configuration.busy_timeout_ms))
                cursor.execute(_PRAGMA_FOREIGN_KEYS)
                cursor.execute(
                    _PRAGMA_JOURNAL_MODE.format(value=configuration.journal_mode.upper())
                )
                cursor.execute(
                    _PRAGMA_SYNCHRONOUS.format(value=configuration.synchronous.upper())
                )
            finally:
                cursor.close()
            if not self._connected_once:
                self._connected_once = True
                _logger.info(
                    "Database connection established (url=%s, memory=%s)",
                    configuration.url,
                    configuration.is_memory,
                )
            else:
                _logger.debug("Additional database connection established")

    # ------------------------------------------------------------------
    # Session API
    # ------------------------------------------------------------------
    @property
    def engine(self) -> Engine:
        """Return the underlying SQLAlchemy engine."""
        return self._engine

    @property
    def configuration(self) -> DatabaseConfiguration:
        """Return the configuration this database was constructed with."""
        return self._configuration

    @contextmanager
    def session(self) -> Iterator[Session]:
        """Yield a session within a transaction.

        The session is committed on success and rolled back on exception.
        The session is closed in all cases. Callers must not hold a
        reference to the session after the context manager exits.

        Exceptions that originate from the application's typed error
        hierarchies are re-raised unchanged; the rollback still occurs.
        Only foreign exceptions are wrapped in ``DatabaseError``.
        """
        session: Session = self._session_factory()
        try:
            yield session
            session.commit()
        except Exception as exc:
            try:
                session.rollback()
            except SQLAlchemyError:
                _logger.exception("Rollback failed after an error")
            # Application errors pass through unchanged. Everything else
            # is wrapped so that callers can depend on a single type.
            if _is_application_error(exc):
                raise
            raise DatabaseError(f"Database transaction failed: {exc}") from exc
        finally:
            session.close()

    # ``session_scope`` is an explicit alias preferred at some call sites
    # for readability. Both names refer to the same context manager.
    session_scope = session

    # ------------------------------------------------------------------
    # Diagnostics and maintenance
    # ------------------------------------------------------------------
    def health_check(self) -> bool:
        """Return True when the engine can execute a trivial statement.

        A failure is logged and reported as False. The method does not
        raise so that it can be used during startup diagnostics without a
        try/except at every call site.
        """
        try:
            with self._engine.connect() as connection:
                connection.execute(text("SELECT 1"))
        except SQLAlchemyError:
            _logger.exception("Database health check failed")
            return False
        return True

    def dispose(self) -> None:
        """Release the engine and its connection pool."""
        try:
            self._engine.dispose()
        except SQLAlchemyError:
            _logger.exception("Engine dispose raised")

    def vacuum(self) -> None:
        """Run ``VACUUM`` against the bound database.

        ``VACUUM`` reclaims space after large deletions. It is not
        applicable to in-memory databases and is skipped there. The
        statement cannot run inside a transaction; a raw connection is
        used to avoid the session's implicit transaction.
        """
        if self._configuration.is_memory:
            _logger.debug("Skipping VACUUM on in-memory database")
            return
        try:
            with self._engine.connect() as connection:
                connection.exec_driver_sql("VACUUM")
        except SQLAlchemyError as exc:
            raise DatabaseError(f"VACUUM failed: {exc}") from exc

    def analyze(self) -> None:
        """Run ``ANALYZE`` to refresh SQLite's query planner statistics."""
        try:
            with self._engine.connect() as connection:
                connection.exec_driver_sql("ANALYZE")
        except SQLAlchemyError as exc:
            raise DatabaseError(f"ANALYZE failed: {exc}") from exc

    def integrity_check(self) -> bool:
        """Run ``PRAGMA integrity_check`` and return True when the result is ``ok``.

        A non-``ok`` result indicates possible corruption; the method
        returns False and logs the reported message.
        """
        try:
            with self._engine.connect() as connection:
                result = connection.exec_driver_sql("PRAGMA integrity_check").scalar()
        except SQLAlchemyError:
            _logger.exception("Integrity check failed to execute")
            return False
        if result != "ok":
            _logger.warning("Integrity check reported: %s", result)
            return False
        return True