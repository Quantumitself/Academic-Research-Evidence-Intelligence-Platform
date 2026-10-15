"""Research History section.

The section is a search-backed workspace. It proposes alternative
queries from the topic and its synonyms, executes them through the
search orchestration service, and renders the retrieved results as a
timeline and a set of themes. The narrative editor captures the user's
own interpretation; the section never generates narrative text.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from academic_platform.application.research_history.errors import (
    ResearchHistoryError,
    ResearchHistorySearchError,
    ResearchHistoryValidationError,
)
from academic_platform.application.research_history.model import (
    HistoryQuery,
    HistoryResult,
    HistorySearchRun,
    HistoryTheme,
    HistoryTimelineBucket,
)
from academic_platform.application.research_history.service import (
    ResearchHistoryService,
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


class ResearchHistorySection(AssistantSection):
    """Research History section backed by the research-history service."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(AssistantSectionId.RESEARCH_HISTORY, parent=parent)
        self._service: ResearchHistoryService | None = None
        self._project_key: str = ""
        self._loading = False

        content = QWidget(self)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        topic_row = QHBoxLayout()
        topic_row.setContentsMargins(0, 0, 0, 0)
        topic_row.setSpacing(6)

        topic_label = QLabel("Topic:", parent=content)
        topic_label.setObjectName("historyTopicLabel")
        topic_row.addWidget(topic_label)

        self._topic_input = QLineEdit(content)
        self._topic_input.setObjectName("historyTopicInput")
        self._topic_input.setPlaceholderText(
            "The topic to investigate, for example 'measurement invariance'."
        )
        self._topic_input.editingFinished.connect(self._on_topic_edited)
        topic_row.addWidget(self._topic_input, 1)

        layout.addLayout(topic_row)

        synonym_row = QHBoxLayout()
        synonym_row.setContentsMargins(0, 0, 0, 0)
        synonym_row.setSpacing(6)

        self._synonym_input = QLineEdit(content)
        self._synonym_input.setObjectName("historySynonymInput")
        self._synonym_input.setPlaceholderText(
            "Add a synonym for the topic, for example 'measurement equivalence'."
        )
        synonym_row.addWidget(self._synonym_input, 1)

        self._add_synonym_button = QPushButton("Add synonym", content)
        self._add_synonym_button.setObjectName("historyAddSynonym")
        self._add_synonym_button.setAutoDefault(False)
        self._add_synonym_button.clicked.connect(self._on_add_synonym)
        synonym_row.addWidget(self._add_synonym_button)

        self._remove_synonym_button = QPushButton("Remove synonym", content)
        self._remove_synonym_button.setObjectName("historyRemoveSynonym")
        self._remove_synonym_button.setAutoDefault(False)
        self._remove_synonym_button.clicked.connect(self._on_remove_synonym)
        synonym_row.addWidget(self._remove_synonym_button)

        layout.addLayout(synonym_row)

        self._synonyms_list = QListWidget(content)
        self._synonyms_list.setObjectName("historySynonymsList")
        self._synonyms_list.setMaximumHeight(120)
        self._synonyms_list.currentItemChanged.connect(
            self._on_synonym_selected
        )
        layout.addWidget(self._synonyms_list)

        query_row = QHBoxLayout()
        query_row.setContentsMargins(0, 0, 0, 0)
        query_row.setSpacing(6)

        self._query_input = QLineEdit(content)
        self._query_input.setObjectName("historyQueryInput")
        self._query_input.setPlaceholderText(
            "Add your own search query…"
        )
        query_row.addWidget(self._query_input, 1)

        self._add_query_button = QPushButton("Add query", content)
        self._add_query_button.setObjectName("historyAddQuery")
        self._add_query_button.setAutoDefault(False)
        self._add_query_button.clicked.connect(self._on_add_query)
        query_row.addWidget(self._add_query_button)

        self._remove_query_button = QPushButton("Remove query", content)
        self._remove_query_button.setObjectName("historyRemoveQuery")
        self._remove_query_button.setAutoDefault(False)
        self._remove_query_button.clicked.connect(self._on_remove_query)
        query_row.addWidget(self._remove_query_button)

        layout.addLayout(query_row)

        actions = QHBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(6)

        self._run_all_button = QPushButton("Run all queries", content)
        self._run_all_button.setObjectName("historyRunAll")
        self._run_all_button.setAutoDefault(False)
        self._run_all_button.clicked.connect(self._on_run_all)
        actions.addWidget(self._run_all_button)

        self._run_selected_button = QPushButton("Run selected", content)
        self._run_selected_button.setObjectName("historyRunSelected")
        self._run_selected_button.setAutoDefault(False)
        self._run_selected_button.clicked.connect(self._on_run_selected)
        actions.addWidget(self._run_selected_button)

        self._clear_button = QPushButton("Clear workspace", content)
        self._clear_button.setObjectName("historyClear")
        self._clear_button.setAutoDefault(False)
        self._clear_button.clicked.connect(self._on_clear)
        actions.addWidget(self._clear_button)

        actions.addStretch(1)
        layout.addLayout(actions)

        self._tabs = QTabWidget(content)
        self._tabs.setObjectName("historyTabs")

        self._queries_tab = self._build_queries_tab(self._tabs)
        self._runs_tab = self._build_runs_tab(self._tabs)
        self._timeline_tab = self._build_timeline_tab(self._tabs)
        self._themes_tab = self._build_themes_tab(self._tabs)
        self._results_tab = self._build_results_tab(self._tabs)

        self._tabs.addTab(self._queries_tab, "Queries")
        self._tabs.addTab(self._runs_tab, "Runs")
        self._tabs.addTab(self._timeline_tab, "Timeline")
        self._tabs.addTab(self._themes_tab, "Themes")
        self._tabs.addTab(self._results_tab, "Results")
        layout.addWidget(self._tabs, 1)

        self._narrative = make_multiline_field(
            content,
            "Narrative",
            placeholder=(
                "Write your own interpretation of the topic's history. "
                "The workspace does not generate this text."
            ),
            minimum_height=120,
        )
        self._narrative.textChanged.connect(self._on_narrative_changed)

        self._install_content(content)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def attach_service(
        self,
        service: ResearchHistoryService,
        project_key: str,
    ) -> None:
        self._service = service
        self._project_key = project_key
        if project_key:
            try:
                service.attach_project(project_key)
            except ResearchHistoryError as exc:
                self._show_error("Unable to attach project", str(exc))
        self._populate_from_service()

    def set_project(self, project_key: str) -> None:
        self._project_key = project_key
        if self._service is not None and project_key:
            try:
                self._service.attach_project(project_key)
            except ResearchHistoryError as exc:
                self._show_error("Unable to attach project", str(exc))
        self._populate_from_service()

    # ------------------------------------------------------------------
    # Tab construction
    # ------------------------------------------------------------------
    def _build_queries_tab(self, parent: QWidget) -> QWidget:
        container = QWidget(parent)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self._queries_list = QListWidget(container)
        self._queries_list.setObjectName("historyQueriesList")
        layout.addWidget(self._queries_list)
        return container

    def _build_runs_tab(self, parent: QWidget) -> QWidget:
        container = QWidget(parent)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self._runs_list = QListWidget(container)
        self._runs_list.setObjectName("historyRunsList")
        layout.addWidget(self._runs_list)
        return container

    def _build_timeline_tab(self, parent: QWidget) -> QWidget:
        container = QWidget(parent)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self._timeline_list = QListWidget(container)
        self._timeline_list.setObjectName("historyTimelineList")
        layout.addWidget(self._timeline_list)
        return container

    def _build_themes_tab(self, parent: QWidget) -> QWidget:
        container = QWidget(parent)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self._themes_list = QListWidget(container)
        self._themes_list.setObjectName("historyThemesList")
        layout.addWidget(self._themes_list)
        return container

    def _build_results_tab(self, parent: QWidget) -> QWidget:
        container = QWidget(parent)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self._results_list = QListWidget(container)
        self._results_list.setObjectName("historyResultsList")
        layout.addWidget(self._results_list)
        return container

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------
    def _on_topic_edited(self) -> None:
        if self._loading or self._service is None or not self._project_key:
            return
        try:
            self._service.set_topic(
                self._project_key, self._topic_input.text()
            )
        except ResearchHistoryValidationError as exc:
            self._show_error("Invalid topic", "; ".join(exc.issues))
            return
        except ResearchHistoryError as exc:
            self._show_error("Unable to save the topic", str(exc))
            return
        self._populate_from_service()

    def _on_add_synonym(self) -> None:
        if self._service is None or not self._project_key:
            return
        text = self._synonym_input.text().strip()
        if not text:
            return
        try:
            self._service.add_synonym(self._project_key, text)
        except ResearchHistoryValidationError as exc:
            self._show_error("Invalid synonym", "; ".join(exc.issues))
            return
        except ResearchHistoryError as exc:
            self._show_error("Unable to add the synonym", str(exc))
            return
        self._synonym_input.clear()
        self._populate_from_service()

    def _on_remove_synonym(self) -> None:
        if self._service is None or not self._project_key:
            return
        item = self._synonyms_list.currentItem()
        if item is None:
            return
        synonym = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(synonym, str):
            return
        try:
            self._service.remove_synonym(self._project_key, synonym)
        except ResearchHistoryError as exc:
            self._show_error("Unable to remove the synonym", str(exc))
            return
        self._populate_from_service()

    def _on_synonym_selected(
        self,
        _current: QListWidgetItem | None,
        _previous: QListWidgetItem | None,
    ) -> None:
        pass

    def _on_add_query(self) -> None:
        if self._service is None or not self._project_key:
            return
        text = self._query_input.text().strip()
        if not text:
            return
        try:
            self._service.add_user_query(self._project_key, text)
        except ResearchHistoryValidationError as exc:
            self._show_error("Invalid query", "; ".join(exc.issues))
            return
        except ResearchHistoryError as exc:
            self._show_error("Unable to add the query", str(exc))
            return
        self._query_input.clear()
        self._populate_from_service()

    def _on_remove_query(self) -> None:
        if self._service is None or not self._project_key:
            return
        item = self._queries_list.currentItem()
        if item is None:
            return
        query = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(query, HistoryQuery):
            return
        if not query.is_user_defined:
            self._show_error(
                "Cannot remove a proposed query",
                (
                    "Proposed queries are generated by the workspace. "
                    "Only user-defined queries can be removed."
                ),
            )
            return
        try:
            self._service.remove_user_query(
                self._project_key, query.identifier
            )
        except ResearchHistoryError as exc:
            self._show_error("Unable to remove the query", str(exc))
            return
        self._populate_from_service()

    def _on_run_selected(self) -> None:
        if self._service is None or not self._project_key:
            return
        item = self._queries_list.currentItem()
        if item is None:
            return
        query = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(query, HistoryQuery):
            return
        self._run_query(query)

    def _on_run_all(self) -> None:
        if self._service is None or not self._project_key:
            return
        try:
            runs = self._service.run_all(self._project_key)
        except ResearchHistoryError as exc:
            self._show_error("Unable to run the queries", str(exc))
            return
        failures = [r for r in runs if r.result_count == 0]
        if failures:
            self._show_error(
                "Some queries returned no results",
                "\n".join(
                    f"{r.query_text}: {r.status.display_name}"
                    for r in failures
                ),
            )
        self._populate_from_service()

    def _on_clear(self) -> None:
        if self._service is None or not self._project_key:
            return
        outcome = DialogFactory.confirm(
            self,
            "Clear research-history workspace",
            (
                "Clear the topic, the synonyms, the queries, the runs and "
                "the retrieved results? This action cannot be undone."
            ),
            confirm_label="Clear",
            cancel_label="Cancel",
            destructive=True,
            default_to_confirm=False,
        )
        if outcome.result is not ConfirmResult.CONFIRMED:
            return
        try:
            self._service.clear(self._project_key)
        except ResearchHistoryError as exc:
            self._show_error("Unable to clear the workspace", str(exc))
            return
        self._populate_from_service()

    def _on_narrative_changed(self) -> None:
        if self._loading or self._service is None or not self._project_key:
            return
        try:
            self._service.set_narrative(
                self._project_key, self._narrative.toPlainText()
            )
        except ResearchHistoryValidationError as exc:
            self._show_error("Invalid narrative", "; ".join(exc.issues))
        except ResearchHistoryError as exc:
            self._show_error("Unable to save the narrative", str(exc))

    def _run_query(self, query: HistoryQuery) -> None:
        if self._service is None or not self._project_key:
            return
        try:
            run = self._service.run_query(self._project_key, query)
        except ResearchHistorySearchError as exc:
            self._show_error("Search failed", str(exc))
            return
        except ResearchHistoryError as exc:
            self._show_error("Unable to run the query", str(exc))
            return
        if run.result_count == 0:
            self._show_error(
                "No results",
                f"The query {query.text!r} returned no results.",
            )
        self._populate_from_service()

    # ------------------------------------------------------------------
    # Contract
    # ------------------------------------------------------------------
    def summary(self) -> str:
        parts: list[str] = []
        topic = self._topic_input.text().strip()
        if topic:
            parts.append(f"topic: {topic[:40]}")
        if self._synonyms_list.count():
            parts.append(f"{self._synonyms_list.count()} synonym(s)")
        if self._results_list.count():
            parts.append(f"{self._results_list.count()} result(s)")
        return " · ".join(parts)

    def reset(self) -> None:
        self._on_clear()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _populate_from_service(self) -> None:
        if self._service is None or not self._project_key:
            return
        self._loading = True
        try:
            draft = self._service.current_draft(self._project_key)
            self._topic_input.blockSignals(True)
            self._narrative.blockSignals(True)
            try:
                self._topic_input.setText(draft.topic)
                self._narrative.setPlainText(draft.narrative)
            finally:
                self._topic_input.blockSignals(False)
                self._narrative.blockSignals(False)
            self._populate_synonyms(draft.synonyms)
            self._populate_queries(self._service.propose_queries(self._project_key))
            self._populate_runs(draft.runs)
            self._populate_timeline(draft.timeline)
            self._populate_themes(draft.themes)
            self._populate_results(draft.results)
        finally:
            self._loading = False

    def _populate_synonyms(self, synonyms: tuple[str, ...]) -> None:
        self._synonyms_list.clear()
        for synonym in synonyms:
            item = QListWidgetItem(synonym, self._synonyms_list)
            item.setData(Qt.ItemDataRole.UserRole, synonym)

    def _populate_queries(self, queries: list[HistoryQuery]) -> None:
        self._queries_list.clear()
        for query in queries:
            item = QListWidgetItem(query.display_label, self._queries_list)
            item.setData(Qt.ItemDataRole.UserRole, query)
            if query.rationale:
                item.setToolTip(query.rationale)

    def _populate_runs(self, runs: tuple[HistorySearchRun, ...]) -> None:
        self._runs_list.clear()
        for run in runs:
            item = QListWidgetItem(run.display_label, self._runs_list)
            item.setData(Qt.ItemDataRole.UserRole, run)
            if run.message:
                item.setToolTip(run.message)

    def _populate_timeline(
        self, timeline: tuple[HistoryTimelineBucket, ...]
    ) -> None:
        self._timeline_list.clear()
        for bucket in timeline:
            item = QListWidgetItem(
                bucket.display_label, self._timeline_list
            )
            item.setData(Qt.ItemDataRole.UserRole, bucket)

    def _populate_themes(self, themes: tuple[HistoryTheme, ...]) -> None:
        self._themes_list.clear()
        for theme in themes:
            item = QListWidgetItem(theme.display_label, self._themes_list)
            item.setData(Qt.ItemDataRole.UserRole, theme)
            if theme.rationale:
                item.setToolTip(theme.rationale)

    def _populate_results(self, results: tuple[HistoryResult, ...]) -> None:
        self._results_list.clear()
        for result in results:
            item = QListWidgetItem(result.display_label, self._results_list)
            item.setData(Qt.ItemDataRole.UserRole, result)
            if result.abstract:
                item.setToolTip(result.abstract)

    def _show_error(self, title: str, message: str) -> None:
        DialogFactory.message(self, title, message, kind=MessageKind.ERROR)