"""Research Questions section.

The section is a service-backed workspace that captures the topic, the
problem, the gap, the primary research question, and the secondary
questions and hypotheses. It renders the validation report and exposes
actions to add, edit, remove, and promote questions.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from academic_platform.application.research_questions.errors import (
    ResearchQuestionWorkspaceError,
    ResearchQuestionWorkspaceNotFoundError,
    ResearchQuestionWorkspaceValidationError,
)
from academic_platform.application.research_questions.model import (
    QuestionKind,
    ResearchQuestionView,
)
from academic_platform.application.research_questions.service import (
    ResearchQuestionWorkspaceService,
)
from academic_platform.ui.dialogs.confirm_dialog import ConfirmResult
from academic_platform.ui.dialogs.dialog_factory import DialogFactory
from academic_platform.ui.dialogs.message_dialog import MessageKind
from academic_platform.ui.pages.research_assistant.section_base import (
    AssistantSection,
    AssistantSectionId,
)
from academic_platform.ui.pages.research_assistant.sections._shared import (
    make_multiline_field,
)

_logger = logging.getLogger(__name__)


class ResearchQuestionsSection(AssistantSection):
    """Research Questions section backed by the workspace service."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(
            AssistantSectionId.RESEARCH_QUESTIONS, parent=parent
        )
        self._service: ResearchQuestionWorkspaceService | None = None
        self._loading = False

        content = QWidget(self)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        self._topic = make_multiline_field(
            content,
            "Topic",
            placeholder="The bounded topic the study addresses.",
            minimum_height=60,
        )
        self._problem = make_multiline_field(
            content,
            "Research problem",
            placeholder=(
                "The practical or theoretical problem the study addresses."
            ),
            minimum_height=80,
        )
        self._gap = make_multiline_field(
            content,
            "Knowledge gap",
            placeholder=(
                "What is not yet known, and what evidence supports that "
                "assessment?"
            ),
            minimum_height=80,
        )
        self._primary = make_multiline_field(
            content,
            "Primary research question",
            placeholder=(
                "The single question the study is designed to answer."
            ),
            minimum_height=90,
        )

        self._validation_label = QLabel("", content)
        self._validation_label.setObjectName("questionsValidation")
        self._validation_label.setWordWrap(True)
        layout.addWidget(self._validation_label)

        secondary_heading = QLabel(
            "Secondary questions and hypotheses", content
        )
        secondary_heading.setObjectName("questionsSecondaryHeading")
        layout.addWidget(secondary_heading)

        actions = QHBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(6)

        self._entry_input = QLineEdit(content)
        self._entry_input.setObjectName("questionsEntryInput")
        self._entry_input.setPlaceholderText(
            "Add a secondary question or hypothesis…"
        )
        actions.addWidget(self._entry_input, 1)

        self._kind_combo = QComboBox(content)
        self._kind_combo.setObjectName("questionsKind")
        for kind in QuestionKind:
            self._kind_combo.addItem(kind.display_name, kind.value)
        self._kind_combo.setCurrentIndex(
            self._kind_combo.findData(QuestionKind.SUB.value)
        )
        actions.addWidget(self._kind_combo)

        self._add_button = QPushButton("Add", content)
        self._add_button.setObjectName("questionsAddEntry")
        self._add_button.setAutoDefault(False)
        self._add_button.setEnabled(False)
        self._add_button.clicked.connect(self._on_add_entry)
        actions.addWidget(self._add_button)

        layout.addLayout(actions)

        self._entries = QListWidget(content)
        self._entries.setObjectName("questionsEntryList")
        self._entries.currentItemChanged.connect(self._on_entry_selected)
        self._entries.itemDoubleClicked.connect(
            lambda _item: self._on_promote_entry()
        )
        layout.addWidget(self._entries, 1)

        entry_actions = QHBoxLayout()
        entry_actions.setContentsMargins(0, 0, 0, 0)
        entry_actions.setSpacing(6)

        self._promote_button = QPushButton("Set primary", content)
        self._promote_button.setObjectName("questionsPromoteEntry")
        self._promote_button.setAutoDefault(False)
        self._promote_button.setEnabled(False)
        self._promote_button.clicked.connect(self._on_promote_entry)
        entry_actions.addWidget(self._promote_button)

        self._edit_button = QPushButton("Edit", content)
        self._edit_button.setObjectName("questionsEditEntry")
        self._edit_button.setAutoDefault(False)
        self._edit_button.setEnabled(False)
        self._edit_button.clicked.connect(self._on_edit_entry)
        entry_actions.addWidget(self._edit_button)

        self._remove_button = QPushButton("Remove", content)
        self._remove_button.setObjectName("questionsRemoveEntry")
        self._remove_button.setAutoDefault(False)
        self._remove_button.setEnabled(False)
        self._remove_button.clicked.connect(self._on_remove_entry)
        entry_actions.addWidget(self._remove_button)

        entry_actions.addStretch(1)
        layout.addLayout(entry_actions)

        for editor in (self._topic, self._problem, self._gap, self._primary):
            editor.textChanged.connect(self._on_field_changed)

        self._install_content(content)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def attach_service(
        self, service: ResearchQuestionWorkspaceService
    ) -> None:
        """Attach the workspace service."""
        self._service = service
        self._add_button.setEnabled(True)
        self._populate_from_service()

    def attach_project(self, project_key: str) -> None:
        """Attach the workspace service to a project."""
        if self._service is None:
            return
        try:
            self._service.attach_project(project_key)
        except ResearchQuestionWorkspaceError as exc:
            self._show_error("Unable to attach project", str(exc))
            return
        self._populate_from_service()

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------
    def _on_field_changed(self) -> None:
        if self._loading or self._service is None:
            return
        try:
            # Each editor writes only when it has been edited; the
            # service validates the input and persists the change.
            if self.sender() is self._topic:
                self._service.set_topic(self._topic.toPlainText())
            elif self.sender() is self._problem:
                self._service.set_problem(self._problem.toPlainText())
            elif self.sender() is self._gap:
                self._service.set_gap(self._gap.toPlainText())
            elif self.sender() is self._primary:
                self._service.set_primary_question(
                    self._primary.toPlainText()
                )
        except ResearchQuestionWorkspaceValidationError as exc:
            self._show_error("Invalid value", "; ".join(exc.issues))
        except ResearchQuestionWorkspaceError as exc:
            self._show_error("Unable to save", str(exc))
        self._refresh_validation()

    def _on_add_entry(self) -> None:
        text = self._entry_input.text().strip()
        if not text:
            return
        try:
            kind = QuestionKind(self._kind_combo.currentData())
        except (TypeError, ValueError):
            kind = QuestionKind.SUB
        if self._service is None:
            # No service attached: add a local placeholder entry so the
            # workspace remains usable as a scratchpad. The entry carries
            # a synthetic view so the rest of the section works uniformly.
            view = ResearchQuestionView(
                identifier=0,
                text=text,
                kind=kind,
                is_primary=False,
                position=self._entries.count(),
                created_at="",
                updated_at="",
            )
            item = QListWidgetItem(view.display_label)
            item.setData(Qt.ItemDataRole.UserRole, view)
            self._entries.addItem(item)
            self._entry_input.clear()
            return
        try:
            self._service.add_question(text, kind=kind)
        except ResearchQuestionWorkspaceValidationError as exc:
            self._show_error("Invalid question", "; ".join(exc.issues))
            return
        except ResearchQuestionWorkspaceError as exc:
            self._show_error("Unable to add the question", str(exc))
            return
        self._entry_input.clear()
        self._populate_from_service()

    def _on_entry_selected(
        self,
        current: QListWidgetItem | None,
        _previous: QListWidgetItem | None,
    ) -> None:
        enabled = current is not None
        self._edit_button.setEnabled(enabled)
        self._remove_button.setEnabled(enabled)
        self._promote_button.setEnabled(enabled)

    def _on_promote_entry(self) -> None:
        if self._service is None:
            return
        item = self._entries.currentItem()
        if item is None:
            return
        view = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(view, ResearchQuestionView):
            return
        try:
            self._service.promote_to_primary(view.identifier)
        except ResearchQuestionWorkspaceError as exc:
            self._show_error("Unable to promote the question", str(exc))
            return
        self._populate_from_service()

    def _on_edit_entry(self) -> None:
        if self._service is None:
            return
        item = self._entries.currentItem()
        if item is None:
            return
        view = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(view, ResearchQuestionView):
            return
        new_text = DialogFactory.prompt(
            self,
            "Edit question",
            "Question",
            initial=view.text,
            validator=_nonempty_validator("Question"),
        )
        if new_text is None:
            return
        try:
            self._service.update_question(
                view.identifier, text=new_text.strip()
            )
        except ResearchQuestionWorkspaceValidationError as exc:
            self._show_error("Invalid question", "; ".join(exc.issues))
            return
        except ResearchQuestionWorkspaceError as exc:
            self._show_error("Unable to update the question", str(exc))
            return
        self._populate_from_service()

    def _on_remove_entry(self) -> None:
        if self._service is None:
            return
        item = self._entries.currentItem()
        if item is None:
            return
        view = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(view, ResearchQuestionView):
            return
        outcome = DialogFactory.confirm(
            self,
            "Remove question",
            f"Remove {view.text[:80]!r}?",
            confirm_label="Remove",
            cancel_label="Cancel",
            destructive=True,
            default_to_confirm=False,
        )
        if outcome.result is not ConfirmResult.CONFIRMED:
            return
        try:
            self._service.remove_question(view.identifier)
        except ResearchQuestionWorkspaceError as exc:
            self._show_error("Unable to remove the question", str(exc))
            return
        self._populate_from_service()

    # ------------------------------------------------------------------
    # Contract
    # ------------------------------------------------------------------
    def primary_question(self) -> str:
        return self._primary.toPlainText().strip()

    def entries(self) -> list[ResearchQuestionView]:
        results: list[ResearchQuestionView] = []
        for index in range(self._entries.count()):
            data = self._entries.item(index).data(Qt.ItemDataRole.UserRole)
            if isinstance(data, ResearchQuestionView):
                results.append(data)
        return results

    def summary(self) -> str:
        parts: list[str] = []
        if self.primary_question():
            parts.append("primary set")
        count = self._entries.count()
        if count:
            parts.append(f"{count} entr(y/ies)")
        if self._service is not None:
            report = self._service.validation_report()
            if report.issues:
                parts.append(report.summary)
        return " · ".join(parts)

    def reset(self) -> None:
        if self._service is None:
            return
        # Clearing a question draft resets the workspace metadata and
        # removes every secondary question, but leaves the topic and the
        # problem in place on the project.
        try:
            self._service.set_gap("")
            self._service.set_primary_question("")
        except ResearchQuestionWorkspaceError:
            pass
        for entry in list(self.entries()):
            try:
                self._service.remove_question(entry.identifier)
            except ResearchQuestionWorkspaceError:
                continue
        self._populate_from_service()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _populate_from_service(self) -> None:
        if self._service is None:
            return
        self._loading = True
        try:
            draft = self._service.current_draft()
            self._topic.blockSignals(True)
            self._problem.blockSignals(True)
            self._gap.blockSignals(True)
            self._primary.blockSignals(True)
            try:
                self._topic.setPlainText(draft.topic)
                self._problem.setPlainText(draft.problem)
                self._gap.setPlainText(draft.gap)
                self._primary.setPlainText(draft.primary_question)
            finally:
                self._topic.blockSignals(False)
                self._problem.blockSignals(False)
                self._gap.blockSignals(False)
                self._primary.blockSignals(False)
        finally:
            self._loading = False
        self._reload_entries()
        self._refresh_validation()

    def _reload_entries(self) -> None:
        self._entries.clear()
        if self._service is None:
            return
        draft = self._service.current_draft()
        for view in draft.questions:
            if view.is_primary:
                continue
            item = QListWidgetItem(view.display_label)
            item.setData(Qt.ItemDataRole.UserRole, view)
            self._entries.addItem(item)

    def _refresh_validation(self) -> None:
        if self._service is None:
            self._validation_label.setText("")
            return
        report = self._service.validation_report()
        if not report.issues:
            self._validation_label.setText(report.summary)
            self._validation_label.setProperty("severity", "ok")
        else:
            lines = [report.summary]
            for issue in report.issues:
                marker = "✖" if issue.is_error else "•"
                lines.append(f"{marker} {issue.message}")
            self._validation_label.setText("\n".join(lines))
            severity = "error" if report.errors else "warning"
            self._validation_label.setProperty("severity", severity)
        style = self._validation_label.style()
        style.unpolish(self._validation_label)
        style.polish(self._validation_label)

    def _show_error(self, title: str, message: str) -> None:
        DialogFactory.message(self, title, message, kind=MessageKind.ERROR)


def _nonempty_validator(field: str):
    def _validator(value: str) -> str | None:
        return None if value.strip() else f"{field} must not be empty"

    return _validator