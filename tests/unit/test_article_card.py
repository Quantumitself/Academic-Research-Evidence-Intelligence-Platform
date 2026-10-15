"""Tests for the ArticleCard component."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QPushButton  # noqa: E402

from academic_platform.ui.components.article_card import (  # noqa: E402
    ArticleCard,
    PublicationSummary,
)


@pytest.fixture(scope="module")
def app() -> QApplication:
    return QApplication.instance() or QApplication([])


def _summary() -> PublicationSummary:
    return PublicationSummary(
        identifier="p1",
        title="A Study",
        authors="A. Author, B. Author",
        year="2023",
        venue="Journal of Things",
        abstract="Abstract text.",
        doi="10.1000/xyz",
        source_providers=("Crossref", "OpenAlex"),
        is_open_access=True,
        citation_count=12,
    )


def test_title_rendered(app: QApplication) -> None:
    from PySide6.QtWidgets import QLabel

    card = ArticleCard(_summary())
    title = card.findChild(QLabel, "articleCardTitle")
    assert title is not None
    assert title.text() == "A Study"


def test_authors_and_year_combined(app: QApplication) -> None:
    from PySide6.QtWidgets import QLabel

    card = ArticleCard(_summary())
    authors = card.findChild(QLabel, "articleCardAuthors")
    assert authors is not None
    assert "2023" in authors.text()
    assert "A. Author" in authors.text()


def test_actions_disabled_by_default(app: QApplication) -> None:
    card = ArticleCard(_summary())
    for name in ("articleCardOpen", "articleCardSave", "articleCardDetails"):
        button = card.findChild(QPushButton, name)
        assert button is not None
        assert not button.isEnabled()


def test_open_signal_after_enable(app: QApplication) -> None:
    card = ArticleCard(_summary())
    card.enable_open()
    received: list[str] = []
    card.open_requested.connect(received.append)
    button = card.findChild(QPushButton, "articleCardOpen")
    assert button is not None
    button.click()
    assert received == ["p1"]


def test_save_signal_after_enable(app: QApplication) -> None:
    card = ArticleCard(_summary())
    card.enable_save()
    received: list[str] = []
    card.save_requested.connect(received.append)
    button = card.findChild(QPushButton, "articleCardSave")
    assert button is not None
    button.click()
    assert received == ["p1"]


def test_missing_optional_fields(app: QApplication) -> None:
    card = ArticleCard(PublicationSummary(identifier="x", title="T"))
    assert card.identifier == "x"