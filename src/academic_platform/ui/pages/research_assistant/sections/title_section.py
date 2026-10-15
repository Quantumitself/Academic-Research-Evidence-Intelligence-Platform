"""Title Builder section.

The section captures the working title and a list of candidate titles.
The user may generate candidates from the topic draft, accept or reject
them, promote a candidate to the working title, and remove candidates.
The section is backed by the ``TitleBuilderService``.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from academic_platform.application.title_builder.errors import (
    TitleBuilderError,
)
from academic_platform.application.title_builder.model import (
    TitleCandidate,
    TitleState,
)
from academic_platform.application.title_builder.service import (
    TitleBuilderService,
)
from academic_platform.ui.dialogs.dialog_factory import DialogFactory
from academic_platform.ui.dialogs.message_dialog import MessageKind
from academic_platform.ui.pages.research_assistant.section_base import (
    AssistantSection,
    AssistantSectionId,
)
from academic_platform.ui.pages.research_assistant.sections._shared import (
    make_line_field,
)
from academic_platform.ui.pages.research_assistant.sections.title_comparison_panel import (
    TitleComparisonPanel,
)


_logger = logging.getLogger(__name__)


class TitleBuilderSection(AssistantSection):
    """Title Builder section backed by the title builder service."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(AssistantSectionId.TITLE_BUILDER, parent=parent)
        self._service: TitleBuilderService | None = None
        self._project_key: str = ""

        content = QWidget(self)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        self._working_title = make_line_field(
            content,
            "Working title",
            placeholder="The current working title.",
        )

        self._candidate_input = QLineEdit(content)
        self._candidate_input.setObjectName("titleCandidateInput")
        self._candidate_input.setPlaceholderText(
            "Type a candidate title manually."
        )
        layout.addWidget(self._candidate_input)

        actions = QHBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(6)

        self._generate_button = QPushButton("Generate candidates", content)
        self._generate_button.setObjectName("titleGenerateCandidates")
        self._generate_button.setAutoDefault(False)
        self._generate_button.setEnabled(False)
        self._generate_button.clicked.connect(self._on_generate_candidates)
        actions.addWidget(self._generate_button)

        self._refresh_button = QPushButton("Refresh", content)
        self._refresh_button.setObjectName("titleRefreshCandidates")
        self._refresh_button.setAutoDefault(False)
        self._refresh_button.clicked.connect(self._reload_candidates)
        actions.addWidget(self._refresh_button)

        actions.addStretch(1)
        layout.addLayout(actions)

        self._candidates = QListWidget(content)
        self._candidates.setObjectName("titleCandidateList")
        self._candidates.currentItemChanged.connect(self._on_candidate_selected)
        self._candidates.itemDoubleClicked.connect(
            lambda _item: self._on_accept_candidate()
        )
        layout.addWidget(self._candidates, 1)

        candidate_actions = QHBoxLayout()
        candidate_actions.setContentsMargins(0, 0, 0, 0)
        candidate_actions.setSpacing(6)

        self._accept_button = QPushButton("Accept", content)
        self._accept_button.setObjectName("titleAcceptCandidate")
        self._accept_button.setAutoDefault(False)
        self._accept_button.setEnabled(False)
        self._accept_button.clicked.connect(self._on_accept_candidate)
        candidate_actions.addWidget(self._accept_button)

        self._reject_button = QPushButton("Reject", content)
        self._reject_button.setObjectName("titleRejectCandidate")
        self._reject_button.setAutoDefault(False)
        self._reject_button.setEnabled(False)
        self._reject_button.clicked.connect(self._on_reject_candidate)
        candidate_actions.addWidget(self._reject_button)

        self._use_button = QPushButton("Use as working title", content)
        self._use_button.setObjectName("titleUseCandidate")
        self._use_button.setAutoDefault(False)
        self._use_button.setEnabled(False)
        self._use_button.clicked.connect(self._on_use_candidate)
        candidate_actions.addWidget(self._use_button)

        candidate_actions.addStretch(1)
        layout.addLayout(candidate_actions)

        self._details = QPlainTextEdit(content)
        self._details.setObjectName("titleCandidateDetails")
        self._details.setReadOnly(True)
        self._details.setMinimumHeight(140)
        layout.addWidget(self._details)

        self._comparison_panel = TitleComparisonPanel(content)
        self._comparison_panel.working_title_selected.connect(
            self._on_working_title_selected
        )
        layout.addWidget(self._comparison_panel)

        self._install_content(content)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def attach_service(
        self,
        service: TitleBuilderService,
        project_key: str,
    ) -> None:
        """Attach the service and the project whose candidates are shown."""
        self._service = service
        self._project_key = project_key
        self._generate_button.setEnabled(True)
        self._comparison_panel.attach_service(service, project_key)
        self._reload_candidates()

    def set_project(self, project_key: str) -> None:
        """Change the project whose candidates are shown."""
        self._project_key = project_key
        self._comparison_panel.set_project(project_key)
        self._reload_candidates()

    def candidate_input_text(self) -> str:
        return self._candidate_input.text().strip()

    def set_candidate_input_text(self, value: str) -> None:
        self._candidate_input.setText(value)

    def candidate_models(self) -> list[TitleCandidate]:
        """Return the full candidate models from the list."""
        results: list[TitleCandidate] = []
        for index in range(self._candidates.count()):
            data = self._candidates.item(index).data(Qt.ItemDataRole.UserRole)
            if isinstance(data, TitleCandidate):
                results.append(data)
        return results

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------
    def _on_generate_candidates(self) -> None:
        if self._service is None or not self._project_key:
            return
        draft = self._current_topic_draft()
        if draft is None:
            self._show_error(
                "Topic workspace unavailable",
                "The topic draft could not be read.",
            )
            return
        try:
            self._service.generate_for_project(self._project_key, draft)
        except TitleBuilderError as exc:
            self._show_error("Unable to generate candidates", str(exc))
            return
        self._reload_candidates()

    def _on_candidate_selected(
        self,
        current: QListWidgetItem | None,
        _previous: QListWidgetItem | None,
    ) -> None:
        enabled = current is not None
        self._accept_button.setEnabled(enabled)
        self._reject_button.setEnabled(enabled)
        self._use_button.setEnabled(enabled)
        if current is not None:
            candidate = current.data(Qt.ItemDataRole.UserRole)
            if isinstance(candidate, TitleCandidate):
                self._details.setPlainText(self._render_details(candidate))
        else:
            self._details.setPlainText("")

    def _on_accept_candidate(self) -> None:
        candidate = self._selected_candidate()
        if candidate is None or self._service is None or not self._project_key:
            return
        if candidate.identifier == "manual":
            return
        try:
            self._service.set_state(
                self._project_key,
                _candidate_row_id(candidate),
                TitleState.ACCEPTED,
            )
        except TitleBuilderError as exc:
            self._show_error("Unable to accept candidate", str(exc))
            return
        self._reload_candidates()

    def _on_reject_candidate(self) -> None:
        candidate = self._selected_candidate()
        if candidate is None or self._service is None or not self._project_key:
            return
        if candidate.identifier == "manual":
            return
        try:
            self._service.set_state(
                self._project_key,
                _candidate_row_id(candidate),
                TitleState.REJECTED,
            )
        except TitleBuilderError as exc:
            self._show_error("Unable to reject candidate", str(exc))
            return
        self._reload_candidates()

    def _on_use_candidate(self) -> None:
        candidate = self._selected_candidate()
        if candidate is None:
            return
        self._working_title.setText(candidate.title)

    def _on_add_candidate(self) -> None:
        """Add the text in the candidate input to the candidate list.

        Used by the manual entry workflow. If a title builder service is
        attached, the candidate is not persisted here — persistence of
        manual candidates is delivered in a later phase. The list entry
        is added so the user can see, select, and promote the title.
        """
        title = self._candidate_input.text().strip()
        if not title:
            return
        item = QListWidgetItem(title)
        item.setData(Qt.ItemDataRole.UserRole, None)
        self._candidates.addItem(item)
        self._candidate_input.clear()
        self._candidates.setCurrentItem(item)

    def add_candidate(self, title: str) -> None:
        """Public entry point mirroring ``_on_add_candidate``."""
        self._candidate_input.setText(title)
        self._on_add_candidate()

    # ------------------------------------------------------------------
    # Contract
    # ------------------------------------------------------------------
    def candidates(self) -> list[str]:
        """Return the display text of every candidate in the list."""
        return [
            self._candidates.item(index).text()
            for index in range(self._candidates.count())
        ]

    def working_title(self) -> str:
        return self._working_title.text().strip()

    def summary(self) -> str:
        parts: list[str] = []
        if self.working_title():
            parts.append("working title set")
        count = self._candidates.count()
        if count:
            parts.append(f"{count} candidate(s)")
        return " · ".join(parts)

    def reset(self) -> None:
        self._working_title.setText("")
        self._candidate_input.setText("")
        self._candidates.clear()
        self._details.setPlainText("")

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _reload_candidates(self) -> None:
        self._candidates.clear()
        self._details.setPlainText("")
        if self._service is None or not self._project_key:
            return
        try:
            candidates = self._service.list_candidates(self._project_key)
        except TitleBuilderError as exc:
            _logger.warning("Unable to load title candidates: %s", exc)
            return
        for candidate in candidates:
            item = QListWidgetItem(candidate.display_label)
            item.setData(Qt.ItemDataRole.UserRole, candidate)
            item.setToolTip(candidate.alignment.summary)
            self._candidates.addItem(item)
        self._comparison_panel.refresh()

    def _selected_candidate(self) -> TitleCandidate | None:
        item = self._candidates.currentItem()
        if item is None:
            return None
        candidate = item.data(Qt.ItemDataRole.UserRole)
        if isinstance(candidate, TitleCandidate):
            return candidate
        # Manual entries carry no service-backed candidate. Represent
        # them as an unsaved proposed candidate so that the use-action
        # still works without a service round-trip.
        from academic_platform.application.title_builder.model import (
            TitleAlignmentReport,
            TitlePattern,
        )

        return TitleCandidate(
            identifier="manual",
            pattern=TitlePattern.EXPLORATION_OF_SUBJECT,
            title=item.text(),
            rationale="Manually entered title.",
            strengths="",
            problems="",
            assumptions="",
            alignment=TitleAlignmentReport(),
            state=TitleState.PROPOSED,
        )

    def _render_details(self, candidate: TitleCandidate) -> str:
        lines: list[str] = [
            f"Title: {candidate.title}",
            f"Pattern: {candidate.pattern.display_name}",
            f"State: {candidate.state.display_name}",
            f"Alignment: {candidate.alignment.summary}",
            "",
            "Rationale:",
            candidate.rationale,
            "",
            "Strengths:",
            candidate.strengths,
            "",
            "Problems:",
            candidate.problems,
            "",
            "Assumptions:",
            candidate.assumptions,
        ]
        return "\n".join(lines)

    def _current_topic_draft(self):
        page = self.window()
        getter = getattr(page, "current_topic_draft", None)
        if callable(getter):
            return getter()
        return None

    def _show_error(self, title: str, message: str) -> None:
        DialogFactory.message(self, title, message, kind=MessageKind.ERROR)

    def _on_working_title_selected(self, title: str) -> None:
        self._working_title.setText(title)

# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
def _candidate_row_id(candidate: TitleCandidate) -> int:
    """Return the numeric row identifier encoded in the candidate's id."""
    identifier = candidate.identifier
    if identifier.startswith("row."):
        try:
            return int(identifier.split(".", 1)[1])
        except (ValueError, IndexError):
            return 0
    return 0