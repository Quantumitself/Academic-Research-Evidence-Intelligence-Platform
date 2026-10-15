"""Application bootstrap.

This module is intentionally the only place in the codebase that constructs
the top-level UI. It is not imported by ``academic_platform.main`` until the
process has decided to launch the graphical interface, which keeps headless
operations (audit, inventory) independent of PySide6.

Startup order
-------------
1. Runtime directories are resolved by ``academic_platform.main``.
2. Logging is configured by ``academic_platform.main``.
3. The settings service loads and validates the configuration file.
4. The Qt application is constructed and the stylesheet is applied.
5. The main window is constructed with the resolved directories and the
   settings service, then shown.
6. The Qt event loop is entered.

A failure during settings loading is reported before any window is shown so
that the user receives a clear diagnostic instead of a partial interface.
"""

from __future__ import annotations

import logging
import sys

from academic_platform.app.configuration import AppDirectories
from academic_platform.app.settings import SettingsError, SettingsService
from academic_platform.application.search_sources import SearchSourceService
from academic_platform.application.search_sources.catalog_installer import (
    CatalogInstaller,
)
from academic_platform.application.settings_persistence import (
    SettingsPersistenceBridge,
    SettingsPersistenceError,
)
from academic_platform.infrastructure.database import Database, DatabaseError
from academic_platform.infrastructure.database.migrations import (
    DatabaseMigrationError,
    upgrade_to_head,
)
from academic_platform.infrastructure.repositories.factory import unit_of_work
from academic_platform.infrastructure.search_providers.registry import (
    default_registry as default_provider_registry,
)
from academic_platform.ui.notifications import NotificationHost, NotificationService


_logger = logging.getLogger(__name__)

APP_NAME = "Academic Research Platform"
ORGANIZATION_NAME = "Academic Platform"
ORGANIZATION_DOMAIN = "academic-platform.local"

EXIT_SETTINGS_ERROR = 4
EXIT_DATABASE_ERROR = 5
EXIT_MIGRATION_ERROR = 6
EXIT_SETTINGS_PERSISTENCE_ERROR = 7
EXIT_SEARCH_SERVICE_ERROR = 8


def _load_settings_or_report(directories: AppDirectories) -> SettingsService | None:
    service = SettingsService(directories.config_file)
    try:
        result = service.load()
    except SettingsError as exc:
        _logger.error("Settings loading failed: %s", exc)
        print(f"Configuration error: {exc}", file=sys.stderr)
        print(
            "The application cannot start with an invalid configuration file. "
            f"Review or remove {directories.config_file} and try again.",
            file=sys.stderr,
        )
        return None
    if result.created:
        _logger.info("Created default configuration at %s", result.path)
    elif result.migrated_from is not None:
        _logger.info(
            "Configuration migrated from schema %d to %d",
            result.migrated_from,
            result.settings.schema_version,
        )
    return service


def _reconcile_settings_or_report(
    settings_service: SettingsService,
    database: Database,
) -> bool:
    """Reconcile the settings file with the database settings row.

    Returns False when reconciliation fails; the failure is reported
    before any UI is constructed.
    """
    try:
        with unit_of_work(database) as repositories:
            bridge = SettingsPersistenceBridge(
                settings_service=settings_service,
                app_settings_repository=repositories.get("app_settings"),
                user_profile_repository=repositories.get("user_profile"),
            )
            row = bridge.synchronize()
            active_user = row.active_user_key
    except SettingsPersistenceError as exc:
        _logger.error("Settings persistence reconciliation failed: %s", exc)
        print(f"Settings persistence error: {exc}", file=sys.stderr)
        return False
    if active_user is None:
        _logger.info("No active user profile selected")
    else:
        _logger.info("Active user profile: %s", active_user)
    return True


def _install_catalog_or_report(database: Database, registry) -> None:
    """Install the built-in search source catalog.

    Failures are logged and reported on stderr but do not prevent the
    application from starting. The search page falls back to the null
    adapter when the catalog is unavailable.
    """
    try:
        with unit_of_work(database) as repositories:
            installer = CatalogInstaller(repositories)
            created, refreshed = installer.install()
            _logger.info(
                "Search source catalog: %d created, %d refreshed",
                created,
                refreshed,
            )
    except Exception as exc:  # noqa: BLE001 - boundary
        _logger.exception("Search source catalog installation failed")
        print(f"Search source catalog warning: {exc}", file=sys.stderr)


class _PerCallRepositoryManager:
    """A repository manager facade that opens a fresh session per call.

    The ``SearchSourceService`` receives an object that behaves like a
    ``RepositoryManager`` but constructs its repositories against a
    short-lived session. The context manager returned by the factory is
    entered on every access and closed when the call completes.

    This is deliberately a small adapter rather than a change to the
    repository layer. The repository layer's contract remains: one
    manager per unit of work. The adapter provides the unit of work on
    demand.
    """

    def __init__(self, database: Database) -> None:
        self._database = database
        self._active: list = []

    def get(self, key: str):
        from academic_platform.infrastructure.repositories.factory import (
            _REPOSITORY_REGISTRY,
        )

        session = self._database._session_factory()  # noqa: SLF001 - adapter shim
        self._active.append(session)
        repository_class = _REPOSITORY_REGISTRY.get(key)
        if repository_class is None:
            from academic_platform.infrastructure.repositories.errors import (
                RepositoryError,
            )

            raise RepositoryError(f"No repository registered under key {key!r}")
        return repository_class(session)

    def close_all(self) -> None:
        for session in self._active:
            try:
                session.commit()
            except Exception:  # noqa: BLE001 - boundary
                session.rollback()
            finally:
                session.close()
        self._active.clear()


def _build_search_source_service(
    database: Database,
    settings_service: SettingsService,
) -> SearchSourceService | None:
    """Construct the search source service for the application.

    The service is constructed with a per-request repository manager.
    The manager is created inside a unit of work; the service opens a
    unit of work per call through the same factory so that its
    repositories are always bound to a live session.
    """
    from academic_platform.infrastructure.search_providers.registry import (
        default_registry,
    )

    try:
        with unit_of_work(database) as repositories:
            _ = repositories.get("search_source")
    except Exception as exc:  # noqa: BLE001 - boundary
        _logger.error("Unable to open the search source repository: %s", exc)
        print(f"Search source service error: {exc}", file=sys.stderr)
        return None

    _ = settings_service  # Reserved for a future network-policy setting.

    service = SearchSourceService(
        repositories=_PerCallRepositoryManager(database),
        registry=default_registry(),
        allow_http=False,
        allow_loopback=False,
    )
    return service


def _open_database_or_report(directories: AppDirectories) -> Database | None:
    """Open the application database, reporting failures before any UI is shown."""
    try:
        database = Database.from_path(directories.database_file)
    except DatabaseError as exc:
        _logger.error("Database initialization failed: %s", exc)
        print(f"Database error: {exc}", file=sys.stderr)
        return None
    return database


def _migrate_or_report(database_url: str) -> bool:
    """Apply migrations to the latest revision, reporting failures."""
    try:
        result = upgrade_to_head(database_url)
    except DatabaseMigrationError as exc:
        _logger.error("Database migration failed: %s", exc)
        print(f"Database migration error: {exc}", file=sys.stderr)
        return False
    if result.changed:
        _logger.info(
            "Database migrated from %s to %s",
            result.previous_revision or "<none>",
            result.current_revision or "<none>",
        )
    return True


def run_application(directories: AppDirectories) -> int:
    try:
        from PySide6.QtWidgets import QApplication
    except ImportError as exc:  # pragma: no cover - environment dependent
        _logger.error("PySide6 is not available: %s", exc)
        print(
            "PySide6 is required to start the graphical interface. "
            "Install project dependencies with: python -m pip install -e .",
            file=sys.stderr,
        )
        return 3

    settings_service = _load_settings_or_report(directories)
    if settings_service is None:
        return EXIT_SETTINGS_ERROR

    database = _open_database_or_report(directories)
    if database is None:
        return EXIT_DATABASE_ERROR

    if not _migrate_or_report(database.configuration.url):
        database.dispose()
        return EXIT_MIGRATION_ERROR

    if not database.health_check():
        print(
            "The database could not be opened. Check the log for details.",
            file=sys.stderr,
        )
        database.dispose()
        return EXIT_DATABASE_ERROR

    if not _reconcile_settings_or_report(settings_service, database):
        database.dispose()
        return EXIT_SETTINGS_PERSISTENCE_ERROR

    _install_catalog_or_report(database, default_provider_registry())

    from academic_platform.ui.main_window import MainWindow

    application = QApplication.instance()
    if application is None:
        application = QApplication(sys.argv)
    application.setApplicationName(APP_NAME)
    application.setOrganizationName(ORGANIZATION_NAME)
    application.setOrganizationDomain(ORGANIZATION_DOMAIN)

    window = MainWindow(
        directories=directories,
        settings_service=settings_service,
        database=database,
    )

    notification_service = NotificationService(max_size=5)
    window.attach_notification_service(notification_service)
    NotificationHost(parent=window, service=notification_service)

    window.show()

    _logger.info("Application window displayed")
    exit_code = application.exec()
    database.dispose()
    return exit_code