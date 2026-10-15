"""AI providers settings tab.

This tab configures the default provider and default model and the
external-provider policy. Per-provider configuration is delivered by a
later phase; this tab surfaces the summary policy that governs the AI
subsystem as a whole.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from academic_platform.app.settings import SettingsService
from academic_platform.ui.notifications import NotificationService
from academic_platform.ui.pages.settings._base_tab import SettingsTab


class AIProvidersSettingsTab(SettingsTab):
    """AI provider preferences."""

    def __init__(
        self,
        settings_service: SettingsService,
        notification_service: NotificationService | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(settings_service, notification_service, parent)
        self.setObjectName("settingsTabAIProviders")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        intro = QLabel(
            "Configure which AI providers are available. Detailed provider "
            "configuration is available on the API & Integrations page.",
            self,
        )
        intro.setObjectName("settingsAIIntro")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(10)

        self._default_provider = QLineEdit(self)
        self._default_provider.setObjectName("settingsAIDefaultProvider")
        self._default_provider.setPlaceholderText("Provider identifier (optional)")
        self._default_provider.editingFinished.connect(self._on_default_provider_changed)
        form.addRow("Default provider", self._default_provider)

        self._default_model = QLineEdit(self)
        self._default_model.setObjectName("settingsAIDefaultModel")
        self._default_model.setPlaceholderText("Model identifier (optional)")
        self._default_model.editingFinished.connect(self._on_default_model_changed)
        form.addRow("Default model", self._default_model)

        self._allow_external = QCheckBox("Allow third-party AI providers", self)
        self._allow_external.setObjectName("settingsAIAllowExternal")
        self._allow_external.setToolTip(
            "Local providers remain available regardless of this setting."
        )
        self._allow_external.toggled.connect(self._on_allow_external_changed)
        form.addRow("", self._allow_external)

        self._send_excerpts = QCheckBox(
            "Allow sending document excerpts to external providers",
            self,
        )
        self._send_excerpts.setObjectName("settingsAISendExcerpts")
        self._send_excerpts.setToolTip(
            "Disabled by default. When disabled, a per-request confirmation "
            "is required before any excerpt is transmitted."
        )
        self._send_excerpts.toggled.connect(self._on_send_excerpts_changed)
        form.addRow("", self._send_excerpts)

        layout.addLayout(form)
        layout.addStretch(1)

        self._populate()

    # ------------------------------------------------------------------
    # Population
    # ------------------------------------------------------------------
    def _populate(self) -> None:
        self._loading = True
        try:
            ai = self.settings.ai
            self._default_provider.setText(ai.default_provider_id or "")
            self._default_model.setText(ai.default_model_id or "")
            self._allow_external.setChecked(ai.allow_external_providers)
            self._send_excerpts.setChecked(ai.send_document_excerpts)
        finally:
            self._loading = False

    def reload(self) -> None:
        self._populate()

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------
    def _on_default_provider_changed(self) -> None:
        value = self._default_provider.text().strip()
        if not self._update_section("ai", default_provider_id=value or None):
            self._populate()

    def _on_default_model_changed(self) -> None:
        value = self._default_model.text().strip()
        if not self._update_section("ai", default_model_id=value or None):
            self._populate()

    def _on_allow_external_changed(self, checked: bool) -> None:
        if not self._update_section("ai", allow_external_providers=checked):
            self._populate()

    def _on_send_excerpts_changed(self, checked: bool) -> None:
        if not self._update_section("ai", send_document_excerpts=checked):
            self._populate()