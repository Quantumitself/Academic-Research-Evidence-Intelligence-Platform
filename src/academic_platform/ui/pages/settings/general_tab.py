"""General settings tab."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from academic_platform.app.settings import SettingsService
from academic_platform.ui.notifications import NotificationService
from academic_platform.ui.pages.settings._base_tab import SettingsTab
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton



class GeneralSettingsTab(SettingsTab):
    """General application preferences."""

    def __init__(
        self,
        settings_service: SettingsService,
        notification_service: NotificationService | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(settings_service, notification_service, parent)
        self.setObjectName("settingsTabGeneral")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(10)

        self._language_input = QLineEdit(self)
        self._language_input.setObjectName("settingsGeneralLanguage")
        self._language_input.setMaxLength(10)
        self._language_input.setPlaceholderText("en")
        self._language_input.editingFinished.connect(self._on_language_changed)
        form.addRow("Interface language", self._language_input)

        self._check_updates = QCheckBox("Check for application updates on startup", self)
        self._check_updates.setObjectName("settingsGeneralCheckUpdates")
        self._check_updates.toggled.connect(self._on_check_updates_changed)
        form.addRow("", self._check_updates)

        self._telemetry = QCheckBox("Send anonymous usage statistics", self)
        self._telemetry.setObjectName("settingsGeneralTelemetry")
        self._telemetry.setToolTip(
            "Disabled by default. Enabling requires an explicit action here."
        )
        self._telemetry.toggled.connect(self._on_telemetry_changed)
        form.addRow("", self._telemetry)

        self._confirm_exit = QCheckBox("Confirm before closing the application", self)
        self._confirm_exit.setObjectName("settingsGeneralConfirmExit")
        self._confirm_exit.toggled.connect(self._on_confirm_exit_changed)
        form.addRow("", self._confirm_exit)

        layout.addLayout(form)
        layout.addWidget(self._build_active_user_section())
        layout.addStretch(1)

        self._populate()

    # ------------------------------------------------------------------
    # Population
    # ------------------------------------------------------------------
    def _populate(self) -> None:
        self._loading = True
        try:
            general = self.settings.general
            self._language_input.setText(general.language)
            self._check_updates.setChecked(general.check_for_updates)
            self._telemetry.setChecked(general.telemetry_enabled)
            self._confirm_exit.setChecked(general.confirm_on_exit)
        finally:
            self._loading = False

    def reload(self) -> None:
        self._populate()

    def _build_active_user_section(self):
        """Build the active-user section shown on the General tab."""
        from PySide6.QtWidgets import QFrame

        container = QFrame(self)
        container.setObjectName("settingsGeneralActiveUser")
        container.setFrameShape(QFrame.Shape.StyledPanel)
        row = QHBoxLayout(container)
        row.setContentsMargins(14, 10, 14, 10)
        row.setSpacing(8)

        label = QLabel("Active user profile:", container)
        label.setObjectName("settingsGeneralActiveUserLabel")
        row.addWidget(label)

        self._active_user_value = QLabel("(none)", container)
        self._active_user_value.setObjectName("settingsGeneralActiveUserValue")
        self._active_user_value.setTextInteractionFlags(
            self._active_user_value.textInteractionFlags()
        )
        row.addWidget(self._active_user_value, 1)

        refresh_button = QPushButton("Refresh", container)
        refresh_button.setObjectName("settingsGeneralActiveUserRefresh")
        refresh_button.setAutoDefault(False)
        refresh_button.clicked.connect(self._on_refresh_active_user)
        row.addWidget(refresh_button)

        self._refresh_active_user_value()
        return container

    def _refresh_active_user_value(self) -> None:
        window = self.window()
        key = getattr(window, "active_user_key", None) if window is not None else None
        self._active_user_value.setText(key or "(none)")

    def _on_refresh_active_user(self) -> None:
        window = self.window()
        if window is None or not hasattr(window, "refresh_active_user"):
            return
        try:
            window.refresh_active_user()
        except Exception:  # noqa: BLE001 - defensive boundary
            pass
        self._refresh_active_user_value()

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------
    def _on_language_changed(self) -> None:
        value = self._language_input.text().strip() or "en"
        if not self._update_section("general", language=value):
            self._populate()

    def _on_check_updates_changed(self, checked: bool) -> None:
        if not self._update_section("general", check_for_updates=checked):
            self._populate()

    def _on_telemetry_changed(self, checked: bool) -> None:
        if not self._update_section("general", telemetry_enabled=checked):
            self._populate()

    def _on_confirm_exit_changed(self, checked: bool) -> None:
        if not self._update_section("general", confirm_on_exit=checked):
            self._populate()