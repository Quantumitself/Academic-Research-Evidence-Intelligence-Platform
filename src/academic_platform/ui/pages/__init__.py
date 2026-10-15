"""Top-level pages hosted by the main window.

Each page inherits from ``BasePage``. The ``create_page`` factory maps a
destination identifier to a concrete page instance. Pages that are not yet
implemented are represented by ``PlaceholderPage`` so that navigation is
always meaningful.
"""

from __future__ import annotations

from PySide6.QtWidgets import QWidget

from academic_platform.app.configuration import AppDirectories
from academic_platform.app.settings import SettingsService
from academic_platform.infrastructure.database import Database
from academic_platform.ui.main_window_destinations import Destination, get_destination
from academic_platform.ui.pages.base_page import BasePage
from academic_platform.ui.pages.dashboard_page import DashboardPage
from academic_platform.ui.pages.placeholder_page import PlaceholderPage
from academic_platform.ui.pages.search import GlobalSearchPage
from academic_platform.ui.pages.settings import SettingsPage
from academic_platform.ui.pages.library import LibraryPage
from academic_platform.ui.pages.projects import ProjectsPage
from academic_platform.ui.pages.collections import CollectionsPage
from academic_platform.ui.pages.research_assistant import (
    ResearchAssistantPage,
)


__all__ = [
    "BasePage",
    "DashboardPage",
    "PlaceholderPage",
    "create_page",
]


def create_page(
    destination: Destination | str,
    directories: AppDirectories,
    settings_service: SettingsService,
    database: Database,
    parent: QWidget | None = None,
) -> BasePage:
    """Construct the page for a destination identifier.

    Parameters
    ----------
    destination:
        A ``Destination`` instance or its identifier string.
    directories:
        Resolved runtime directories. Passed to pages that need filesystem
        access.
    settings_service:
        The application settings service. Passed to pages that read or
        mutate settings.
    database:
        The application database wrapper. Passed to pages that read from or
        write to the persistence layer.
    parent:
        Optional Qt parent widget.
    """
    resolved = (
        destination if isinstance(destination, Destination) else get_destination(destination)
    )
    if resolved.identifier == "dashboard":
        return DashboardPage(directories=directories, parent=parent)
    if resolved.identifier == "discover":
        page = GlobalSearchPage(parent=parent)
        orchestrator_factory = (
            getattr(parent, "_search_orchestrator_factory", None)
            if parent is not None
            else None
        )
        if callable(orchestrator_factory):
            from academic_platform.ui.pages.search.orchestration_controller import (
                OrchestrationSearchController,
            )

            controller = OrchestrationSearchController(
                orchestrator_factory=orchestrator_factory,
                source_service_factory=orchestrator_factory,
            )
            page.set_controller(controller)
        return page
    if resolved.identifier == "library":
        return LibraryPage(parent=parent)
    if resolved.identifier == "collections":
        return CollectionsPage(parent=parent)
    if resolved.identifier == "research_projects":
        return ProjectsPage(parent=parent)
    if resolved.identifier == "research_assistant":
        return ResearchAssistantPage(parent=parent)
    if resolved.identifier == "settings":
        return SettingsPage(
            settings_service=settings_service,
            directories=directories,
            parent=parent,
        )
    return PlaceholderPage(destination=resolved, parent=parent)