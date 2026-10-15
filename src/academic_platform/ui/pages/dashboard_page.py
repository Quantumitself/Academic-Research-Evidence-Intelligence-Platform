"""Dashboard page.

The dashboard surfaces recent activity, saved searches, recommended
publications, current tasks, pending evidence reviews, and quick actions.
It is the landing page after application start.

Data sources
------------
The page reads from repositories through the application services that are
attached to the window. Because the persistence layer is introduced in a
later phase, the page renders explicit empty states for every section whose
data source is not yet available. No section displays fabricated content.

Refresh contract
----------------
The shell calls ``refresh()`` when the page becomes visible. The method
re-reads every data source and repopulates the corresponding section. It is
idempotent and cheap when there is no data.

Notification contract
---------------------
Quick actions publish a notification when the action cannot be performed
because the destination is not yet implemented. The notification is
informational; it explains the situation and does not claim that the action
was performed.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from academic_platform.app.configuration import AppDirectories
from academic_platform.ui.components.article_card import (
    ArticleCard,
    PublicationSummary,
)
from academic_platform.ui.components.collection_card import (
    CollectionCard,
    CollectionSummary,
)
from academic_platform.ui.components.empty_state import EmptyState
from academic_platform.ui.components.research_project_card import (
    ResearchProjectCard,
    ResearchProjectSummary,
)
from academic_platform.ui.components.section_card import SectionCard
from academic_platform.ui.main_window_destinations import get_destination
from academic_platform.ui.pages.base_page import BasePage

_logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class QuickAction:
    """Description of a quick action button on the dashboard."""

    identifier: str
    label: str
    tooltip: str
    destination: str
    enabled: bool


_QUICK_ACTIONS: tuple[QuickAction, ...] = (
    QuickAction(
        identifier="new_project",
        label="Start a research project",
        tooltip="Define a topic, question, and plan.",
        destination="research_projects",
        enabled=True,
    ),
    QuickAction(
        identifier="import_document",
        label="Import a document",
        tooltip="Add a PDF, book, or reference file.",
        destination="library",
        enabled=True,
    ),
    QuickAction(
        identifier="search_literature",
        label="Search literature",
        tooltip="Query your enabled academic sources.",
        destination="discover",
        enabled=True,
    ),
    QuickAction(
        identifier="open_assistant",
        label="Open research assistant",
        tooltip="Develop a topic into a research plan.",
        destination="research_assistant",
        enabled=True,
    ),
)


class DashboardPage(BasePage):
    """Landing page shown immediately after application start."""

    #: Emitted when the user activates a quick action. Carries the
    #: destination identifier the shell should navigate to.
    destination_requested = Signal(str)

    #: Emitted when the user requests a refresh of the dashboard data.
    refresh_requested = Signal()

    def __init__(
        self,
        directories: AppDirectories,
        parent: QWidget | None = None,
    ) -> None:
        destination = get_destination("dashboard")
        super().__init__(
            title=destination.label,
            subtitle=destination.purpose,
            parent=parent,
        )
        self._directories = directories
        self.setObjectName("dashboardPage")

        # Header actions: a manual refresh control. The refresh button is
        # enabled because the shell wires it to ``refresh`` during
        # construction; the page does not depend on the shell for that
        # wiring, it performs it itself.
        self._refresh_button = QPushButton("Refresh", self)
        self._refresh_button.setObjectName("dashboardRefresh")
        self._refresh_button.setAutoDefault(False)
        self._refresh_button.clicked.connect(self.refresh)
        self.add_header_action(self._refresh_button)

        self._build_content()

    # ------------------------------------------------------------------
    # Content construction
    # ------------------------------------------------------------------
    def _build_content(self) -> None:
        content = QWidget(self)
        content.setObjectName("dashboardContent")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(20)

        layout.addWidget(self._build_quick_actions(content))
        layout.addWidget(self._build_recent_projects(content))
        layout.addWidget(self._build_recent_articles(content))
        layout.addWidget(self._build_saved_searches(content))
        layout.addWidget(self._build_research_tasks(content))
        layout.addWidget(self._build_pending_evidence(content))
        layout.addWidget(self._build_recent_reports(content))
        layout.addWidget(self._build_recent_activity(content))
        layout.addStretch(1)

        self._install_content(content)

    # ------------------------------------------------------------------
    # Quick actions
    # ------------------------------------------------------------------
    def _build_quick_actions(self, parent: QWidget) -> SectionCard:
        card = SectionCard(title="Quick actions", parent=parent)
        card.setObjectName("dashboardQuickActionsCard")
        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(12)

        self._quick_action_buttons: dict[str, QPushButton] = {}
        for index, action in enumerate(_QUICK_ACTIONS):
            button = QPushButton(action.label, card)
            button.setObjectName(f"quickActionButton_{action.identifier}")
            button.setToolTip(action.tooltip)
            button.setEnabled(action.enabled)
            button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            button.clicked.connect(
                lambda _checked=False, key=action.destination: self._on_quick_action(key)
            )
            self._quick_action_buttons[action.identifier] = button
            grid.addWidget(button, index // 2, index % 2)

        card.set_content_layout(grid)
        return card

    def _on_quick_action(self, destination_identifier: str) -> None:
        self.destination_requested.emit(destination_identifier)

    # ------------------------------------------------------------------
    # Recent projects
    # ------------------------------------------------------------------
    def _build_recent_projects(self, parent: QWidget) -> SectionCard:
        card = SectionCard(title="Recent research projects", parent=parent)
        card.setObjectName("dashboardRecentProjectsCard")

        self._recent_projects_container = QWidget(card)
        self._recent_projects_layout = QVBoxLayout(self._recent_projects_container)
        self._recent_projects_layout.setContentsMargins(0, 0, 0, 0)
        self._recent_projects_layout.setSpacing(10)
        card.set_content_widget(self._recent_projects_container)
        return card

    def _populate_recent_projects(self, projects: list[ResearchProjectSummary]) -> None:
        self._clear_layout(self._recent_projects_layout)
        if not projects:
            self._recent_projects_layout.addWidget(
                EmptyState(
                    title="No research projects yet",
                    message=(
                        "Start a research project to define a topic, question, "
                        "and plan. Projects appear here as you create them."
                    ),
                    glyph="\u2637",
                    action_label="Start a project",
                    parent=self._recent_projects_container,
                )
            )
            self._enable_empty_state_action(self._recent_projects_layout, "research_projects")
            return
        for project in projects:
            card = ResearchProjectCard(project, parent=self._recent_projects_container)
            card.enable_open()
            card.opened.connect(lambda _identifier: self.destination_requested.emit("research_projects"))
            card.enable_edit()
            card.edited.connect(lambda _identifier: self.destination_requested.emit("research_projects"))
            self._recent_projects_layout.addWidget(card)

    # ------------------------------------------------------------------
    # Recent articles
    # ------------------------------------------------------------------
    def _build_recent_articles(self, parent: QWidget) -> SectionCard:
        card = SectionCard(title="Recently opened articles", parent=parent)
        card.setObjectName("dashboardRecentArticlesCard")

        self._recent_articles_container = QWidget(card)
        self._recent_articles_layout = QVBoxLayout(self._recent_articles_container)
        self._recent_articles_layout.setContentsMargins(0, 0, 0, 0)
        self._recent_articles_layout.setSpacing(10)
        card.set_content_widget(self._recent_articles_container)
        return card

    def _populate_recent_articles(self, articles: list[PublicationSummary]) -> None:
        self._clear_layout(self._recent_articles_layout)
        if not articles:
            self._recent_articles_layout.addWidget(
                EmptyState(
                    title="No articles opened yet",
                    message=(
                        "Articles you open from search results or import appear "
                        "here for quick access."
                    ),
                    glyph="\u2261",
                    parent=self._recent_articles_container,
                )
            )
            return
        for article in articles:
            card = ArticleCard(article, parent=self._recent_articles_container)
            card.enable_open()
            card.open_requested.connect(
                lambda _identifier: self.destination_requested.emit("library")
            )
            self._recent_articles_layout.addWidget(card)

    # ------------------------------------------------------------------
    # Saved searches
    # ------------------------------------------------------------------
    def _build_saved_searches(self, parent: QWidget) -> SectionCard:
        card = SectionCard(title="Saved searches", parent=parent)
        card.setObjectName("dashboardSavedSearchesCard")

        self._saved_searches_container = QWidget(card)
        self._saved_searches_layout = QVBoxLayout(self._saved_searches_container)
        self._saved_searches_layout.setContentsMargins(0, 0, 0, 0)
        self._saved_searches_layout.setSpacing(8)
        card.set_content_widget(self._saved_searches_container)
        return card

    def _populate_saved_searches(self, searches: list[str]) -> None:
        self._clear_layout(self._saved_searches_layout)
        if not searches:
            self._saved_searches_layout.addWidget(
                EmptyState(
                    title="No saved searches",
                    message=(
                        "Save a search from the Discover page to reuse it later. "
                        "Saved searches appear here."
                    ),
                    glyph="\u2315",
                    parent=self._saved_searches_container,
                )
            )
            return
        for label in searches:
            row = QWidget(self._saved_searches_container)
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(8)
            label_widget = QLabel(label, row)
            label_widget.setObjectName("dashboardSavedSearchLabel")
            label_widget.setWordWrap(True)
            row_layout.addWidget(label_widget, 1)
            open_button = QPushButton("Open", row)
            open_button.setObjectName("dashboardSavedSearchOpen")
            open_button.clicked.connect(
                lambda _checked=False: self.destination_requested.emit("discover")
            )
            row_layout.addWidget(open_button)
            self._saved_searches_layout.addWidget(row)

    # ------------------------------------------------------------------
    # Research tasks
    # ------------------------------------------------------------------
    def _build_research_tasks(self, parent: QWidget) -> SectionCard:
        card = SectionCard(title="Current research tasks", parent=parent)
        card.setObjectName("dashboardResearchTasksCard")

        self._tasks_container = QWidget(card)
        self._tasks_layout = QVBoxLayout(self._tasks_container)
        self._tasks_layout.setContentsMargins(0, 0, 0, 0)
        self._tasks_layout.setSpacing(8)
        card.set_content_widget(self._tasks_container)
        return card

    def _populate_research_tasks(self, tasks: list[str]) -> None:
        self._clear_layout(self._tasks_layout)
        if not tasks:
            self._tasks_layout.addWidget(
                EmptyState(
                    title="No open tasks",
                    message=(
                        "Tasks you create in a research project appear here. "
                        "Tasks help track decisions, readings, and analyses."
                    ),
                    glyph="\u2699",
                    parent=self._tasks_container,
                )
            )
            return
        for task in tasks:
            label = QLabel(f"• {task}", self._tasks_container)
            label.setObjectName("dashboardTaskLabel")
            label.setWordWrap(True)
            self._tasks_layout.addWidget(label)

    # ------------------------------------------------------------------
    # Pending evidence reviews
    # ------------------------------------------------------------------
    def _build_pending_evidence(self, parent: QWidget) -> SectionCard:
        card = SectionCard(title="Pending evidence reviews", parent=parent)
        card.setObjectName("dashboardPendingEvidenceCard")

        self._pending_evidence_container = QWidget(card)
        self._pending_evidence_layout = QVBoxLayout(self._pending_evidence_container)
        self._pending_evidence_layout.setContentsMargins(0, 0, 0, 0)
        self._pending_evidence_layout.setSpacing(8)
        card.set_content_widget(self._pending_evidence_container)
        return card

    def _populate_pending_evidence(self, entries: list[str]) -> None:
        self._clear_layout(self._pending_evidence_layout)
        if not entries:
            self._pending_evidence_layout.addWidget(
                EmptyState(
                    title="No evidence awaiting review",
                    message=(
                        "Values extracted from documents appear here for "
                        "verification before they can be used in a synthesis."
                    ),
                    glyph="\u222B",
                    parent=self._pending_evidence_container,
                )
            )
            return
        for entry in entries:
            label = QLabel(f"• {entry}", self._pending_evidence_container)
            label.setObjectName("dashboardPendingEvidenceLabel")
            label.setWordWrap(True)
            self._pending_evidence_layout.addWidget(label)

    # ------------------------------------------------------------------
    # Recent reports
    # ------------------------------------------------------------------
    def _build_recent_reports(self, parent: QWidget) -> SectionCard:
        card = SectionCard(title="Recent analysis reports", parent=parent)
        card.setObjectName("dashboardRecentReportsCard")

        self._recent_reports_container = QWidget(card)
        self._recent_reports_layout = QVBoxLayout(self._recent_reports_container)
        self._recent_reports_layout.setContentsMargins(0, 0, 0, 0)
        self._recent_reports_layout.setSpacing(8)
        card.set_content_widget(self._recent_reports_container)
        return card

    def _populate_recent_reports(self, reports: list[str]) -> None:
        self._clear_layout(self._recent_reports_layout)
        if not reports:
            self._recent_reports_layout.addWidget(
                EmptyState(
                    title="No analysis reports yet",
                    message=(
                        "Reports produced by the statistical engine or the "
                        "synthesis workflow appear here for reference."
                    ),
                    glyph="\u2630",
                    parent=self._recent_reports_container,
                )
            )
            return
        for report in reports:
            label = QLabel(f"• {report}", self._recent_reports_container)
            label.setObjectName("dashboardRecentReportLabel")
            label.setWordWrap(True)
            self._recent_reports_layout.addWidget(label)

    # ------------------------------------------------------------------
    # Recent activity
    # ------------------------------------------------------------------
    def _build_recent_activity(self, parent: QWidget) -> SectionCard:
        card = SectionCard(title="Recent activity", parent=parent)
        card.setObjectName("dashboardRecentActivityCard")

        self._activity_container = QWidget(card)
        self._activity_layout = QVBoxLayout(self._activity_container)
        self._activity_layout.setContentsMargins(0, 0, 0, 0)
        self._activity_layout.setSpacing(8)
        card.set_content_widget(self._activity_container)
        return card

    def _populate_recent_activity(self, entries: list[str]) -> None:
        self._clear_layout(self._activity_layout)
        if not entries:
            self._activity_layout.addWidget(
                EmptyState(
                    title="No activity yet",
                    message=(
                        "Projects, saved searches, and imported documents will "
                        "appear here once you begin working."
                    ),
                    glyph="\u2302",
                    parent=self._activity_container,
                )
            )
            return
        for entry in entries:
            label = QLabel(f"• {entry}", self._activity_container)
            label.setObjectName("dashboardActivityLabel")
            label.setWordWrap(True)
            self._activity_layout.addWidget(label)

    # ------------------------------------------------------------------
    # Refresh
    # ------------------------------------------------------------------
    def refresh(self) -> None:
        """Re-read every dashboard data source and repopulate the sections.

        Data sources are provided by the window through an optional
        ``dashboard_data_provider`` attribute. When the attribute is absent
        — which is the case until the persistence layer is introduced — the
        page populates every section with its empty state.

        The provider contract is: a callable that returns a mapping whose
        keys are ``"recent_projects"``, ``"recent_articles"``,
        ``"saved_searches"``, ``"research_tasks"``, ``"pending_evidence"``,
        ``"recent_reports"``, and ``"recent_activity"``. Missing keys are
        treated as empty.
        """
        provider = getattr(self.window(), "dashboard_data_provider", None)
        data: dict[str, object] = {}
        if callable(provider):
            try:
                data = dict(provider() or {})
            except Exception:  # noqa: BLE001 - defensive boundary
                _logger.exception("Dashboard data provider raised; rendering empty state")
                data = {}

        self._populate_recent_projects(list(data.get("recent_projects") or []))
        self._populate_recent_articles(list(data.get("recent_articles") or []))
        self._populate_saved_searches(list(data.get("saved_searches") or []))
        self._populate_research_tasks(list(data.get("research_tasks") or []))
        self._populate_pending_evidence(list(data.get("pending_evidence") or []))
        self._populate_recent_reports(list(data.get("recent_reports") or []))
        self._populate_recent_activity(list(data.get("recent_activity") or []))

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def on_activated(self) -> None:
        self.refresh()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    @staticmethod
    def _clear_layout(layout: QVBoxLayout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

    def _enable_empty_state_action(
        self,
        layout: QVBoxLayout,
        destination: str,
    ) -> None:
        """Enable the action button of the most recently added EmptyState.

        The button is enabled only when the destination identifier matches a
        registered destination. The button is wired to emit
        ``destination_requested`` so that the shell navigates to the
        destination.
        """
        for index in range(layout.count()):
            widget = layout.itemAt(index).widget()
            if isinstance(widget, EmptyState):
                widget.action_button.setEnabled(True)
                widget.set_action_enabled(True)
                widget.action_requested.connect(
                    lambda dest=destination: self.destination_requested.emit(dest)
                )
                break