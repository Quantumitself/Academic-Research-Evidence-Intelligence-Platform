"""Tests for the research assistant sections."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from academic_platform.ui.pages.research_assistant.section_base import (  # noqa: E402
    AssistantSectionId,
)
from academic_platform.ui.pages.research_assistant.sections import (  # noqa: E402
    create_section,
)


@pytest.fixture(scope="module")
def app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_every_section_is_constructible(app: QApplication) -> None:
    for section_id in AssistantSectionId:
        section = create_section(section_id)
        assert section.section_id is section_id
        assert section.objectName() == f"assistantSection_{section_id.value}"


def test_unknown_section_raises(app: QApplication) -> None:
    with pytest.raises(KeyError):
        create_section("nonexistent")  # type: ignore[arg-type]


def test_topic_section_summary(app: QApplication) -> None:
    section = create_section(AssistantSectionId.TOPIC)
    assert section.summary() == ""
    # The section exposes its editors through public accessors.
    section._subject.setPlainText("Subject")
    assert "subject" in section.summary().lower()


def test_title_section_candidates(app: QApplication) -> None:
    section = create_section(AssistantSectionId.TITLE_BUILDER)
    section._candidate_input.setText("A candidate")
    section._on_add_candidate()
    assert section.candidates() == ["A candidate"]


def test_title_section_working_title(app: QApplication) -> None:
    section = create_section(AssistantSectionId.TITLE_BUILDER)
    section._working_title.setText("Working")
    assert section.working_title() == "Working"
    section._candidate_input.setText("Alt")
    section._on_add_candidate()
    assert "1 candidate" in section.summary()


def test_questions_section_entries(app: QApplication) -> None:
    section = create_section(AssistantSectionId.RESEARCH_QUESTIONS)
    section._entry_input.setText("A sub question")
    section._on_add_entry()
    entries = section.entries()
    assert len(entries) == 1
    assert entries[0].kind.value in {"main", "sub"}


def test_theories_section_entries(app: QApplication) -> None:
    section = create_section(AssistantSectionId.THEORIES)
    section._name_input.setText("Theory X")
    section._on_add_entry()
    assert section.entries() == ["Theory X"]


def test_methodology_section_candidates(app: QApplication) -> None:
    section = create_section(AssistantSectionId.METHODOLOGY)
    section._method_combo.setCurrentIndex(0)
    section._on_add_candidate()
    assert len(section.candidates()) == 1
    section._candidates.setCurrentRow(0)
    section._on_choose_candidate()
    assert section.chosen_methodology() is not None


def test_statistical_section_candidates(app: QApplication) -> None:
    section = create_section(AssistantSectionId.STATISTICAL_ADVISOR)
    section._method_combo.setCurrentIndex(0)
    section._on_add_candidate()
    assert len(section.candidates()) == 1
    section._candidates.setCurrentRow(0)
    section._on_choose_candidate()
    assert section.chosen_method() is not None


def test_plan_section_fields(app: QApplication) -> None:
    section = create_section(AssistantSectionId.RESEARCH_PLAN)
    assert section.populated_fields() == []
    section._fields["background"].setPlainText("Background text")  # type: ignore[attr-defined]
    assert "background" in section.populated_fields()
    assert "1 /" in section.summary()


def test_sources_section_sources(app: QApplication) -> None:
    section = create_section(AssistantSectionId.SOURCES)
    section._source_input.setText("Smith 2020")
    section._on_add_source()
    assert section.sources() == ["Smith 2020"]


def test_review_section_summary_provider(app: QApplication) -> None:
    section = create_section(AssistantSectionId.REVIEW)
    section.set_summary_provider(lambda: "Summary text")
    assert "Summary text" in section.summary()


def test_review_section_without_provider(app: QApplication) -> None:
    section = create_section(AssistantSectionId.REVIEW)
    assert "not available" in section._summary.toPlainText().lower()  # noqa: SLF001


def test_section_reset_clears_state(app: QApplication) -> None:
    section = create_section(AssistantSectionId.THEORIES)
    section._name_input.setText("X")
    section._on_add_entry()
    assert section.summary()
    section.reset()
    assert section.summary() == ""