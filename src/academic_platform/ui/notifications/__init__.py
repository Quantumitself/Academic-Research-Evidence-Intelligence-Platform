"""Non-blocking notification system.

Notifications are transient messages displayed over the main window. They
are used for events that do not require a decision: a background task
finished, a source returned no results, a document was imported.

Public surface
--------------
- ``Notification`` — immutable value describing a single notification.
- ``NotificationSeverity`` — severity levels.
- ``NotificationService`` — the service that manages a queue of
  notifications and delivers them to a host widget.
- ``NotificationHost`` — the widget that renders notifications over the
  main window.
"""

from academic_platform.ui.notifications.model import (
    Notification,
    NotificationSeverity,
)
from academic_platform.ui.notifications.host import NotificationHost
from academic_platform.ui.notifications.service import NotificationService

__all__ = [
    "Notification",
    "NotificationHost",
    "NotificationService",
    "NotificationSeverity",
]