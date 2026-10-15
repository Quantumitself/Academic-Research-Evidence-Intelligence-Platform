"""Tests for the Collections page's smart-collection integration."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QListWidget, QPushButton  # noqa: E402

from academic_platform.application.collections.model import (  # noqa: E402
    CollectionKind,
)
from academic_platform.application.collections.service import (  # noqa: E402
    CollectionService,
)
from academic_platform.infrastructure.database import Database  # noqa: E402
from academic_platform.infrastructure.database.base import Base  # noqa: E402
from academic_platform.infrastructure.database.models import DocumentAsset  # noqa: E402
from academic_platform.infrastructure.repositories.factory import (  # noqa: E402
    _REPOSITORY_REGISTRY,
)
from academic_platform.ui.pages.collections import CollectionsPage  # noqa: E402


@pytest.fixture(scope="module")
def app() -> QApplication:
    return QApplication.instance() or QApplication([])


class _ShimmedManager:
    def __init__(self, database: Database) -> None:
        self._database = database
        self._sessions: list = []

    def get(self, key: str):
        session = self._database._session_factory()  # noqa: SLF001
        self._sessions.append(session)
        return _REPOSITORY_REGISTRY[key](session)

    def register_all(self, mapping) -> None:
        return None

    def close_all(self) -> None:
        for session in self._sessions:
            try:
                session.commit()
            except Exception:  # noqa: BLE001
                session.rollback()
            finally:
                session.close()
        self._sessions.clear()


def _seed(database: Database) -> None:
    with database.session() as session:
        session.add(
            DocumentAsset(
                key="a",
                display_name="Alpha",
                location="/tmp/a.pdf",
                checksum_sha256="0" * 64,
                processing_state="extracted",
            )
        )
        session.add(
            DocumentAsset(
                key="b",
                display_name="Beta",
                location="/tmp/b.epub",
                checksum_sha256="1" * 64,
                processing_state="pending",
            )
        )


def test_smart_collection_lists_evaluated_items(app: QApplication) -> None:
    database = Database.in_memory()
    Base.metadata.create_all(database.engine)
    _seed(database)
    manager = _ShimmedManager(database)
    service = CollectionService(manager)  # type: ignore[arg-type]
    service.create_collection(
        key="smart-1",
        kind=CollectionKind.SMART,
        filter_json='{"extensions": [".pdf"]}',
    )
    manager.close_all()
    page = CollectionsPage()
    page.attach_service(CollectionService(manager))  # type: ignore[arg-type]
    page._select_by_key("smart-1")  # noqa: SLF001
    listing = page.findChild(QListWidget, "collectionsItemsList")
    assert listing is not None
    assert listing.count() == 1
    manager.close_all()
    database.dispose()


def test_smart_collection_item_actions_disabled(app: QApplication) -> None:
    database = Database.in_memory()
    Base.metadata.create_all(database.engine)
    _seed(database)
    manager = _ShimmedManager(database)
    service = CollectionService(manager)  # type: ignore[arg-type]
    service.create_collection(
        key="smart-1",
        kind=CollectionKind.SMART,
        filter_json='{"extensions": [".pdf"]}',
    )
    manager.close_all()
    page = CollectionsPage()
    page.attach_service(CollectionService(manager))  # type: ignore[arg-type]
    page._select_by_key("smart-1")  # noqa: SLF001
    add_button = page.findChild(QPushButton, "collectionsAddItem")
    assert add_button is not None
    assert not add_button.isEnabled()
    manager.close_all()
    database.dispose()


def test_smart_collection_hint_visible(app: QApplication) -> None:
    database = Database.in_memory()
    Base.metadata.create_all(database.engine)
    _seed(database)
    manager = _ShimmedManager(database)
    service = CollectionService(manager)  # type: ignore[arg-type]
    service.create_collection(
        key="smart-1",
        kind=CollectionKind.SMART,
        filter_json='{"extensions": [".pdf"]}',
    )
    manager.close_all()
    page = CollectionsPage()
    page.attach_service(CollectionService(manager))  # type: ignore[arg-type]
    page._select_by_key("smart-1")  # noqa: SLF001
    page._detail_tabs.setCurrentWidget(page._items_tab)  # noqa: SLF001
    from PySide6.QtWidgets import QLabel

    hint = page.findChild(QLabel, "collectionsItemsHint")
    assert hint is not None
    assert hint.isVisibleTo(page)
    assert "smart" in hint.text().lower()
    manager.close_all()
    database.dispose()


def test_manual_collection_does_not_show_hint(app: QApplication) -> None:
    database = Database.in_memory()
    Base.metadata.create_all(database.engine)
    _seed(database)
    manager = _ShimmedManager(database)
    service = CollectionService(manager)  # type: ignore[arg-type]
    service.create_collection(key="manual-1", title="Manual")
    manager.close_all()
    page = CollectionsPage()
    page.attach_service(CollectionService(manager))  # type: ignore[arg-type]
    page._select_by_key("manual-1")  # noqa: SLF001
    from PySide6.QtWidgets import QLabel

    hint = page.findChild(QLabel, "collectionsItemsHint")
    assert hint is not None
    assert not hint.isVisibleTo(page)
    manager.close_all()
    database.dispose()