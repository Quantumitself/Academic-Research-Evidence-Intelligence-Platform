"""Topic & Problem section.

Captures the broad subject, the research problem, the context, the
population, and any constraints the researcher works under. The
section's state lives in this widget and is exposed through ``summary``
so the page's navigation sidebar reflects the work.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from academic_platform.ui.pages.research_assistant.section_base import (
    AssistantSection,
    AssistantSectionId,
)
from academic_platform.ui.pages.research_assistant.sections._shared import (
    make_multiline_field,
)
import logging

from academic_platform.application.topic_workspace.errors import (
    TopicWorkspaceError,
    TopicWorkspaceValidationError,
)
from academic_platform.application.topic_workspace.model import (
    TopicField,
)
from academic_platform.application.topic_workspace.service import (
    TopicWorkspaceService,
)
from academic_platform.ui.dialogs.dialog_factory import DialogFactory
from academic_platform.ui.dialogs.message_dialog import MessageKind
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
)

from academic_platform.application.clarifying_questions.engine import (
    ClarifyingQuestionEngine,
)
from academic_platform.application.clarifying_questions.model import (
    ClarifyingQuestion,
)


_logger = logging.getLogger(__name__)

class TopicSection(AssistantSection):
    """Topic & Problem section backed by the workspace service."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(AssistantSectionId.TOPIC, parent=parent)
        self._service: TopicWorkspaceService | None = None
        self._loading = False

        content = QWidget(self)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        self._subject = make_multiline_field(
            content,
            "Broad subject",
            placeholder="The general area of inquiry.",
            minimum_height=80,
        )
        self._problem = make_multiline_field(
            content,
            "Research problem",
            placeholder="What practical or theoretical problem does this address?",
            minimum_height=100,
        )
        self._context = make_multiline_field(
            content,
            "Context",
            placeholder="Setting and circumstances.",
            minimum_height=80,
        )
        self._population = make_multiline_field(
            content,
            "Population",
            placeholder="The population the study concerns.",
            minimum_height=80,
        )
        self._time_period = make_multiline_field(
            content,
            "Time period",
            placeholder="The time period the study covers.",
            minimum_height=60,
        )
        self._key_concepts = make_multiline_field(
            content,
            "Key concepts",
            placeholder="The concepts and constructs at the center of the study.",
            minimum_height=80,
        )
        self._potential_outcomes = make_multiline_field(
            content,
            "Potential outcomes",
            placeholder="The outcomes or variables of interest.",
            minimum_height=80,
        )
        self._constraints = make_multiline_field(
            content,
            "Constraints",
            placeholder="Time, resources, ethics, or access constraints.",
            minimum_height=80,
        )
        self._knowledge_level = make_multiline_field(
            content,
            "Researcher's knowledge level",
            placeholder="How familiar are you with this topic?",
            minimum_height=60,
        )
        self._question_engine = ClarifyingQuestionEngine()
        self._dismissed: set[str] = set()
        self._questions_panel = self._build_questions_panel(content)
        layout.addWidget(self._questions_panel)

        # Wire change notifications after construction so that the
        # initial population does not trigger writes.
        for field, editor in self._editors().items():
            editor.textChanged.connect(
                lambda f=field: self._on_editor_changed(f)
            )

        self._install_content(content)
        self._populate_from_service()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def attach_service(self, service: TopicWorkspaceService) -> None:
        """Attach the workspace service and reload the section."""
        self._service = service
        self._populate_from_service()

    @property
    def attached_project_key(self) -> str | None:
        if self._service is None:
            return None
        return self._service.attached_project_key

    def attach_project(self, project_key: str) -> None:
        """Attach the section's service to a project and reload."""
        if self._service is None:
            return
        try:
            self._service.attach_project(project_key)
        except TopicWorkspaceError as exc:
            self._show_error("Unable to attach project", str(exc))
            return
        self._populate_from_service()

    # ------------------------------------------------------------------
    # Editor accessors
    # ------------------------------------------------------------------
    @property
    def broad_subject(self) -> str:
        return self._subject.toPlainText().strip()

    @property
    def research_problem(self) -> str:
        return self._problem.toPlainText().strip()

    @property
    def context(self) -> str:
        return self._context.toPlainText().strip()

    @property
    def population(self) -> str:
        return self._population.toPlainText().strip()

    @property
    def time_period(self) -> str:
        return self._time_period.toPlainText().strip()

    @property
    def key_concepts(self) -> str:
        return self._key_concepts.toPlainText().strip()

    @property
    def potential_outcomes(self) -> str:
        return self._potential_outcomes.toPlainText().strip()

    @property
    def constraints(self) -> str:
        return self._constraints.toPlainText().strip()

    @property
    def knowledge_level(self) -> str:
        return self._knowledge_level.toPlainText().strip()

    # ------------------------------------------------------------------
    # Contract
    # ------------------------------------------------------------------
    def summary(self) -> str:
        if self._service is not None:
            completeness = self._service.completeness()
            if completeness.populated_count == 0:
                return ""
            return completeness.summary
        # The section falls back to a local summary when no service is
        # attached; this occurs before the page wires the service.
        populated = [
            name
            for name, value in (
                ("subject", self.broad_subject),
                ("problem", self.research_problem),
                ("context", self.context),
                ("population", self.population),
                ("concepts", self.key_concepts),
                ("constraints", self.constraints),
            )
            if value
        ]
        if not populated:
            return ""
        return " · ".join(populated)

    def reset(self) -> None:
        if self._service is not None:
            try:
                self._service.clear()
            except TopicWorkspaceError as exc:
                self._show_error("Unable to clear the section", str(exc))
                return
        self._populate_from_service()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _editors(self) -> dict[TopicField, object]:
        return {
            TopicField.BROAD_SUBJECT: self._subject,
            TopicField.RESEARCH_PROBLEM: self._problem,
            TopicField.CONTEXT: self._context,
            TopicField.POPULATION: self._population,
            TopicField.TIME_PERIOD: self._time_period,
            TopicField.KEY_CONCEPTS: self._key_concepts,
            TopicField.POTENTIAL_OUTCOMES: self._potential_outcomes,
            TopicField.CONSTRAINTS: self._constraints,
            TopicField.KNOWLEDGE_LEVEL: self._knowledge_level,
        }

    def _populate_from_service(self) -> None:
        self._loading = True
        try:
            if self._service is None:
                return
            draft = self._service.current_draft()
            for field, editor in self._editors().items():
                editor.blockSignals(True)
                try:
                    editor.setPlainText(draft.value(field))
                finally:
                    editor.blockSignals(False)
        finally:
            self._loading = False
        self._refresh_questions()

    def _on_editor_changed(self, field: TopicField) -> None:
        if self._loading or self._service is None:
            return
        editor = self._editors()[field]
        value = editor.toPlainText()
        try:
            self._service.set_field(field, value)
            self._refresh_questions()
        except TopicWorkspaceValidationError as exc:
            self._show_error("Invalid value", "; ".join(exc.issues))
        except TopicWorkspaceError as exc:
            self._show_error("Unable to save", str(exc))

    def _show_error(self, title: str, message: str) -> None:
        DialogFactory.message(self, title, message, kind=MessageKind.ERROR)

    def _build_questions_panel(self, parent: QWidget) -> QWidget:
        """Build the clarifying-questions panel."""
        container = QWidget(parent)
        container.setObjectName("topicQuestionsPanel")
        panel_layout = QVBoxLayout(container)
        panel_layout.setContentsMargins(0, 0, 0, 0)
        panel_layout.setSpacing(6)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(6)

        heading = QLabel("Clarifying questions", container)
        heading.setObjectName("topicQuestionsHeading")
        header.addWidget(heading, 1)

        refresh_button = QPushButton("Refresh", container)
        refresh_button.setObjectName("topicQuestionsRefresh")
        refresh_button.setAutoDefault(False)
        refresh_button.clicked.connect(self._refresh_questions)
        header.addWidget(refresh_button)

        panel_layout.addLayout(header)

        self._questions_summary = QLabel("", container)
        self._questions_summary.setObjectName("topicQuestionsSummary")
        self._questions_summary.setWordWrap(True)
        panel_layout.addWidget(self._questions_summary)

        self._questions_list = QListWidget(container)
        self._questions_list.setObjectName("topicQuestionsList")
        self._questions_list.setAlternatingRowColors(False)
        self._questions_list.currentItemChanged.connect(
            self._on_question_selected
        )
        panel_layout.addWidget(self._questions_list, 1)

        actions = QHBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(6)

        self._focus_field_button = QPushButton(
            "Focus target field", container
        )
        self._focus_field_button.setObjectName("topicQuestionsFocusField")
        self._focus_field_button.setAutoDefault(False)
        self._focus_field_button.setEnabled(False)
        self._focus_field_button.clicked.connect(self._on_focus_target_field)
        actions.addWidget(self._focus_field_button)

        self._dismiss_button = QPushButton("Dismiss", container)
        self._dismiss_button.setObjectName("topicQuestionsDismiss")
        self._dismiss_button.setAutoDefault(False)
        self._dismiss_button.setEnabled(False)
        self._dismiss_button.clicked.connect(self._on_dismiss_question)
        actions.addWidget(self._dismiss_button)

        actions.addStretch(1)
        panel_layout.addLayout(actions)

        self._refresh_questions()
        return container

    def _refresh_questions(self) -> None:
        """Recompute the clarifying questions from the current draft."""
        if self._service is None:
            self._questions_list.clear()
            self._questions_summary.setText(
                "Attach the topic workspace to receive clarifying questions."
            )
            return
        draft = self._service.current_draft()
        try:
            questions = self._question_engine.evaluate(
                draft,
                dismissed_identifiers=frozenset(self._dismissed),
            )
        except ClarifyingQuestionError as exc:
            self._questions_list.clear()
            self._questions_summary.setText(
                f"Unable to compute questions: {exc}"
            )
            return
        self._questions_list.clear()
        for question in questions:
            item = QListWidgetItem(question.display_label)
            item.setData(Qt.ItemDataRole.UserRole, question)
            item.setToolTip(question.rationale)
            self._questions_list.addItem(item)
        blocking = [q for q in questions if q.blocking]
        if not questions:
            self._questions_summary.setText(
                "No clarifying questions right now. The topic draft "
                "covers the essentials."
            )
        else:
            parts = [f"{len(questions)} question(s)"]
            if blocking:
                parts.append(f"{len(blocking)} essential")
            self._questions_summary.setText(" · ".join(parts))

    def _on_question_selected(
        self,
        current: QListWidgetItem | None,
        _previous: QListWidgetItem | None,
    ) -> None:
        enabled = current is not None
        self._focus_field_button.setEnabled(enabled)
        self._dismiss_button.setEnabled(enabled)

    def _on_focus_target_field(self) -> None:
        item = self._questions_list.currentItem()
        if item is None:
            return
        question = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(question, ClarifyingQuestion):
            return
        try:
            field = TopicField(question.target_field)
        except ValueError:
            return
        editor = self._editors().get(field)
        if editor is None:
            return
        editor.setFocus(Qt.FocusReason.ShortcutFocusReason)

    def _on_dismiss_question(self) -> None:
        item = self._questions_list.currentItem()
        if item is None:
            return
        question = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(question, ClarifyingQuestion):
            return
        self._dismissed.add(question.identifier)
        self._refresh_questions()