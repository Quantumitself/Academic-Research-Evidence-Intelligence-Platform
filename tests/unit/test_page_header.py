"""Tests for the PageHeader component."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QLabel  # noqa: E402

from academic_platform.ui.components.page_header import PageHeader  # noqa: E402


@pytest.fixture(scope="module")
def app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_title_and_subtitle(app: QApplication) -> None:
    header = PageHeader("Title", "Subtitle")
    assert header.title == "Title"
    assert header.subtitle == "Subtitle"


def test_subtitle_empty_hidden(app: QApplication) -> None:
    header = PageHeader("Title")
    labels = header.findChildren(QLabel)
    subtitle = [lbl for lbl in labels if lbl.objectName() == "pageSubtitle"]
    assert subtitle
    assert not subtitle[0].isVisible()


def test_set_subtitle_toggles_visibility(app: QApplication) -> None:
    header = PageHeader("Title")
    header.set_subtitle("Visible")
    labels = header.findChildren(QLabel)
    subtitle = [lbl for lbl in labels if lbl.objectName() == "pageSubtitle"][0]
    assert subtitle.isVisibleTo(header)
    header.set_subtitle("")
    assert not subtitle.isVisibleTo(header)


def test_add_action(app: QApplication) -> None:
    header = PageHeader("Title")
    action = QLabel("A", header)
    header.add_action(action)