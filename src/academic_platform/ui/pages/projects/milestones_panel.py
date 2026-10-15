"""Milestones panel for the Projects page.

The panel renders the project's tasks grouped by status and exposes
actions to change status, priority, and milestone marking. It is
embedded in the project detail panel as a third tab alongside the
existing questions and tasks tabs.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from academic_platform.application.tasks.errors import (
    TaskError,
    TaskNotFoundError,
    TaskValidationError,
)
from academic_platform.application.tasks.model import (
    TaskPriority,
    TaskProgressSummary,
    TaskStatus,
    TaskView,
)
from academic_platform.application.tasks.service import TaskService
from academic_platform.ui.dialogs.confirm_dialog import ConfirmResult
from academic_platform.ui.dialogs.dialog_factory import DialogFactory
from academic_platform.ui.dialogs.form_dialog import FormField, FormFieldKind
from academic_platform.ui.dialogs.message_dialog import MessageKind

_logger = logging.getLogger(__name__)


class MilestonesPanel(QWidget):
    """Panel exposing the task workflow for a project."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("milestonesPanel")
        self._service: TaskService | None = None
        self._project_key: str = ""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # Summary row
        self._summary_frame = QFrame(self)
        self._summary_frame.setObjectName("milestonesSummary")
        self._summary_frame.setFrameShape(QFrame.Shape.StyledPanel)
        summary_layout = QHBoxLayout(self._summary_frame)
        summary_layout.setContentsMargins(10, 6, 10, 6)
        summary_layout.setSpacing(12)

        self._summary_total = QLabel("0 tasks", self._summary_frame)
        self._summary_total.setObjectName("milestonesSummaryTotal")
        summary_layout.addWidget(self._summary_total)

        self._summary_active = QLabel("0 active", self._summary_frame)
        self._summary_active.setObjectName("milestonesSummaryActive")
        summary_layout.addWidget(self._summary_active)

        self._summary_done = QLabel("0 done", self._summary_frame)
        self._summary_done.setObjectName("milestonesSummaryDone")
        summary_layout.addWidget(self._summary_done)

        self._summary_milestones = QLabel(
            "0 / 0 milestones", self._summary_frame
        )
        self._summary_milestones.setObjectName("milestonesSummaryMilestones")
        summary_layout.addWidget(self._summary_milestones)

        self._summary_overdue = QLabel("0 overdue", self._summary_frame)
        self._summary_overdue.setObjectName("milestonesSummaryOverdue")
        summary_layout.addWidget(self._summary_overdue)

        summary_layout.addStretch(1)
        layout.addWidget(self._summary_frame)

        # Filter row
        filter_row = QHBoxLayout()
        filter_row.setContentsMargins(0, 0, 0, 0)
        filter_row.setSpacing(6)

        status_label = QLabel("Filter:", self)
        status_label.setObjectName("milestonesFilterLabel")
        filter_row.addWidget(status_label)

        self._status_filter = QComboBox(self)
        self._status_filter.setObjectName("milestonesStatusFilter")
        self._status_filter.addItem("All statuses", "")
        for status in TaskStatus:
            self._status_filter.addItem(status.display_name, status.value)
        self._status_filter.currentIndexChanged.connect(self._on_filter_changed)
        filter_row.addWidget(self._status_filter)

        self._milestones_only = QComboBox(self)
        self._milestones_only.setObjectName("milestonesOnlyFilter")
        self._milestones_only.addItem("All tasks", False)
        self._milestones_only.addItem("Milestones only", True)
        self._milestones_only.currentIndexChanged.connect(self._on_filter_changed)
        filter_row.addWidget(self._milestones_only)

        filter_row.addStretch(1)

        self._add_button = QPushButton("Add task", self)
        self._add_button.setObjectName("milestonesAddTask")
        self._add_button.setAutoDefault(False)
        self._add_button.setEnabled(False)
        self._add_button.clicked.connect(self._on_add_task)
        filter_row.addWidget(self._add_button)

        self._edit_button = QPushButton("Edit", self)
        self._edit_button.setObjectName("milestonesEditTask")
        self._edit_button.setAutoDefault(False)
        self._edit_button.setEnabled(False)
        self._edit_button.clicked.connect(self._on_edit_task)
        filter_row.addWidget(self._edit_button)

        self._remove_button = QPushButton("Remove", self)
        self._remove_button.setObjectName("milestonesRemoveTask")
        self._remove_button.setAutoDefault(False)
        self._remove_button.setEnabled(False)
        self._remove_button.clicked.connect(self._on_remove_task)
        filter_row.addWidget(self._remove_button)

        layout.addLayout(filter_row)

        # Task list
        self._list = QListWidget(self)
        self._list.setObjectName("milestonesList")
        self._list.currentItemChanged.connect(self._on_task_selected)
        self._list.itemDoubleClicked.connect(self._on_edit_task)
        self._list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._list.customContextMenuRequested.connect(self._on_context_menu)
        layout.addWidget(self._list, 1)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def attach_service(self, service: TaskService) -> None:
        self._service = service
        if self._project_key:
            self.refresh()

    def set_project(self, project_key: str) -> None:
        self._project_key = project_key
        self.refresh()

    def refresh(self) -> None:
        self._list.clear()
        if self._service is None or not self._project_key:
            self._reset_summary()
            self._add_button.setEnabled(False)
            return
        try:
            summary = self._service.progress_summary(self._project_key)
        except TaskError as exc:
            _logger.warning("Unable to load task progress: %s", exc)
            self._reset_summary()
            return
        self._render_summary(summary)
        self._add_button.setEnabled(True)
        for task in self._filtered_tasks(summary.tasks):
            item = QListWidgetItem(task.display_label)
            item.setData(Qt.ItemDataRole.UserRole, task)
            self._list.addItem(item)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------
    def _on_filter_changed(self, _index: int) -> None:
        self.refresh()

    def _on_task_selected(
        self,
        current: QListWidgetItem | None,
        _previous: QListWidgetItem | None,
    ) -> None:
        enabled = current is not None
        self._edit_button.setEnabled(enabled)
        self._remove_button.setEnabled(enabled)

    def _on_add_task(self) -> None:
        if self._service is None or not self._project_key:
            return
        fields = _task_form_fields()
        values = DialogFactory.form(
            self,
            "Add task",
            fields,
            submit_label="Add",
            cancel_label="Cancel",
        )
        if values is None:
            return
        try:
            status = TaskStatus(str(values.get("status") or "open"))
        except ValueError:
            status = TaskStatus.OPEN
        try:
            priority = TaskPriority(str(values.get("priority") or "normal"))
        except ValueError:
            priority = TaskPriority.NORMAL
        try:
            self._service.create_task(
                self._project_key,
                title=str(values.get("title") or "").strip(),
                description=str(values.get("description") or "").strip(),
                status=status,
                priority=priority,
                is_milestone=bool(values.get("is_milestone")),
                due_at=str(values.get("due_at") or "").strip() or None,
                notes=str(values.get("notes") or "").strip(),
            )
        except TaskValidationError as exc:
            self._show_error("; ".join(exc.issues))
            return
        except TaskError as exc:
            self._show_error(str(exc))
            return
        self.refresh()

    def _on_edit_task(self) -> None:
        item = self._list.currentItem()
        if item is None or self._service is None or not self._project_key:
            return
        task = item.data(Qt.ItemDataRole.UserRole)
        if task is None:
            return
        fields = _task_form_fields(task)
        values = DialogFactory.form(
            self,
            f"Edit task: {task.title}",
            fields,
            submit_label="Save",
            cancel_label="Cancel",
        )
        if values is None:
            return
        try:
            status = TaskStatus(str(values.get("status") or "open"))
        except ValueError:
            status = TaskStatus.OPEN
        try:
            priority = TaskPriority(str(values.get("priority") or "normal"))
        except ValueError:
            priority = TaskPriority.NORMAL
        try:
            self._service.update_task(
                self._project_key,
                task.identifier,
                title=str(values.get("title") or "").strip(),
                description=str(values.get("description") or "").strip(),
                status=status,
                priority=priority,
                is_milestone=bool(values.get("is_milestone")),
                due_at=str(values.get("due_at") or "").strip() or None,
                clear_due_at=not bool(str(values.get("due_at") or "").strip()),
                notes=str(values.get("notes") or "").strip(),
            )
        except TaskValidationError as exc:
            self._show_error("; ".join(exc.issues))
            return
        except TaskError as exc:
            self._show_error(str(exc))
            return
        self.refresh()

    def _on_remove_task(self) -> None:
        item = self._list.currentItem()
        if item is None or self._service is None or not self._project_key:
            return
        task = item.data(Qt.ItemDataRole.UserRole)
        if task is None:
            return
        outcome = DialogFactory.confirm(
            self,
            "Remove task",
            f"Remove the task {task.title[:80]!r}?",
            confirm_label="Remove",
            cancel_label="Cancel",
            destructive=True,
            default_to_confirm=False,
        )
        if outcome.result is not ConfirmResult.CONFIRMED:
            return
        try:
            self._service.delete_task(self._project_key, task.identifier)
        except TaskNotFoundError:
            pass
        except TaskError as exc:
            self._show_error(str(exc))
            return
        self.refresh()

    def _on_context_menu(self, position) -> None:
        item = self._list.itemAt(position)
        if item is None or self._service is None or not self._project_key:
            return
        task = item.data(Qt.ItemDataRole.UserRole)
        if task is None:
            return
        menu = QMenu(self._list)

        status_menu = menu.addMenu("Set status")
        for status in TaskStatus:
            action = status_menu.addAction(status.display_name)
            action.setCheckable(True)
            action.setChecked(task.status is status)
            action.triggered.connect(
                lambda _checked=False, s=status: self._set_status(task, s)
            )

        priority_menu = menu.addMenu("Set priority")
        for priority in TaskPriority:
            action = priority_menu.addAction(priority.display_name)
            action.setCheckable(True)
            action.setChecked(task.priority is priority)
            action.triggered.connect(
                lambda _checked=False, p=priority: self._set_priority(task, p)
            )

        menu.addSeparator()
        if task.is_milestone:
            clear_milestone = menu.addAction("Clear milestone")
            clear_milestone.triggered.connect(
                lambda _checked=False: self._clear_milestone(task)
            )
        else:
            mark_milestone = menu.addAction("Mark as milestone")
            mark_milestone.triggered.connect(
                lambda _checked=False: self._mark_milestone(task)
            )

        menu.exec(self._list.viewport().mapToGlobal(position))

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def _set_status(self, task: TaskView, status: TaskStatus) -> None:
        if self._service is None or not self._project_key:
            return
        try:
            self._service.set_status(self._project_key, task.identifier, status)
        except TaskError as exc:
            self._show_error(str(exc))
            return
        self.refresh()

    def _set_priority(self, task: TaskView, priority: TaskPriority) -> None:
        if self._service is None or not self._project_key:
            return
        try:
            self._service.set_priority(
                self._project_key, task.identifier, priority
            )
        except TaskError as exc:
            self._show_error(str(exc))
            return
        self.refresh()

    def _mark_milestone(self, task: TaskView) -> None:
        if self._service is None or not self._project_key:
            return
        try:
            self._service.mark_milestone(self._project_key, task.identifier)
        except TaskError as exc:
            self._show_error(str(exc))
            return
        self.refresh()

    def _clear_milestone(self, task: TaskView) -> None:
        if self._service is None or not self._project_key:
            return
        try:
            self._service.clear_milestone(self._project_key, task.identifier)
        except TaskError as exc:
            self._show_error(str(exc))
            return
        self.refresh()

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------
    def _render_summary(self, summary: TaskProgressSummary) -> None:
        self._summary_total.setText(f"{summary.total} task(s)")
        self._summary_active.setText(f"{summary.active_count} active")
        self._summary_done.setText(f"{summary.done} done")
        self._summary_milestones.setText(
            f"{summary.milestones_done} / {summary.milestones_total} milestones"
        )
        self._summary_overdue.setText(f"{summary.overdue} overdue")
        self._summary_overdue.setVisible(summary.overdue > 0)

    def _reset_summary(self) -> None:
        self._summary_total.setText("0 tasks")
        self._summary_active.setText("0 active")
        self._summary_done.setText("0 done")
        self._summary_milestones.setText("0 / 0 milestones")
        self._summary_overdue.setText("0 overdue")
        self._summary_overdue.setVisible(False)

    def _filtered_tasks(self, tasks: tuple[TaskView, ...]) -> list[TaskView]:
        status_value = self._status_filter.currentData() or ""
        milestones_only = bool(self._milestones_only.currentData())
        results: list[TaskView] = []
        for task in tasks:
            if status_value and task.status.value != status_value:
                continue
            if milestones_only and not task.is_milestone:
                continue
            results.append(task)
        return results

    def _show_error(self, message: str) -> None:
        DialogFactory.message(
            self, "Task error", message, kind=MessageKind.ERROR
        )


# ----------------------------------------------------------------------
# Form helpers
# ----------------------------------------------------------------------
def _task_form_fields(task: TaskView | None = None) -> tuple[FormField, ...]:
    return (
        FormField(
            identifier="title",
            label="Title",
            kind=FormFieldKind.TEXT,
            initial=task.title if task else "",
            validator=_validate_required("Title"),
        ),
        FormField(
            identifier="description",
            label="Description",
            kind=FormFieldKind.MULTILINE,
            initial=task.description if task else "",
        ),
        FormField(
            identifier="status",
            label="Status",
            kind=FormFieldKind.SELECT,
            options=tuple((s.value, s.display_name) for s in TaskStatus),
            initial=task.status.value if task else "open",
        ),
        FormField(
            identifier="priority",
            label="Priority",
            kind=FormFieldKind.SELECT,
            options=tuple((p.value, p.display_name) for p in TaskPriority),
            initial=task.priority.value if task else "normal",
        ),
        FormField(
            identifier="is_milestone",
            label="Milestone",
            kind=FormFieldKind.CHECKBOX,
            initial="true" if (task and task.is_milestone) else "",
        ),
        FormField(
            identifier="due_at",
            label="Due date",
            kind=FormFieldKind.TEXT,
            initial=task.due_at if task and task.due_at else "",
            placeholder="YYYY-MM-DDTHH:MM:SS",
        ),
        FormField(
            identifier="notes",
            label="Notes",
            kind=FormFieldKind.MULTILINE,
            initial=task.notes if task else "",
        ),
    )


def _validate_required(field: str):
    def _validator(value: str) -> str | None:
        if not value.strip():
            return f"{field} must not be empty"
        return None

    return _validator