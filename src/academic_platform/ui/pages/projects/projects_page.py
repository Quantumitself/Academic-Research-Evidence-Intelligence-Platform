"""Research projects page.

The page lists research projects in a table, supports creation and
editing through the standard form dialog, allows changing the lifecycle
stage inline, and exposes a detail panel with the project's research
questions and tasks.

Design decisions
----------------
- The page reads and writes through the application-layer
  ``ProjectService``. It never touches the database directly.
- The list is rendered as a ``QTableView`` with a custom model. The
  model holds ``ProjectView`` instances and exposes the columns the
  user can sort by.
- The detail panel is populated on selection. It renders the project's
  questions and tasks and exposes actions to add, edit, and remove
  them.
- Creation and editing use the standard form dialog from the dialogs
  package. The form fields mirror the service's accepted parameters.
- Destructive actions are guarded by a confirmation prompt with a
  non-destructive default.
- The page never modifies documents; document linking is delivered by
  the reader and library flows.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QSortFilterProxyModel,
    Qt,
    Signal,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPushButton,
    QSplitter,
    QTableView,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from academic_platform.application.projects.errors import (
    ProjectError,
    ProjectNotFoundError,
    ProjectValidationError,
)
from academic_platform.application.projects.model import (
    ProjectQuestionView,
    ProjectStage,
    ProjectTaskView,
    ProjectView,
)
from academic_platform.application.projects.service import ProjectService
from academic_platform.application.tasks.service import TaskService
from academic_platform.ui.components.empty_state import EmptyState
from academic_platform.ui.components.section_card import SectionCard
from academic_platform.ui.dialogs.confirm_dialog import ConfirmResult
from academic_platform.ui.dialogs.dialog_factory import DialogFactory
from academic_platform.ui.dialogs.form_dialog import FormField, FormFieldKind
from academic_platform.ui.dialogs.message_dialog import MessageKind
from academic_platform.ui.main_window_destinations import get_destination
from academic_platform.ui.pages.base_page import BasePage
from academic_platform.ui.pages.projects.milestones_panel import (
    MilestonesPanel,
)
from academic_platform.application.project_export.service import (
    ProjectExportService,
)
from academic_platform.ui.dialogs.project_export_dialog import (
    ProjectExportDialog,
)


_logger = logging.getLogger(__name__)


class _ProjectsTableModel(QAbstractTableModel):
    """Table model exposing ``ProjectView`` instances."""

    COLUMNS: tuple[tuple[str, str], ...] = (
        ("title", "Title"),
        ("stage", "Stage"),
        ("questions", "Questions"),
        ("tasks", "Tasks"),
        ("documents", "Documents"),
        ("updated_at", "Updated"),
    )

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._projects: list[ProjectView] = []

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        if parent.isValid():
            return 0
        return len(self._projects)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        if parent.isValid():
            return 0
        return len(self.COLUMNS)

    def headerData(  # noqa: N802
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ):
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal:
            if 0 <= section < len(self.COLUMNS):
                return self.COLUMNS[section][1]
            return None
        return section + 1

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        if index.row() < 0 or index.row() >= len(self._projects):
            return None
        project = self._projects[index.row()]
        column = (
            self.COLUMNS[index.column()][0]
            if index.column() < len(self.COLUMNS)
            else ""
        )
        if role == Qt.ItemDataRole.DisplayRole:
            return _display_value(project, column)
        if role == Qt.ItemDataRole.ToolTipRole:
            return _tooltip_value(project, column)
        if role == Qt.ItemDataRole.UserRole:
            return project
        if role == Qt.ItemDataRole.TextAlignmentRole and column in {
            "questions",
            "tasks",
            "documents",
        }:
            return int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        return None

    def set_projects(self, projects: list[ProjectView]) -> None:
        self.beginResetModel()
        self._projects = list(projects)
        self.endResetModel()

    def project_at(self, row: int) -> ProjectView | None:
        if 0 <= row < len(self._projects):
            return self._projects[row]
        return None

    @property
    def projects(self) -> tuple[ProjectView, ...]:
        return tuple(self._projects)


class ProjectsPage(BasePage):
    """Research projects page."""

    #: Emitted when the user requests to open a document from the
    #: project's linked collection.
    open_document_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        destination = get_destination("research_projects")
        super().__init__(
            title=destination.label,
            subtitle=destination.purpose,
            parent=parent,
        )
        self.setObjectName("projectsPage")

        self._service: ProjectService | None = None
        self._current_project_key: str | None = None
        self._task_service: TaskService | None = None
        self._export_service: ProjectExportService | None = None

        self._build_content()
        self._install_empty_state(
            EmptyState(
                title="No research projects yet",
                message=(
                    "Create a project to define a topic, develop a research "
                    "question, and track the work."
                ),
                glyph="\u2637",
                action_label="Create a project",
                parent=self,
            )
        )
        self._enable_empty_action()
        self._wire_header_actions()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def attach_service(self, service: ProjectService) -> None:
        """Attach the application-layer project service."""
        self._service = service
        self.refresh()

    def attach_task_service(self, service: TaskService) -> None:
        """Attach the application-layer task service."""
        self._task_service = service
        self._milestones_panel.attach_service(service)
        if self._current_project_key:
            self._milestones_panel.set_project(self._current_project_key)

    def refresh(self) -> None:
        """Reload the project list from the service."""
        if self._service is None:
            self._model.set_projects([])
            self._update_empty_state()
            return
        try:
            projects = self._service.list_projects()
        except ProjectError as exc:
            _logger.warning("Unable to load projects: %s", exc)
            self._show_error(str(exc))
            return
        self._model.set_projects(projects)
        self._update_summary(len(projects))
        self._update_empty_state()
        if self._current_project_key is not None:
            self._select_by_key(self._current_project_key)
        else:
            self._clear_detail()

    # ------------------------------------------------------------------
    # Content construction
    # ------------------------------------------------------------------
    def _build_content(self) -> None:
        content = QWidget(self)
        content.setObjectName("projectsContent")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        splitter = QSplitter(Qt.Orientation.Horizontal, content)
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(self._build_table(content))
        splitter.addWidget(self._build_detail_panel(content))
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([720, 420])
        layout.addWidget(splitter, 1)

        self._install_content(content)

    def _build_table(self, parent: QWidget) -> QWidget:
        container = QWidget(parent)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        filter_row = QHBoxLayout()
        filter_row.setContentsMargins(0, 0, 0, 0)
        filter_row.setSpacing(8)

        filter_label = QLabel("Show stage:", parent)
        filter_label.setObjectName("projectsFilterLabel")
        filter_row.addWidget(filter_label)

        self._stage_filter = QComboBox(parent)
        self._stage_filter.setObjectName("projectsStageFilter")
        self._stage_filter.addItem("All stages", "")
        for stage in ProjectStage:
            self._stage_filter.addItem(stage.display_name, stage.value)
        self._stage_filter.currentIndexChanged.connect(self._on_filter_changed)
        filter_row.addWidget(self._stage_filter)

        filter_row.addStretch(1)
        layout.addLayout(filter_row)

        self._model = _ProjectsTableModel(container)
        self._proxy = QSortFilterProxyModel(container)
        self._proxy.setSourceModel(self._model)
        self._proxy.setSortRole(Qt.ItemDataRole.DisplayRole)

        self._table = QTableView(container)
        self._table.setObjectName("projectsTable")
        self._table.setModel(self._proxy)
        self._table.setSortingEnabled(False)
        self._table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self._table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self._table.setAlternatingRowColors(True)
        self._table.setShowGrid(False)
        self._table.verticalHeader().setVisible(False)
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in range(1, len(_ProjectsTableModel.COLUMNS)):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        self._table.selectionModel().currentRowChanged.connect(
            self._on_current_row_changed
        )
        self._table.doubleClicked.connect(self._on_double_clicked)
        self._table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._on_context_menu)
        layout.addWidget(self._table, 1)

        return container

    def _build_detail_panel(self, parent: QWidget) -> QWidget:
        container = QWidget(parent)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        header_card = SectionCard("Project details", container)
        header_body = QWidget(header_card)
        header_layout = QVBoxLayout(header_body)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(6)

        self._detail_title = QLabel("Select a project to view details.", header_body)
        self._detail_title.setObjectName("projectsDetailTitle")
        self._detail_title.setWordWrap(True)
        header_layout.addWidget(self._detail_title)

        self._detail_topic = QLabel("", header_body)
        self._detail_topic.setObjectName("projectsDetailTopic")
        self._detail_topic.setWordWrap(True)
        header_layout.addWidget(self._detail_topic)

        stage_row = QHBoxLayout()
        stage_row.setContentsMargins(0, 0, 0, 0)
        stage_row.setSpacing(6)
        stage_label = QLabel("Stage:", header_body)
        stage_label.setObjectName("projectsDetailStageLabel")
        stage_row.addWidget(stage_label)
        self._detail_stage_combo = QComboBox(header_body)
        self._detail_stage_combo.setObjectName("projectsDetailStage")
        for stage in ProjectStage:
            self._detail_stage_combo.addItem(stage.display_name, stage.value)
        self._detail_stage_combo.currentIndexChanged.connect(
            self._on_detail_stage_changed
        )
        self._detail_stage_combo.setEnabled(False)
        stage_row.addWidget(self._detail_stage_combo)
        stage_row.addStretch(1)
        header_layout.addLayout(stage_row)

        self._detail_summary = QLabel("", header_body)
        self._detail_summary.setObjectName("projectsDetailSummary")
        self._detail_summary.setWordWrap(True)
        header_layout.addWidget(self._detail_summary)

        header_card.set_content_widget(header_body)
        layout.addWidget(header_card)

        self._detail_tabs = QTabWidget(container)
        self._detail_tabs.setObjectName("projectsDetailTabs")

        self._questions_tab = self._build_questions_tab()
        self._tasks_tab = self._build_tasks_tab()
        self._detail_tabs.addTab(self._questions_tab, "Research questions")
        self._detail_tabs.addTab(self._tasks_tab, "Tasks")

        self._milestones_panel = MilestonesPanel(container)
        self._detail_tabs.addTab(self._milestones_panel, "Milestones")

        layout.addWidget(self._detail_tabs, 1)

        return container

    def _build_questions_tab(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        actions = QHBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(6)

        self._add_question_button = QPushButton("Add question", container)
        self._add_question_button.setObjectName("projectsAddQuestion")
        self._add_question_button.setAutoDefault(False)
        self._add_question_button.setEnabled(False)
        self._add_question_button.clicked.connect(self._on_add_question)
        actions.addWidget(self._add_question_button)

        self._set_primary_button = QPushButton("Set primary", container)
        self._set_primary_button.setObjectName("projectsSetPrimaryQuestion")
        self._set_primary_button.setAutoDefault(False)
        self._set_primary_button.setEnabled(False)
        self._set_primary_button.clicked.connect(self._on_set_primary_question)
        actions.addWidget(self._set_primary_button)

        self._remove_question_button = QPushButton("Remove", container)
        self._remove_question_button.setObjectName("projectsRemoveQuestion")
        self._remove_question_button.setAutoDefault(False)
        self._remove_question_button.setEnabled(False)
        self._remove_question_button.clicked.connect(self._on_remove_question)
        actions.addWidget(self._remove_question_button)

        actions.addStretch(1)
        layout.addLayout(actions)

        self._questions_list = QListWidget(container)
        self._questions_list.setObjectName("projectsQuestionsList")
        self._questions_list.currentItemChanged.connect(
            self._on_question_selected
        )
        self._questions_list.itemDoubleClicked.connect(
            lambda _item: self._on_edit_question()
        )
        layout.addWidget(self._questions_list, 1)

        return container

    def _build_tasks_tab(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        actions = QHBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(6)

        self._add_task_button = QPushButton("Add task", container)
        self._add_task_button.setObjectName("projectsAddTask")
        self._add_task_button.setAutoDefault(False)
        self._add_task_button.setEnabled(False)
        self._add_task_button.clicked.connect(self._on_add_task)
        actions.addWidget(self._add_task_button)

        self._toggle_task_button = QPushButton("Toggle complete", container)
        self._toggle_task_button.setObjectName("projectsToggleTask")
        self._toggle_task_button.setAutoDefault(False)
        self._toggle_task_button.setEnabled(False)
        self._toggle_task_button.clicked.connect(self._on_toggle_task)
        actions.addWidget(self._toggle_task_button)

        self._remove_task_button = QPushButton("Remove", container)
        self._remove_task_button.setObjectName("projectsRemoveTask")
        self._remove_task_button.setAutoDefault(False)
        self._remove_task_button.setEnabled(False)
        self._remove_task_button.clicked.connect(self._on_remove_task)
        actions.addWidget(self._remove_task_button)

        actions.addStretch(1)
        layout.addLayout(actions)

        self._tasks_list = QListWidget(container)
        self._tasks_list.setObjectName("projectsTasksList")
        self._tasks_list.currentItemChanged.connect(self._on_task_selected)
        self._tasks_list.itemDoubleClicked.connect(
            lambda _item: self._on_edit_task()
        )
        layout.addWidget(self._tasks_list, 1)

        return container

    def _wire_header_actions(self) -> None:
        self._create_button = QPushButton("New project", self)
        self._create_button.setObjectName("projectsCreateButton")
        self._create_button.setAutoDefault(False)
        self._create_button.clicked.connect(self._on_create_project)
        self.add_header_action(self._create_button)

        self._edit_button = QPushButton("Edit project", self)
        self._edit_button.setObjectName("projectsEditButton")
        self._edit_button.setAutoDefault(False)
        self._edit_button.setEnabled(False)
        self._edit_button.clicked.connect(self._on_edit_project)
        self.add_header_action(self._edit_button)

        self._export_button = QPushButton("Export…", self)
        self._export_button.setObjectName("projectsExportButton")
        self._export_button.setAutoDefault(False)
        self._export_button.setEnabled(False)
        self._export_button.clicked.connect(self._on_export_project)
        self.add_header_action(self._export_button)

        self._refresh_button = QPushButton("Refresh", self)
        self._refresh_button.setObjectName("projectsRefreshButton")
        self._refresh_button.setAutoDefault(False)
        self._refresh_button.clicked.connect(self.refresh)
        self.add_header_action(self._refresh_button)

    def _enable_empty_action(self) -> None:
        from academic_platform.ui.components.empty_state import EmptyState

        for widget in self.findChildren(EmptyState):
            widget.set_action("Create a project", enabled=True)
            widget.action_requested.connect(self._on_create_project)
            break

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------
    def _on_filter_changed(self, _index: int) -> None:
        stage_value = self._stage_filter.currentData() or ""
        projects = self._model.projects
        if stage_value:
            filtered = [p for p in projects if p.stage.value == stage_value]
        else:
            filtered = list(projects)
        self._model.set_projects(filtered)
        self._update_summary(len(filtered))
        self._update_empty_state()

    def _on_current_row_changed(
        self,
        current: QModelIndex,
        _previous: QModelIndex,
    ) -> None:
        if not current.isValid():
            self._clear_detail()
            return
        source_index = self._proxy.mapToSource(current)
        project = self._model.project_at(source_index.row())
        if project is None:
            self._clear_detail()
            return
        self._show_detail(project)

    def _on_double_clicked(self, index: QModelIndex) -> None:
        if not index.isValid():
            return
        source_index = self._proxy.mapToSource(index)
        project = self._model.project_at(source_index.row())
        if project is None:
            return
        self._show_detail(project)

    def _on_context_menu(self, position) -> None:
        index = self._table.indexAt(position)
        if not index.isValid():
            return
        source_index = self._proxy.mapToSource(index)
        project = self._model.project_at(source_index.row())
        if project is None:
            return
        menu = QMenu(self._table)

        edit_action = menu.addAction("Edit…")
        edit_action.triggered.connect(
            lambda _checked=False, key=project.key: self._edit_project_by_key(key)
        )
        export_action = menu.addAction("Export…")
        export_action.triggered.connect(
            lambda _checked=False, key=project.key: self._export_project_by_key(key)
        )

        stage_menu = menu.addMenu("Change stage")
        for stage in ProjectStage:
            action = stage_menu.addAction(stage.display_name)
            action.setCheckable(True)
            action.setChecked(project.stage is stage)
            action.triggered.connect(
                lambda _checked=False, key=project.key, s=stage: self._change_stage(
                    key, s
                )
            )

        menu.addSeparator()
        delete_action = menu.addAction("Delete…")
        delete_action.triggered.connect(
            lambda _checked=False, key=project.key: self._delete_project_by_key(key)
        )

        menu.exec(self._table.viewport().mapToGlobal(position))

    def _on_detail_stage_changed(self, _index: int) -> None:
        if self._current_project_key is None:
            return
        value = self._detail_stage_combo.currentData()
        if not isinstance(value, str):
            return
        try:
            stage = ProjectStage(value)
        except ValueError:
            return
        if self._service is None:
            return
        try:
            current = self._service.get_project(self._current_project_key)
        except ProjectError:
            return
        if current.stage is stage:
            return
        self._change_stage(self._current_project_key, stage)

    def _on_create_project(self) -> None:
        if self._service is None:
            self._show_error("The project service is not attached.")
            return
        fields = (
            FormField(
                identifier="key",
                label="Project key",
                kind=FormFieldKind.TEXT,
                placeholder="lowercase-with-hyphens",
                validator=_validate_project_key,
            ),
            FormField(
                identifier="title",
                label="Title",
                kind=FormFieldKind.TEXT,
                validator=_validate_optional_length(512),
            ),
            FormField(
                identifier="topic",
                label="Topic",
                kind=FormFieldKind.MULTILINE,
                placeholder="A short description of the research area.",
                validator=_validate_optional_length(1024),
            ),
            FormField(
                identifier="stage",
                label="Stage",
                kind=FormFieldKind.SELECT,
                options=tuple((stage.value, stage.display_name) for stage in ProjectStage),
                initial=ProjectStage.IDEA.value,
            ),
        )
        values = DialogFactory.form(
            self,
            "New research project",
            fields,
            submit_label="Create",
            cancel_label="Cancel",
        )
        if values is None:
            return
        try:
            stage_value = str(values.get("stage") or ProjectStage.IDEA.value)
            stage = ProjectStage(stage_value)
        except (TypeError, ValueError):
            stage = ProjectStage.IDEA
        try:
            view = self._service.create_project(
                key=str(values.get("key") or "").strip(),
                title=str(values.get("title") or "").strip(),
                topic=str(values.get("topic") or "").strip(),
                stage=stage,
            )
        except ProjectValidationError as exc:
            self._show_error("; ".join(exc.issues))
            return
        except ProjectError as exc:
            self._show_error(str(exc))
            return
        self._current_project_key = view.key
        self.refresh()
        self._select_by_key(view.key)

    def _on_edit_project(self) -> None:
        if self._current_project_key is None:
            return
        self._edit_project_by_key(self._current_project_key)

    def _edit_project_by_key(self, key: str) -> None:
        if self._service is None:
            return
        try:
            project = self._service.get_project(key)
        except ProjectError as exc:
            self._show_error(str(exc))
            return
        fields = (
            FormField(
                identifier="title",
                label="Title",
                kind=FormFieldKind.TEXT,
                initial=project.title,
                validator=_validate_optional_length(512),
            ),
            FormField(
                identifier="topic",
                label="Topic",
                kind=FormFieldKind.MULTILINE,
                initial=project.topic,
                validator=_validate_optional_length(1024),
            ),
        )
        values = DialogFactory.form(
            self,
            f"Edit project: {project.display_label}",
            fields,
            submit_label="Save",
            cancel_label="Cancel",
        )
        if values is None:
            return
        try:
            self._service.update_project(
                key,
                title=str(values.get("title") or "").strip(),
                topic=str(values.get("topic") or "").strip(),
            )
        except ProjectValidationError as exc:
            self._show_error("; ".join(exc.issues))
            return
        except ProjectError as exc:
            self._show_error(str(exc))
            return
        self.refresh()
        self._select_by_key(key)

    def _change_stage(self, key: str, stage: ProjectStage) -> None:
        if self._service is None:
            return
        try:
            self._service.update_project(key, stage=stage)
        except ProjectError as exc:
            self._show_error(str(exc))
            return
        self.refresh()
        self._select_by_key(key)

    def _delete_project_by_key(self, key: str) -> None:
        outcome = DialogFactory.confirm(
            self,
            "Delete project",
            (
                "Delete this project and its research questions and tasks? "
                "The linked documents are not deleted."
            ),
            confirm_label="Delete",
            cancel_label="Cancel",
            destructive=True,
            default_to_confirm=False,
        )
        if outcome.result is not ConfirmResult.CONFIRMED:
            return
        if self._service is None:
            return
        try:
            self._service.delete_project(key)
        except ProjectError as exc:
            self._show_error(str(exc))
            return
        if self._current_project_key == key:
            self._current_project_key = None
        self.refresh()

    # ------------------------------------------------------------------
    # Question actions
    # ------------------------------------------------------------------
    def _on_add_question(self) -> None:
        if self._service is None or self._current_project_key is None:
            return
        fields = (
            FormField(
                identifier="text",
                label="Question",
                kind=FormFieldKind.MULTILINE,
                placeholder="What question does this project answer?",
                validator=_validate_required("Question"),
            ),
            FormField(
                identifier="kind",
                label="Kind",
                kind=FormFieldKind.SELECT,
                options=(
                    ("main", "Main"),
                    ("sub", "Sub"),
                    ("exploratory", "Exploratory"),
                    ("hypothesis", "Hypothesis"),
                ),
                initial="main",
            ),
            FormField(
                identifier="is_primary",
                label="Set as primary question",
                kind=FormFieldKind.CHECKBOX,
            ),
        )
        values = DialogFactory.form(
            self,
            "Add research question",
            fields,
            submit_label="Add",
            cancel_label="Cancel",
        )
        if values is None:
            return
        try:
            self._service.add_question(
                self._current_project_key,
                text=str(values.get("text") or "").strip(),
                kind=str(values.get("kind") or "main"),
                is_primary=bool(values.get("is_primary")),
            )
        except ProjectValidationError as exc:
            self._show_error("; ".join(exc.issues))
            return
        except ProjectError as exc:
            self._show_error(str(exc))
            return
        self._reload_questions()

    def _on_edit_question(self) -> None:
        if self._service is None or self._current_project_key is None:
            return
        item = self._questions_list.currentItem()
        if item is None:
            return
        question = item.data(Qt.ItemDataRole.UserRole)
        if question is None:
            return
        fields = (
            FormField(
                identifier="text",
                label="Question",
                kind=FormFieldKind.MULTILINE,
                initial=question.text,
                validator=_validate_required("Question"),
            ),
            FormField(
                identifier="kind",
                label="Kind",
                kind=FormFieldKind.SELECT,
                options=(
                    ("main", "Main"),
                    ("sub", "Sub"),
                    ("exploratory", "Exploratory"),
                    ("hypothesis", "Hypothesis"),
                ),
                initial=question.kind,
            ),
            FormField(
                identifier="is_primary",
                label="Primary question",
                kind=FormFieldKind.CHECKBOX,
                initial="true" if question.is_primary else "",
            ),
        )
        values = DialogFactory.form(
            self,
            "Edit research question",
            fields,
            submit_label="Save",
            cancel_label="Cancel",
        )
        if values is None:
            return
        try:
            self._service.update_question(
                self._current_project_key,
                question.identifier,
                text=str(values.get("text") or "").strip(),
                kind=str(values.get("kind") or "main"),
                is_primary=bool(values.get("is_primary")),
            )
        except ProjectValidationError as exc:
            self._show_error("; ".join(exc.issues))
            return
        except ProjectError as exc:
            self._show_error(str(exc))
            return
        self._reload_questions()

    def _on_remove_question(self) -> None:
        if self._service is None or self._current_project_key is None:
            return
        item = self._questions_list.currentItem()
        if item is None:
            return
        question = item.data(Qt.ItemDataRole.UserRole)
        if question is None:
            return
        outcome = DialogFactory.confirm(
            self,
            "Remove research question",
            f"Remove the question {question.text[:80]!r}?",
            confirm_label="Remove",
            cancel_label="Cancel",
            destructive=True,
            default_to_confirm=False,
        )
        if outcome.result is not ConfirmResult.CONFIRMED:
            return
        try:
            self._service.remove_question(
                self._current_project_key, question.identifier
            )
        except ProjectError as exc:
            self._show_error(str(exc))
            return
        self._reload_questions()

    def _on_set_primary_question(self) -> None:
        if self._service is None or self._current_project_key is None:
            return
        item = self._questions_list.currentItem()
        if item is None:
            return
        question = item.data(Qt.ItemDataRole.UserRole)
        if question is None:
            return
        try:
            self._service.set_primary_question(
                self._current_project_key, question.identifier
            )
        except ProjectError as exc:
            self._show_error(str(exc))
            return
        self._reload_questions()

    def _on_question_selected(
        self,
        current: QListWidgetItem | None,
        _previous: QListWidgetItem | None,
    ) -> None:
        enabled = current is not None
        self._set_primary_button.setEnabled(enabled)
        self._remove_question_button.setEnabled(enabled)

    # ------------------------------------------------------------------
    # Task actions
    # ------------------------------------------------------------------
    def _on_add_task(self) -> None:
        if self._service is None or self._current_project_key is None:
            return
        fields = (
            FormField(
                identifier="title",
                label="Title",
                kind=FormFieldKind.TEXT,
                validator=_validate_required("Title"),
            ),
            FormField(
                identifier="description",
                label="Description",
                kind=FormFieldKind.MULTILINE,
                placeholder="Optional details.",
            ),
        )
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
            self._service.add_task(
                self._current_project_key,
                title=str(values.get("title") or "").strip(),
                description=str(values.get("description") or "").strip(),
            )
        except ProjectValidationError as exc:
            self._show_error("; ".join(exc.issues))
            return
        except ProjectError as exc:
            self._show_error(str(exc))
            return
        self._reload_tasks()

    def _on_edit_task(self) -> None:
        if self._service is None or self._current_project_key is None:
            return
        item = self._tasks_list.currentItem()
        if item is None:
            return
        task = item.data(Qt.ItemDataRole.UserRole)
        if task is None:
            return
        fields = (
            FormField(
                identifier="title",
                label="Title",
                kind=FormFieldKind.TEXT,
                initial=task.title,
                validator=_validate_required("Title"),
            ),
            FormField(
                identifier="description",
                label="Description",
                kind=FormFieldKind.MULTILINE,
                initial=task.description,
            ),
        )
        values = DialogFactory.form(
            self,
            "Edit task",
            fields,
            submit_label="Save",
            cancel_label="Cancel",
        )
        if values is None:
            return
        try:
            self._service.update_task(
                self._current_project_key,
                task.identifier,
                title=str(values.get("title") or "").strip(),
                description=str(values.get("description") or "").strip(),
            )
        except ProjectValidationError as exc:
            self._show_error("; ".join(exc.issues))
            return
        except ProjectError as exc:
            self._show_error(str(exc))
            return
        self._reload_tasks()

    def _on_toggle_task(self) -> None:
        if self._service is None or self._current_project_key is None:
            return
        item = self._tasks_list.currentItem()
        if item is None:
            return
        task = item.data(Qt.ItemDataRole.UserRole)
        if task is None:
            return
        try:
            self._service.update_task(
                self._current_project_key,
                task.identifier,
                completed=not task.completed,
            )
        except ProjectError as exc:
            self._show_error(str(exc))
            return
        self._reload_tasks()

    def _on_remove_task(self) -> None:
        if self._service is None or self._current_project_key is None:
            return
        item = self._tasks_list.currentItem()
        if item is None:
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
            self._service.remove_task(
                self._current_project_key, task.identifier
            )
        except ProjectError as exc:
            self._show_error(str(exc))
            return
        self._reload_tasks()

    def _on_task_selected(
        self,
        current: QListWidgetItem | None,
        _previous: QListWidgetItem | None,
    ) -> None:
        enabled = current is not None
        self._toggle_task_button.setEnabled(enabled)
        self._remove_task_button.setEnabled(enabled)

    # ------------------------------------------------------------------
    # Rendering helpers
    # ------------------------------------------------------------------
    def _show_detail(self, project: ProjectView) -> None:
        self._current_project_key = project.key
        self._detail_title.setText(project.display_label)
        self._detail_topic.setText(project.topic or "")
        self._detail_stage_combo.blockSignals(True)
        for index in range(self._detail_stage_combo.count()):
            if self._detail_stage_combo.itemData(index) == project.stage.value:
                self._detail_stage_combo.setCurrentIndex(index)
                break
        self._detail_stage_combo.blockSignals(False)
        self._detail_stage_combo.setEnabled(True)
        self._detail_summary.setText(
            f"{project.question_count} question(s) · "
            f"{project.total_task_count - project.open_task_count}/"
            f"{project.total_task_count} task(s) completed · "
            f"{project.document_count} document(s)"
        )
        self._edit_button.setEnabled(True)
        self._export_button.setEnabled(True)
        self._add_question_button.setEnabled(True)
        self._add_task_button.setEnabled(True)
        self._reload_questions()
        self._reload_tasks()
        if self._task_service is not None:
            self._milestones_panel.set_project(project.key)

    def _clear_detail(self) -> None:
        self._current_project_key = None
        self._detail_title.setText("Select a project to view details.")
        self._detail_topic.setText("")
        self._detail_stage_combo.setEnabled(False)
        self._detail_summary.setText("")
        self._edit_button.setEnabled(False)
        self._export_button.setEnabled(False)
        self._add_question_button.setEnabled(False)
        self._add_task_button.setEnabled(False)
        self._questions_list.clear()
        self._tasks_list.clear()
        self._set_primary_button.setEnabled(False)
        self._remove_question_button.setEnabled(False)
        self._toggle_task_button.setEnabled(False)
        self._remove_task_button.setEnabled(False)
        self._milestones_panel.set_project("")

    def _reload_questions(self) -> None:
        self._questions_list.clear()
        if self._service is None or self._current_project_key is None:
            return
        try:
            questions = self._service.list_questions(self._current_project_key)
        except ProjectError as exc:
            _logger.warning("Unable to load questions: %s", exc)
            return
        for question in questions:
            item = QListWidgetItem(question.display_label)
            item.setData(Qt.ItemDataRole.UserRole, question)
            self._questions_list.addItem(item)

    def _reload_tasks(self) -> None:
        self._tasks_list.clear()
        if self._service is None or self._current_project_key is None:
            return
        try:
            tasks = self._service.list_tasks(self._current_project_key)
        except ProjectError as exc:
            _logger.warning("Unable to load tasks: %s", exc)
            return
        for task in tasks:
            item = QListWidgetItem(task.display_label)
            item.setData(Qt.ItemDataRole.UserRole, task)
            self._tasks_list.addItem(item)

    def _select_by_key(self, key: str) -> None:
        for row in range(self._model.rowCount()):
            project = self._model.project_at(row)
            if project is None or project.key != key:
                continue
            source_index = self._model.index(row, 0)
            proxy_index = self._proxy.mapFromSource(source_index)
            if proxy_index.isValid():
                self._table.setCurrentIndex(proxy_index)
                self._table.scrollTo(proxy_index)
                self._show_detail(project)
            return

    def _update_summary(self, count: int) -> None:
        self.set_subtitle(
            f"{count} research project(s)."
            if count
            else "No research projects yet."
        )

    def _update_empty_state(self) -> None:
        if self._model.rowCount() == 0:
            self.show_empty_state()
        else:
            self.show_content()

    def _show_error(self, message: str) -> None:
        DialogFactory.message(
            self,
            "Project error",
            message,
            kind=MessageKind.ERROR,
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def on_activated(self) -> None:
        self.refresh()

    def attach_export_service(self, service: ProjectExportService) -> None:
        """Attach the application-layer project export service."""
        self._export_service = service

    def _on_export_project(self) -> None:
        if self._current_project_key is None:
            return
        self._export_project_by_key(self._current_project_key)

    def _export_project_by_key(self, key: str) -> None:
        if self._export_service is None:
            self._show_error("The export service is not attached.")
            return
        dialog = ProjectExportDialog(
            self._export_service, key, parent=self
        )
        dialog.exec()

# ----------------------------------------------------------------------
# Rendering helpers
# ----------------------------------------------------------------------
def _display_value(project: ProjectView, column: str) -> str:
    if column == "title":
        return project.display_label
    if column == "stage":
        return project.stage.display_name
    if column == "questions":
        return str(project.question_count)
    if column == "tasks":
        completed = project.total_task_count - project.open_task_count
        return f"{completed}/{project.total_task_count}"
    if column == "documents":
        return str(project.document_count)
    if column == "updated_at":
        return project.updated_at[:19].replace("T", " ") if project.updated_at else "—"
    return ""


def _tooltip_value(project: ProjectView, column: str) -> str:
    if column == "title":
        return project.topic or project.key
    return ""


# ----------------------------------------------------------------------
# Form validators
# ----------------------------------------------------------------------
def _validate_project_key(value: str) -> str | None:
    cleaned = value.strip()
    if not cleaned:
        return "Project key must not be empty"
    if not cleaned[0].isalnum():
        return "Project key must start with a letter or digit"
    for character in cleaned:
        if not (character.isalnum() or character in "-_"):
            return "Project key may contain letters, digits, hyphens, and underscores"
    if cleaned != cleaned.lower():
        return "Project key must be lowercase"
    return None


def _validate_optional_length(limit: int):
    def _validator(value: str) -> str | None:
        if len(value) > limit:
            return f"Must be at most {limit} characters"
        return None

    return _validator


def _validate_required(field: str):
    def _validator(value: str) -> str | None:
        if not value.strip():
            return f"{field} must not be empty"
        return None

    return _validator