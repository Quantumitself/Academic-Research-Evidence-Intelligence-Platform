"""Tests for PlaceholderPage."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from academic_platform.ui.main_window_destinations import DESTINATIONS  # noqa: E402
from academic_platform.ui.pages.placeholder_page import PlaceholderPage  # noqa: E402


@pytest.fixture(scope="module")
def app() -> QApplication:
    instance = QApplication.instance() or QApplication([])
    return instance


def test_placeholder_uses_destination_metadata(app: QApplication) -> None:
    for destination in DESTINATIONS:
        if destination.identifier == "dashboard":
            continue
        page = PlaceholderPage(destination=destination)
        assert page.title == destination.label
        assert page.subtitle == destination.purpose
        assert page.destination is destination