"""Configuration for the database engine.

A single ``DatabaseConfiguration`` value object describes how the engine
is bound. The configuration is immutable so that it can be shared safely
across threads and so that accidental mutation cannot desynchronize the
engine from its declared behavior.

Design decisions
----------------
- SQLite is the only supported URL scheme at this stage of the project. The
  configuration validates the scheme and refuses unknown schemes rather than
  silently constructing an engine that will fail later.
- The connection pool uses ``NullPool`` for file-backed databases. SQLite
  serializes writes at the file level and does not benefit from a
  connection pool; ``NullPool`` avoids keeping idle connections alive and
  reduces the risk of lock contention during long analysis runs.
- For in-memory databases the pool is ``StaticPool`` because every
  connection must share the same in-memory instance; otherwise each new
  connection would create an empty database.
- ``echo`` is off by default. Diagnostics may enable it for troubleshooting
  through the ``echo`` field; the flag is not read from user settings.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from academic_platform.infrastructure.database.errors import DatabaseConfigurationError

_SUPPORTED_SCHEMES: frozenset[str] = frozenset({"sqlite"})


@dataclass(frozen=True, slots=True)
class DatabaseConfiguration:
    """Immutable configuration for the database engine.

    Attributes
    ----------
    url:
        SQLAlchemy database URL. Must use the ``sqlite`` scheme. File
        URLs use ``sqlite:///absolute/path``; in-memory URLs use
        ``sqlite://`` or ``sqlite:///:memory:``.
    echo:
        When True, SQLAlchemy logs every statement to the ``sqlalchemy.engine``
        logger. Disabled by default and never enabled outside of
        diagnostics.
    busy_timeout_ms:
        Value applied to the SQLite ``busy_timeout`` PRAGMA. A longer
        timeout lets a writer wait instead of failing immediately when a
        reader holds a lock.
    journal_mode:
        Value applied to the SQLite ``journal_mode`` PRAGMA. ``WAL``
        improves concurrency for the read-heavy workloads the application
        performs. ``MEMORY`` is used for in-memory databases where WAL is
        not supported.
    synchronous:
        Value applied to the SQLite ``synchronous`` PRAGMA. ``NORMAL`` is
        the recommended setting when WAL is enabled: it is durable across
        application crashes but may lose the last transaction on a power
        failure. ``FULL`` is available for callers that require the
        stronger guarantee.
    """

    url: str
    echo: bool = False
    busy_timeout_ms: int = 5000
    journal_mode: str = "WAL"
    synchronous: str = "NORMAL"

    def __post_init__(self) -> None:
        if not self.url:
            raise DatabaseConfigurationError("Database URL must not be empty")
        scheme = self.url.split(":", 1)[0].lower()
        if scheme not in _SUPPORTED_SCHEMES:
            raise DatabaseConfigurationError(
                f"Unsupported database scheme {scheme!r}; "
                f"expected one of {sorted(_SUPPORTED_SCHEMES)}"
            )
        if self.busy_timeout_ms <= 0:
            raise DatabaseConfigurationError("busy_timeout_ms must be positive")
        if self.journal_mode.upper() not in {"WAL", "DELETE", "TRUNCATE", "PERSIST", "MEMORY", "OFF"}:
            raise DatabaseConfigurationError(
                f"Unsupported journal_mode {self.journal_mode!r}"
            )
        if self.synchronous.upper() not in {"OFF", "NORMAL", "FULL", "EXTRA"}:
            raise DatabaseConfigurationError(
                f"Unsupported synchronous mode {self.synchronous!r}"
            )

    # ------------------------------------------------------------------
    # Convenience constructors
    # ------------------------------------------------------------------
    @classmethod
    def for_file(cls, path: Path, **overrides) -> "DatabaseConfiguration":
        """Return a configuration bound to a file-backed SQLite database.

        The parent directory is not created here; the caller is expected
        to have created it. The URL is absolute so that the engine does not
        depend on the process working directory.
        """
        absolute = path.expanduser().resolve()
        url = f"sqlite:///{absolute.as_posix()}"
        return cls(url=url, **overrides)

    @classmethod
    def for_memory(cls, **overrides) -> "DatabaseConfiguration":
        """Return a configuration bound to an in-memory SQLite database.

        In-memory databases do not support WAL; the journal mode is forced
        to ``MEMORY`` so that the PRAGMA succeeds.
        """
        overrides.setdefault("journal_mode", "MEMORY")
        return cls(url="sqlite://", **overrides)

    # ------------------------------------------------------------------
    # Derived properties
    # ------------------------------------------------------------------
    @property
    def is_memory(self) -> bool:
        """Return True when the configuration targets an in-memory database."""
        return self.url in {"sqlite://", "sqlite:///:memory:"} or self.url.endswith(
            "/:memory:"
        )

    @property
    def database_path(self) -> Path | None:
        """Return the filesystem path of a file-backed database.

        Returns None for in-memory configurations.
        """
        if self.is_memory:
            return None
        prefix = "sqlite:///"
        if not self.url.startswith(prefix):
            return None
        raw = self.url[len(prefix):]
        return Path(raw)