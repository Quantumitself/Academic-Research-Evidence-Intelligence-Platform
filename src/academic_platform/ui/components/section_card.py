"""Reusable section card.

A section card groups related content under a heading. It exposes a stack of
content states so that callers can present loading, empty, error, and normal
states without constructing separate containers.

Design decisions
----------------
- The card owns a header (title + optional header actions) and a body.
- The body is a ``QStackedWidget`` with a stable set of slots. Callers can
  install content, a loading indicator, an empty state, or an error state
  and switch between them by calling the corresponding method.
- Content is installed once per slot. Replacing an existing slot widget is
  not permitted; callers must construct a new card if they need to
  completely replace the body.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLayout,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from academic_platform.ui.components.empty_state import EmptyState
from academic_platform.ui.components.error_state import ErrorState
from academic_platform.ui.components.loading_indicator import LoadingIndicator


class SectionCard(QFrame):
    """Card containing a title, optional actions, and a stateful body."""

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("sectionCard")
        self.setFrameShape(QFrame.Shape.StyledPanel)

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 20)
        root.setSpacing(12)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(8)

        self._title_label = QLabel(title, self)
        self._title_label.setObjectName("sectionCardTitle")
        header.addWidget(self._title_label, 1)

        self._actions_container = QWidget(self)
        actions_layout = QHBoxLayout(self._actions_container)
        actions_layout.setContentsMargins(0, 0, 0, 0)
        actions_layout.setSpacing(6)
        self._actions_layout = actions_layout
        header.addWidget(self._actions_container, 0, Qt.AlignmentFlag.AlignRight)

        root.addLayout(header)

        self._body_stack = QStackedWidget(self)
        self._body_stack.setObjectName("sectionCardBodyStack")
        root.addWidget(self._body_stack, 1)

        self._content_index: int | None = None
        self._loading_index: int | None = None
        self._empty_index: int | None = None
        self._error_index: int | None = None
        self._content_container: QWidget | None = None

    # ------------------------------------------------------------------
    # Header API
    # ------------------------------------------------------------------
    def set_title(self, title: str) -> None:
        """Replace the displayed title."""
        self._title_label.setText(title)

    def add_header_action(self, widget: QWidget) -> None:
        """Add a widget to the header actions region."""
        self._actions_layout.addWidget(widget)

    # ------------------------------------------------------------------
    # Body API
    # ------------------------------------------------------------------
    def set_content_widget(self, widget: QWidget) -> None:
        """Install a single widget as the primary content.

        The widget becomes the sole child of the content slot. Calling this
        method replaces any previously installed content widget; the previous
        widget is detached and scheduled for deletion.
        """
        self._set_content_container(widget)

    def set_content_layout(self, layout: QLayout) -> None:
        """Install a layout as the primary content.

        The layout is wrapped in a container widget so that the stack can
        manage it uniformly with the widget-based API.
        """
        container = QWidget(self)
        container.setLayout(layout)
        self._set_content_container(container)

    def show_content(self) -> None:
        """Display the primary content slot."""
        if self._content_index is None:
            raise RuntimeError("No content has been installed on this card")
        self._body_stack.setCurrentIndex(self._content_index)

    def show_loading(self, message: str = "Loading…") -> None:
        """Display the loading state, installing it on first use."""
        if self._loading_index is None:
            indicator = LoadingIndicator(message=message, parent=self)
            self._loading_index = self._body_stack.addWidget(indicator)
        else:
            widget = self._body_stack.widget(self._loading_index)
            if isinstance(widget, LoadingIndicator):
                widget.set_message(message)
        self._body_stack.setCurrentIndex(self._loading_index)

    def show_empty(self, title: str, message: str) -> None:
        """Display the empty state, installing it on first use."""
        if self._empty_index is None:
            state = EmptyState(title=title, message=message, parent=self)
            self._empty_index = self._body_stack.addWidget(state)
        else:
            widget = self._body_stack.widget(self._empty_index)
            if isinstance(widget, EmptyState):
                widget.set_content(title, message)
        self._body_stack.setCurrentIndex(self._empty_index)

    def show_error(self, message: str, *, retryable: bool = False) -> None:
        """Display the error state, installing it on first use."""
        if self._error_index is None:
            state = ErrorState(message=message, retryable=retryable, parent=self)
            self._error_index = self._body_stack.addWidget(state)
        else:
            widget = self._body_stack.widget(self._error_index)
            if isinstance(widget, ErrorState):
                widget.set_message(message)
                widget.set_retryable(retryable)
        self._body_stack.setCurrentIndex(self._error_index)

    def error_state(self) -> ErrorState | None:
        """Return the error state widget if it has been installed."""
        if self._error_index is None:
            return None
        widget = self._body_stack.widget(self._error_index)
        return widget if isinstance(widget, ErrorState) else None

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _set_content_container(self, container: QWidget) -> None:
        if self._content_container is not None:
            self._body_stack.removeWidget(self._content_container)
            self._content_container.setParent(None)
            self._content_container.deleteLater()
        self._content_container = container
        if self._content_index is None:
            self._content_index = self._body_stack.addWidget(container)
        else:
            self._body_stack.insertWidget(self._content_index, container)
            self._body_stack.removeWidget(self._body_stack.widget(self._content_index + 1))
        self._body_stack.setCurrentIndex(self._content_index)