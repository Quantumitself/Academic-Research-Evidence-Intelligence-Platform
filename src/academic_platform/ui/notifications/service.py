"""Notification service.

The service owns the current set of notifications and exposes operations
to publish and dismiss them. It is presentation-agnostic: it does not
import Qt. The host widget subscribes to the service and renders the
notifications.

Design decisions
----------------
- The service maintains a bounded queue. When the queue exceeds the
  maximum size, the oldest notification is dropped.
- The service emits changes through plain Python callbacks. The host
  registers one callback and re-renders on each change. This keeps the
  service independent of Qt and testable without a Qt event loop.
- Dismissal is idempotent. Dismissing an unknown identifier is a no-op.
- The service does not own timing. Automatic dismissal is a host
  responsibility; the service only carries the requested timeout.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Callable, Iterable

from academic_platform.ui.notifications.model import (
    Notification,
    NotificationSeverity,
)

Observer = Callable[[tuple[Notification, ...]], None]


class NotificationService:
    """Manages a bounded queue of notifications."""

    def __init__(self, max_size: int = 5) -> None:
        if max_size <= 0:
            raise ValueError("max_size must be positive")
        self._max_size = max_size
        self._queue: deque[Notification] = deque(maxlen=max_size)
        self._observers: list[Observer] = []

    # ------------------------------------------------------------------
    # Observer API
    # ------------------------------------------------------------------
    def add_observer(self, observer: Observer) -> None:
        """Register a callback invoked whenever the queue changes."""
        self._observers.append(observer)
        observer(self.current())

    def remove_observer(self, observer: Observer) -> None:
        """Unregister a previously registered observer. No-op if absent."""
        if observer in self._observers:
            self._observers.remove(observer)

    # ------------------------------------------------------------------
    # Publication
    # ------------------------------------------------------------------
    def publish(
        self,
        title: str,
        message: str = "",
        *,
        severity: NotificationSeverity = NotificationSeverity.INFO,
        timeout_ms: int = 6000,
    ) -> Notification:
        """Add a notification to the queue and return it."""
        notification = Notification(
            title=title,
            message=message,
            severity=severity,
            timeout_ms=timeout_ms,
        )
        self._queue.append(notification)
        self._notify()
        return notification

    def info(self, title: str, message: str = "", *, timeout_ms: int = 6000) -> Notification:
        """Publish an informational notification."""
        return self.publish(
            title, message, severity=NotificationSeverity.INFO, timeout_ms=timeout_ms
        )

    def success(
        self, title: str, message: str = "", *, timeout_ms: int = 6000
    ) -> Notification:
        """Publish a success notification."""
        return self.publish(
            title, message, severity=NotificationSeverity.SUCCESS, timeout_ms=timeout_ms
        )

    def warning(
        self, title: str, message: str = "", *, timeout_ms: int = 8000
    ) -> Notification:
        """Publish a warning notification."""
        return self.publish(
            title, message, severity=NotificationSeverity.WARNING, timeout_ms=timeout_ms
        )

    def error(
        self, title: str, message: str = "", *, timeout_ms: int = 0
    ) -> Notification:
        """Publish an error notification. Errors do not auto-dismiss."""
        return self.publish(
            title, message, severity=NotificationSeverity.ERROR, timeout_ms=timeout_ms
        )

    # ------------------------------------------------------------------
    # Dismissal
    # ------------------------------------------------------------------
    def dismiss(self, identifier: str) -> None:
        """Remove the notification with the given identifier."""
        for notification in list(self._queue):
            if notification.identifier == identifier:
                self._queue.remove(notification)
                self._notify()
                return

    def dismiss_all(self) -> None:
        """Remove all notifications."""
        if not self._queue:
            return
        self._queue.clear()
        self._notify()

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------
    def current(self) -> tuple[Notification, ...]:
        """Return the current notifications in display order."""
        return tuple(self._queue)

    def __len__(self) -> int:
        return len(self._queue)

    def __iter__(self) -> Iterable[Notification]:
        return iter(self._queue)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _notify(self) -> None:
        snapshot = self.current()
        for observer in list(self._observers):
            observer(snapshot)