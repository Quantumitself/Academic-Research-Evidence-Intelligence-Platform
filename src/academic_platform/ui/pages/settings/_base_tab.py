"""Base class for settings tabs.

A settings tab reads its initial state from the settings service and writes
changes back through the service. The base class provides:

- A reference to the settings service.
- A reference to the notification service, used to report persistence
  failures.
- A protected ``_update_section`` helper that catches ``SettingsError``
  and surfaces it through the notification service.
- A ``reload`` method invoked when the settings change outside the tab
  (for example, when another tab modifies the same section).

Tabs must not import the settings schema directly beyond what they need;
they read the current settings through ``self.settings``.
"""

from __future__ import annotations

import logging

from PySide6.QtWidgets import QWidget

from academic_platform.app.settings import SettingsError, SettingsSchema, SettingsService
from academic_platform.ui.notifications import NotificationService

_logger = logging.getLogger(__name__)


class SettingsTab(QWidget):
    """Base class for a single tab of the Settings page."""

    def __init__(
        self,
        settings_service: SettingsService,
        notification_service: NotificationService | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._settings_service = settings_service
        self._notification_service = notification_service
        self._loading = False

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------
    @property
    def settings(self) -> SettingsSchema:
        """Return the current validated settings."""
        return self._settings_service.settings

    # ------------------------------------------------------------------
    # Update helpers
    # ------------------------------------------------------------------
    def _update_section(self, section: str, **changes) -> bool:
        """Persist changes to a settings section.

        Returns True on success and False when the update is rejected. On
        failure, the problem is reported through the notification service
        and the log. Callers should re-read the current settings and reset
        their controls accordingly.
        """
        if self._loading:
            return False
        try:
            self._settings_service.update_section(section, **changes)
        except SettingsError as exc:
            _logger.warning("Settings update rejected: %s", exc)
            if self._notification_service is not None:
                self._notification_service.error(
                    "Settings update rejected",
                    str(exc),
                )
            return False
        return True

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def reload(self) -> None:
        """Re-read settings and refresh every control on the tab.

        The base implementation is a no-op. Subclasses override to refresh
        their controls. Implementations must set ``self._loading = True``
        while populating controls so that user-facing signals do not
        trigger redundant persistence calls.
        """