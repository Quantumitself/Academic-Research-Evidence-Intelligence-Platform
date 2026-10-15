"""Tests for the FilterPanel component."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from academic_platform.ui.components.filter_panel import (  # noqa: E402
    FilterField,
    FilterOption,
    FilterPanel,
)


@pytest.fixture(scope="module")
def app() -> QApplication:
    return QApplication.instance() or QApplication([])


def _fields() -> tuple[FilterField, ...]:
    return (
        FilterField(
            identifier="kinds",
            label="Kinds",
            kind="checkbox_group",
            options=(
                FilterOption("a", "Alpha"),
                FilterOption("b", "Beta"),
            ),
        ),
        FilterField(
            identifier="sort",
            label="Sort",
            kind="select",
            options=(
                FilterOption("recent", "Recent"),
                FilterOption("relevance", "Relevance"),
            ),
        ),
        FilterField(
            identifier="year",
            label="Year",
            kind="range",
            range_min=1990,
            range_max=2024,
        ),
    )


def test_initial_state_is_empty(app: QApplication) -> None:
    panel = FilterPanel("Filters", _fields())
    state = panel.current_state()
    assert state["kinds"] == frozenset()
    assert state["sort"] is None
    assert state["year"] is None


def test_checkbox_change_emits(app: QApplication) -> None:
    panel = FilterPanel("Filters", _fields())
    received: list[dict] = []
    panel.filters_changed.connect(received.append)
    panel._checkbox_groups["kinds"]["a"].setChecked(True)  # noqa: SLF001
    assert received
    assert received[-1]["kinds"] == frozenset({"a"})


def test_select_change_emits(app: QApplication) -> None:
    panel = FilterPanel("Filters", _fields())
    received: list[dict] = []
    panel.filters_changed.connect(received.append)
    panel.set_state({"sort": "recent"}, emit=True)
    assert received[-1]["sort"] == "recent"


def test_range_change_emits(app: QApplication) -> None:
    panel = FilterPanel("Filters", _fields())
    received: list[dict] = []
    panel.filters_changed.connect(received.append)
    minimum, maximum = panel._ranges["year"]  # noqa: SLF001
    minimum.setValue(2000)
    assert received[-1]["year"] == (2000, 2024)
    maximum.setValue(2020)
    assert received[-1]["year"] == (2000, 2020)


def test_reset_restores_initial(app: QApplication) -> None:
    panel = FilterPanel("Filters", _fields())
    panel.set_state(
        {"kinds": frozenset({"a"}), "sort": "recent", "year": (2000, 2010)}
    )
    panel.reset()
    state = panel.current_state()
    assert state["kinds"] == frozenset()
    assert state["sort"] is None
    assert state["year"] is None


def test_reset_emits_signals(app: QApplication) -> None:
    panel = FilterPanel("Filters", _fields())
    received_changes: list[dict] = []
    received_reset: list[int] = []
    panel.filters_changed.connect(received_changes.append)
    panel.reset_requested.connect(lambda: received_reset.append(1))
    panel.reset()
    assert received_changes
    assert received_reset == [1]


def test_toggle_collapses_body(app: QApplication) -> None:
    panel = FilterPanel("Filters", _fields())
    panel._toggle_button.setChecked(False)  # noqa: SLF001
    assert not panel._body.isVisibleTo(panel)  # noqa: SLF001
    panel._toggle_button.setChecked(True)  # noqa: SLF001
    assert panel._body.isVisibleTo(panel)  # noqa: SLF001