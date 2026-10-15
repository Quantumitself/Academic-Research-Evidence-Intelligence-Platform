"""Notification host widget.

The host renders notifications as stacked cards anchored to the bottom-right
of its parent widget. Each card carries a title, an optional message, a
severity indicator, and a close button. Cards fade out automatically after
their timeout expires unless the timeout is zero.

Design decisions
----------------
- The host is a child of the main window, not a separate window. It is
  raised above other widgets and made transparent to mouse events outside
  the notification area.
- Each notification card is a separate widget so that dismissal can be
  performed per notification.
- Automatic dismissal uses a per-card ``QTimer``. The timer is stopped
  when the card is dismissed manually.
- The host repositions itself when its parent is resized.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, Qt, QTimer
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from academic_platform.ui.notifications.model import (
    Notification,
    NotificationSeverity,
)
from academic_platform.ui.notifications.service import NotificationService

_CARD_WIDTH = 340
_MARGIN = 16
_SPACING = 8


class _NotificationCard(QFrame):
    """Internal notification card. Not part of the public API."""

    def __init__(
        self,
        notification: Notification,
        service: NotificationService,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("notificationCard")
        self.setProperty("severity", notification.severity.value)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setFixedWidth(_CARD_WIDTH)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 10, 12)
        layout.setSpacing(4)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(6)

        title = QLabel(notification.title, self)
        title.setObjectName("notificationTitle")
        title.setWordWrap(True)
        header.addWidget(title, 1)

        close_button = QPushButton("\u00D7", self)
        close_button.setObjectName("notificationClose")
        close_button.setFixedWidth(22)
        close_button.setAutoDefault(False)
        close_button.clicked.connect(
            lambda: service.dismiss(notification.identifier)
        )
        header.addWidget(close_button, 0, Qt.AlignmentFlag.AlignTop)

        layout.addLayout(header)

        if notification.message:
            message = QLabel(notification.message, self)
            message.setObjectName("notificationMessage")
            message.setWordWrap(True)
            layout.addWidget(message)

        self._timer: QTimer | None = None
        if notification.timeout_ms > 0:
            self._timer = QTimer(self)
            self._timer.setSingleShot(True)
            self._timer.setInterval(notification.timeout_ms)
            self._timer.timeout.connect(
                lambda: service.dismiss(notification.identifier)
            )
            self._timer.start()


class NotificationHost(QObject):
    """Renders notifications over a parent widget."""

    def __init__(
        self,
        parent: QWidget,
        service: NotificationService,
    ) -> None:
        super().__init__(parent)
        self._parent = parent
        self._service = service
        self._container = QWidget(parent)
        self._container.setObjectName("notificationHost")
        self._container.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self._container.raise_()

        layout = QVBoxLayout(self._container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(_SPACING)
        layout.setAlignment(Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignRight)
        self._layout = layout

        self._cards: dict[str, _NotificationCard] = {}

        service.add_observer(self._on_notifications_changed)
        parent.installEventFilter(self)
        self._reposition()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def container(self) -> QWidget:
        """Return the container widget for tests and diagnostics."""
        return self._container

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------
    def _on_notifications_changed(self, notifications: tuple[Notification, ...]) -> None:
        incoming = {n.identifier: n for n in notifications}

        # Remove cards for dismissed notifications.
        for identifier in list(self._cards.keys()):
            if identifier not in incoming:
                card = self._cards.pop(identifier)
                self._layout.removeWidget(card)
                card.setParent(None)
                card.deleteLater()

        # Add cards for new notifications.
        for notification in notifications:
            if notification.identifier in self._cards:
                continue
            card = _NotificationCard(notification, self._service, self._container)
            self._cards[notification.identifier] = card
            self._layout.addWidget(card)

        # Reorder existing cards to match the service order.
        for index, notification in enumerate(notifications):
            card = self._cards.get(notification.identifier)
            if card is None:
                continue
            self._layout.removeWidget(card)
            self._layout.insertWidget(index, card)

        self._reposition()

    # ------------------------------------------------------------------
    # Positioning
    # ------------------------------------------------------------------
    def _reposition(self) -> None:
        parent_size = self._parent.size()
        self._container.adjustSize()
        container_size = self._container.sizeHint()
        width = max(container_size.width(), _CARD_WIDTH)
        height = container_size.height()
        x = max(_MARGIN, parent_size.width() - width - _MARGIN)
        y = max(_MARGIN, parent_size.height() - height - _MARGIN)
        self._container.setGeometry(x, y, width, height)
        self._container.raise_()

    # ------------------------------------------------------------------
    # Event filter
    # ------------------------------------------------------------------
    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802 - Qt API
        if watched is self._parent and event.type() in (
            QEvent.Type.Resize,
            QEvent.Type.Show,
        ):
            self._reposition()
        return super().eventFilter(watched, event)