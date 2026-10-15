"""Reusable filter panel.

The panel renders filter fields from a declarative description so that pages
do not construct filter widgets ad hoc. Each field is one of:

- ``FilterField`` with kind ``"checkbox_group"`` — a set of checkboxes with
  a shared label. Emits a set of selected option identifiers.
- ``FilterField`` with kind ``"select"`` — a single-select combo box. Emits
  the selected identifier, or ``None`` for the "Any" option.
- ``FilterField`` with kind ``"range"`` — two spin boxes for a numeric range.
  Emits a tuple of ``(minimum, maximum)`` or ``None`` when unset.

The panel emits ``filters_changed`` with the complete current state whenever
any field changes. The state is a dictionary keyed by field identifier.

The panel is collapsible. Its header carries a title and a "Reset" button
that restores the initial state of every field.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

FilterValue = str | frozenset[str] | tuple[int, int] | None


@dataclass(frozen=True, slots=True)
class FilterOption:
    """A single option inside a filter field."""

    identifier: str
    label: str


@dataclass(frozen=True, slots=True)
class FilterField:
    """Declarative description of a single filter field."""

    identifier: str
    label: str
    kind: Literal["checkbox_group", "select", "range"]
    options: tuple[FilterOption, ...] = field(default_factory=tuple)
    range_min: int = 0
    range_max: int = 0
    range_step: int = 1
    select_any_label: str = "Any"


class FilterPanel(QFrame):
    """Collapsible panel hosting typed filter fields."""

    filters_changed = Signal(dict)
    reset_requested = Signal()

    def __init__(
        self,
        title: str,
        fields: tuple[FilterField, ...],
        *,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("filterPanel")
        self.setFrameShape(QFrame.Shape.StyledPanel)

        self._fields = fields
        self._state: dict[str, FilterValue] = {}
        self._checkbox_groups: dict[str, dict[str, QCheckBox]] = {}
        self._selects: dict[str, QComboBox] = {}
        self._ranges: dict[str, tuple[QSpinBox, QSpinBox]] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 12)
        root.setSpacing(10)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(8)

        self._toggle_button = QToolButton(self)
        self._toggle_button.setObjectName("filterPanelToggle")
        self._toggle_button.setCheckable(True)
        self._toggle_button.setChecked(True)
        self._toggle_button.setArrowType(Qt.ArrowType.DownArrow)
        self._toggle_button.setAutoRaise(True)
        self._toggle_button.toggled.connect(self._on_toggle)
        header.addWidget(self._toggle_button)

        title_label = QLabel(title, self)
        title_label.setObjectName("filterPanelTitle")
        header.addWidget(title_label, 1)

        self._reset_button = QPushButton("Reset", self)
        self._reset_button.setObjectName("filterPanelReset")
        self._reset_button.clicked.connect(self._on_reset)
        header.addWidget(self._reset_button)

        root.addLayout(header)

        self._body = QWidget(self)
        body_layout = QVBoxLayout(self._body)
        body_layout.setContentsMargins(24, 4, 0, 0)
        body_layout.setSpacing(12)

        for field in fields:
            body_layout.addWidget(self._build_field(field))

        root.addWidget(self._body)

        self._initialize_state()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def current_state(self) -> dict[str, FilterValue]:
        """Return a copy of the current filter state."""
        return dict(self._state)

    def set_state(self, state: dict[str, FilterValue], *, emit: bool = False) -> None:
        """Apply a state dictionary. Unknown fields are ignored."""
        for identifier, value in state.items():
            if identifier in self._checkbox_groups:
                group = self._checkbox_groups[identifier]
                selected = value if isinstance(value, frozenset) else frozenset()
                for option_identifier, checkbox in group.items():
                    checkbox.setChecked(option_identifier in selected)
            elif identifier in self._selects:
                combo = self._selects[identifier]
                target = value if isinstance(value, str) else ""
                for index in range(combo.count()):
                    if (combo.itemData(index) or "") == target:
                        combo.setCurrentIndex(index)
                        break
            elif identifier in self._ranges:
                minimum, maximum = self._ranges[identifier]
                if isinstance(value, tuple) and len(value) == 2:
                    minimum.setValue(int(value[0]))
                    maximum.setValue(int(value[1]))
                else:
                    field = next(f for f in self._fields if f.identifier == identifier)
                    minimum.setValue(field.range_min)
                    maximum.setValue(field.range_max)
        self._recompute_state()
        if emit:
            self.filters_changed.emit(self.current_state())

    def reset(self) -> None:
        """Restore the initial state of every field."""
        self._initialize_state()
        self.filters_changed.emit(self.current_state())
        self.reset_requested.emit()

    # ------------------------------------------------------------------
    # Construction helpers
    # ------------------------------------------------------------------
    def _build_field(self, field: FilterField) -> QWidget:
        container = QWidget(self._body)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        label = QLabel(field.label, container)
        label.setObjectName("filterPanelFieldLabel")
        layout.addWidget(label)

        if field.kind == "checkbox_group":
            group: dict[str, QCheckBox] = {}
            for option in field.options:
                checkbox = QCheckBox(option.label, container)
                checkbox.setObjectName(f"filterPanelCheckbox_{field.identifier}_{option.identifier}")
                checkbox.toggled.connect(self._on_field_changed)
                layout.addWidget(checkbox)
                group[option.identifier] = checkbox
            self._checkbox_groups[field.identifier] = group

        elif field.kind == "select":
            combo = QComboBox(container)
            combo.setObjectName(f"filterPanelSelect_{field.identifier}")
            combo.addItem(field.select_any_label, "")
            for option in field.options:
                combo.addItem(option.label, option.identifier)
            combo.currentIndexChanged.connect(self._on_field_changed)
            layout.addWidget(combo)
            self._selects[field.identifier] = combo

        elif field.kind == "range":
            row = QWidget(container)
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(6)

            minimum = QSpinBox(row)
            minimum.setObjectName(f"filterPanelRangeMin_{field.identifier}")
            minimum.setRange(field.range_min, field.range_max)
            minimum.setSingleStep(field.range_step)
            minimum.setValue(field.range_min)
            minimum.valueChanged.connect(self._on_field_changed)
            row_layout.addWidget(minimum)

            to_label = QLabel("to", row)
            to_label.setObjectName("filterPanelRangeTo")
            row_layout.addWidget(to_label)

            maximum = QSpinBox(row)
            maximum.setObjectName(f"filterPanelRangeMax_{field.identifier}")
            maximum.setRange(field.range_min, field.range_max)
            maximum.setSingleStep(field.range_step)
            maximum.setValue(field.range_max)
            maximum.valueChanged.connect(self._on_field_changed)
            row_layout.addWidget(maximum)

            layout.addWidget(row)
            self._ranges[field.identifier] = (minimum, maximum)

        else:  # pragma: no cover - Literal type prevents this at type-check time
            raise ValueError(f"Unknown filter field kind: {field.kind}")

        return container

    # ------------------------------------------------------------------
    # State management
    # ------------------------------------------------------------------
    def _initialize_state(self) -> None:
        for field in self._fields:
            if field.identifier in self._checkbox_groups:
                for checkbox in self._checkbox_groups[field.identifier].values():
                    checkbox.blockSignals(True)
                    checkbox.setChecked(False)
                    checkbox.blockSignals(False)
            elif field.identifier in self._selects:
                combo = self._selects[field.identifier]
                combo.blockSignals(True)
                combo.setCurrentIndex(0)
                combo.blockSignals(False)
            elif field.identifier in self._ranges:
                minimum, maximum = self._ranges[field.identifier]
                minimum.blockSignals(True)
                maximum.blockSignals(True)
                minimum.setValue(field.range_min)
                maximum.setValue(field.range_max)
                minimum.blockSignals(False)
                maximum.blockSignals(False)
        self._recompute_state()

    def _recompute_state(self) -> None:
        state: dict[str, FilterValue] = {}
        for field in self._fields:
            if field.identifier in self._checkbox_groups:
                selected = frozenset(
                    option_identifier
                    for option_identifier, checkbox in self._checkbox_groups[field.identifier].items()
                    if checkbox.isChecked()
                )
                state[field.identifier] = selected
            elif field.identifier in self._selects:
                combo = self._selects[field.identifier]
                data = combo.currentData()
                state[field.identifier] = str(data) if data else None
            elif field.identifier in self._ranges:
                minimum, maximum = self._ranges[field.identifier]
                if minimum.value() == field.range_min and maximum.value() == field.range_max:
                    state[field.identifier] = None
                else:
                    state[field.identifier] = (minimum.value(), maximum.value())
        self._state = state

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------
    def _on_field_changed(self, _value: object = None) -> None:
        self._recompute_state()
        self.filters_changed.emit(self.current_state())

    def _on_toggle(self, checked: bool) -> None:
        self._body.setVisible(checked)
        self._toggle_button.setArrowType(
            Qt.ArrowType.DownArrow if checked else Qt.ArrowType.RightArrow
        )

    def _on_reset(self) -> None:
        self.reset()