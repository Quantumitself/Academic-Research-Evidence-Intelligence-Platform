"""Compact tag list.

Renders a set of tags as small chips. Tags may be removable; removal is
requested through a signal and the caller decides whether to honor it. The
component does not own the canonical set of tags; it is a view onto a list
supplied by the caller.

Design decisions
----------------
- A tag is identified by a stable string identifier. The label may differ
  from the identifier, which lets callers display a localized or
  user-friendly name while keeping a stable identity.
- Removal and activation are signals. The component does not mutate its
  own list in response; the caller must call ``set_tags`` with the new
  list. This keeps the component's state consistent with the caller's
  state.
- The list wraps its content based on the available width.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QToolButton,
    QWidget,
)


@dataclass(frozen=True, slots=True)
class Tag:
    """A single tag with a stable identifier and a display label."""

    identifier: str
    label: str = ""

    def display(self) -> str:
        """Return the label to display, defaulting to the identifier."""
        return self.label or self.identifier


@dataclass(frozen=True, slots=True)
class _TagChip:
    tag: Tag
    widget: QFrame = field(repr=False, compare=False)


class _ChipWidget(QFrame):
    """Internal chip widget. Not part of the public API."""

    remove_requested = Signal(str)
    activated = Signal(str)

    def __init__(
        self,
        tag: Tag,
        *,
        removable: bool,
        clickable: bool,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("tagChip")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        self.setProperty("tag", tag)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 2, 6, 2)
        layout.setSpacing(4)

        if clickable:
            self._label: QWidget = QPushButton(tag.display(), self)
            self._label.setObjectName("tagChipButton")
            self._label.setFlat(True)
            self._label.setAutoDefault(False)
            self._label.clicked.connect(lambda: self.activated.emit(tag.identifier))  # type: ignore[attr-defined]
        else:
            label = QLabel(tag.display(), self)
            label.setObjectName("tagChipLabel")
            self._label = label
        layout.addWidget(self._label)

        if removable:
            remove = QToolButton(self)
            remove.setObjectName("tagChipRemove")
            remove.setText("\u00D7")
            remove.setAutoRaise(True)
            remove.setToolTip(f"Remove {tag.display()}")
            remove.clicked.connect(lambda: self.remove_requested.emit(tag.identifier))
            layout.addWidget(remove)


class TagList(QWidget):
    """A wrapping list of tag chips with optional removal and activation."""

    tag_removed = Signal(str)
    tag_activated = Signal(str)

    def __init__(
        self,
        *,
        removable: bool = False,
        clickable: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("tagList")
        self._removable = removable
        self._clickable = clickable
        self._chips: list[_ChipWidget] = []

        self._layout = _FlowLayout(self, h_spacing=6, v_spacing=6)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def set_tags(self, tags: list[Tag]) -> None:
        """Replace the displayed tags.

        Any previously displayed chips are removed. This method does not
        emit removal signals for the replaced tags; the caller is expected
        to have produced the new list from its own state.
        """
        for chip in self._chips:
            self._layout.removeWidget(chip)
            chip.setParent(None)
            chip.deleteLater()
        self._chips.clear()

        for tag in tags:
            chip = _ChipWidget(
                tag,
                removable=self._removable,
                clickable=self._clickable,
                parent=self,
            )
            chip.remove_requested.connect(self.tag_removed.emit)
            chip.activated.connect(self.tag_activated.emit)
            self._chips.append(chip)
            self._layout.addWidget(chip)

    def tags(self) -> list[Tag]:
        """Return the currently displayed tags."""
        return [chip_tag for chip_tag in self._current_tags()]

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _current_tags(self) -> list[Tag]:
        # Reconstruct tags from the chips. The chips retain the original
        # ``Tag`` instance through the closure used to build them; the
        # reconstruction here reads from a shadow list that is updated in
        # ``set_tags``.
        return [self._tag_for(chip) for chip in self._chips]

    def _tag_for(self, chip: _ChipWidget) -> Tag:
        # The tag is stored on the chip's dynamic property at construction
        # time so that the reconstruction does not require a side table.
        return chip.property("tag")


# A minimal flow layout. Qt does not ship a public flow layout, and the
# required behavior is small enough that a self-contained implementation is
# preferable to a dependency. The layout arranges children left-to-right
# and wraps to a new row when the available width is exhausted.
from PySide6.QtWidgets import QLayout, QSizePolicy  # noqa: E402
from PySide6.QtCore import QRect, QSize, QPoint  # noqa: E402


class _FlowLayout(QLayout):
    """Simple wrapping layout for tag chips."""

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        h_spacing: int = 6,
        v_spacing: int = 6,
    ) -> None:
        super().__init__(parent)
        self._items: list = []
        self._h_spacing = h_spacing
        self._v_spacing = v_spacing

    def addItem(self, item) -> None:  # noqa: N802 - Qt API
        self._items.append(item)

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index: int):  # noqa: N802 - Qt API
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def takeAt(self, index: int):  # noqa: N802 - Qt API
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def expandingDirections(self):  # noqa: N802 - Qt API
        return Qt.Orientation(0)

    def hasHeightForWidth(self) -> bool:  # noqa: N802 - Qt API
        return True

    def heightForWidth(self, width: int) -> int:  # noqa: N802 - Qt API
        return self._do_layout(QRect(0, 0, width, 0), test_only=True)

    def setGeometry(self, rect: QRect) -> None:  # noqa: N802 - Qt API
        super().setGeometry(rect)
        self._do_layout(rect, test_only=False)

    def sizeHint(self) -> QSize:  # noqa: N802 - Qt API
        return self.minimumSize()

    def minimumSize(self) -> QSize:  # noqa: N802 - Qt API
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        size += QSize(margins.left() + margins.right(), margins.top() + margins.bottom())
        return size

    def _do_layout(self, rect: QRect, *, test_only: bool) -> int:
        margins = self.contentsMargins()
        effective = rect.adjusted(margins.left(), margins.top(), -margins.right(), -margins.bottom())
        x = effective.x()
        y = effective.y()
        line_height = 0

        for item in self._items:
            hint = item.sizeHint()
            next_x = x + hint.width() + self._h_spacing
            if next_x - self._h_spacing > effective.right() and line_height > 0:
                x = effective.x()
                y = y + line_height + self._v_spacing
                next_x = x + hint.width() + self._h_spacing
                line_height = 0
            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), hint))
            x = next_x
            line_height = max(line_height, hint.height())

        return y + line_height - rect.y() + margins.bottom()