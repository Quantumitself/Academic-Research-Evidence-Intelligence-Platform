"""Research project summary card.

Displays the title, stage, active research question, and progress of a
research project. Emits typed signals for opening, editing, and archiving.

Design decisions
----------------
- The card accepts a plain payload rather than a domain object so that it
  can be used by the UI before the domain layer is complete.
- The stage badge tone is derived from the stage value using a fixed
  mapping. The mapping is a presentation detail and does not encode
  business rules.
- Progress is expressed as a pair of counts (completed tasks, total tasks)
  and rendered as a determinate ProgressBar. When total is zero the bar is
  hidden.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from academic_platform.ui.components.progress_bar import ProgressBar
from academic_platform.ui.components.stat_badge import StatBadge, StatBadgeTone


class ProjectStage(str, Enum):
    """Presentation stages for a research project.

    The set is deliberately small and closed. Later phases may extend it,
    but the mapping to visual tones is fixed here.
    """

    IDEA = "idea"
    DESIGN = "design"
    COLLECTION = "collection"
    ANALYSIS = "analysis"
    WRITING = "writing"
    COMPLETE = "complete"


_STAGE_LABELS: dict[ProjectStage, str] = {
    ProjectStage.IDEA: "Idea",
    ProjectStage.DESIGN: "Design",
    ProjectStage.COLLECTION: "Collection",
    ProjectStage.ANALYSIS: "Analysis",
    ProjectStage.WRITING: "Writing",
    ProjectStage.COMPLETE: "Complete",
}

_STAGE_TONES: dict[ProjectStage, StatBadgeTone] = {
    ProjectStage.IDEA: StatBadgeTone.NEUTRAL,
    ProjectStage.DESIGN: StatBadgeTone.NEUTRAL,
    ProjectStage.COLLECTION: StatBadgeTone.NEUTRAL,
    ProjectStage.ANALYSIS: StatBadgeTone.WARNING,
    ProjectStage.WRITING: StatBadgeTone.WARNING,
    ProjectStage.COMPLETE: StatBadgeTone.POSITIVE,
}


@dataclass(frozen=True, slots=True)
class ResearchProjectSummary:
    """Presentation payload for a research project card."""

    identifier: str
    title: str
    research_question: str = ""
    stage: ProjectStage = ProjectStage.IDEA
    completed_tasks: int = 0
    total_tasks: int = 0
    document_count: int = 0
    last_activity: str = ""


class ResearchProjectCard(QFrame):
    """Research project summary card."""

    opened = Signal(str)
    edited = Signal(str)
    archived = Signal(str)

    def __init__(
        self,
        project: ResearchProjectSummary,
        *,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("researchProjectCard")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self._project = project

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(8)

        title = QLabel(project.title or "(untitled project)", self)
        title.setObjectName("researchProjectCardTitle")
        title.setWordWrap(True)
        header.addWidget(title, 1)

        header.addWidget(
            StatBadge(
                "Stage",
                _STAGE_LABELS[project.stage],
                tone=_STAGE_TONES[project.stage],
                parent=self,
            ),
            0,
            Qt.AlignmentFlag.AlignTop,
        )
        layout.addLayout(header)

        if project.research_question:
            question = QLabel(project.research_question, self)
            question.setObjectName("researchProjectCardQuestion")
            question.setWordWrap(True)
            layout.addWidget(question)

        meta_row = QHBoxLayout()
        meta_row.setContentsMargins(0, 0, 0, 0)
        meta_row.setSpacing(6)
        if project.document_count:
            meta_row.addWidget(StatBadge("Documents", str(project.document_count), parent=self))
        if project.last_activity:
            meta_row.addWidget(StatBadge("Last activity", project.last_activity, parent=self))
        meta_row.addStretch(1)
        layout.addLayout(meta_row)

        if project.total_tasks > 0:
            self._progress = ProgressBar(
                total=project.total_tasks,
                label=f"Tasks: {project.completed_tasks} / {project.total_tasks}",
                parent=self,
            )
            self._progress.set_value(project.completed_tasks)
            layout.addWidget(self._progress)

        actions = QHBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(6)

        self._open_button = QPushButton("Open", self)
        self._open_button.setObjectName("researchProjectCardOpen")
        self._open_button.setEnabled(False)
        self._open_button.clicked.connect(
            lambda: self.opened.emit(project.identifier)
        )
        actions.addWidget(self._open_button)

        self._edit_button = QPushButton("Edit", self)
        self._edit_button.setObjectName("researchProjectCardEdit")
        self._edit_button.setEnabled(False)
        self._edit_button.clicked.connect(
            lambda: self.edited.emit(project.identifier)
        )
        actions.addWidget(self._edit_button)

        self._archive_button = QPushButton("Archive", self)
        self._archive_button.setObjectName("researchProjectCardArchive")
        self._archive_button.setEnabled(False)
        self._archive_button.clicked.connect(
            lambda: self.archived.emit(project.identifier)
        )
        actions.addWidget(self._archive_button)

        actions.addStretch(1)
        layout.addLayout(actions)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def enable_open(self, enabled: bool = True) -> None:
        self._open_button.setEnabled(enabled)

    def enable_edit(self, enabled: bool = True) -> None:
        self._edit_button.setEnabled(enabled)

    def enable_archive(self, enabled: bool = True) -> None:
        self._archive_button.setEnabled(enabled)

    @property
    def identifier(self) -> str:
        return self._project.identifier

    @property
    def project(self) -> ResearchProjectSummary:
        return self._project