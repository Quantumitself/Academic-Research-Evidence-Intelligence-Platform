"""Tests for the StatBadge component."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from academic_platform.ui.components.stat_badge import StatBadge, StatBadgeTone  # noqa: E402


@pytest.fixture(scope="module")
def app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_label_and_value(app: QApplication) -> None:
    badge = StatBadge("Citations", "42")
    assert badge.label == "Citations"
    assert badge.value == "42"


def test_empty_value_hidden(app: QApplication) -> None:
    badge = StatBadge("Status")
    value_label = badge.findChild(type(badge._value), "statBadgeValue")  # noqa: SLF001
    assert value_label is not None
    assert not value_label.isVisible()


def test_set_value_shows(app: QApplication) -> None:
    badge = StatBadge("Status")
    badge.set_value("Open")
    value_label = badge.findChild(type(badge._value), "statBadgeValue")  # noqa: SLF001
    assert value_label is not None
    assert value_label.isVisibleTo(badge)


def test_tone_property_set(app: QApplication) -> None:
    badge = StatBadge("Status", "OK", tone=StatBadgeTone.POSITIVE)
    assert badge.tone is StatBadgeTone.POSITIVE
    assert badge.property("tone") == "positive"


def test_set_tone_updates_property(app: QApplication) -> None:
    badge = StatBadge("Status", "OK")
    badge.set_tone(StatBadgeTone.DANGER)
    assert badge.property("tone") == "danger"