"""Tests for the NotificationService."""

from __future__ import annotations

import pytest

from academic_platform.ui.notifications.model import NotificationSeverity
from academic_platform.ui.notifications.service import NotificationService


def test_publish_adds_notification() -> None:
    service = NotificationService()
    notification = service.publish("Title", "Message")
    assert service.current() == (notification,)


def test_max_size_enforced() -> None:
    service = NotificationService(max_size=3)
    for index in range(5):
        service.publish(f"T{index}")
    assert len(service) == 3
    # The oldest two notifications were dropped.
    titles = [n.title for n in service.current()]
    assert titles == ["T2", "T3", "T4"]


def test_severity_helpers() -> None:
    service = NotificationService()
    assert service.info("a").severity is NotificationSeverity.INFO
    assert service.success("b").severity is NotificationSeverity.SUCCESS
    assert service.warning("c").severity is NotificationSeverity.WARNING
    assert service.error("d").severity is NotificationSeverity.ERROR


def test_error_does_not_auto_dismiss() -> None:
    service = NotificationService()
    notification = service.error("boom")
    assert notification.timeout_ms == 0


def test_dismiss_by_identifier() -> None:
    service = NotificationService()
    first = service.publish("A")
    service.publish("B")
    service.dismiss(first.identifier)
    assert len(service) == 1
    assert service.current()[0].title == "B"


def test_dismiss_unknown_is_noop() -> None:
    service = NotificationService()
    service.publish("A")
    service.dismiss("nonexistent")
    assert len(service) == 1


def test_dismiss_all() -> None:
    service = NotificationService()
    service.publish("A")
    service.publish("B")
    service.dismiss_all()
    assert len(service) == 0


def test_observer_called_on_publish() -> None:
    service = NotificationService()
    seen: list[tuple] = []
    service.add_observer(lambda notifications: seen.append(notifications))
    service.publish("A")
    assert len(seen) == 2  # initial + one publish
    assert seen[-1][0].title == "A"


def test_observer_called_on_dismiss() -> None:
    service = NotificationService()
    seen: list[tuple] = []
    service.add_observer(lambda notifications: seen.append(notifications))
    notification = service.publish("A")
    service.dismiss(notification.identifier)
    assert seen[-1] == ()


def test_remove_observer_stops_callbacks() -> None:
    service = NotificationService()
    seen: list[tuple] = []

    def observer(notifications: tuple) -> None:
        seen.append(notifications)

    service.add_observer(observer)
    service.remove_observer(observer)
    service.publish("A")
    assert len(seen) == 1  # only the initial call


def test_invalid_max_size_raises() -> None:
    with pytest.raises(ValueError):
        NotificationService(max_size=0)