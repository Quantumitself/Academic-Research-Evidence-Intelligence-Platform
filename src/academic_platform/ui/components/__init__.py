"""Reusable presentation components.

Components in this package are presentation-only. They do not access
repositories, HTTP clients, or statistical libraries. They emit signals and
expose properties; the shell or a controller wires them to application
services.

Component inventory
-------------------
Part 1:
- ``SectionCard`` — titled card container with a body state stack.
- ``EmptyState`` — empty-region panel with a title and message.
- ``ErrorState`` — error panel with a message and optional retry action.
- ``LoadingIndicator`` — indeterminate or determinate progress indicator.
- ``ProgressBar`` — determinate progress bar with an optional label.
- ``SearchBar`` — text input with submit, clear, and optional scope.
- ``FilterPanel`` — collapsible panel hosting filter controls.
- ``PageHeader`` — title, subtitle, and actions region.

Part 2:
- ``ArticleCard`` — publication summary card.
- ``ResearchProjectCard`` — research project summary card.
- ``CollectionCard`` — collection summary card.
- ``AIProviderCard`` — AI provider configuration card.
- ``SearchSourceRow`` — search source configuration row.
- ``TagList`` — compact list of removable tags.
- ``MetadataGrid`` — label/value grid for metadata display.
- ``StatBadge`` — compact badge for a single numeric or status value.
"""

from academic_platform.ui.components.ai_provider_card import AIProviderCard
from academic_platform.ui.components.article_card import ArticleCard
from academic_platform.ui.components.collection_card import CollectionCard
from academic_platform.ui.components.empty_state import EmptyState
from academic_platform.ui.components.error_state import ErrorState
from academic_platform.ui.components.filter_panel import (
    FilterField,
    FilterOption,
    FilterPanel,
)
from academic_platform.ui.components.loading_indicator import LoadingIndicator
from academic_platform.ui.components.metadata_grid import MetadataGrid
from academic_platform.ui.components.page_header import PageHeader
from academic_platform.ui.components.progress_bar import ProgressBar
from academic_platform.ui.components.research_project_card import ResearchProjectCard
from academic_platform.ui.components.search_bar import SearchBar
from academic_platform.ui.components.search_source_row import SearchSourceRow
from academic_platform.ui.components.section_card import SectionCard
from academic_platform.ui.components.stat_badge import StatBadge, StatBadgeTone
from academic_platform.ui.components.tag_list import TagList

__all__ = [
    "AIProviderCard",
    "ArticleCard",
    "CollectionCard",
    "EmptyState",
    "ErrorState",
    "FilterField",
    "FilterOption",
    "FilterPanel",
    "LoadingIndicator",
    "MetadataGrid",
    "PageHeader",
    "ProgressBar",
    "ResearchProjectCard",
    "SearchBar",
    "SearchSourceRow",
    "SectionCard",
    "StatBadge",
    "StatBadgeTone",
    "TagList",
]