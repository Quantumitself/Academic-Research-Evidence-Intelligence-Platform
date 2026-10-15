"""Base class for all primary pages hosted by the main window.

Responsibilities
----------------
- Provide a consistent header (title, subtitle, optional actions region).
- Provide a scrollable content region with sane margins.
- Define a small lifecycle contract invoked by the main window:
    * ``on_activated`` is called each time the page becomes visible.
    * ``on_deactivated`` is called each time the page stops being visible.
    * ``can_close`` is consulted before the application exits; a page may
      veto closure (for example to prompt about unsaved work).
- Provide a default empty state and a default busy-state overlay so that
  every page presents consistent loading, empty, and error semantics.

Pages must not manipulate the main window directly. All cross-page
communication goes through signals emitted from the page and connected by
the main window or a controller.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)
from academic_platform.ui.components.page_header import PageHeader


class BasePage(QWidget):
    """Common base for pages hosted by the main window."""

    #: Emitted when the page needs the status bar to display a message.
    status_message_requested = Signal(str)

    #: Emitted when the page wants to inform the shell that its header
    #: should reflect a new subtitle (for example a filter summary).
    subtitle_changed = Signal(str)

    def __init__(
        self,
        title: str,
        subtitle: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._title = title
        self._subtitle = subtitle

        self._root_layout = QVBoxLayout(self)
        self._root_layout.setContentsMargins(0, 0, 0, 0)
        self._root_layout.setSpacing(0)

        self._header = self._build_header()
        self._root_layout.addWidget(self._header)

        self._body_stack = QStackedWidget(self)
        self._body_stack.setObjectName("pageBodyStack")
        self._root_layout.addWidget(self._body_stack, 1)

        self._scroll_area: QScrollArea | None = None
        self._content_widget: QWidget | None = None
        self._empty_widget: QWidget | None = None

    # ------------------------------------------------------------------
    # Header construction
    # ------------------------------------------------------------------
    def _build_header(self) -> QWidget:
        self._page_header = PageHeader(
            title=self._title,
            subtitle=self._subtitle,
            parent=self,
        )
        self._title_label = self._page_header.findChild(QLabel, "pageHeading")
        self._subtitle_label = self._page_header.findChild(QLabel, "pageSubtitle")
        self._actions_layout = self._page_header._actions_layout  # noqa: SLF001 - intentional reuse
        return self._page_header

    # ------------------------------------------------------------------
    # Content region helpers used by subclasses
    # ------------------------------------------------------------------
    def _install_content(self, content: QWidget, scrollable: bool = True) -> None:
        """Install the primary content widget.

        If ``scrollable`` is True, the widget is wrapped in a scroll area
        with consistent margins. Otherwise, the widget is installed directly.
        The body stack always contains at least one widget after this call.
        """
        if self._content_widget is not None:
            raise RuntimeError("Page content has already been installed")

        if scrollable:
            scroll = QScrollArea(self)
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.Shape.NoFrame)
            container = QWidget(scroll)
            layout = QVBoxLayout(container)
            layout.setContentsMargins(24, 8, 24, 24)
            layout.setSpacing(20)
            layout.addWidget(content)
            layout.addStretch(1)
            scroll.setWidget(container)
            self._scroll_area = scroll
            self._body_stack.addWidget(scroll)
        else:
            self._body_stack.addWidget(content)
        self._content_widget = content
        self._body_stack.setCurrentWidget(self._body_stack.widget(0))

    def _install_empty_state(self, widget: QWidget) -> None:
        """Install an empty-state widget that can be shown instead of content.

        The empty-state widget is stored on a second stack index. Pages call
        ``show_empty_state`` and ``show_content`` to switch between them.
        """
        if self._empty_widget is not None:
            raise RuntimeError("Empty state has already been installed")
        self._empty_widget = widget
        self._body_stack.addWidget(widget)

    def show_content(self) -> None:
        """Display the primary content widget."""
        if self._content_widget is None:
            raise RuntimeError("No content widget has been installed")
        self._body_stack.setCurrentWidget(self._content_widget.parent() or self._content_widget)

    def show_empty_state(self) -> None:
        """Display the empty-state widget, if one has been installed."""
        if self._empty_widget is None:
            return
        self._body_stack.setCurrentWidget(self._empty_widget)

    # ------------------------------------------------------------------
    # Header mutation API for subclasses
    # ------------------------------------------------------------------
    def set_subtitle(self, subtitle: str) -> None:
        """Update the subtitle text and visibility."""
        self._subtitle = subtitle
        self._page_header.set_subtitle(subtitle)
        self.subtitle_changed.emit(subtitle)

    def add_header_action(self, widget: QWidget) -> None:
        """Add a widget to the header actions region."""
        self._page_header.add_action(widget)

    # ------------------------------------------------------------------
    # Lifecycle contract
    # ------------------------------------------------------------------
    def on_activated(self) -> None:
        """Called when the page becomes the visible page.

        Subclasses may override to refresh data. The default implementation
        is a no-op.
        """

    def on_deactivated(self) -> None:
        """Called when the page stops being the visible page.

        Subclasses may override to pause timers or flush state. The default
        implementation is a no-op.
        """

    def can_close(self) -> bool:
        """Return True if the application may close while this page is open.

        The default implementation permits closure. Pages that hold unsaved
        state should override and return False after prompting the user.
        """
        return True

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------
    @property
    def title(self) -> str:
        return self._title

    @property
    def subtitle(self) -> str:
        return self._subtitle