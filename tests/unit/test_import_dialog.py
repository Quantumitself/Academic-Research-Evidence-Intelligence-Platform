"""Tests for the import dialog.

The tests construct the dialog directly with a coordinator factory that
yields a coordinator bound to an in-memory database and a temporary
managed root. They do not exercise the platform file dialog.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import (  # noqa: E402
    QApplication,
    QCheckBox,
    QComboBox,
    QPushButton,
)

from academic_platform.application.library_import.coordinator import (  # noqa: E402
    ImportCoordinator,
)
from academic_platform.application.library_import.model import (  # noqa: E402
    ImportMode,
)
from academic_platform.infrastructure.database import Database  # noqa: E402
from academic_platform.infrastructure.database.base import Base  # noqa: E402
from academic_platform.infrastructure.file_storage import (  # noqa: E402
    FileStorage,
    FileStorageConfig,
)
from academic_platform.infrastructure.repositories.factory import (  # noqa: E402
    _REPOSITORY_REGISTRY,
)
from academic_platform.ui.dialogs.import_dialog import ImportDialog  # noqa: E402


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


@pytest.fixture()
def coordinator_factory(tmp_path: Path):
    database = Database.in_memory()
    Base.metadata.create_all(database.engine)
    manager = _ShimmedManager(database)
    storage = FileStorage(
        FileStorageConfig(
            managed_root=tmp_path / "library",
            max_file_size_bytes=1024 * 1024,
            chunk_size_bytes=64,
        )
    )

    def _factory() -> ImportCoordinator:
        return ImportCoordinator(manager, storage)  # type: ignore[arg-type]

    yield _factory
    manager.close_all()
    database.dispose()


def _pdf(tmp_path: Path, name: str = "paper.pdf") -> Path:
    target = tmp_path / name
    target.write_bytes(b"%PDF-1.4")
    return target


def test_dialog_renders_candidates(app: QApplication, coordinator_factory, tmp_path: Path) -> None:
    source = _pdf(tmp_path)
    dialog = ImportDialog(coordinator_factory, [source])
    checkboxes = dialog.findChildren(QCheckBox, "importRowCheckbox")
    assert len(checkboxes) == 1
    assert checkboxes[0].isChecked()
    dialog.close()


def test_dialog_summary_and_import_button(
    app: QApplication, coordinator_factory, tmp_path: Path
) -> None:
    source = _pdf(tmp_path)
    dialog = ImportDialog(coordinator_factory, [source])
    button = dialog.findChild(QPushButton, "importDialogImport")
    assert button is not None
    assert button.isEnabled()
    dialog.close()


def test_dialog_mode_switch_rebuilds_plan(
    app: QApplication, coordinator_factory, tmp_path: Path
) -> None:
    source = _pdf(tmp_path)
    dialog = ImportDialog(coordinator_factory, [source])
    combo = dialog.findChild(QComboBox, "importDialogMode")
    assert combo is not None
    combo.setCurrentIndex(1)
    # The plan is rebuilt; the candidates remain the same.
    assert dialog._plan is not None  # noqa: SLF001
    dialog.close()


def test_dialog_empty_selection_disables_import(
    app: QApplication, coordinator_factory, tmp_path: Path
) -> None:
    source = _pdf(tmp_path)
    dialog = ImportDialog(coordinator_factory, [source])
    clear_button = dialog.findChild(QPushButton, "importDialogClearSelection")
    assert clear_button is not None
    clear_button.click()
    button = dialog.findChild(QPushButton, "importDialogImport")
    assert button is not None
    assert not button.isEnabled()
    dialog.close()


def test_dialog_with_missing_file_blocks(
    app: QApplication, coordinator_factory, tmp_path: Path
) -> None:
    dialog = ImportDialog(coordinator_factory, [tmp_path / "missing.pdf"])
    button = dialog.findChild(QPushButton, "importDialogImport")
    assert button is not None
    assert not button.isEnabled()
    dialog.close()


def test_dialog_import_action(
    app: QApplication, coordinator_factory, tmp_path: Path
) -> None:
    source = _pdf(tmp_path)
    dialog = ImportDialog(coordinator_factory, [source])
    received: list = []
    dialog.imported.connect(lambda result: received.append(result))
    dialog._on_accept()  # noqa: SLF001
    assert len(received) == 1
    assert received[0].imported_count == 1
    dialog.close()