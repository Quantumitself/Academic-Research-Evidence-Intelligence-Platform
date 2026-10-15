"""Repository manager.

``RepositoryManager`` constructs repositories bound to a session. It is
the single point from which the application layer obtains a repository
for the duration of a unit of work. The manager is created per unit of
work; it does not cache repositories across sessions.

Design decisions
----------------
- The manager holds a session and a registry of repository classes.
  Repositories are constructed lazily on first request and cached for the
  lifetime of the manager.
- The manager does not commit. Commit and rollback are the caller's
  responsibility through ``Database.session()``.
- The manager is generic over the session type so that tests can supply a
  session backed by an in-memory database without special cases.
- Registering a repository class with a duplicate key replaces the
  previous registration. This is intentional: tests may register a stub
  that shadows a production repository for the duration of the test.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from academic_platform.infrastructure.repositories.base import Repository
from academic_platform.infrastructure.repositories.errors import RepositoryError

_logger = logging.getLogger(__name__)


class RepositoryManager:
    """Constructs and caches repositories for a single session."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._registry: dict[str, type[Repository[Any]]] = {}
        self._instances: dict[str, Repository[Any]] = {}

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------
    def register(self, key: str, repository_class: type[Repository[Any]]) -> None:
        """Register a repository class under a stable key."""
        self._registry[key] = repository_class
        # Invalidate any cached instance for the key so that the new class
        # takes effect immediately.
        self._instances.pop(key, None)

    def register_all(self, mapping: dict[str, type[Repository[Any]]]) -> None:
        """Register multiple repository classes at once."""
        for key, repository_class in mapping.items():
            self.register(key, repository_class)

    # ------------------------------------------------------------------
    # Access
    # ------------------------------------------------------------------
    def get(self, key: str) -> Repository[Any]:
        """Return the repository registered under ``key``.

        The repository is constructed on first request and cached.

        Raises
        ------
        RepositoryError
            If no repository is registered under the key.
        """
        instance = self._instances.get(key)
        if instance is not None:
            return instance
        repository_class = self._registry.get(key)
        if repository_class is None:
            raise RepositoryError(f"No repository registered under key {key!r}")
        instance = repository_class(self._session)
        self._instances[key] = instance
        return instance

    def registered_keys(self) -> tuple[str, ...]:
        """Return the sorted keys of every registered repository."""
        return tuple(sorted(self._registry.keys()))

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def clear_cache(self) -> None:
        """Drop cached repository instances.

        The registry is preserved. Subsequent ``get`` calls construct new
        instances bound to the same session.
        """
        self._instances.clear()

    @property
    def session(self) -> Session:
        """Return the session every repository in this manager is bound to."""
        return self._session