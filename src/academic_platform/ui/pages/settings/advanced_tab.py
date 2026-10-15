"""Advanced settings tab.

The Advanced tab surfaces network behavior and diagnostic actions. It is
the only tab that performs actions beyond editing settings: it exposes
buttons to open the configuration file directory, open the log directory,
and reset all settings to schema defaults.
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from academic_platform.app.configuration import AppDirectories
from academic_platform.app.settings import SettingsService
from academic_platform.ui.dialogs.confirm_dialog import ConfirmResult
from academic_platform.ui.dialogs.dialog_factory import DialogFactory
from academic_platform.ui.notifications import NotificationService
from academic_platform.ui.pages.settings._base_tab import SettingsTab

_logger = logging.getLogger(__name__)


class AdvancedSettingsTab(SettingsTab):
    """Advanced preferences and diagnostic actions."""

    #: Emitted after the user resets settings to defaults.
    settings_reset = Signal()

    def __init__(
        self,
        settings_service: SettingsService,
        directories: AppDirectories,
        notification_service: NotificationService | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(settings_service, notification_service, parent)
        self._directories = directories
        self.setObjectName("settingsTabAdvanced")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(10)

        self._offline = QCheckBox("Work offline (no outbound requests)", self)
        self._offline.setObjectName("settingsAdvancedOffline")
        self._offline.toggled.connect(self._on_offline_changed)
        form.addRow("", self._offline)

        self._system_proxy = QCheckBox("Use system proxy configuration", self)
        self._system_proxy.setObjectName("settingsAdvancedSystemProxy")
        self._system_proxy.toggled.connect(self._on_system_proxy_changed)
        form.addRow("", self._system_proxy)

        self._user_agent_suffix = QLineEdit(self)
        self._user_agent_suffix.setObjectName("settingsAdvancedUserAgentSuffix")
        self._user_agent_suffix.setPlaceholderText("Optional User-Agent suffix")
        self._user_agent_suffix.setMaxLength(128)
        self._user_agent_suffix.editingFinished.connect(self._on_user_agent_changed)
        form.addRow("User-Agent suffix", self._user_agent_suffix)

        layout.addLayout(form)

        layout.addWidget(self._build_paths_section())

        actions = QHBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(8)

        open_config = QPushButton("Open configuration folder", self)
        open_config.setObjectName("settingsAdvancedOpenConfigFolder")
        open_config.clicked.connect(self._on_open_config_folder)
        actions.addWidget(open_config)

        open_logs = QPushButton("Open log folder", self)
        open_logs.setObjectName("settingsAdvancedOpenLogFolder")
        open_logs.clicked.connect(self._on_open_log_folder)
        actions.addWidget(open_logs)

        reset = QPushButton("Reset to defaults", self)
        reset.setObjectName("settingsAdvancedReset")
        reset.clicked.connect(self._on_reset)
        actions.addWidget(reset)

        actions.addStretch(1)
        layout.addLayout(actions)
        layout.addStretch(1)

        self._populate()

    # ------------------------------------------------------------------
    # Construction helpers
    # ------------------------------------------------------------------
    def _build_paths_section(self) -> QWidget:
        container = QWidget(self)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        heading = QLabel("Resolved paths", container)
        heading.setObjectName("settingsAdvancedPathsHeading")
        layout.addWidget(heading)

        for label, path in (
            ("Configuration", self._directories.config_file),
            ("Database", self._directories.database_file),
            ("Logs", self._directories.logs_dir),
            ("Managed library", self._directories.managed_library_dir),
            ("Exports", self._directories.exports_dir),
        ):
            line = QLabel(f"{label}: {path}", container)
            line.setObjectName("settingsAdvancedPathLine")
            line.setWordWrap(True)
            line.setTextInteractionFlags(line.textInteractionFlags())
            layout.addWidget(line)

        return container

    # ------------------------------------------------------------------
    # Population
    # ------------------------------------------------------------------
    def _populate(self) -> None:
        self._loading = True
        try:
            network = self.settings.network
            self._offline.setChecked(network.offline_mode)
            self._system_proxy.setChecked(network.use_system_proxy)
            self._user_agent_suffix.setText(network.user_agent_suffix)
        finally:
            self._loading = False

    def reload(self) -> None:
        self._populate()

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------
    def _on_offline_changed(self, checked: bool) -> None:
        if not self._update_section("network", offline_mode=checked):
            self._populate()

    def _on_system_proxy_changed(self, checked: bool) -> None:
        if not self._update_section("network", use_system_proxy=checked):
            self._populate()

    def _on_user_agent_changed(self) -> None:
        value = self._user_agent_suffix.text().strip()
        if not self._update_section("network", user_agent_suffix=value):
            self._populate()

    def _on_open_config_folder(self) -> None:
        self._open_path(self._directories.config_dir)

    def _on_open_log_folder(self) -> None:
        self._open_path(self._directories.logs_dir)

    def _on_reset(self) -> None:
        outcome = DialogFactory.confirm(
            self,
            "Reset settings to defaults",
            (
                "This will replace every setting with its default value. "
                "Your library, projects, and other data are not affected."
            ),
            confirm_label="Reset",
            cancel_label="Cancel",
            destructive=True,
            default_to_confirm=False,
        )
        if outcome.result is not ConfirmResult.CONFIRMED:
            return
        try:
            self._settings_service.reset_to_defaults()
        except Exception as exc:  # noqa: BLE001 - boundary
            _logger.exception("Settings reset failed")
            if self._notification_service is not None:
                self._notification_service.error(
                    "Settings reset failed",
                    str(exc),
                )
            return
        self._populate()
        self.settings_reset.emit()
        if self._notification_service is not None:
            self._notification_service.success(
                "Settings reset",
                "Every setting has been restored to its default value.",
            )

    # ------------------------------------------------------------------
    # Platform open helper
    # ------------------------------------------------------------------
    @staticmethod
    def _open_path(path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True)
        target = str(path)
        try:
            if sys.platform.startswith("win"):
                os.startfile(target)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", target])
            else:
                subprocess.Popen(["xdg-open", target])
        except OSError as exc:
            _logger.warning("Unable to open path %s: %s", path, exc)