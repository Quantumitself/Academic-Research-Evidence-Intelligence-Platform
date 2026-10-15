"""Tests for the research assistant page."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import (  # noqa: E402
    QApplication,
    QListWidget,
    QPushButton,
    QStackedWidget,
)

from academic_platform.ui.pages.research_assistant import (  # noqa: E402
    AssistantSectionId,
    ResearchAssistantPage,
)


@pytest.fixture(scope="module")
def app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_page_constructs_with_all_sections(app: QApplication) -> None:
    page = ResearchAssistantPage()
    for section_id in AssistantSectionId:
        section = page.section(section_id)
        assert section.section_id is section_id


def test_page_starts_on_topic(app: QApplication) -> None:
    page = ResearchAssistantPage()
    assert page._current_section_id is AssistantSectionId.TOPIC  # noqa: SLF001


def test_page_selects_section(app: QApplication) -> None:
    page = ResearchAssistantPage()
    page.select_section(AssistantSectionId.METHODOLOGY)
    assert page._current_section_id is AssistantSectionId.METHODOLOGY  # noqa: SLF001
    stack = page.findChild(QStackedWidget, "assistantStack")
    assert stack is not None
    host = page._hosts[AssistantSectionId.METHODOLOGY]  # noqa: SLF001
    assert stack.currentWidget() is host


def test_page_sidebar_lists_every_section(app: QApplication) -> None:
    page = ResearchAssistantPage()
    listing = page.findChild(QListWidget, "assistantSectionList")
    assert listing is not None
    assert listing.count() == len(AssistantSectionId)


def test_page_sidebar_navigation(app: QApplication) -> None:
    page = ResearchAssistantPage()
    listing = page.findChild(QListWidget, "assistantSectionList")
    assert listing is not None
    for index in range(listing.count()):
        item = listing.item(index)
        if item.data(0x0100) == AssistantSectionId.RESEARCH_PLAN.value:
            listing.setCurrentItem(item)
            break
    assert page._current_section_id is AssistantSectionId.RESEARCH_PLAN  # noqa: SLF001


def test_page_preserves_work_across_navigation(app: QApplication) -> None:
    page = ResearchAssistantPage()
    topic = page.section(AssistantSectionId.TOPIC)
    topic._subject.setPlainText("Subject preserved")  # noqa: SLF001
    page.select_section(AssistantSectionId.METHODOLOGY)
    page.select_section(AssistantSectionId.TOPIC)
    assert topic.broad_subject == "Subject preserved"


def test_page_refresh_summaries(app: QApplication) -> None:
    page = ResearchAssistantPage()
    topic = page.section(AssistantSectionId.TOPIC)
    topic._subject.setPlainText("Subject")  # noqa: SLF001
    page.refresh_summaries()
    listing = page.findChild(QListWidget, "assistantSectionList")
    assert listing is not None
    found = False
    for index in range(listing.count()):
        item = listing.item(index)
        if item.data(0x0100) == AssistantSectionId.TOPIC.value:
            assert "subject" in item.text().lower()
            found = True
            break
    assert found


def test_review_section_summary_includes_sections(app: QApplication) -> None:
    page = ResearchAssistantPage()
    topic = page.section(AssistantSectionId.TOPIC)
    topic._subject.setPlainText("Set")  # noqa: SLF001
    page.select_section(AssistantSectionId.REVIEW)
    review = page.section(AssistantSectionId.REVIEW)
    text = review._summary.toPlainText()  # noqa: SLF001
    assert "Topic & Problem" in text


def test_page_header_buttons_present(app: QApplication) -> None:
    page = ResearchAssistantPage()
    for name in ("assistantRefresh", "assistantOpenProjects"):
        button = page.findChild(QPushButton, name)
        assert button is not None, name


def test_destination_requested_signal(app: QApplication) -> None:
    page = ResearchAssistantPage()
    received: list[str] = []
    page.destination_requested.connect(received.append)
    page._projects_button.click()  # noqa: SLF001
    assert received == ["research_projects"]