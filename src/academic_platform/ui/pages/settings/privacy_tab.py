"""Privacy settings tab."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from academic_platform.app.settings import SettingsService
from academic_platform.ui.notifications import NotificationService
from academic_platform.ui.pages.settings._base_tab import SettingsTab


_LOG_LEVELS: tuple[str, ...] = ("DEBUG", "INFO", "WARNING", "ERROR")


class PrivacySettingsTab(SettingsTab):
    """Privacy and data-protection preferences."""

    def __init__(
        self,
        settings_service: SettingsService,
        notification_service: NotificationService | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(settings_service, notification_service, parent)
        self.setObjectName("settingsTabPrivacy")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(10)

        self._log_level = QComboBox(self)
        self._log_level.setObjectName("settingsPrivacyLogLevel")
        for level in _LOG_LEVELS:
            self._log_level.addItem(level, level)
        self._log_level.currentIndexChanged.connect(self._on_log_level_changed)
        form.addRow("Log level", self._log_level)

        self._log_retention = QSpinBox(self)
        self._log_retention.setObjectName("settingsPrivacyLogRetention")
        self._log_retention.setRange(1, 365)
        self._log_retention.setSuffix(" days")
        self._log_retention.valueChanged.connect(self._on_log_retention_changed)
        form.addRow("Log retention", self._log_retention)

        self._redact = QCheckBox(
            "Redact document content from diagnostic logs",
            self,
        )
        self._redact.setObjectName("settingsPrivacyRedact")
        self._redact.setToolTip(
            "Must remain enabled unless explicitly overridden for support."
        )
        self._redact.toggled.connect(self._on_redact_changed)
        form.addRow("", self._redact)

        self._search_history = QCheckBox("Store search history", self)
        self._search_history.setObjectName("settingsPrivacySearchHistory")
        self._search_history.toggled.connect(self._on_search_history_changed)
        form.addRow("", self._search_history)

        layout.addLayout(form)
        layout.addStretch(1)

        self._populate()

    # ------------------------------------------------------------------
    # Population
    # ------------------------------------------------------------------
    def _populate(self) -> None:
        self._loading = True
        try:
            privacy = self.settings.privacy
            for index in range(self._log_level.count()):
                if self._log_level.itemData(index) == privacy.log_level:
                    self._log_level.setCurrentIndex(index)
                    break
            self._log_retention.setValue(privacy.log_retention_days)
            self._redact.setChecked(privacy.redact_document_content_in_logs)
            self._search_history.setChecked(privacy.store_search_history)
        finally:
            self._loading = False

    def reload(self) -> None:
        self._populate()

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------
    def _on_log_level_changed(self, _index: int) -> None:
        value = self._log_level.currentData()
        if not isinstance(value, str):
            return
        if not self._update_section("privacy", log_level=value):
            self._populate()

    def _on_log_retention_changed(self, value: int) -> None:
        if not self._update_section("privacy", log_retention_days=int(value)):
            self._populate()

    def _on_redact_changed(self, checked: bool) -> None:
        if not self._update_section("privacy", redact_document_content_in_logs=checked):
            self._populate()

    def _on_search_history_changed(self, checked: bool) -> None:
        if not self._update_section("privacy", store_search_history=checked):
            self._populate()