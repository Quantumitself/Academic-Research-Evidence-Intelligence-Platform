"""Top-level application window.

Responsibilities
----------------
- Own the primary navigation and the page stack.
- Provide a stable frame that later phases populate with real pages.
- Present a consistent status bar and menu structure.
- Install keyboard shortcuts for navigation.
- Honour the page lifecycle contract when switching pages.
- React to appearance settings changes by re-applying the stylesheet.

This window must not implement business logic. It arranges widgets and wires
signals to the navigation controller.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QCloseEvent, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QLabel,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QStackedWidget,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from academic_platform import __version__
from academic_platform.app.configuration import AppDirectories
from academic_platform.app.settings import SettingsSchema, SettingsService
from academic_platform.application.search_orchestration import SearchOrchestrator
from academic_platform.application.search_sources import SearchSourceService
from academic_platform.application.settings_persistence import (
    SettingsPersistenceBridge,
    SettingsPersistenceError,
)
from academic_platform.infrastructure.database import Database
from academic_platform.infrastructure.repositories.factory import unit_of_work
from academic_platform.infrastructure.search_providers.registry import (
    default_registry as default_provider_registry,
)
from academic_platform.ui.main_window_destinations import DESTINATIONS
from academic_platform.ui.navigation.navigation_bar import NavigationBar
from academic_platform.ui.notifications import NotificationService
from academic_platform.ui.pages import BasePage, create_page
from academic_platform.ui.resources.styles import build_application_stylesheet
from academic_platform.application.saved_searches import SavedSearchService
from academic_platform.application.library_import import ImportCoordinator
from academic_platform.infrastructure.file_storage import (
    FileStorage,
    FileStorageConfig,
)
from academic_platform.application.deduplication.policy import DuplicatePolicy
from academic_platform.application.library_import.coordinator import (
    ImportCoordinator as _ImportCoordinator,
)
from academic_platform.application.document_extraction.service import (
    DocumentExtractionService,
)
from academic_platform.infrastructure.document_processing.ocr_config import (
    OcrConfig,
)
from academic_platform.application.library import LibraryService
from academic_platform.ui.pages.library import LibraryPage
from academic_platform.ui.pages.library.import_helper import (
    open_import_dialog,
)
from academic_platform.application.document_reading import (
    DocumentReaderService,
)
from academic_platform.ui.pages.reader import ReaderPage
from academic_platform.application.annotations import AnnotationService
from academic_platform.application.document_search import (
    DocumentSearchService,
)
from academic_platform.application.document_linking.service import (
    DocumentLinkingService,
)
from academic_platform.application.assistant_handoff import (
    AssistantHandoffService,
)
from academic_platform.application.assistant_handoff.store import (
    default_handoff_store,
)
from academic_platform.application.projects import ProjectService
from academic_platform.ui.pages.projects import ProjectsPage
from academic_platform.application.collections import CollectionService
from academic_platform.ui.pages.collections import CollectionsPage
from academic_platform.application.tasks import TaskService
from academic_platform.application.project_export import (
    ProjectExportService,
)
from academic_platform.application.topic_workspace import (
    TopicWorkspaceService,
)
from academic_platform.application.title_builder.service import (
    TitleBuilderService,
)
from academic_platform.application.research_questions.service import (
    ResearchQuestionWorkspaceService,
)
from academic_platform.application.research_history.service import (
    ResearchHistoryService,
)


_logger = logging.getLogger(__name__)

_WINDOW_TITLE = "Academic Research Platform"
_MINIMUM_SIZE = (1180, 760)


class MainWindow(QMainWindow):
    """Primary application window hosting navigation and the page stack."""

    def __init__(
        self,
        directories: AppDirectories,
        settings_service: SettingsService,
        database: Database,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._directories = directories
        self._database = database
        self._ensure_schema_at_head()
        self._settings_service = settings_service
        self._stack = QStackedWidget(self)
        self._navigation = NavigationBar(self)
        self._pages: dict[str, BasePage] = {}
        self._page_indices: dict[str, int] = {}
        self._current_identifier: str | None = None
        self._notification_service: NotificationService | None = None
        self._dashboard_data_provider: object | None = None
        self._active_user_key: str | None = None
        self._search_source_service: SearchSourceService | None = None
        self._search_orchestrator: SearchOrchestrator | None = None
        self._shortcuts: list[QShortcut] = []

        self.setWindowTitle(_WINDOW_TITLE)
        self.setMinimumSize(*_MINIMUM_SIZE)

        # Construct the source service before pages are registered so that
        # the Discover page and the Settings page can consult it during
        # construction. The service uses a per-call manager, matching the
        # orchestrator factory. Sessions are opened per call and closed by
        # the caller.
        from academic_platform.application.search_sources.service import (
            SearchSourceService as _SearchSourceService,
        )
        from academic_platform.infrastructure.search_providers.registry import (
            default_registry as _default_registry,
        )

        self._search_source_service = _SearchSourceService(
            _PerCallManager(self._database),
            _default_registry(),
        )

        self._search_orchestrator_factory = self._build_orchestrator_factory()
        self._saved_search_factory = self._build_saved_search_factory()
        self._import_coordinator_factory = self._build_import_coordinator_factory()
        self._document_extraction_factory = self._build_document_extraction_factory()
        self._library_service_factory = self._build_library_service_factory()
        self._reader_page: ReaderPage | None = None
        self._annotation_service_factory = self._build_annotation_service_factory()
        self._document_search_service_factory = (
            self._build_document_search_service_factory()
        )
        self._document_linking_service_factory = (
            self._build_document_linking_service_factory()
        )
        self._handoff_service_factory = self._build_handoff_service_factory()
        self._project_service_factory = self._build_project_service_factory()        
        self._task_service_factory = self._build_task_service_factory()
        self._project_export_service_factory = (
            self._build_project_export_service_factory()
        )
        self._topic_workspace_service_factory = (
            self._build_topic_workspace_service_factory()
        )
        self._title_builder_service_factory = (
            self._build_title_builder_service_factory()
        )
        self._question_workspace_service_factory = (
            self._build_question_workspace_service_factory()
        )
        self._history_workspace_service_factory = (
            self._build_history_workspace_service_factory()
        )
        self._collection_service_factory = self._build_collection_service_factory()
        self._reader_previous_destination: str | None = None

        self._build_menu()
        self._build_layout()
        self._register_pages()
        self._connect_signals()
        self._install_shortcuts()
        self._configure_status_bar()
        self._apply_settings(self._settings_service.settings)

        self._settings_service.add_observer(self._on_settings_changed)

        self._navigation.select("dashboard")
        self.refresh_active_user()
        _logger.info("MainWindow initialized with %d destinations", len(self._pages))

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------
    def _ensure_schema_at_head(self) -> None:
        """Ensure the database schema is at the current head revision.

        The bootstrap normally applies migrations before constructing the
        window. Tests and other callers may construct the window against
        a freshly created database whose schema has not been applied.
        Running the migration here is idempotent and cheap when the
        schema is already at head. Failures are logged and tolerated: the
        window remains constructible and individual pages report their
        own errors when they attempt to read.
        """
        try:
            from academic_platform.infrastructure.database.migrations import (
                upgrade_to_head,
            )

            url = self._database.configuration.url
            upgrade_to_head(url)
        except Exception:  # noqa: BLE001 - defensive boundary
            _logger.exception(
                "Unable to ensure the database schema is at head"
            )

    def _build_menu(self) -> None:
        menu_bar = self.menuBar()

        file_menu = menu_bar.addMenu("&File")
        quit_action = QAction("E&xit", self)
        quit_action.setShortcut(QKeySequence.StandardKey.Quit)
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        view_menu = menu_bar.addMenu("&View")
        for destination in DESTINATIONS:
            action = QAction(destination.label, self)
            if destination.shortcut:
                action.setShortcut(QKeySequence(destination.shortcut))
            action.triggered.connect(
                lambda _checked=False, key=destination.identifier: self.navigate_to(key)
            )
            view_menu.addAction(action)

        help_menu = menu_bar.addMenu("&Help")
        about_action = QAction("&About", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _build_layout(self) -> None:
        central = QWidget(self)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal, central)
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(self._navigation)
        splitter.addWidget(self._stack)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([250, 930])
        self._splitter = splitter

        outer.addWidget(splitter)
        self.setCentralWidget(central)

    def _register_pages(self) -> None:
        for destination in DESTINATIONS:
            page = create_page(
                destination=destination,
                directories=self._directories,
                settings_service=self._settings_service,
                database=self._database,
                parent=self,
            )
            self._pages[destination.identifier] = page
            index = self._stack.addWidget(page)
            self._page_indices[destination.identifier] = index
        self._wire_library_page()
        self._wire_projects_page()
        self._wire_collections_page()
        self._wire_research_assistant_page()


    def _wire_library_page(self) -> None:
        """Wire the library page to the application services and the import dialog."""
        library_page = self._pages.get("library")
        if not isinstance(library_page, LibraryPage):
            return
        # The service is constructed per call so that each operation runs
        # in its own transaction boundary.
        try:
            service = self._library_service_factory()
        except Exception:  # noqa: BLE001 - boundary
            _logger.exception("Unable to construct the library service")
            return
        library_page.attach_service(service)
        library_page.attach_import_factory(self._open_import_dialog)
        library_page.open_document_requested.connect(self._on_open_document_requested)
        library_page.add_to_collection_requested.connect(
            self._on_add_to_collection_requested
        )
        library_page.add_to_project_requested.connect(
            self._on_add_to_project_requested
        )

    def _open_import_dialog(self, parent) -> None:
        """Open the import dialog with the application's coordinator factory."""
        notification_service = self._notification_service

        def _on_imported(_result) -> None:
            library_page = self._pages.get("library")
            if isinstance(library_page, LibraryPage):
                library_page.refresh()

        open_import_dialog(
            parent,
            self._import_coordinator_factory,
            notification_service=notification_service,
            on_imported=_on_imported,
        )

    def _on_open_document_requested(self, document_key: str) -> None:
        """Handle a document-open request from the library page.

        The document reader is delivered in a later phase. The handler
        publishes an informational notification so the user receives
        immediate feedback.
        """
        if self._notification_service is not None:
            self._notification_service.info(
                "Open document",
                f"The reader is not yet available ({document_key}).",
            )


    def _connect_signals(self) -> None:
        self._navigation.destination_selected.connect(self._on_destination_selected)
        from academic_platform.ui.pages.dashboard_page import DashboardPage
        from academic_platform.ui.pages.research_assistant import (
            ResearchAssistantPage,
        )
        from academic_platform.ui.pages.search import GlobalSearchPage

        dashboard = self._pages.get("dashboard")
        if isinstance(dashboard, DashboardPage):
            dashboard.destination_requested.connect(self.navigate_to)

        discover = self._pages.get("discover")
        if isinstance(discover, GlobalSearchPage):
            discover.search_submitted.connect(self._on_search_submitted)
            discover.retry_requested.connect(self._on_search_retry_requested)

        assistant = self._pages.get("research_assistant")
        if isinstance(assistant, ResearchAssistantPage):
            assistant.destination_requested.connect(self.navigate_to)

    def _install_shortcuts(self) -> None:
        """Install global navigation shortcuts for every destination."""
        for destination in DESTINATIONS:
            if not destination.shortcut:
                continue
            shortcut = QShortcut(QKeySequence(destination.shortcut), self)
            shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
            shortcut.activated.connect(
                lambda key=destination.identifier: self.navigate_to(key)
            )
            self._shortcuts.append(shortcut)

    def _configure_status_bar(self) -> None:
        status = QStatusBar(self)
        status.showMessage("Ready")
        version_label = QLabel(f"v{__version__}", self)
        version_label.setObjectName("statusBarVersionLabel")
        status.addPermanentWidget(version_label)
        self.setStatusBar(status)

    def _build_orchestrator_factory(self):
        """Return a callable that constructs a search orchestrator per call."""

        def _factory() -> SearchOrchestrator:
            from academic_platform.application.search_sources.service import (
                SearchSourceService as _Service,
            )
            from academic_platform.infrastructure.search_providers.registry import (
                default_registry,
            )

            manager = _PerCallManager(self._database)
            registry = default_registry()
            source_service = _Service(manager, registry)
            orchestrator = SearchOrchestrator(manager, source_service, registry)
            return orchestrator

        return _factory

    @property
    def search_orchestrator_factory(self):
        """Return a callable that constructs a search orchestrator per call.

        The callable opens a fresh unit of work so that each call runs
        in its own transaction boundary. Callers invoke the factory once
        per search.
        """
        return self._search_orchestrator_factory

    @property
    def saved_search_service_factory(self):
        """Return a callable that constructs a ``SavedSearchService``.

        The callable opens a fresh per-call repository manager so that
        every operation runs in its own transaction boundary.
        """
        return self._saved_search_factory

    @property
    def import_coordinator_factory(self):
        """Return a callable that constructs an ``ImportCoordinator``.

        The callable opens a fresh per-call repository manager and a
        file storage service bound to the application's managed library
        directory.
        """
        return self._import_coordinator_factory

    @property
    def document_extraction_factory(self):
        """Return a callable that constructs a ``DocumentExtractionService``.

        The callable opens a fresh per-call repository manager so that
        every extraction runs in its own transaction boundary. The
        service is constructed with the OCR configuration derived from
        the current library settings.
        """
        return self._document_extraction_factory

    @property
    def library_service_factory(self):
        """Return a callable that constructs a ``LibraryService``."""
        return self._library_service_factory

    @property
    def annotation_service_factory(self):
        """Return a callable that constructs an ``AnnotationService``."""
        return self._annotation_service_factory

    @property
    def document_search_service_factory(self):
        """Return a callable that constructs a ``DocumentSearchService``."""
        return self._document_search_service_factory

    @property
    def document_linking_service_factory(self):
        """Return a callable that constructs a ``DocumentLinkingService``."""
        return self._document_linking_service_factory

    @property
    def handoff_service_factory(self):
        """Return a callable that constructs an ``AssistantHandoffService``."""
        return self._handoff_service_factory

    @property
    def project_service_factory(self):
        """Return a callable that constructs a ``ProjectService``."""
        return self._project_service_factory

    @property
    def task_service_factory(self):
        """Return a callable that constructs a ``TaskService``."""
        return self._task_service_factory

    @property
    def project_export_service_factory(self):
        """Return a callable that constructs a ``ProjectExportService``."""
        return self._project_export_service_factory

    @property
    def topic_workspace_service_factory(self):
        """Return a callable that constructs a ``TopicWorkspaceService``."""
        return self._topic_workspace_service_factory

    @property
    def title_builder_service_factory(self):
        """Return a callable that constructs a ``TitleBuilderService``."""
        return self._title_builder_service_factory

    @property
    def question_workspace_service_factory(self):
        """Return a callable that constructs a question workspace service."""
        return self._question_workspace_service_factory

    @property
    def history_workspace_service_factory(self):
        """Return a callable that constructs a research-history service."""
        return self._history_workspace_service_factory

    def _build_history_workspace_service_factory(self):
        """Build the research-history service factory.

        The factory opens a fresh per-call repository manager, composes
        the search orchestrator and the publication service against
        that manager, and returns a research-history service bound to
        the same manager.
        """

        def _factory() -> ResearchHistoryService:
            from academic_platform.application.search_orchestration.orchestrator import (
                SearchOrchestrator,
            )
            from academic_platform.application.search_sources.service import (
                SearchSourceService,
            )
            from academic_platform.infrastructure.search_providers.registry import (
                default_registry,
            )

            manager = _PerCallManager(self._database)
            registry = default_registry()
            source_service = SearchSourceService(manager, registry)  # type: ignore[arg-type]
            orchestrator = SearchOrchestrator(
                manager, source_service, registry  # type: ignore[arg-type]
            )
            return ResearchHistoryService(
                manager,  # type: ignore[arg-type]
                orchestrator_factory=lambda: orchestrator,
            )

        return _factory


    def _build_question_workspace_service_factory(self):
        """Build the question workspace service factory."""

        def _factory() -> ResearchQuestionWorkspaceService:
            manager = _PerCallManager(self._database)
            return ResearchQuestionWorkspaceService(manager)  # type: ignore[arg-type]

        return _factory

    def _build_title_builder_service_factory(self):
        """Build the title builder service factory."""

        def _factory() -> TitleBuilderService:
            manager = _PerCallManager(self._database)
            return TitleBuilderService(manager)  # type: ignore[arg-type]

        return _factory


    def _build_topic_workspace_service_factory(self):
        """Build the topic workspace service factory."""

        def _factory() -> TopicWorkspaceService:
            manager = _PerCallManager(self._database)
            return TopicWorkspaceService(manager)  # type: ignore[arg-type]

        return _factory

    def _build_project_export_service_factory(self):
        """Build the project export service factory."""

        def _factory() -> ProjectExportService:
            manager = _PerCallManager(self._database)
            return ProjectExportService(manager)  # type: ignore[arg-type]

        return _factory

    def _build_task_service_factory(self):
        """Build the task service factory bound to per-call sessions."""

        def _factory() -> TaskService:
            manager = _PerCallManager(self._database)
            return TaskService(manager)  # type: ignore[arg-type]

        return _factory

    @property
    def collection_service_factory(self):
        """Return a callable that constructs a ``CollectionService``."""
        return self._collection_service_factory

    def _build_collection_service_factory(self):
        """Build the collection service factory bound to per-call sessions."""

        def _factory() -> CollectionService:
            manager = _PerCallManager(self._database)
            return CollectionService(manager)  # type: ignore[arg-type]

        return _factory

    def _build_project_service_factory(self):
        """Build the project service factory bound to per-call sessions."""

        def _factory() -> ProjectService:
            manager = _PerCallManager(self._database)
            return ProjectService(manager)  # type: ignore[arg-type]

        return _factory

    def _build_handoff_service_factory(self):
        """Build the handoff service factory."""

        def _factory() -> AssistantHandoffService:
            manager = _PerCallManager(self._database)
            return AssistantHandoffService(
                manager,  # type: ignore[arg-type]
                store=default_handoff_store(),
            )

        return _factory

    def _build_document_linking_service_factory(self):
        """Build the linking service factory bound to per-call sessions."""

        def _factory() -> DocumentLinkingService:
            manager = _PerCallManager(self._database)
            return DocumentLinkingService(manager)  # type: ignore[arg-type]

        return _factory

    def _build_document_search_service_factory(self):
        """Build the in-document search service factory."""

        def _factory() -> DocumentSearchService:
            manager = _PerCallManager(self._database)
            return DocumentSearchService(manager)  # type: ignore[arg-type]

        return _factory

    def _build_annotation_service_factory(self):
        """Build the annotation service factory bound to per-call sessions."""

        def _factory() -> AnnotationService:
            manager = _PerCallManager(self._database)
            return AnnotationService(manager)  # type: ignore[arg-type]

        return _factory

    def _build_library_service_factory(self):
        """Build the library service factory bound to per-call sessions."""

        def _factory() -> LibraryService:
            manager = _PerCallManager(self._database)
            return LibraryService(manager)  # type: ignore[arg-type]

        return _factory

    def _build_document_extraction_factory(self):
        """Build the document extraction service factory."""

        def _factory() -> DocumentExtractionService:
            manager = _PerCallManager(self._database)
            settings = self._settings_service.settings
            library_settings = settings.library
            ocr_config = OcrConfig(
                language=library_settings.ocr_language,
                dpi=library_settings.ocr_dpi,
                max_pages=library_settings.ocr_max_pages,
            )
            return DocumentExtractionService(
                repositories=manager,  # type: ignore[arg-type]
                ocr_config=ocr_config,
                ocr_enabled=library_settings.ocr_enabled,
            )

        return _factory

    @property
    def duplicate_policy(self) -> DuplicatePolicy:
        """Return the application-wide duplicate detection policy."""
        return DuplicatePolicy()

    def _build_import_coordinator_factory(self):
        """Build the import coordinator factory bound to per-call sessions."""
        from academic_platform.infrastructure.file_storage import (
            FileStorage,
            FileStorageConfig,
        )
        from academic_platform.app.settings.schema import LibrarySettings

        managed_root = self._directories.managed_library_dir

        def _factory() -> _ImportCoordinator:
            manager = _PerCallManager(self._database)
            settings = self._settings_service.settings
            library_settings: LibrarySettings = settings.library
            max_bytes = library_settings.max_import_size_mb * 1024 * 1024
            config = FileStorageConfig(
                managed_root=managed_root,
                max_file_size_bytes=max_bytes,
            )
            storage = FileStorage(config)
            return _ImportCoordinator(
                repositories=manager,  # type: ignore[arg-type]
                storage=storage,
                max_file_size_bytes=max_bytes,
                duplicate_policy=self.duplicate_policy,
            )

        return _factory

    def _build_import_coordinator_factory(self):
        """Build the import coordinator factory bound to per-call sessions."""
        from academic_platform.app.settings import SettingsSchema
        from academic_platform.app.settings.schema import LibrarySettings

        managed_root = self._directories.managed_library_dir

        def _factory() -> ImportCoordinator:
            manager = _PerCallManager(self._database)
            settings: SettingsSchema = self._settings_service.settings
            library_settings: LibrarySettings = settings.library
            max_bytes = library_settings.max_import_size_mb * 1024 * 1024
            config = FileStorageConfig(
                managed_root=managed_root,
                max_file_size_bytes=max_bytes,
            )
            storage = FileStorage(config)
            return ImportCoordinator(
                repositories=manager,  # type: ignore[arg-type]
                storage=storage,
                max_file_size_bytes=max_bytes,
            )

        return _factory

    def _build_saved_search_factory(self):
        """Build the saved-search service factory bound to per-call sessions."""

        def _factory() -> SavedSearchService:
            manager = _PerCallManager(self._database)
            return SavedSearchService(manager)  # type: ignore[arg-type]

        return _factory

    # ------------------------------------------------------------------
    # Appearance
    # ------------------------------------------------------------------
    def _apply_settings(self, settings: SettingsSchema) -> None:
        stylesheet = build_application_stylesheet(
            theme=settings.appearance.theme,
            font_scale=settings.appearance.font_scale,
            density=settings.appearance.density,
        )
        self.setStyleSheet(stylesheet)
        self._navigation.set_labels_visible(settings.appearance.show_sidebar_labels)

    def _on_settings_changed(self, settings: SettingsSchema) -> None:
        self._apply_settings(settings)
        self.refresh_active_user()

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------
    def navigate_to(self, identifier: str) -> None:
        """Navigate to the destination with the given identifier.

        Unknown identifiers are logged and ignored; the current page remains
        active. Known identifiers cause the previous page to be deactivated
        and the new page to be activated.
        """
        page = self._pages.get(identifier)
        if page is None:
            _logger.warning("Unknown destination requested: %s", identifier)
            return

        if self._current_identifier == identifier:
            page.on_activated()
            return

        previous = self._pages.get(self._current_identifier) if self._current_identifier else None
        if previous is not None:
            previous.on_deactivated()

        self._stack.setCurrentWidget(page)
        self._current_identifier = identifier
        page.on_activated()
        self.statusBar().showMessage(page.title)

    def _on_search_submitted(self, query: str, scope: str) -> None:
        """Handle a search submission from the Discover page."""
        _logger.debug("Search submitted: query=%r scope=%r", query, scope)

    def _on_search_retry_requested(self) -> None:
        """Retry the last search executed on the Discover page."""
        from academic_platform.ui.pages.search import GlobalSearchPage

        page = self._pages.get("discover")
        if isinstance(page, GlobalSearchPage):
            page.execute_search(page._last_query, page._last_scope)  # noqa: SLF001

    # ------------------------------------------------------------------
    # Attachments
    # ------------------------------------------------------------------
    def attach_notification_service(self, service: NotificationService) -> None:
        """Attach the notification service used by pages to publish events."""
        self._notification_service = service

    def attach_search_source_service(self, service: SearchSourceService) -> None:
        """Attach the application-level search source service."""
        self._search_source_service = service

    def attach_search_orchestrator(self, orchestrator: SearchOrchestrator) -> None:
        """Attach the application-level search orchestrator."""
        self._search_orchestrator = orchestrator

    def set_dashboard_data_provider(self, provider) -> None:
        """Register a callable that supplies dashboard data.

        The callable must return a mapping whose keys are drawn from the
        set ``recent_projects``, ``recent_articles``, ``saved_searches``,
        ``research_tasks``, ``pending_evidence``, ``recent_reports``, and
        ``recent_activity``. Missing keys are treated as empty.
        """
        self._dashboard_data_provider = provider

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------
    @property
    def database(self) -> Database:
        """Return the application database wrapper."""
        return self._database

    @property
    def search_source_service(self) -> SearchSourceService | None:
        """Return the search source service, or ``None`` when unattached.

        The bootstrap attaches the service before the window is shown.
        During window construction, the service is not yet available;
        pages that read it must tolerate ``None`` and re-read the value
        when the window is fully constructed.
        """
        return self._search_source_service

    @property
    def search_orchestrator(self) -> SearchOrchestrator:
        """Return the search orchestrator.

        Raises
        ------
        RuntimeError
            If the orchestrator has not been attached.
        """
        if self._search_orchestrator is None:
            raise RuntimeError("Search orchestrator has not been attached")
        return self._search_orchestrator

    @property
    def active_user_key(self) -> str | None:
        """Return the cached active user key, or ``None`` when unset."""
        return self._active_user_key

    @property
    def dashboard_data_provider(self):
        """Return the currently registered dashboard data provider."""
        return self._dashboard_data_provider

    @property
    def notifications(self) -> NotificationService:
        """Return the notification service.

        Raises
        ------
        RuntimeError
            If the service has not been attached. The bootstrap attaches it
            before the window is shown, so this indicates a programming error.
        """
        if self._notification_service is None:
            raise RuntimeError("Notification service has not been attached")
        return self._notification_service

    # ------------------------------------------------------------------
    # Active user
    # ------------------------------------------------------------------
    def refresh_active_user(self) -> str | None:
        """Read the active user key from the database and cache it.

        The value is refreshed after a user-visible settings change and
        once during window construction. When the settings tables are not
        yet present (for example in tests that construct the window
        against an unmigrated database), the method treats the active
        user as ``None`` and logs the reason at debug level.

        Returns
        -------
        str | None
            The active user key, or ``None`` when no user is active or the
            database cannot answer yet.
        """
        try:
            with unit_of_work(self._database) as repositories:
                bridge = SettingsPersistenceBridge(
                    settings_service=self._settings_service,
                    app_settings_repository=repositories.get("app_settings"),
                    user_profile_repository=repositories.get("user_profile"),
                )
                key = bridge.get_active_user_key()
        except SettingsPersistenceError:
            _logger.exception("Unable to read active user key")
            return self._active_user_key
        except Exception as exc:  # noqa: BLE001 - defensive boundary
            _logger.debug("Active user key unavailable: %s", exc)
            return self._active_user_key
        self._active_user_key = key
        return key

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------
    def _on_destination_selected(self, identifier: str) -> None:
        self.navigate_to(identifier)

    def _show_about(self) -> None:
        QMessageBox.about(
            self,
            "About Academic Research Platform",
            (
                "<h3>Academic Research &amp; Evidence Intelligence Platform</h3>"
                "<p>Desktop-first academic research environment for literature "
                "discovery, reading, research design, evidence extraction, and "
                "traceable reporting.</p>"
                f"<p>Version {__version__}</p>"
            ),
        )

    # ------------------------------------------------------------------
    # Close handling
    # ------------------------------------------------------------------
    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 - Qt API
        """Consult each page's ``can_close`` before permitting closure."""
        for identifier, page in self._pages.items():
            try:
                if not page.can_close():
                    _logger.info("Closure vetoed by page: %s", identifier)
                    event.ignore()
                    return
            except Exception:  # noqa: BLE001 - page contract violation
                _logger.exception("Page %s raised during can_close()", identifier)
        super().closeEvent(event)

    def _ensure_reader_page(self) -> ReaderPage | None:
        """Construct the reader page lazily and register it in the shell."""
        if self._reader_page is not None:
            return self._reader_page
        try:
            manager = _PerCallManager(self._database)
            service = DocumentReaderService(manager)  # type: ignore[arg-type]
        except Exception:  # noqa: BLE001 - boundary
            _logger.exception("Unable to construct the document reader service")
            return None
        page = ReaderPage(parent=self)
        page.attach_service(service)
        try:
            annotation_service = self._annotation_service_factory()
        except Exception:  # noqa: BLE001 - boundary
            _logger.exception(
                "Unable to construct the annotation service"
            )
        else:
            page.attach_annotation_service(
                annotation_service,
                notification_service=self._notification_service,
            )
        try:
            search_service = self._document_search_service_factory()
        except Exception:  # noqa: BLE001 - boundary
            _logger.exception(
                "Unable to construct the in-document search service"
            )
        else:
            page.attach_search_service(search_service)
        try:
            linking_service = self._document_linking_service_factory()
        except Exception:  # noqa: BLE001 - boundary
            _logger.exception(
                "Unable to construct the document linking service"
            )
        else:
            page.attach_linking_service(linking_service)
        try:
            handoff_service = self._handoff_service_factory()
        except Exception:  # noqa: BLE001 - boundary
            _logger.exception(
                "Unable to construct the assistant handoff service"
            )
        else:
            page.attach_handoff_service(handoff_service)
        page.close_requested.connect(self._on_reader_close_requested)
        self._reader_page = page
        index = self._stack.addWidget(page)
        self._page_indices["reader"] = index
        return page

    def _on_open_document_requested(self, document_key: str) -> None:
        """Open a document in the reader and switch to the reader view."""
        page = self._ensure_reader_page()
        if page is None:
            if self._notification_service is not None:
                self._notification_service.error(
                    "Reader unavailable",
                    "The document reader could not be initialized.",
                )
            return
        # Remember the destination the user came from so the reader can
        # return there when closed.
        if self._current_identifier and self._current_identifier != "reader":
            self._reader_previous_destination = self._current_identifier
        opened = page.load_document(document_key)
        if not opened:
            return
        previous = self._pages.get(self._current_identifier) if self._current_identifier else None
        if previous is not None:
            previous.on_deactivated()
        self._stack.setCurrentWidget(page)
        self._current_identifier = "reader"
        page.on_activated()
        self.statusBar().showMessage("Reader")

    def _on_reader_close_requested(self) -> None:
        """Return to the destination the user came from before the reader."""
        target = self._reader_previous_destination or "library"
        self._reader_previous_destination = None
        if target not in self._pages and target != "reader":
            target = "library"
        self.navigate_to(target)

    def _on_add_to_collection_requested(self, document_key: str) -> None:
        """Open the linking dialog focused on the Collections tab."""
        self._open_link_dialog(document_key, default_tab=0)

    def _on_add_to_project_requested(self, document_key: str) -> None:
        """Open the linking dialog focused on the Projects tab."""
        self._open_link_dialog(document_key, default_tab=1)

    def _open_link_dialog(self, document_key: str, *, default_tab: int) -> None:
        """Open the linking dialog for a document."""
        try:
            service = self._document_linking_service_factory()
        except Exception:  # noqa: BLE001 - boundary
            _logger.exception(
                "Unable to construct the document linking service"
            )
            return
        from academic_platform.ui.dialogs.link_document_dialog import (
            LinkDocumentDialog,
        )

        dialog = LinkDocumentDialog(service, document_key, parent=self)
        dialog._tabs.setCurrentIndex(default_tab)  # noqa: SLF001
        dialog.links_changed.connect(self._on_links_changed)
        dialog.exec()

    def _on_links_changed(self, document_key: str) -> None:
        if self._notification_service is not None:
            self._notification_service.success(
                "Links updated",
                f"Document {document_key} updated.",
            )

    def _wire_projects_page(self) -> None:
        """Wire the projects page to the application services."""
        projects_page = self._pages.get("research_projects")
        if not isinstance(projects_page, ProjectsPage):
            return
        try:
            project_service = self._project_service_factory()
        except Exception:  # noqa: BLE001 - boundary
            _logger.exception("Unable to construct the project service")
            return
        projects_page.attach_service(project_service)
        try:
            task_service = self._task_service_factory()
        except Exception:  # noqa: BLE001 - boundary
            _logger.exception("Unable to construct the task service")
            return
        projects_page.attach_task_service(task_service)
        try:
            export_service = self._project_export_service_factory()
        except Exception:  # noqa: BLE001 - boundary
            _logger.exception("Unable to construct the export service")
        else:
            projects_page.attach_export_service(export_service)
        
    def _wire_collections_page(self) -> None:
        """Wire the collections page to the application service."""
        collections_page = self._pages.get("collections")
        if not isinstance(collections_page, CollectionsPage):
            return
        try:
            service = self._collection_service_factory()
        except Exception:  # noqa: BLE001 - boundary
            _logger.exception("Unable to construct the collection service")
            return
        collections_page.attach_service(service)

    def _wire_research_assistant_page(self) -> None:
        """Wire the research assistant page to its application services."""
        from academic_platform.ui.pages.research_assistant import (
            ResearchAssistantPage,
        )

        page = self._pages.get("research_assistant")
        if not isinstance(page, ResearchAssistantPage):
            return
        try:
            service = self._topic_workspace_service_factory()
        except Exception:  # noqa: BLE001 - boundary
            _logger.exception(
                "Unable to construct the topic workspace service"
            )
            return
        try:
            title_service = self._title_builder_service_factory()
        except Exception:  # noqa: BLE001 - boundary
            _logger.exception(
                "Unable to construct the title builder service"
            )
        else:
            page.attach_title_service(title_service)
        try:
            question_service = self._question_workspace_service_factory()
        except Exception:  # noqa: BLE001 - boundary
            _logger.exception(
                "Unable to construct the research-question workspace service"
            )
        else:
            page.attach_question_service(question_service)
        try:
            history_service = self._history_workspace_service_factory()
        except Exception:  # noqa: BLE001 - boundary
            _logger.exception(
                "Unable to construct the research-history workspace service"
            )
        else:
            page.attach_history_service(history_service)
        page.attach_topic_service(service)

class _PerCallManager:
    """A repository manager that opens a fresh session per call.

    Each call to :meth:`get` opens a session, wraps the repository so that
    the session is committed on success, rolled back on failure, and
    closed in all cases before the call returns. This prevents SQLite
    from holding the file lock across the multiple repository accesses
    that make up a single search.
    """

    def __init__(self, database) -> None:
        self._database = database
        self._sessions: list = []

    def get(self, key: str):
        from academic_platform.infrastructure.repositories.factory import (
            _REPOSITORY_REGISTRY,
        )

        session = self._database._session_factory()  # noqa: SLF001
        self._sessions.append(session)
        repository_class = _REPOSITORY_REGISTRY.get(key)
        if repository_class is None:
            from academic_platform.infrastructure.repositories.errors import (
                RepositoryError,
            )

            session.close()
            raise RepositoryError(f"No repository registered under key {key!r}")
        return _SessionClosingRepository(repository_class(session), session)

    def close_all(self) -> None:
        for session in self._sessions:
            try:
                session.commit()
            except Exception:  # noqa: BLE001
                session.rollback()
            finally:
                session.close()
        self._sessions.clear()


class _SessionClosingRepository:
    """Proxy that commits and closes the session after each repository call."""

    def __init__(self, repository, session) -> None:
        self._repository = repository
        self._session = session

    def __getattr__(self, name):
        target = getattr(self._repository, name)
        if not callable(target):
            return target

        def _call(*args, **kwargs):
            try:
                result = target(*args, **kwargs)
                self._session.commit()
                return result
            except Exception:
                try:
                    self._session.rollback()
                except Exception:  # noqa: BLE001
                    pass
                raise
            finally:
                try:
                    self._session.close()
                except Exception:  # noqa: BLE001
                    pass

        return _call