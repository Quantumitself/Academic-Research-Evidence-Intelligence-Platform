"""Tests for the built-in catalog installer."""

from __future__ import annotations

from academic_platform.application.search_sources.catalog import (
    BUILTIN_SOURCES,
)
from academic_platform.application.search_sources.catalog_installer import (
    CatalogInstaller,
)
from academic_platform.infrastructure.database import Database
from academic_platform.infrastructure.database.base import Base
from academic_platform.infrastructure.repositories.manager import (
    RepositoryManager,
)


def test_install_creates_all_builtins() -> None:
    database = Database.in_memory()
    try:
        Base.metadata.create_all(database.engine)
        with database.session() as session:
            repositories = RepositoryManager(session)
            from academic_platform.infrastructure.repositories.factory import (
                _REPOSITORY_REGISTRY,
            )

            repositories.register_all(dict(_REPOSITORY_REGISTRY))
            installer = CatalogInstaller(repositories)
            created, refreshed = installer.install()
            assert created == len(BUILTIN_SOURCES)
            assert refreshed == 0
    finally:
        database.dispose()


def test_install_is_idempotent() -> None:
    database = Database.in_memory()
    try:
        Base.metadata.create_all(database.engine)
        with database.session() as session:
            repositories = RepositoryManager(session)
            from academic_platform.infrastructure.repositories.factory import (
                _REPOSITORY_REGISTRY,
            )

            repositories.register_all(dict(_REPOSITORY_REGISTRY))
            installer = CatalogInstaller(repositories)
            installer.install()
        with database.session() as session:
            repositories = RepositoryManager(session)
            from academic_platform.infrastructure.repositories.factory import (
                _REPOSITORY_REGISTRY,
            )

            repositories.register_all(dict(_REPOSITORY_REGISTRY))
            installer = CatalogInstaller(repositories)
            created, refreshed = installer.install()
            assert created == 0
            assert refreshed == 0
    finally:
        database.dispose()