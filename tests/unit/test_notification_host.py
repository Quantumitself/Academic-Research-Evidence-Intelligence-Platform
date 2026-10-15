"""Tests for the NotificationHost."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QWidget  # noqa: E402

from academic_platform.ui.notifications.host import NotificationHost  # noqa: E402
from academic_platform.ui.notifications.service import NotificationService  # noqa: E402


@pytest.fixture(scope="module")
def app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_publishing_adds_card(app: QApplication) -> None:
    parent = QWidget()
    parent.resize(800, 600)
    service = NotificationService()
    host = NotificationHost(parent=parent, service=service)
    service.publish("Title", "Message")
    card = host.container().findChild(
        type(host.container()),
        "notificationCard",
    )
    # The card is a QFrame; assert at least one exists.
    from PySide6.QtWidgets import QFrame

    cards = host.container().findChildren(QFrame, "notificationCard")
    assert cards


def test_dismiss_removes_card(app: QApplication) -> None:
    from PySide6.QtWidgets import QFrame

    parent = QWidget()
    parent.resize(800, 600)
    service = NotificationService()
    host = NotificationHost(parent=parent, service=service)
    notification = service.publish("Title")
    assert host.container().findChildren(QFrame, "notificationCard")
    service.dismiss(notification.identifier)
    assert not host.container().findChildren(QFrame, "notificationCard")