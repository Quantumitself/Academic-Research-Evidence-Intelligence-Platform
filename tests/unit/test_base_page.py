"""Tests for the BasePage contract."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QLabel, QWidget  # noqa: E402

from academic_platform.ui.pages.base_page import BasePage  # noqa: E402


@pytest.fixture(scope="module")
def app() -> QApplication:
    instance = QApplication.instance() or QApplication([])
    return instance


def _make_page(title: str = "Test", subtitle: str = "Subtitle") -> BasePage:
    page = BasePage(title=title, subtitle=subtitle)
    content = QWidget(page)
    page._install_content(content)  # noqa: SLF001 - direct installation for test
    return page


def test_title_and_subtitle(app: QApplication) -> None:
    page = _make_page(title="Dashboard", subtitle="Overview")
    assert page.title == "Dashboard"
    assert page.subtitle == "Overview"


def test_set_subtitle_updates_label_and_emits(app: QApplication) -> None:
    page = _make_page()
    received: list[str] = []
    page.subtitle_changed.connect(received.append)
    page.set_subtitle("New")
    assert page.subtitle == "New"
    assert received == ["New"]


def test_set_subtitle_empty_hides_label(app: QApplication) -> None:
    page = _make_page(subtitle="Initial")
    page.set_subtitle("")
    labels = page.findChildren(QLabel)
    subtitle_labels = [label for label in labels if label.objectName() == "pageSubtitle"]
    assert subtitle_labels
    assert not subtitle_labels[0].isVisible()


def test_add_header_action(app: QApplication) -> None:
    page = _make_page()
    action = QLabel("A", page)
    page.add_header_action(action)


def test_content_installed_once(app: QApplication) -> None:
    page = _make_page()
    with pytest.raises(RuntimeError):
        page._install_content(QWidget(page))  # noqa: SLF001 - contract test


def test_default_can_close_true(app: QApplication) -> None:
    page = _make_page()
    assert page.can_close() is True


def test_lifecycle_hooks_do_not_raise(app: QApplication) -> None:
    page = _make_page()
    page.on_activated()
    page.on_deactivated()


def test_show_empty_state_without_empty_widget_is_noop(app: QApplication) -> None:
    page = _make_page()
    page.show_empty_state()