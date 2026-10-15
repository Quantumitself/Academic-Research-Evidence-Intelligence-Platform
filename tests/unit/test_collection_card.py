"""Tests for the CollectionCard component."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QPushButton  # noqa: E402

from academic_platform.ui.components.collection_card import (  # noqa: E402
    CollectionCard,
    CollectionSummary,
)


@pytest.fixture(scope="module")
def app() -> QApplication:
    return QApplication.instance() or QApplication([])


def _summary() -> CollectionSummary:
    return CollectionSummary(
        identifier="c1",
        title="Collection A",
        description="Description.",
        item_count=5,
        preview_items=("One", "Two", "Three", "Four"),
        updated_at="2024-01-01",
    )


def test_preview_limited(app: QApplication) -> None:
    from PySide6.QtWidgets import QLabel

    card = CollectionCard(_summary())
    preview = card.findChild(QLabel, "collectionCardPreview")
    assert preview is not None
    # Three preview lines plus the "… and N more" line
    assert "One" in preview.text()
    assert "Four" not in preview.text()
    assert "more" in preview.text()


def test_open_signal(app: QApplication) -> None:
    card = CollectionCard(_summary())
    card.enable_open()
    received: list[str] = []
    card.opened.connect(received.append)
    button = card.findChild(QPushButton, "collectionCardOpen")
    assert button is not None
    button.click()
    assert received == ["c1"]


def test_actions_disabled_by_default(app: QApplication) -> None:
    card = CollectionCard(_summary())
    for name in ("collectionCardOpen", "collectionCardEdit", "collectionCardExport"):
        button = card.findChild(QPushButton, name)
        assert button is not None
        assert not button.isEnabled()