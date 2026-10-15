"""Tests for the TagList component."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from academic_platform.ui.components.tag_list import Tag, TagList  # noqa: E402


@pytest.fixture(scope="module")
def app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_set_tags_replaces(app: QApplication) -> None:
    tags = TagList()
    tags.set_tags([Tag("a"), Tag("b")])
    assert [t.identifier for t in tags.tags()] == ["a", "b"]
    tags.set_tags([Tag("c")])
    assert [t.identifier for t in tags.tags()] == ["c"]


def test_tag_display_uses_label_when_present(app: QApplication) -> None:
    assert Tag("a", "Alpha").display() == "Alpha"
    assert Tag("a").display() == "a"


def test_remove_signal(app: QApplication) -> None:
    tags = TagList(removable=True)
    tags.set_tags([Tag("a"), Tag("b")])
    received: list[str] = []
    tags.tag_removed.connect(received.append)
    from PySide6.QtWidgets import QToolButton

    chip = tags._chips[0]  # noqa: SLF001
    button = chip.findChild(QToolButton, "tagChipRemove")
    assert button is not None
    button.click()
    assert received == ["a"]


def test_activate_signal(app: QApplication) -> None:
    tags = TagList(clickable=True)
    tags.set_tags([Tag("a")])
    received: list[str] = []
    tags.tag_activated.connect(received.append)
    from PySide6.QtWidgets import QPushButton

    chip = tags._chips[0]  # noqa: SLF001
    button = chip.findChild(QPushButton, "tagChipButton")
    assert button is not None
    button.click()
    assert received == ["a"]


def test_no_remove_button_when_not_removable(app: QApplication) -> None:
    tags = TagList(removable=False)
    tags.set_tags([Tag("a")])
    from PySide6.QtWidgets import QToolButton

    chip = tags._chips[0]  # noqa: SLF001
    assert chip.findChild(QToolButton, "tagChipRemove") is None