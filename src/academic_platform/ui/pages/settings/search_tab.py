"""Search settings tab."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QFormLayout,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from academic_platform.app.settings import SettingsService
from academic_platform.ui.notifications import NotificationService
from academic_platform.ui.pages.settings._base_tab import SettingsTab
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout
from PySide6.QtWidgets import QPushButton



class SearchSettingsTab(SettingsTab):
    """Academic search preferences."""

    def __init__(
        self,
        settings_service: SettingsService,
        notification_service: NotificationService | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(settings_service, notification_service, parent)
        self.setObjectName("settingsTabSearch")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(10)

        self._result_limit = QSpinBox(self)
        self._result_limit.setObjectName("settingsSearchResultLimit")
        self._result_limit.setRange(1, 500)
        self._result_limit.valueChanged.connect(self._on_result_limit_changed)
        form.addRow("Default results per source", self._result_limit)

        self._timeout = QDoubleSpinBox(self)
        self._timeout.setObjectName("settingsSearchTimeout")
        self._timeout.setRange(1.0, 180.0)
        self._timeout.setDecimals(1)
        self._timeout.setSingleStep(1.0)
        self._timeout.setSuffix(" s")
        self._timeout.valueChanged.connect(self._on_timeout_changed)
        form.addRow("Request timeout", self._timeout)

        self._concurrency = QSpinBox(self)
        self._concurrency.setObjectName("settingsSearchConcurrency")
        self._concurrency.setRange(1, 16)
        self._concurrency.valueChanged.connect(self._on_concurrency_changed)
        form.addRow("Maximum concurrent sources", self._concurrency)

        self._dedup = QCheckBox("Deduplicate results across sources", self)
        self._dedup.setObjectName("settingsSearchDeduplicate")
        self._dedup.toggled.connect(self._on_dedup_changed)
        form.addRow("", self._dedup)

        self._require_https = QCheckBox("Require HTTPS for custom sources", self)
        self._require_https.setObjectName("settingsSearchRequireHttps")
        self._require_https.setToolTip(
            "HTTP is never permitted unless this is explicitly disabled for "
            "a specific local-development source."
        )
        self._require_https.toggled.connect(self._on_require_https_changed)
        form.addRow("", self._require_https)

        layout.addLayout(form)
        layout.addWidget(self._build_configured_sources_section())
        layout.addStretch(1)

        self._populate()

    # ------------------------------------------------------------------
    # Population
    # ------------------------------------------------------------------
    def _populate(self) -> None:
        self._loading = True
        try:
            search = self.settings.search
            self._result_limit.setValue(search.default_result_limit)
            self._timeout.setValue(search.request_timeout_seconds)
            self._concurrency.setValue(search.max_concurrent_sources)
            self._dedup.setChecked(search.deduplicate_results)
            self._require_https.setChecked(search.require_https)
        finally:
            self._loading = False

    def reload(self) -> None:
        self._populate()

    def _build_configured_sources_section(self):
        """Build the configured search sources panel."""
        container = QFrame(self)
        container.setObjectName("settingsSearchSources")
        container.setFrameShape(QFrame.Shape.StyledPanel)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(14, 10, 14, 12)
        layout.setSpacing(6)

        heading = QLabel("Configured sources", container)
        heading.setObjectName("settingsSearchSourcesHeading")
        layout.addWidget(heading)

        self._sources_container = QWidget(container)
        self._sources_layout = QVBoxLayout(self._sources_container)
        self._sources_layout.setContentsMargins(0, 0, 0, 0)
        self._sources_layout.setSpacing(4)
        layout.addWidget(self._sources_container)

        controls = QWidget(container)
        controls_layout = QHBoxLayout(controls)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        controls_layout.setSpacing(8)

        hint = QLabel(
            "Sources are managed here. Built-in sources may be disabled "
            "but not removed.",
            controls,
        )
        hint.setObjectName("settingsSearchSourcesHint")
        hint.setWordWrap(True)
        controls_layout.addWidget(hint, 1)

        manage_button = QPushButton("Manage sources…", controls)
        manage_button.setObjectName("settingsSearchSourcesManage")
        manage_button.setAutoDefault(False)
        manage_button.clicked.connect(self._on_manage_sources)
        controls_layout.addWidget(manage_button)

        layout.addWidget(controls)

        self._refresh_sources_panel()
        return container

    def _refresh_sources_panel(self) -> None:
        while self._sources_layout.count():
            item = self._sources_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

        window = self.window()
        service = getattr(window, "search_source_service", None) if window is not None else None
        if service is None:
            placeholder = QLabel("Search source service is not attached.", self._sources_container)
            placeholder.setObjectName("settingsSearchSourcesPlaceholder")
            self._sources_layout.addWidget(placeholder)
            return

        try:
            records = service.list_sources()
        except Exception:  # noqa: BLE001 - defensive boundary
            placeholder = QLabel(
                "Unable to read search sources. Check the log for details.",
                self._sources_container,
            )
            placeholder.setObjectName("settingsSearchSourcesPlaceholder")
            self._sources_layout.addWidget(placeholder)
            return

        if not records:
            placeholder = QLabel(
                "No sources configured yet.", self._sources_container
            )
            placeholder.setObjectName("settingsSearchSourcesPlaceholder")
            self._sources_layout.addWidget(placeholder)
            return

        for record in records:
            row = QWidget(self._sources_container)
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(6)

            name = QLabel(record.config.display_name, row)
            name.setObjectName("settingsSearchSourceName")
            row_layout.addWidget(name, 1)

            status = QLabel("enabled" if record.config.enabled else "disabled", row)
            status.setObjectName("settingsSearchSourceStatus")
            row_layout.addWidget(status)

            self._sources_layout.addWidget(row)

    def reload(self) -> None:
        self._populate()
        self._refresh_sources_panel()

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------
    def _on_result_limit_changed(self, value: int) -> None:
        if not self._update_section("search", default_result_limit=int(value)):
            self._populate()

    def _on_timeout_changed(self, value: float) -> None:
        if not self._update_section("search", request_timeout_seconds=float(value)):
            self._populate()

    def _on_concurrency_changed(self, value: int) -> None:
        if not self._update_section("search", max_concurrent_sources=int(value)):
            self._populate()

    def _on_dedup_changed(self, checked: bool) -> None:
        if not self._update_section("search", deduplicate_results=checked):
            self._populate()

    def _on_require_https_changed(self, checked: bool) -> None:
        if not self._update_section("search", require_https=checked):
            self._populate()

    def _on_manage_sources(self) -> None:
        """Open the source management dialog."""
        window = self.window()
        service = getattr(window, "search_source_service", None) if window is not None else None
        if service is None:
            from academic_platform.ui.dialogs.message_dialog import MessageKind
            from academic_platform.ui.dialogs.dialog_factory import DialogFactory

            DialogFactory.message(
                self,
                "Search source service unavailable",
                "The application did not initialize the search source service. "
                "Restart the application and try again.",
                kind=MessageKind.ERROR,
            )
            return

        notification_service = None
        if window is not None and hasattr(window, "_notification_service"):
            notification_service = window._notification_service  # noqa: SLF001

        from academic_platform.ui.pages.settings.sources_dialog import (
            SourcesDialog,
        )

        dialog = SourcesDialog(
            service,
            notification_service=notification_service,
            parent=self,
        )
        dialog.sources_changed.connect(self._refresh_sources_panel)
        dialog.exec()
        self._refresh_sources_panel()