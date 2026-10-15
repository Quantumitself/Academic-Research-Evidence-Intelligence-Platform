"""Tests for SectionCard state transitions."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QLabel  # noqa: E402

from academic_platform.ui.components.section_card import SectionCard  # noqa: E402


@pytest.fixture(scope="module")
def app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_content_installation(app: QApplication) -> None:
    card = SectionCard("Title")
    content = QLabel("body")
    card.set_content_widget(content)
    assert card._content_container is content  # noqa: SLF001


def test_show_content_requires_content(app: QApplication) -> None:
    card = SectionCard("Title")
    with pytest.raises(RuntimeError):
        card.show_content()


def test_show_loading_creates_indicator(app: QApplication) -> None:
    card = SectionCard("Title")
    card.show_loading("Working…")
    assert card._loading_index is not None  # noqa: SLF001


def test_show_loading_reuses_indicator(app: QApplication) -> None:
    card = SectionCard("Title")
    card.show_loading("Working…")
    first_index = card._loading_index  # noqa: SLF001
    card.show_loading("Still working…")
    assert card._loading_index == first_index  # noqa: SLF001


def test_show_empty_creates_and_reuses(app: QApplication) -> None:
    card = SectionCard("Title")
    card.show_empty("Empty", "Nothing here")
    index = card._empty_index  # noqa: SLF001
    card.show_empty("Empty2", "Nothing here 2")
    assert card._empty_index == index  # noqa: SLF001
    widget = card._body_stack.widget(index)  # noqa: SLF001
    assert widget is not None
    assert widget.findChild(QLabel, "emptyStateTitle").text() == "Empty2"  # type: ignore[union-attr]


def test_show_error_creates_and_reuses(app: QApplication) -> None:
    card = SectionCard("Title")
    card.show_error("Boom", retryable=True)
    index = card._error_index  # noqa: SLF001
    card.show_error("Boom2", retryable=False)
    assert card._error_index == index  # noqa: SLF001
    error = card.error_state()
    assert error is not None
    assert error.message == "Boom2"
    assert not error.retry_button.isVisible()


def test_add_header_action(app: QApplication) -> None:
    card = SectionCard("Title")
    action = QLabel("A", card)
    card.add_header_action(action)


def test_set_title(app: QApplication) -> None:
    card = SectionCard("Title")
    card.set_title("New")
    label = card.findChild(QLabel, "sectionCardTitle")
    assert label is not None
    assert label.text() == "New"


def test_replace_content_widget(app: QApplication) -> None:
    card = SectionCard("Title")
    first = QLabel("first", card)
    second = QLabel("second", card)
    card.set_content_widget(first)
    card.set_content_widget(second)
    assert card._content_container is second  # noqa: SLF001