"""Tests for the MetadataGrid component."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from academic_platform.ui.components.metadata_grid import MetadataGrid  # noqa: E402


@pytest.fixture(scope="module")
def app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_add_and_value(app: QApplication) -> None:
    grid = MetadataGrid()
    grid.add_row("doi", "DOI", "10.1000/xyz")
    assert grid.value("doi") == "10.1000/xyz"


def test_set_value(app: QApplication) -> None:
    grid = MetadataGrid()
    grid.add_row("year", "Year", "2020")
    grid.set_value("year", "2021")
    assert grid.value("year") == "2021"


def test_unknown_key_raises(app: QApplication) -> None:
    grid = MetadataGrid()
    with pytest.raises(KeyError):
        grid.set_value("nope", "x")


def test_duplicate_key_raises(app: QApplication) -> None:
    grid = MetadataGrid()
    grid.add_row("year", "Year", "2020")
    with pytest.raises(KeyError):
        grid.add_row("year", "Year", "2021")


def test_empty_value_hidden(app: QApplication) -> None:
    grid = MetadataGrid()
    grid.add_row("doi", "DOI", "")
    from PySide6.QtWidgets import QLabel

    label = grid.findChild(QLabel, "metadataGridLabel")
    assert label is not None
    assert not label.isVisible()


def test_link_signal(app: QApplication) -> None:
    grid = MetadataGrid()
    grid.add_row("doi", "DOI", "10.1000/xyz", link=True)
    received: list[tuple[str, str]] = []
    grid.link_activated.connect(lambda k, v: received.append((k, v)))
    from PySide6.QtWidgets import QPushButton

    button = grid.findChild(QPushButton, "metadataGridLink")
    assert button is not None
    button.click()
    assert received == [("doi", "10.1000/xyz")]


def test_remove_row(app: QApplication) -> None:
    grid = MetadataGrid()
    grid.add_row("year", "Year", "2020")
    grid.remove_row("year")
    assert grid.value("year") == ""


def test_clear(app: QApplication) -> None:
    grid = MetadataGrid()
    grid.add_row("a", "A", "1")
    grid.add_row("b", "B", "2")
    grid.clear()
    assert grid.value("a") == ""
    assert grid.value("b") == ""