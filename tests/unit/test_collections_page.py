"""Tests for the collections page."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import (  # noqa: E402
    QApplication,
    QComboBox,
    QListWidget,
    QPlainTextEdit,
    QPushButton,
    QTableView,
)

from academic_platform.application.collections.model import (  # noqa: E402
    CollectionKind,
)
from academic_platform.application.collections.service import (  # noqa: E402
    CollectionService,
)
from academic_platform.infrastructure.database import Database  # noqa: E402
from academic_platform.infrastructure.database.base import Base  # noqa: E402
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


def _empty_database() -> Database:
    database = Database.in_memory()
    Base.metadata.create_all(database.engine)
    return database


def _service(database: Database) -> CollectionService:
    return CollectionService(_ShimmedManager(database))  # type: ignore[arg-type]


def test_page_empty_state(app: QApplication) -> None:
    database = _empty_database()
    page = CollectionsPage()
    page.attach_service(_service(database))
    assert page._model.rowCount() == 0  # noqa: SLF001
    database.dispose()


def test_page_lists_collections(app: QApplication) -> None:
    database = _empty_database()
    service = _service(database)
    service.create_collection(key="a", title="Alpha")
    service.create_collection(key="b", title="Beta")
    manager = _ShimmedManager(database)
    page = CollectionsPage()
    page.attach_service(CollectionService(manager))  # type: ignore[arg-type]
    assert page._model.rowCount() == 2  # noqa: SLF001
    manager.close_all()
    database.dispose()


def test_page_kind_filter(app: QApplication) -> None:
    database = _empty_database()
    service = _service(database)
    service.create_collection(key="a", title="Alpha")
    service.create_collection(
        key="b",
        title="Beta",
        kind=CollectionKind.SMART,
        filter_json='{"year_from": 2020}',
    )
    manager = _ShimmedManager(database)
    page = CollectionsPage()
    page.attach_service(CollectionService(manager))  # type: ignore[arg-type]
    combo = page.findChild(QComboBox, "collectionsKindFilter")
    assert combo is not None
    for index in range(combo.count()):
        if combo.itemData(index) == CollectionKind.SMART.value:
            combo.setCurrentIndex(index)
            break
    assert page._model.rowCount() == 1  # noqa: SLF001
    manager.close_all()
    database.dispose()


def test_page_selection_populates_detail(app: QApplication) -> None:
    database = _empty_database()
    manager = _ShimmedManager(database)
    service = CollectionService(manager)  # type: ignore[arg-type]
    service.create_collection(
        key="a", title="Alpha", description="A description"
    )
    manager.close_all()
    page = CollectionsPage()
    page.attach_service(CollectionService(manager))  # type: ignore[arg-type]
    page._select_by_key("a")  # noqa: SLF001
    assert page._current_collection_key == "a"  # noqa: SLF001
    assert "Alpha" in page._detail_title.text()  # noqa: SLF001
    assert "A description" in page._detail_description.text()  # noqa: SLF001
    manager.close_all()
    database.dispose()


def test_page_lists_items(app: QApplication) -> None:
    database = _empty_database()
    manager = _ShimmedManager(database)
    service = CollectionService(manager)  # type: ignore[arg-type]
    service.create_collection(key="a", title="Alpha")
    service.add_item(
        "a", item_type="publication", item_identifier="pub-1"
    )
    service.add_item(
        "a", item_type="document", item_identifier="doc-1"
    )
    manager.close_all()
    page = CollectionsPage()
    page.attach_service(CollectionService(manager))  # type: ignore[arg-type]
    page._select_by_key("a")  # noqa: SLF001
    listing = page.findChild(QListWidget, "collectionsItemsList")
    assert listing is not None and listing.count() == 2
    manager.close_all()
    database.dispose()


def test_page_filter_tab_enabled_for_smart(app: QApplication) -> None:
    database = _empty_database()
    manager = _ShimmedManager(database)
    service = CollectionService(manager)  # type: ignore[arg-type]
    service.create_collection(
        key="smart-1",
        kind=CollectionKind.SMART,
        filter_json='{"year_from": 2020}',
    )
    manager.close_all()
    page = CollectionsPage()
    page.attach_service(CollectionService(manager))  # type: ignore[arg-type]
    page._select_by_key("smart-1")  # noqa: SLF001
    editor = page.findChild(QPlainTextEdit, "collectionsFilterEditor")
    assert editor is not None
    assert editor.isEnabled()
    assert "year_from" in editor.toPlainText()
    manager.close_all()
    database.dispose()


def test_page_filter_tab_disabled_for_manual(app: QApplication) -> None:
    database = _empty_database()
    manager = _ShimmedManager(database)
    service = CollectionService(manager)  # type: ignore[arg-type]
    service.create_collection(key="manual-1", title="Manual")
    manager.close_all()
    page = CollectionsPage()
    page.attach_service(CollectionService(manager))  # type: ignore[arg-type]
    page._select_by_key("manual-1")  # noqa: SLF001
    editor = page.findChild(QPlainTextEdit, "collectionsFilterEditor")
    assert editor is not None
    assert not editor.isEnabled()
    manager.close_all()
    database.dispose()


def test_page_buttons_present(app: QApplication) -> None:
    page = CollectionsPage()
    for name in (
        "collectionsCreateButton",
        "collectionsEditButton",
        "collectionsRefreshButton",
        "collectionsAddItem",
        "collectionsEditItemNote",
        "collectionsMoveUp",
        "collectionsMoveDown",
        "collectionsRemoveItem",
        "collectionsSaveFilter",
    ):
        button = page.findChild(QPushButton, name)
        assert button is not None, name


def test_page_table_present(app: QApplication) -> None:
    page = CollectionsPage()
    table = page.findChild(QTableView, "collectionsTable")
    assert table is not None


def test_move_item_up_reorders(app: QApplication) -> None:
    database = _empty_database()
    manager = _ShimmedManager(database)
    service = CollectionService(manager)  # type: ignore[arg-type]
    service.create_collection(key="a", title="Alpha")
    service.add_item("a", item_type="publication", item_identifier="pub-1")
    service.add_item("a", item_type="publication", item_identifier="pub-2")
    manager.close_all()
    page = CollectionsPage()
    page.attach_service(CollectionService(manager))  # type: ignore[arg-type]
    page._select_by_key("a")  # noqa: SLF001
    listing = page.findChild(QListWidget, "collectionsItemsList")
    assert listing is not None
    listing.setCurrentRow(1)
    page._on_move_item_up()  # noqa: SLF001
    # Reload the items and verify the order.
    with database.session() as session:
        from academic_platform.infrastructure.repositories.factory import (
            _REPOSITORY_REGISTRY,
        )

        session_objects = _REPOSITORY_REGISTRY
        items_repo = session_objects["collection_item"](session)
        items = items_repo.list_for_collection(1)
        assert [i.item_identifier for i in items] == ["pub-2", "pub-1"]
    manager.close_all()
    database.dispose()