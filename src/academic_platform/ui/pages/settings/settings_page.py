"""Settings page composition.

The page hosts the six settings tabs in a single ``QTabWidget``. It owns
the settings service reference, provides the Advanced tab with the
resolved runtime directories, and subscribes to settings changes so that
every tab can re-read its section when the configuration changes
externally.
"""

from __future__ import annotations

import logging

from PySide6.QtWidgets import QTabWidget, QVBoxLayout, QWidget

from academic_platform.app.configuration import AppDirectories
from academic_platform.app.settings import SettingsSchema, SettingsService
from academic_platform.ui.main_window_destinations import get_destination
from academic_platform.ui.notifications import NotificationService
from academic_platform.ui.pages.base_page import BasePage
from academic_platform.ui.pages.settings._base_tab import SettingsTab
from academic_platform.ui.pages.settings.advanced_tab import AdvancedSettingsTab
from academic_platform.ui.pages.settings.ai_providers_tab import AIProvidersSettingsTab
from academic_platform.ui.pages.settings.appearance_tab import AppearanceSettingsTab
from academic_platform.ui.pages.settings.general_tab import GeneralSettingsTab
from academic_platform.ui.pages.settings.privacy_tab import PrivacySettingsTab
from academic_platform.ui.pages.settings.search_tab import SearchSettingsTab

_logger = logging.getLogger(__name__)


class SettingsPage(BasePage):
    """Settings page hosting all configuration tabs."""

    def __init__(
        self,
        settings_service: SettingsService,
        directories: AppDirectories,
        notification_service: NotificationService | None = None,
        parent: QWidget | None = None,
    ) -> None:
        destination = get_destination("settings")
        super().__init__(
            title=destination.label,
            subtitle=destination.purpose,
            parent=parent,
        )
        self._settings_service = settings_service
        self._directories = directories
        self._notification_service = notification_service
        self.setObjectName("settingsPage")

        self._tabs: list[SettingsTab] = []

        self._build_content()
        self._settings_service.add_observer(self._on_settings_changed)

    # ------------------------------------------------------------------
    # Content
    # ------------------------------------------------------------------
    def _build_content(self) -> None:
        content = QWidget(self)
        content.setObjectName("settingsContent")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        self._tab_widget = QTabWidget(content)
        self._tab_widget.setObjectName("settingsTabs")

        general = GeneralSettingsTab(
            self._settings_service, self._notification_service, self._tab_widget
        )
        appearance = AppearanceSettingsTab(
            self._settings_service, self._notification_service, self._tab_widget
        )
        search = SearchSettingsTab(
            self._settings_service, self._notification_service, self._tab_widget
        )
        ai_providers = AIProvidersSettingsTab(
            self._settings_service, self._notification_service, self._tab_widget
        )
        privacy = PrivacySettingsTab(
            self._settings_service, self._notification_service, self._tab_widget
        )
        advanced = AdvancedSettingsTab(
            self._settings_service,
            self._directories,
            self._notification_service,
            self._tab_widget,
        )

        self._tabs = [general, appearance, search, ai_providers, privacy, advanced]

        self._tab_widget.addTab(general, "General")
        self._tab_widget.addTab(appearance, "Appearance")
        self._tab_widget.addTab(search, "Search")
        self._tab_widget.addTab(ai_providers, "AI Providers")
        self._tab_widget.addTab(privacy, "Privacy")
        self._tab_widget.addTab(advanced, "Advanced")

        layout.addWidget(self._tab_widget, 1)

        self._install_content(content)

    # ------------------------------------------------------------------
    # Settings observer
    # ------------------------------------------------------------------
    def _on_settings_changed(self, settings: SettingsSchema) -> None:
        # Only reload tabs whose controls may be stale. For simplicity and
        # correctness we reload every tab; each tab's ``reload`` is cheap
        # and suppresses signals during population.
        for tab in self._tabs:
            try:
                tab.reload()
            except Exception:  # noqa: BLE001 - defensive boundary
                _logger.exception("Settings tab reload raised")

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def on_activated(self) -> None:
        for tab in self._tabs:
            try:
                tab.reload()
            except Exception:  # noqa: BLE001 - defensive boundary
                _logger.exception("Settings tab reload raised")