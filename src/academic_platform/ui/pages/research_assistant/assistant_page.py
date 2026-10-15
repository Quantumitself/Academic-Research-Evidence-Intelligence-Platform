"""Research assistant page.

The page hosts the ten sections declared by the product specification.
A sidebar lists the sections in order; selecting one activates the
section and switches the content stack. Work is preserved across
navigation because each section is a persistent widget.

Design decisions
----------------
- The page owns a single content stack; sections are added to the
  stack and remain constructed for the lifetime of the page.
- The sidebar renders a summary per section; the summary is refreshed
  when the section is activated and when the user clicks the sidebar's
  refresh action.
- The review section is given a summary provider at construction time
  that composes a summary from every other section. The page owns the
  provider; the section calls it.
- The page does not perform any AI or rule-based reasoning. The
  sections are the structural foundation the next phases fill.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from academic_platform.ui.main_window_destinations import get_destination
from academic_platform.ui.pages.base_page import BasePage
from academic_platform.ui.pages.research_assistant.section_base import (
    AssistantSection,
    AssistantSectionId,
)
from academic_platform.ui.pages.research_assistant.section_host import (
    SectionHost,
)
from academic_platform.ui.pages.research_assistant.sections import (
    create_section,
)
from academic_platform.application.topic_workspace.service import (
    TopicWorkspaceService,
)
from academic_platform.application.title_builder.service import (
    TitleBuilderService,
)
from academic_platform.application.research_questions.service import (
    ResearchQuestionWorkspaceService,
)
from academic_platform.application.research_history.service import (
    ResearchHistoryService,
)



_logger = logging.getLogger(__name__)


class ResearchAssistantPage(BasePage):
    """Research assistant page hosting the ten workflow sections."""

    #: Emitted when the user requests to move to a different destination
    #: (for example, to open the project export dialog).
    destination_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        destination = get_destination("research_assistant")
        super().__init__(
            title=destination.label,
            subtitle=destination.purpose,
            parent=parent,
        )
        self.setObjectName("researchAssistantPage")

        self._hosts: dict[AssistantSectionId, SectionHost] = {}
        self._current_section_id: AssistantSectionId | None = None
        self._topic_service: TopicWorkspaceService | None = None
        self._title_service: TitleBuilderService | None = None
        self._question_service: ResearchQuestionWorkspaceService | None = None
        self._history_service: ResearchHistoryService | None = None

        self._build_content()
        self._wire_header_actions()
        self._select_section(AssistantSectionId.TOPIC)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def section(self, section_id: AssistantSectionId) -> AssistantSection:
        """Return the section for the given identifier."""
        host = self._hosts.get(section_id)
        if host is None:
            raise KeyError(f"Section is not registered: {section_id!r}")
        return host.section

    def select_section(self, section_id: AssistantSectionId) -> None:
        """Programmatically select a section."""
        self._select_section(section_id)

    def refresh_summaries(self) -> None:
        """Refresh every section's summary label."""
        for host in self._hosts.values():
            host.refresh_summary()
        self._refresh_sidebar_summaries()

    # ------------------------------------------------------------------
    # Content construction
    # ------------------------------------------------------------------
    def _build_content(self) -> None:
        content = QWidget(self)
        content.setObjectName("researchAssistantContent")
        layout = QHBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal, content)
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(self._build_sidebar(content))
        splitter.addWidget(self._build_stack(content))
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([260, 900])
        layout.addWidget(splitter, 1)

        self._install_content(content, scrollable=False)

    def _build_sidebar(self, parent: QWidget) -> QWidget:
        container = QWidget(parent)
        container.setObjectName("assistantSidebar")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(12, 16, 12, 16)
        layout.setSpacing(8)

        heading = QLabel("Sections", container)
        heading.setObjectName("assistantSidebarHeading")
        layout.addWidget(heading)

        self._section_list = QListWidget(container)
        self._section_list.setObjectName("assistantSectionList")
        self._section_list.setUniformItemSizes(False)
        self._section_list.setSelectionMode(
            QListWidget.SelectionMode.SingleSelection
        )
        for section_id in AssistantSectionId:
            item = QListWidgetItem(section_id.display_name, self._section_list)
            item.setData(Qt.ItemDataRole.UserRole, section_id.value)
            item.setToolTip(section_id.description)
        self._section_list.currentItemChanged.connect(
            self._on_section_list_changed
        )
        layout.addWidget(self._section_list, 1)

        refresh_button = QPushButton("Refresh summaries", container)
        refresh_button.setObjectName("assistantRefreshSummaries")
        refresh_button.setAutoDefault(False)
        refresh_button.clicked.connect(self.refresh_summaries)
        layout.addWidget(refresh_button)

        return container

    def _build_stack(self, parent: QWidget) -> QWidget:
        self._stack = QStackedWidget(parent)
        self._stack.setObjectName("assistantStack")
        review_section: AssistantSection | None = None
        for section_id in AssistantSectionId:
            section = create_section(section_id, parent=self._stack)
            host = SectionHost(section, self._stack)
            host.summary_changed.connect(self._refresh_sidebar_summaries)
            self._hosts[section_id] = host
            self._stack.addWidget(host)
            if section_id is AssistantSectionId.REVIEW:
                review_section = section
        if review_section is not None:
            review_section.set_summary_provider(self._build_review_summary)
        return self._stack

    def _wire_header_actions(self) -> None:
        self._projects_button = QPushButton("Open projects…", self)
        self._projects_button.setObjectName("assistantOpenProjects")
        self._projects_button.setAutoDefault(False)
        self._projects_button.clicked.connect(
            lambda: self.destination_requested.emit("research_projects")
        )
        self.add_header_action(self._projects_button)

        self._refresh_button = QPushButton("Refresh", self)
        self._refresh_button.setObjectName("assistantRefresh")
        self._refresh_button.setAutoDefault(False)
        self._refresh_button.clicked.connect(self.refresh_summaries)
        self.add_header_action(self._refresh_button)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------
    def _on_section_list_changed(
        self,
        current: QListWidgetItem | None,
        _previous: QListWidgetItem | None,
    ) -> None:
        if current is None:
            return
        value = current.data(Qt.ItemDataRole.UserRole)
        try:
            section_id = AssistantSectionId(value)
        except (TypeError, ValueError):
            return
        self._select_section(section_id, sync_list=False)

    def _select_section(
        self,
        section_id: AssistantSectionId,
        *,
        sync_list: bool = True,
    ) -> None:
        if self._current_section_id is not None:
            previous = self._hosts.get(self._current_section_id)
            if previous is not None:
                previous.on_deactivated()
        host = self._hosts.get(section_id)
        if host is None:
            return
        self._current_section_id = section_id
        self._stack.setCurrentWidget(host)
        host.on_activated()
        if sync_list:
            for index in range(self._section_list.count()):
                item = self._section_list.item(index)
                if item.data(Qt.ItemDataRole.UserRole) == section_id.value:
                    self._section_list.setCurrentItem(item)
                    break
        self._refresh_sidebar_summaries()

    def _refresh_sidebar_summaries(self) -> None:
        for index in range(self._section_list.count()):
            item = self._section_list.item(index)
            value = item.data(Qt.ItemDataRole.UserRole)
            try:
                section_id = AssistantSectionId(value)
            except (TypeError, ValueError):
                continue
            host = self._hosts.get(section_id)
            summary = ""
            if host is not None:
                try:
                    summary = host.section.summary()
                except Exception:  # noqa: BLE001 - defensive boundary
                    _logger.exception(
                        "Section %s raised while computing its summary",
                        section_id.value,
                    )
                    summary = ""
            label = section_id.display_name
            if summary:
                label = f"{label} — {summary}"
            item.setText(label)

    # ------------------------------------------------------------------
    # Review summary
    # ------------------------------------------------------------------
    def _build_review_summary(self) -> str:
        lines: list[str] = []
        lines.append("Research assistant summary")
        lines.append("")
        for section_id in AssistantSectionId:
            if section_id is AssistantSectionId.REVIEW:
                continue
            host = self._hosts.get(section_id)
            if host is None:
                continue
            summary = ""
            try:
                summary = host.section.summary()
            except Exception:  # noqa: BLE001 - defensive boundary
                summary = ""
            state = summary or "(empty)"
            lines.append(f"• {section_id.display_name}: {state}")
        lines.append("")
        lines.append(
            "Use the sections in the sidebar to fill in the research "
            "design. The Review & Export section reflects the state of "
            "every other section."
        )
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def on_activated(self) -> None:
        if self._current_section_id is not None:
            host = self._hosts.get(self._current_section_id)
            if host is not None:
                host.on_activated()
        self._refresh_sidebar_summaries()

    def on_deactivated(self) -> None:
        if self._current_section_id is not None:
            host = self._hosts.get(self._current_section_id)
            if host is not None:
                host.on_deactivated()

    def attach_topic_service(self, service: TopicWorkspaceService) -> None:
        """Attach the topic workspace service to the page."""
        self._topic_service = service
        from academic_platform.ui.pages.research_assistant.sections.topic_section import (
            TopicSection,
        )

        section = self.section(AssistantSectionId.TOPIC)
        if isinstance(section, TopicSection):
            section.attach_service(service)

    def attach_project_to_topic(self, project_key: str) -> None:
        """Attach a project to the topic and title sections."""
        from academic_platform.ui.pages.research_assistant.sections.title_section import (
            TitleSection,
        )
        from academic_platform.ui.pages.research_assistant.sections.topic_section import (
            TopicSection,
        )

        topic = self.section(AssistantSectionId.TOPIC)
        if isinstance(topic, TopicSection):
            topic.attach_project(project_key)
        title = self.section(AssistantSectionId.TITLE_BUILDER)
        if isinstance(title, TitleSection) and self._title_service is not None:
            title.attach_service(self._title_service, project_key)

    @property
    def topic_service(self) -> TopicWorkspaceService | None:
        return self._topic_service

    def attach_title_service(self, service: TitleBuilderService) -> None:
        """Attach the title builder service to the page."""
        self._title_service = service

    def attach_project_to_sections(self, project_key: str) -> None:
        """Attach a project to every section that needs it."""
        from academic_platform.ui.pages.research_assistant.sections.history_section import (
            ResearchHistorySection,
        )
        from academic_platform.ui.pages.research_assistant.sections.questions_section import (
            ResearchQuestionsSection,
        )
        from academic_platform.ui.pages.research_assistant.sections.title_section import (
            TitleSection,
        )

        title = self.section(AssistantSectionId.TITLE_BUILDER)
        if isinstance(title, TitleSection) and self._title_service is not None:
            title.attach_service(self._title_service, project_key)
        questions = self.section(AssistantSectionId.RESEARCH_QUESTIONS)
        if isinstance(questions, ResearchQuestionsSection):
            questions.attach_project(project_key)
        history = self.section(AssistantSectionId.RESEARCH_HISTORY)
        if isinstance(history, ResearchHistorySection) and self._history_service is not None:
            history.attach_service(self._history_service, project_key)

    def current_topic_draft(self):
        """Return the current topic draft, or ``None`` when unavailable."""
        if self._topic_service is None:
            return None
        try:
            return self._topic_service.current_draft()
        except Exception:  # noqa: BLE001 - defensive boundary
            return None

    @property
    def title_service(self) -> TitleBuilderService | None:
        return self._title_service

    def attach_question_service(
        self, service: ResearchQuestionWorkspaceService
    ) -> None:
        """Attach the research-question workspace service."""
        self._question_service = service
        from academic_platform.ui.pages.research_assistant.sections.questions_section import (
            ResearchQuestionsSection,
        )

        section = self.section(AssistantSectionId.RESEARCH_QUESTIONS)
        if isinstance(section, ResearchQuestionsSection):
            section.attach_service(service)

    @property
    def question_service(self) -> ResearchQuestionWorkspaceService | None:
        return self._question_service

    def attach_history_service(self, service: ResearchHistoryService) -> None:
        """Attach the research-history workspace service."""
        self._history_service = service

    @property
    def history_service(self) -> ResearchHistoryService | None:
        return self._history_service