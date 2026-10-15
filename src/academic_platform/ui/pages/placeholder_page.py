"""Placeholder page for destinations not yet implemented.

The placeholder is informative rather than decorative. It states the
destination name and the purpose defined by the product specification, so
that navigation remains meaningful while the destination is under
development. It contains no inert buttons pretending to be features.
"""

from __future__ import annotations

from PySide6.QtWidgets import QVBoxLayout, QWidget

from academic_platform.ui.components.empty_state import EmptyState
from academic_platform.ui.main_window_destinations import Destination
from academic_platform.ui.pages.base_page import BasePage


class PlaceholderPage(BasePage):
    """Destination placeholder presenting the destination purpose."""

    def __init__(
        self,
        destination: Destination,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            title=destination.label,
            subtitle=destination.purpose,
            parent=parent,
        )
        self._destination = destination
        self.setObjectName(f"placeholderPage_{destination.identifier}")

        content = QWidget(self)
        content.setObjectName("placeholderContent")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        layout.addWidget(
            EmptyState(
                title="Under development",
                message=(
                    "This destination is part of the product scope and will be "
                    "implemented in a later development step. Navigation, "
                    "layout, and the application shell are fully functional."
                ),
                parent=content,
            )
        )
        layout.addStretch(1)

        self._install_content(content)

    @property
    def destination(self) -> Destination:
        return self._destination