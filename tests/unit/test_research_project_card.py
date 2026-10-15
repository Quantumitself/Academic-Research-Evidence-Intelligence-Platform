"""Tests for the ResearchProjectCard component."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QPushButton  # noqa: E402

from academic_platform.ui.components.research_project_card import (  # noqa: E402
    ProjectStage,
    ResearchProjectCard,
    ResearchProjectSummary,
)


@pytest.fixture(scope="module")
def app() -> QApplication:
    return QApplication.instance() or QApplication([])


def _summary() -> ResearchProjectSummary:
    return ResearchProjectSummary(
        identifier="proj1",
        title="Project A",
        research_question="What?",
        stage=ProjectStage.DESIGN,
        completed_tasks=2,
        total_tasks=5,
        document_count=10,
        last_activity="2024-01-01",
    )


def test_open_signal(app: QApplication) -> None:
    card = ResearchProjectCard(_summary())
    card.enable_open()
    received: list[str] = []
    card.opened.connect(received.append)
    button = card.findChild(QPushButton, "researchProjectCardOpen")
    assert button is not None
    button.click()
    assert received == ["proj1"]


def test_progress_shown_when_tasks(app: QApplication) -> None:
    card = ResearchProjectCard(_summary())
    from academic_platform.ui.components.progress_bar import ProgressBar

    progress = card.findChild(ProgressBar)
    assert progress is not None
    assert progress.total == 5
    assert progress.value == 2


def test_progress_hidden_when_no_tasks(app: QApplication) -> None:
    card = ResearchProjectCard(
        ResearchProjectSummary(identifier="p", title="T", total_tasks=0)
    )
    from academic_platform.ui.components.progress_bar import ProgressBar

    assert card.findChild(ProgressBar) is None


def test_actions_disabled_by_default(app: QApplication) -> None:
    card = ResearchProjectCard(_summary())
    for name in (
        "researchProjectCardOpen",
        "researchProjectCardEdit",
        "researchProjectCardArchive",
    ):
        button = card.findChild(QPushButton, name)
        assert button is not None
        assert not button.isEnabled()